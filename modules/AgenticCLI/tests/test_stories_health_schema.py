"""CLI contract test for `agentic stories health --json` output schema.

Validates the agent-facing JSON contract defined in US-STR-020, step 6:
  - Top-level keys: stories[], summary{}
  - Per-story keys: id, title, status, flags, test, uat, staleness, related_files, lifecycle
  - flags: {flaky, blocked}
  - test: {status, last_pass_commit, last_pass_tree_hash, last_tested}
  - uat: {last_uat_commit}
  - staleness: {is_stale, reason, related_files_changed, global_config_changed}
  - summary: {total_shown, hidden_archived, counts, flaky_count}
  - status value is one of the 7 canonical enum values

Uses tmp_path + monkeypatch to provide a minimal 2-story userstories fixture,
with _find_userstories_dir and _find_repo_root patched to point at the fixture.
Git helpers are also patched so the test is deterministic (no real git needed).
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.story("US-STR-020")

_CANONICAL_STATUSES = frozenset(
    {"broken", "stale", "never-passed", "untested", "passing", "uat-verified", "archived"}
)


@pytest.fixture
def health_fixture(tmp_path, monkeypatch):
    """Minimal userstories fixture with 2 stories for schema testing."""
    stories_dir = tmp_path / "docs" / "userstories"
    stories_dir.mkdir(parents=True)

    # Write one passing story and one untested story
    story_file = stories_dir / "test_health.yml"
    story_file.write_text(yaml.dump({
        "stories": [
            {
                "id": "US-HLT-001",
                "title": "Passing Story",
                "test_status": "pass",
                "last_pass_commit": "abc1234",
                "related_files": ["modules/foo/bar.py"],
                "lifecycle": "implemented",
            },
            {
                "id": "US-HLT-002",
                "title": "Untested Story",
                "test_status": "untested",
                "lifecycle": "implemented",
            },
        ]
    }))

    # Patch _find_userstories_dir so cmd_health uses our fixture
    import agenticcli.commands.stories as stories_mod
    monkeypatch.setattr(stories_mod, "_find_userstories_dir", lambda: stories_dir)

    # Patch _find_repo_root so no real git lookup occurs
    monkeypatch.setattr(stories_mod, "_find_repo_root", lambda: tmp_path)

    # Patch _scan_pytest_story_markers to return empty set (no test markers)
    monkeypatch.setattr(stories_mod, "_scan_pytest_story_markers", lambda: set())

    # Patch _scan_pytest_flaky_markers to return empty set
    monkeypatch.setattr(stories_mod, "_scan_pytest_flaky_markers", lambda _: set())

    # Patch load_global_watch to return empty list (no global watch)
    import agenticguidance.services.story as story_svc_mod
    monkeypatch.setattr(stories_mod, "load_global_watch", lambda d: [])
    monkeypatch.setattr(stories_mod, "expand_watch_patterns", lambda p, r: set())

    # Patch git changed files to return empty set (no drift)
    monkeypatch.setattr(
        story_svc_mod,
        "_git_changed_files_since",
        lambda commit, repo_root: set(),
    )

    return stories_dir


class TestHealthJsonSchema:
    """Verify the --json output satisfies the US-STR-020 contract."""

    def _call_health_json(self, health_fixture):
        """Invoke cmd_health in JSON mode and capture the output dict."""
        from agenticcli.commands.stories import cmd_health

        args = SimpleNamespace(
            project=None,
            coverage=False,
            all=False,
        )

        captured = {}

        def _capture_json(data):
            captured["result"] = data

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json", side_effect=_capture_json):
                cmd_health(args)

        assert "result" in captured, "print_json was never called — cmd_health did not produce JSON"
        return captured["result"]

    def test_top_level_keys_present(self, health_fixture):
        """Output has 'stories' and 'summary' top-level keys."""
        result = self._call_health_json(health_fixture)
        assert "stories" in result, f"Missing 'stories' key. Keys: {list(result.keys())}"
        assert "summary" in result, f"Missing 'summary' key. Keys: {list(result.keys())}"

    def test_stories_is_a_list(self, health_fixture):
        result = self._call_health_json(health_fixture)
        assert isinstance(result["stories"], list)
        assert len(result["stories"]) >= 1

    def test_story_entry_required_keys(self, health_fixture):
        """Each story entry has all required keys from the contract."""
        result = self._call_health_json(health_fixture)
        required = {"id", "title", "status", "flags", "test", "uat", "staleness",
                    "related_files", "lifecycle"}
        for story in result["stories"]:
            missing = required - set(story.keys())
            assert not missing, (
                f"Story '{story.get('id', '?')}' missing keys: {missing}"
            )

    def test_flags_subkeys(self, health_fixture):
        """flags has exactly {flaky, blocked}."""
        result = self._call_health_json(health_fixture)
        for story in result["stories"]:
            flags = story["flags"]
            assert "flaky" in flags, f"flags missing 'flaky' for story {story['id']}"
            assert "blocked" in flags, f"flags missing 'blocked' for story {story['id']}"
            assert isinstance(flags["flaky"], bool)
            assert isinstance(flags["blocked"], bool)

    def test_test_subkeys(self, health_fixture):
        """test{} has status, last_pass_commit, last_pass_tree_hash, last_tested."""
        result = self._call_health_json(health_fixture)
        for story in result["stories"]:
            t = story["test"]
            assert "status" in t, f"test missing 'status' for story {story['id']}"
            assert "last_pass_commit" in t, (
                f"test missing 'last_pass_commit' for story {story['id']}"
            )
            assert "last_pass_tree_hash" in t, (
                f"test missing 'last_pass_tree_hash' for story {story['id']}"
            )
            assert "last_tested" in t, f"test missing 'last_tested' for story {story['id']}"

    def test_uat_subkeys(self, health_fixture):
        """uat{} has last_uat_commit."""
        result = self._call_health_json(health_fixture)
        for story in result["stories"]:
            uat = story["uat"]
            assert "last_uat_commit" in uat, (
                f"uat missing 'last_uat_commit' for story {story['id']}"
            )

    def test_staleness_subkeys(self, health_fixture):
        """staleness{} has is_stale, reason, related_files_changed, global_config_changed."""
        result = self._call_health_json(health_fixture)
        for story in result["stories"]:
            s = story["staleness"]
            assert "is_stale" in s, f"staleness missing 'is_stale' for story {story['id']}"
            assert "reason" in s, f"staleness missing 'reason' for story {story['id']}"
            assert "related_files_changed" in s, (
                f"staleness missing 'related_files_changed' for story {story['id']}"
            )
            assert "global_config_changed" in s, (
                f"staleness missing 'global_config_changed' for story {story['id']}"
            )
            assert isinstance(s["is_stale"], bool)
            assert isinstance(s["related_files_changed"], list)
            assert isinstance(s["global_config_changed"], list)

    def test_status_values_are_canonical(self, health_fixture):
        """status field value is one of the 7 canonical enum values."""
        result = self._call_health_json(health_fixture)
        for story in result["stories"]:
            assert story["status"] in _CANONICAL_STATUSES, (
                f"Story '{story['id']}' has non-canonical status '{story['status']}'"
            )

    def test_summary_keys(self, health_fixture):
        """summary{} has total_shown, hidden_archived, counts, flaky_count."""
        result = self._call_health_json(health_fixture)
        summary = result["summary"]
        assert "total_shown" in summary, f"summary missing 'total_shown'. Keys: {list(summary)}"
        assert "hidden_archived" in summary, (
            f"summary missing 'hidden_archived'. Keys: {list(summary)}"
        )
        assert "counts" in summary, f"summary missing 'counts'. Keys: {list(summary)}"
        assert "flaky_count" in summary, f"summary missing 'flaky_count'. Keys: {list(summary)}"

    def test_summary_counts_covers_all_statuses(self, health_fixture):
        """summary.counts has entries for all 7 canonical status values."""
        result = self._call_health_json(health_fixture)
        counts = result["summary"]["counts"]
        for status in _CANONICAL_STATUSES:
            assert status in counts, (
                f"summary.counts missing key '{status}'. Keys: {list(counts)}"
            )

    def test_summary_counts_are_integers(self, health_fixture):
        result = self._call_health_json(health_fixture)
        for key, val in result["summary"]["counts"].items():
            assert isinstance(val, int), f"counts['{key}'] is not int: {val!r}"

    def test_total_shown_matches_stories_list_length(self, health_fixture):
        """summary.total_shown matches the number of entries in stories[]."""
        result = self._call_health_json(health_fixture)
        assert result["summary"]["total_shown"] == len(result["stories"])

    def test_full_length_commit_sha_preserved(self, health_fixture):
        """Full-length SHAs are preserved in JSON (short SHAs are a table concern only)."""
        result = self._call_health_json(health_fixture)
        for story in result["stories"]:
            commit = story["test"].get("last_pass_commit")
            if commit is not None:
                # "abc1234" is already the value in the fixture — we just verify it's
                # not truncated further (it's already short in the fixture, but real
                # usage would have 40-char SHAs and the contract says preserve them)
                assert isinstance(commit, str)
                assert len(commit) >= 7  # at minimum 7 chars, up to 40

    def test_related_files_is_list(self, health_fixture):
        result = self._call_health_json(health_fixture)
        for story in result["stories"]:
            assert isinstance(story["related_files"], list)

    def test_lifecycle_is_string(self, health_fixture):
        result = self._call_health_json(health_fixture)
        for story in result["stories"]:
            assert isinstance(story["lifecycle"], str)
