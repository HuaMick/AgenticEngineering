"""Tests for story traceability enforcement features.

Validates:
- Story dataclass new fields (related_files, last_pass_commit, last_uat_commit)
- StoryService.update_commit_status()
- StoryService.get_stale_stories() with mock git
- StoryService.compute_story_status()
- cmd_audit --check-files and --check-tickets
- cmd_affected --commit
- Enhanced health dashboard output
- pytest --check-story-coverage option
"""

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

pytestmark = pytest.mark.story("US-STR-001")


@pytest.fixture(autouse=True)
def _reset_json_mode():
    """Ensure JSON mode is reset after each test."""
    yield
    from agenticcli.console import set_json_mode
    set_json_mode(False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def story_dir(tmp_path):
    """Create a userstories directory with test stories."""
    us_dir = tmp_path / "docs" / "userstories" / "Test"
    us_dir.mkdir(parents=True)
    story_file = us_dir / "01_test.yml"
    story_file.write_text(yaml.dump({
        "area": "test",
        "stories": [
            {
                "id": "US-TST-001",
                "title": "Test Story One",
                "test_status": "pass",
                "related_files": ["modules/A/src/a/foo.py", "modules/A/src/a/bar.py"],
                "last_pass_commit": "abc1234",
                "last_uat_commit": "def5678",
            },
            {
                "id": "US-TST-002",
                "title": "Test Story Two",
                "test_status": "untested",
                "related_files": ["modules/A/src/a/baz.py"],
            },
            {
                "id": "US-TST-003",
                "title": "Test Story Three",
                "test_status": "pass",
                "related_files": ["modules/A/src/a/qux.py"],
                "last_pass_commit": "111aaaa",
            },
        ],
    }, sort_keys=False))
    return tmp_path / "docs" / "userstories"


# ---------------------------------------------------------------------------
# Story dataclass tests
# ---------------------------------------------------------------------------


class TestStoryDataclass:
    """Test new fields on Story dataclass."""

    def test_related_files_default_empty(self):
        from agenticguidance.services.story import Story
        s = Story(id="US-TEST-001", title="Test")
        assert s.related_files == []

    def test_related_files_populated(self):
        from agenticguidance.services.story import Story
        s = Story(id="US-TEST-001", title="Test", related_files=["a.py", "b.py"])
        assert s.related_files == ["a.py", "b.py"]

    def test_last_pass_commit_default_empty(self):
        from agenticguidance.services.story import Story
        s = Story(id="US-TEST-001", title="Test")
        assert s.last_pass_commit == ""

    def test_last_uat_commit_default_empty(self):
        from agenticguidance.services.story import Story
        s = Story(id="US-TEST-001", title="Test")
        assert s.last_uat_commit == ""

    def test_commit_fields_populated(self):
        from agenticguidance.services.story import Story
        s = Story(id="US-TEST-001", title="Test",
                  last_pass_commit="abc123", last_uat_commit="def456")
        assert s.last_pass_commit == "abc123"
        assert s.last_uat_commit == "def456"


# ---------------------------------------------------------------------------
# StoryService parsing tests
# ---------------------------------------------------------------------------


class TestStoryServiceParsing:
    """Test that _parse_file reads new fields from YAML."""

    def test_parse_related_files(self, story_dir):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        stories = svc.load_all()
        s1 = next(s for s in stories if s.id == "US-TST-001")
        assert s1.related_files == ["modules/A/src/a/foo.py", "modules/A/src/a/bar.py"]

    def test_parse_commit_hashes(self, story_dir):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        stories = svc.load_all()
        s1 = next(s for s in stories if s.id == "US-TST-001")
        assert s1.last_pass_commit == "abc1234"
        assert s1.last_uat_commit == "def5678"

    def test_parse_missing_commit_defaults_empty(self, story_dir):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        stories = svc.load_all()
        s2 = next(s for s in stories if s.id == "US-TST-002")
        assert s2.last_pass_commit == ""
        assert s2.last_uat_commit == ""


# ---------------------------------------------------------------------------
# update_commit_status tests
# ---------------------------------------------------------------------------


class TestUpdateCommitStatus:
    """Test StoryService.update_commit_status()."""

    def test_update_test_commit(self, story_dir):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        result = svc.update_commit_status("US-TST-002", "new_hash", commit_type="test")
        assert result is True
        # Reload and verify
        svc2 = StoryService(story_dir)
        s = svc2.get_by_id("US-TST-002")
        assert s.last_pass_commit == "new_hash"

    def test_update_uat_commit(self, story_dir):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        result = svc.update_commit_status("US-TST-001", "uat_hash", commit_type="uat")
        assert result is True
        svc2 = StoryService(story_dir)
        s = svc2.get_by_id("US-TST-001")
        assert s.last_uat_commit == "uat_hash"

    def test_update_nonexistent_story_returns_false(self, story_dir):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        result = svc.update_commit_status("US-FAKE-999", "hash", commit_type="test")
        assert result is False


# ---------------------------------------------------------------------------
# Atomic write path: update_test_status + commit hash
# ---------------------------------------------------------------------------


class TestUpdateTestStatusAtomicCommit:
    """Regression coverage for the two-write-path gap.

    Prior to the fix, ``update_test_status`` and ``update_commit_status``
    were separate writes. Every CLI entry point called only the former,
    so stories could be recorded as ``pass`` with no commit hash. These
    tests pin the contract that a passing write atomically records the
    commit in the same YAML update.
    """

    def test_pass_with_commit_writes_last_pass_commit(self, story_dir):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        ok = svc.update_test_status(
            "US-TST-002", "pass",
            tested_by="uat-run", last_tested="2026-04-11T00:00:00Z",
            commit="abcdef1234567890",
        )
        assert ok is True
        svc2 = StoryService(story_dir)
        s = svc2.get_by_id("US-TST-002")
        assert s.test_status == "pass"
        assert s.last_pass_commit == "abcdef1234567890"
        # UAT field untouched when kind defaults to test
        assert s.last_uat_commit == ""

    def test_pass_with_commit_kind_uat_writes_last_uat_commit(self, story_dir):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        ok = svc.update_test_status(
            "US-TST-002", "pass",
            commit="uatcommit99", commit_kind="uat",
        )
        assert ok is True
        svc2 = StoryService(story_dir)
        s = svc2.get_by_id("US-TST-002")
        assert s.test_status == "pass"
        assert s.last_uat_commit == "uatcommit99"
        # Test-pass field is NOT written when kind=uat
        assert s.last_pass_commit == ""

    def test_fail_with_commit_does_not_write_commit(self, story_dir):
        """A failing status must not stamp a commit as 'passing at HEAD'."""
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        ok = svc.update_test_status(
            "US-TST-002", "fail",
            commit="shouldnotwrite",
        )
        assert ok is True
        svc2 = StoryService(story_dir)
        s = svc2.get_by_id("US-TST-002")
        assert s.test_status == "fail"
        assert s.last_pass_commit == ""

    def test_pass_without_commit_still_updates_status(self, story_dir):
        """Back-compat: calls that pass no commit still work (no hash written)."""
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        ok = svc.update_test_status("US-TST-002", "pass")
        assert ok is True
        svc2 = StoryService(story_dir)
        s = svc2.get_by_id("US-TST-002")
        assert s.test_status == "pass"
        assert s.last_pass_commit == ""

    def test_record_story_pass_helper_writes_commit(self, story_dir, monkeypatch):
        """record_story_pass is the shared write path for CLI + framework hooks.

        Framework hooks (executor pass-hash, UatRunner) and cmd_update must
        all flow through this helper so the write path stays single-source.
        """
        from agenticcli.commands import stories as stories_mod

        monkeypatch.setattr(stories_mod, "_find_userstories_dir", lambda: story_dir)

        class _FakeResult:
            returncode = 0
            stdout = "cafebabe1111222\n"

        monkeypatch.setattr("subprocess.run", lambda *a, **k: _FakeResult())

        result = stories_mod.record_story_pass(
            ["US-TST-002"],
            commit_kind="test",
            tested_by="executor:fake:Build",
        )
        assert result["updated"] == ["US-TST-002"]
        assert result["commit"] == "cafebabe1111222"

        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        s = svc.get_by_id("US-TST-002")
        assert s.test_status == "pass"
        assert s.last_pass_commit == "cafebabe1111222"
        assert s.tested_by_plan == "executor:fake:Build"

    def test_record_story_pass_helper_uat_kind(self, story_dir, monkeypatch):
        """commit_kind='uat' writes last_uat_commit, not last_pass_commit."""
        from agenticcli.commands import stories as stories_mod

        monkeypatch.setattr(stories_mod, "_find_userstories_dir", lambda: story_dir)

        result = stories_mod.record_story_pass(
            ["US-TST-002"],
            commit="uat9999",
            commit_kind="uat",
        )
        assert result["updated"] == ["US-TST-002"]

        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        s = svc.get_by_id("US-TST-002")
        assert s.last_uat_commit == "uat9999"

    def test_record_story_pass_helper_missing_story(self, story_dir, monkeypatch):
        """Unknown story IDs are reported in the 'missing' list, not raised."""
        from agenticcli.commands import stories as stories_mod

        monkeypatch.setattr(stories_mod, "_find_userstories_dir", lambda: story_dir)

        result = stories_mod.record_story_pass(
            ["US-DOES-NOT-EXIST"], commit="x", commit_kind="test",
        )
        assert result["updated"] == []
        assert "US-DOES-NOT-EXIST" in result["missing"]

    def test_cmd_update_captures_head_commit(self, story_dir, monkeypatch, capsys):
        """cmd_update must capture git HEAD and pass it to update_test_status."""
        from agenticcli.commands import stories as stories_mod

        monkeypatch.setattr(stories_mod, "_find_userstories_dir", lambda: story_dir)

        class _FakeResult:
            returncode = 0
            stdout = "deadbeef1234567890\n"

        def _fake_run(*args, **kwargs):
            return _FakeResult()

        monkeypatch.setattr("subprocess.run", _fake_run)

        args = SimpleNamespace(
            id="US-TST-002", status="pass", notes="uat pass",
            plan="260410AG_example", commit=None, kind="test",
        )
        stories_mod.cmd_update(args)

        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)
        s = svc.get_by_id("US-TST-002")
        assert s.test_status == "pass"
        assert s.last_pass_commit == "deadbeef1234567890"
        assert s.tested_by_plan == "260410AG_example"


