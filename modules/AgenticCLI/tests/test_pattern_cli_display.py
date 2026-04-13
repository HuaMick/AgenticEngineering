"""Tests for CLI display of pattern watch_files and pattern_watch stale_reason.

Validates:
- cmd_pattern_cat shows watch_files in rich and JSON modes (P2_010)
- cmd_pattern_claimants shows inherited watch_files per claimant (P2_010)
- stories health reports pattern_watch stale_reason correctly (P2_010)

Epic: 260411AG_pattern_claimant_watch_files_fold_global_watch.
"""

import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.story("US-260411AG-001")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_pattern_yaml(path: Path, patterns: list[dict]) -> Path:
    """Write a patterns YAML file."""
    path.write_text(yaml.dump({"patterns": patterns}, sort_keys=False))
    return path


def _write_story_yaml(path: Path, stories: list[dict]) -> Path:
    """Write a stories YAML file."""
    path.write_text(yaml.dump({"stories": stories}, sort_keys=False))
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_fixture(tmp_path, monkeypatch):
    """Set up userstories with patterns and stories for CLI command testing."""
    stories_dir = tmp_path / "docs" / "userstories"

    # Create pattern directory with watch_files
    patterns_dir = stories_dir / "Patterns" / "cli"
    patterns_dir.mkdir(parents=True)
    _write_pattern_yaml(patterns_dir / "01_patterns.yml", [
        {
            "id": "PAT-CLI-001",
            "title": "JSON Output",
            "description": "Commands support --json for machine-readable output.",
            "tags": ["cli", "json"],
            "applicable_categories": ["US-SET"],
            "parameters": {
                "command": {"description": "CLI command", "required": True},
            },
            "verification": {
                "behavioral": {
                    "steps": [
                        {"step": 1, "action": "Run command", "expect": "JSON output"},
                    ]
                }
            },
            "watch_files": [
                "modules/AgenticCLI/src/agenticcli/commands/*.py",
            ],
        },
        {
            "id": "PAT-CLI-002",
            "title": "No Watch Files Pattern",
            "description": "Pattern without watch_files.",
            "tags": ["cli"],
        },
    ])

    # Create CLI command files matching the watch_files glob
    cli_commands = tmp_path / "modules" / "AgenticCLI" / "src" / "agenticcli" / "commands"
    cli_commands.mkdir(parents=True)
    (cli_commands / "stories.py").write_text("# stories command")
    (cli_commands / "epic.py").write_text("# epic command")

    # Create a story that inherits the pattern
    story_category = stories_dir / "Testing"
    story_category.mkdir(parents=True)
    _write_story_yaml(story_category / "01_stories.yml", [
        {
            "id": "US-TEST-001",
            "title": "Test Story With Pattern",
            "lifecycle": "implemented",
            "test_status": "pass",
            "last_pass_commit": "abc1234def",
            "related_files": ["modules/foo/bar.py"],
            "inherits_patterns": [
                {"id": "PAT-CLI-001", "bind": {"command": "agentic stories health"}},
            ],
        },
        {
            "id": "US-TEST-002",
            "title": "Test Story No Pattern",
            "lifecycle": "implemented",
            "test_status": "pass",
            "last_pass_commit": "abc1234def",
            "related_files": [],
        },
    ])

    # Patch module-level lookups
    import agenticcli.commands.stories as stories_mod
    import agenticguidance.services.story as story_svc_mod
    monkeypatch.setattr(stories_mod, "_find_userstories_dir", lambda: stories_dir)
    monkeypatch.setattr(stories_mod, "_find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(stories_mod, "_scan_pytest_story_markers", lambda: set())
    monkeypatch.setattr(stories_mod, "_scan_pytest_flaky_markers", lambda _: set())

    return {
        "stories_dir": stories_dir,
        "repo_root": tmp_path,
    }


def _capture_json_call(func, args):
    """Call a CLI function in JSON mode and capture the print_json output."""
    captured = {}

    def _capture(data):
        captured["result"] = data

    with patch("agenticcli.console.is_json_output", return_value=True):
        with patch("agenticcli.console.print_json", side_effect=_capture):
            func(args)

    assert "result" in captured, f"print_json was never called by {func.__name__}"
    return captured["result"]


def _capture_rich_output(func, args):
    """Call a CLI function in rich mode and capture console output."""
    output_lines = []

    class MockConsole:
        def print(self, *a, **kw):
            output_lines.append(str(a[0]) if a else "")

    mock_console = MockConsole()

    with patch("agenticcli.console.is_json_output", return_value=False):
        with patch("agenticcli.commands.stories.PatternService") as MockPatSvc:
            # Don't mock PatternService here — let it use real data
            pass

    # Actually, capture via StringIO approach on console
    with patch("agenticcli.console.is_json_output", return_value=False):
        with patch("agenticcli.console.console") as mock_console_obj:
            printed = []
            mock_console_obj.print = lambda *a, **kw: printed.append(str(a[0]) if a else "")
            func(args)

    return "\n".join(printed)


# ---------------------------------------------------------------------------
# cmd_pattern_cat — watch_files display
# ---------------------------------------------------------------------------


class TestPatternCatWatchFiles:
    """cmd_pattern_cat displays watch_files in JSON and rich output."""

    def test_json_includes_watch_files(self, cli_fixture):
        """JSON output includes watch_files array."""
        from agenticcli.commands.stories import cmd_pattern_cat

        args = SimpleNamespace(id="PAT-CLI-001")
        result = _capture_json_call(cmd_pattern_cat, args)

        assert "watch_files" in result
        assert isinstance(result["watch_files"], list)
        assert "modules/AgenticCLI/src/agenticcli/commands/*.py" in result["watch_files"]

    def test_json_watch_files_empty_when_absent(self, cli_fixture):
        """JSON output has empty watch_files list when pattern has no watch_files."""
        from agenticcli.commands.stories import cmd_pattern_cat

        args = SimpleNamespace(id="PAT-CLI-002")
        result = _capture_json_call(cmd_pattern_cat, args)

        assert "watch_files" in result
        assert result["watch_files"] == []

    def test_json_includes_all_expected_keys(self, cli_fixture):
        """JSON output for pattern-cat has all required keys."""
        from agenticcli.commands.stories import cmd_pattern_cat

        args = SimpleNamespace(id="PAT-CLI-001")
        result = _capture_json_call(cmd_pattern_cat, args)

        expected_keys = {
            "id", "title", "description", "domain", "tags",
            "applicable_categories", "parameters", "verification",
            "watch_files", "source_file",
        }
        missing = expected_keys - set(result.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_rich_shows_watch_files_section(self, cli_fixture):
        """Rich output shows Watch Files section when pattern has watch_files."""
        from agenticcli.commands.stories import cmd_pattern_cat

        args = SimpleNamespace(id="PAT-CLI-001")
        output = _capture_rich_output(cmd_pattern_cat, args)

        assert "Watch Files" in output
        assert "modules/AgenticCLI/src/agenticcli/commands/*.py" in output

    def test_rich_omits_watch_files_section_when_empty(self, cli_fixture):
        """Rich output omits Watch Files heading when pattern has no watch_files."""
        from agenticcli.commands.stories import cmd_pattern_cat

        args = SimpleNamespace(id="PAT-CLI-002")
        output = _capture_rich_output(cmd_pattern_cat, args)

        # Check for the bold section header, not the substring in the title
        assert "[bold]Watch Files:[/bold]" not in output


# ---------------------------------------------------------------------------
# cmd_pattern_claimants — inherited watch_files display
# ---------------------------------------------------------------------------


class TestPatternClaimantsWatchFiles:
    """cmd_pattern_claimants displays inherited watch_files."""

    def test_json_includes_inherited_watch_files(self, cli_fixture):
        """JSON output includes inherited_watch_files for each claimant."""
        from agenticcli.commands.stories import cmd_pattern_claimants

        args = SimpleNamespace(id="PAT-CLI-001")
        result = _capture_json_call(cmd_pattern_claimants, args)

        assert "claimants" in result
        assert result["claimant_count"] >= 1

        claimant = result["claimants"][0]
        assert "inherited_watch_files" in claimant
        assert isinstance(claimant["inherited_watch_files"], list)
        # The watch_files glob should have expanded to match our fixture files
        assert any("stories.py" in f for f in claimant["inherited_watch_files"])

    def test_json_has_expected_claimant_keys(self, cli_fixture):
        """Each claimant in JSON output has id, title, source_file, inherited_watch_files."""
        from agenticcli.commands.stories import cmd_pattern_claimants

        args = SimpleNamespace(id="PAT-CLI-001")
        result = _capture_json_call(cmd_pattern_claimants, args)

        for claimant in result["claimants"]:
            assert "id" in claimant
            assert "title" in claimant
            assert "source_file" in claimant
            assert "inherited_watch_files" in claimant

    def test_json_has_pattern_metadata(self, cli_fixture):
        """JSON output includes pattern_id, pattern_title, claimant_count."""
        from agenticcli.commands.stories import cmd_pattern_claimants

        args = SimpleNamespace(id="PAT-CLI-001")
        result = _capture_json_call(cmd_pattern_claimants, args)

        assert result["pattern_id"] == "PAT-CLI-001"
        assert result["pattern_title"] == "JSON Output"
        assert isinstance(result["claimant_count"], int)

    def test_rich_shows_watch_files_count(self, cli_fixture):
        """Rich output shows watch_files file count for claimants."""
        from agenticcli.commands.stories import cmd_pattern_claimants

        args = SimpleNamespace(id="PAT-CLI-001")
        output = _capture_rich_output(cmd_pattern_claimants, args)

        assert "watch_files:" in output
        assert "files" in output


# ---------------------------------------------------------------------------
# cmd_health — pattern_watch stale_reason in JSON output
# ---------------------------------------------------------------------------


class TestHealthPatternWatchDisplay:
    """stories health reports pattern_watch stale_reason correctly."""

    @pytest.fixture
    def stale_fixture(self, tmp_path, monkeypatch):
        """Health fixture with a story that is stale due to pattern_watch."""
        stories_dir = tmp_path / "docs" / "userstories"

        # Create pattern with watch_files
        patterns_dir = stories_dir / "Patterns" / "cli"
        patterns_dir.mkdir(parents=True)
        _write_pattern_yaml(patterns_dir / "01_patterns.yml", [
            {
                "id": "PAT-CLI-001",
                "title": "JSON Output",
                "watch_files": ["modules/AgenticCLI/src/agenticcli/commands/stories.py"],
            },
        ])

        # Create matching file on disk
        cli_commands = tmp_path / "modules" / "AgenticCLI" / "src" / "agenticcli" / "commands"
        cli_commands.mkdir(parents=True)
        (cli_commands / "stories.py").write_text("# stories command")

        # Create story claiming the pattern (passing, with last_pass_commit)
        story_category = stories_dir / "Testing"
        story_category.mkdir(parents=True)
        _write_story_yaml(story_category / "01_stories.yml", [
            {
                "id": "US-TEST-001",
                "title": "Pattern Watch Stale Story",
                "lifecycle": "implemented",
                "test_status": "pass",
                "last_pass_commit": "abc1234def",
                "related_files": [],
                "inherits_patterns": [{"id": "PAT-CLI-001"}],
            },
        ])

        import agenticcli.commands.stories as stories_mod
        import agenticguidance.services.story as story_svc_mod

        monkeypatch.setattr(stories_mod, "_find_userstories_dir", lambda: stories_dir)
        monkeypatch.setattr(stories_mod, "_find_repo_root", lambda: tmp_path)
        monkeypatch.setattr(stories_mod, "_scan_pytest_story_markers", lambda: set())
        monkeypatch.setattr(stories_mod, "_scan_pytest_flaky_markers", lambda _: set())

        # Make git report that the pattern-watched file has changed.
        # Patch in both modules: story service (used by compute_story_*) and
        # stories CLI (used by cmd_health JSON detail population, imported as local name).
        _changed_files = {"modules/AgenticCLI/src/agenticcli/commands/stories.py"}
        monkeypatch.setattr(
            story_svc_mod,
            "_git_changed_files_since",
            lambda commit, repo_root: _changed_files,
        )
        monkeypatch.setattr(
            stories_mod,
            "_git_changed_files_since",
            lambda commit, repo_root: _changed_files,
        )

        return stories_dir

    def test_json_staleness_has_pattern_watch_changed_key(self, stale_fixture):
        """JSON output staleness section includes pattern_watch_changed key."""
        from agenticcli.commands.stories import cmd_health

        args = SimpleNamespace(project=None, coverage=False, all=False)
        result = _capture_json_call(cmd_health, args)

        for story in result["stories"]:
            staleness = story["staleness"]
            assert "pattern_watch_changed" in staleness, (
                f"Story {story['id']} staleness missing 'pattern_watch_changed' key"
            )

    def test_json_pattern_watch_stale_reason(self, stale_fixture):
        """Story stale due to pattern watch shows reason='pattern:<PAT-ID>' in JSON."""
        from agenticcli.commands.stories import cmd_health

        args = SimpleNamespace(project=None, coverage=False, all=False)
        result = _capture_json_call(cmd_health, args)

        # Find the story that inherits the pattern
        stale_story = next(
            (s for s in result["stories"] if s["id"] == "US-TEST-001"),
            None,
        )
        assert stale_story is not None, "US-TEST-001 not found in health output"
        assert stale_story["status"] == "stale"
        assert stale_story["staleness"]["is_stale"] is True
        assert stale_story["staleness"]["reason"] == "pattern:PAT-CLI-001"

    def test_json_pattern_watch_changed_files_populated(self, stale_fixture):
        """pattern_watch_changed lists the specific pattern-watched files that changed."""
        from agenticcli.commands.stories import cmd_health

        args = SimpleNamespace(project=None, coverage=False, all=False)
        result = _capture_json_call(cmd_health, args)

        stale_story = next(
            (s for s in result["stories"] if s["id"] == "US-TEST-001"),
            None,
        )
        assert stale_story is not None
        pw_changed = stale_story["staleness"]["pattern_watch_changed"]
        assert isinstance(pw_changed, list)
        assert "modules/AgenticCLI/src/agenticcli/commands/stories.py" in pw_changed

    def test_json_related_empty_when_pattern_watch_only(self, stale_fixture):
        """related_files_changed is empty when only pattern_watch triggered staleness."""
        from agenticcli.commands.stories import cmd_health

        args = SimpleNamespace(project=None, coverage=False, all=False)
        result = _capture_json_call(cmd_health, args)

        stale_story = next(
            (s for s in result["stories"] if s["id"] == "US-TEST-001"),
            None,
        )
        assert stale_story is not None
        assert stale_story["staleness"]["related_files_changed"] == []
        assert "global_config_changed" not in stale_story["staleness"]