# ---------------------------------------------------------------------------
# get_stale_stories tests
# ---------------------------------------------------------------------------


class TestGetStaleStories:
    """Test StoryService.get_stale_stories() with mocked git."""

    def test_stale_when_files_changed(self, story_dir, tmp_path):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)

        # Mock git to say foo.py changed
        with patch("agenticguidance.services.story._git_changed_files_since") as mock_git:
            mock_git.return_value = {"modules/A/src/a/foo.py", "other.py"}
            stale = svc.get_stale_stories(repo_root=tmp_path)

        # US-TST-001 has last_pass_commit and foo.py in related_files
        assert len(stale) == 1
        assert stale[0].id == "US-TST-001"

    def test_not_stale_when_no_overlap(self, story_dir, tmp_path):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)

        with patch("agenticguidance.services.story._git_changed_files_since") as mock_git:
            mock_git.return_value = {"other.py", "unrelated.py"}
            stale = svc.get_stale_stories(repo_root=tmp_path)

        assert len(stale) == 0

    def test_no_commit_means_not_stale(self, story_dir, tmp_path):
        from agenticguidance.services.story import StoryService
        svc = StoryService(story_dir)

        # US-TST-002 has no last_pass_commit — should not be stale
        with patch("agenticguidance.services.story._git_changed_files_since") as mock_git:
            mock_git.return_value = {"modules/A/src/a/baz.py"}
            stale = svc.get_stale_stories(repo_root=tmp_path)

        # Only US-TST-001 has a commit to be stale against, but its files didn't change
        stale_ids = {s.id for s in stale}
        assert "US-TST-002" not in stale_ids


# ---------------------------------------------------------------------------
# compute_story_status tests
# ---------------------------------------------------------------------------


class TestComputeStoryStatus:
    """Test StoryService.compute_story_status()."""

    def test_broken_on_fail(self, story_dir):
        from agenticguidance.services.story import Story, StoryService
        svc = StoryService(story_dir)
        s = Story(id="X", title="X", test_status="fail")
        assert svc.compute_story_status(s) == "broken"

    def test_broken_on_regression(self, story_dir):
        from agenticguidance.services.story import Story, StoryService
        svc = StoryService(story_dir)
        s = Story(id="X", title="X", test_status="regression")
        assert svc.compute_story_status(s) == "broken"

    def test_untested_on_empty(self, story_dir):
        from agenticguidance.services.story import Story, StoryService
        svc = StoryService(story_dir)
        s = Story(id="X", title="X", test_status="")
        assert svc.compute_story_status(s) == "untested"

    def test_passing_when_no_related_files(self, story_dir):
        from agenticguidance.services.story import Story, StoryService
        svc = StoryService(story_dir)
        s = Story(id="X", title="X", test_status="pass", related_files=[], last_pass_commit="abc")
        assert svc.compute_story_status(s) == "passing"

    def test_stale_when_files_changed(self, story_dir, tmp_path):
        from agenticguidance.services.story import Story, StoryService
        svc = StoryService(story_dir)
        s = Story(id="X", title="X", test_status="pass",
                  related_files=["a.py"], last_pass_commit="abc")
        with patch("agenticguidance.services.story._git_changed_files_since") as mock_git:
            mock_git.return_value = {"a.py"}
            result = svc.compute_story_status(s, repo_root=tmp_path)
        assert result == "stale"


# ---------------------------------------------------------------------------
# cmd_health enhanced output tests
# ---------------------------------------------------------------------------


class TestCmdHealth:
    """Test the two-axis health dashboard JSON schema (US-STR-020)."""

    def test_health_json_has_new_schema(self, story_dir, monkeypatch, capsys):
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_userstories_dir",
            lambda: story_dir,
        )
        monkeypatch.setattr(
            "agenticguidance.services.story._find_repo_root",
            lambda: None,
        )
        from agenticcli.console import set_json_mode
        set_json_mode(True)

        from agenticcli.commands.stories import cmd_health
        args = SimpleNamespace(project=None, coverage=False, json=True, debug=False, all=False)
        cmd_health(args)
        out = capsys.readouterr().out
        data = json.loads(out)

        # Top-level shape
        assert "stories" in data
        assert "summary" in data
        assert data["summary"]["total_shown"] == 3

        # Story-level shape
        s1 = next(s for s in data["stories"] if s["id"] == "US-TST-001")
        assert s1["test"]["last_pass_commit"] == "abc1234"
        assert s1["uat"]["last_uat_commit"] == "def5678"
        assert s1["status"] in {
            "broken", "stale", "never-passed", "untested",
            "passing", "uat-verified", "archived",
        }
        assert "flaky" in s1["flags"]
        assert "is_stale" in s1["staleness"]
        assert "related_files" in s1

    def test_health_json_summary_counts(self, story_dir, monkeypatch, capsys):
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_userstories_dir",
            lambda: story_dir,
        )
        monkeypatch.setattr(
            "agenticguidance.services.story._find_repo_root",
            lambda: None,
        )
        from agenticcli.console import set_json_mode
        set_json_mode(True)

        from agenticcli.commands.stories import cmd_health
        args = SimpleNamespace(project=None, coverage=False, json=True, debug=False, all=False)
        cmd_health(args)
        out = capsys.readouterr().out
        data = json.loads(out)

        counts = data["summary"]["counts"]
        # All 7 status keys present in the counts dict
        for key in ("broken", "stale", "never-passed", "untested",
                    "passing", "uat-verified", "archived"):
            assert key in counts
        assert "flaky_count" in data["summary"]
        assert "hidden_archived" in data["summary"]


# ---------------------------------------------------------------------------
# cmd_affected --commit tests
# ---------------------------------------------------------------------------


class TestCmdAffectedByCommit:
    """Test commit-based story impact detection."""

    def test_affected_by_commit_json(self, story_dir, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_userstories_dir",
            lambda: story_dir,
        )
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_repo_root",
            lambda: tmp_path,
        )
        from agenticcli.console import set_json_mode
        set_json_mode(True)

        # Create source file with story header
        src_dir = tmp_path / "modules" / "A" / "src" / "a"
        src_dir.mkdir(parents=True)
        (src_dir / "foo.py").write_text("# story: US-TST-001\n")

        # Mock git diff to return foo.py
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "modules/A/src/a/foo.py\n"

        with patch("agenticcli.commands.stories.subprocess.run", return_value=mock_result):
            from agenticcli.commands.stories import cmd_affected
            args = SimpleNamespace(
                commit="abc123", changes=None, plan=None,
                json=True, debug=False,
            )
            cmd_affected(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["commit"] == "abc123"
        assert data["count"] >= 1
        affected_ids = {s["id"] for s in data["affected_stories"]}
        assert "US-TST-001" in affected_ids

    def test_affected_by_commit_no_changes(self, story_dir, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_userstories_dir",
            lambda: story_dir,
        )
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_repo_root",
            lambda: tmp_path,
        )
        from agenticcli.console import set_json_mode
        set_json_mode(True)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("agenticcli.commands.stories.subprocess.run", return_value=mock_result):
            from agenticcli.commands.stories import cmd_affected
            args = SimpleNamespace(
                commit="abc123", changes=None, plan=None,
                json=True, debug=False,
            )
            cmd_affected(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["count"] == 0


# ---------------------------------------------------------------------------
# cmd_audit --check-files tests
# ---------------------------------------------------------------------------


class TestCmdAuditCheckFiles:
    """Test YAML↔header bidirectional consistency check."""

    def test_consistent_files(self, story_dir, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_userstories_dir",
            lambda: story_dir,
        )
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_repo_root",
            lambda: tmp_path,
        )
        from agenticcli.console import set_json_mode
        set_json_mode(True)

        # Create matching source files with correct headers
        for f, ids in [
            ("modules/A/src/a/foo.py", "US-TST-001"),
            ("modules/A/src/a/bar.py", "US-TST-001"),
            ("modules/A/src/a/baz.py", "US-TST-002"),
            ("modules/A/src/a/qux.py", "US-TST-003"),
        ]:
            p = tmp_path / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# story: {ids}\n")

        from agenticcli.commands.stories import cmd_audit
        args = SimpleNamespace(
            check_files=True, check_tickets=False, strict=False, epic=None,
            json=True, debug=False,
        )
        cmd_audit(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["consistent"] is True
        assert data["mismatch_count"] == 0

    def test_mismatch_detected(self, story_dir, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_userstories_dir",
            lambda: story_dir,
        )
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_repo_root",
            lambda: tmp_path,
        )
        from agenticcli.console import set_json_mode
        set_json_mode(True)

        # Create files with WRONG headers
        for f in ["modules/A/src/a/foo.py", "modules/A/src/a/bar.py",
                   "modules/A/src/a/baz.py", "modules/A/src/a/qux.py"]:
            p = tmp_path / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# no story header\n")

        from agenticcli.commands.stories import cmd_audit
        args = SimpleNamespace(
            check_files=True, check_tickets=False, strict=False, epic=None,
            json=True, debug=False,
        )
        cmd_audit(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["consistent"] is False
        assert data["mismatch_count"] > 0

    def test_strict_mode_exits_nonzero(self, story_dir, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_userstories_dir",
            lambda: story_dir,
        )
        monkeypatch.setattr(
            "agenticcli.commands.stories._find_repo_root",
            lambda: tmp_path,
        )
        from agenticcli.console import set_json_mode
        set_json_mode(True)

        # Create files without headers → mismatches
        for f in ["modules/A/src/a/foo.py", "modules/A/src/a/bar.py",
                   "modules/A/src/a/baz.py", "modules/A/src/a/qux.py"]:
            p = tmp_path / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("")

        from agenticcli.commands.stories import cmd_audit
        args = SimpleNamespace(
            check_files=True, check_tickets=False, strict=True, epic=None,
            json=True, debug=False,
        )
        with pytest.raises(SystemExit) as exc:
            cmd_audit(args)
        assert exc.value.code == 1


# ---------------------------------------------------------------------------
# cmd_audit --check-tickets tests
# ---------------------------------------------------------------------------


class TestCmdAuditCheckTickets:
    """Test ticket traceability check across live epics."""

    def test_all_tickets_linked(self, tmp_path, _isolate_tinydb, monkeypatch, capsys):
        from agenticcli.console import set_json_mode
        set_json_mode(True)
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository()
        epic_folder = tmp_path / "docs" / "epics" / "live" / "260101AB_test"
        epic_folder.mkdir(parents=True)
        repo.create_epic({
            "epic_folder_name": "260101AB_test",
            "epic_folder": str(epic_folder),
            "name": "test_epic",
            "status": "active",
        })
        repo.add_phase("260101AB_test", {"name": "P1", "status": "planning"})
        repo.add_ticket("260101AB_test", "P1", {
            "id": "T1", "name": "Task one", "status": "pending",
            "story_ids": ["US-TST-001"],
        })
        repo.close()

        from agenticcli.commands.stories import cmd_audit
        args = SimpleNamespace(
            check_files=False, check_tickets=True, strict=False, epic=None,
            json=True, debug=False,
        )
        cmd_audit(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["all_linked"] is True

    def test_unlinked_tickets_found(self, tmp_path, _isolate_tinydb, monkeypatch, capsys):
        from agenticcli.console import set_json_mode
        set_json_mode(True)
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository()
        epic_folder = tmp_path / "docs" / "epics" / "live" / "260101AB_test"
        epic_folder.mkdir(parents=True)
        repo.create_epic({
            "epic_folder_name": "260101AB_test",
            "epic_folder": str(epic_folder),
            "name": "test_epic",
            "status": "active",
        })
        repo.add_phase("260101AB_test", {"name": "P1", "status": "planning"})
        repo.add_ticket("260101AB_test", "P1", {
            "id": "T1", "name": "Task one", "status": "pending",
        })  # no story_ids
        repo.close()

        from agenticcli.commands.stories import cmd_audit
        args = SimpleNamespace(
            check_files=False, check_tickets=True, strict=False, epic=None,
            json=True, debug=False,
        )
        cmd_audit(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["all_linked"] is False
        assert data["unlinked_count"] >= 1


# ---------------------------------------------------------------------------
# _git_changed_files_since tests
# ---------------------------------------------------------------------------


class TestGitChangedFilesSince:
    """Test the git diff helper function."""

    def test_returns_set_on_success(self, tmp_path):
        from agenticguidance.services.story import _git_changed_files_since
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "a.py\nb.py\n"

        with patch("agenticguidance.services.story.subprocess.run", return_value=mock_result):
            result = _git_changed_files_since("abc123", tmp_path)

        assert result == {"a.py", "b.py"}

    def test_returns_none_on_error(self, tmp_path):
        from agenticguidance.services.story import _git_changed_files_since
        mock_result = MagicMock()
        mock_result.returncode = 128  # git error

        with patch("agenticguidance.services.story.subprocess.run", return_value=mock_result):
            result = _git_changed_files_since("badcommit", tmp_path)

        assert result is None
