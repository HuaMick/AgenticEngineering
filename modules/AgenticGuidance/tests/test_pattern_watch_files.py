"""Tests for Pattern.watch_files field, PatternService YAML parsing, and watch_files collection.

Validates:
- Pattern dataclass accepts and stores watch_files field (P2_007)
- Pattern with no watch_files defaults to empty list (P2_007)
- PatternService._parse_file() reads watch_files from pattern YAML files (P2_007)
- PatternService._parse_file() handles missing watch_files key gracefully (P2_007)
- PatternService.get_watch_files_for_story() collects and merges watch_files (P2_008)
- Deduplication of overlapping pattern watch_files (P2_008)
- Graceful handling of missing patterns and empty inherits_patterns (P2_008)

Epic: 260411AG_pattern_claimant_watch_files_fold_global_watch.
"""

from pathlib import Path

import pytest
import yaml

from agenticguidance.services.story import Pattern, PatternService, Story

pytestmark = pytest.mark.story("US-260411AG-001")


# ---------------------------------------------------------------------------
# Helper: write a pattern YAML file
# ---------------------------------------------------------------------------


def _write_pattern_yaml(path: Path, patterns: list[dict]) -> Path:
    """Write a patterns YAML file with the given pattern items."""
    path.write_text(yaml.dump({"patterns": patterns}, sort_keys=False))
    return path


# ---------------------------------------------------------------------------
# Pattern dataclass — watch_files field
# ---------------------------------------------------------------------------


class TestPatternWatchFilesField:
    """Pattern dataclass accepts and stores watch_files."""

    def test_pattern_with_watch_files(self):
        """Pattern constructed with watch_files stores them correctly."""
        watch = ["modules/AgenticCLI/src/**/*.py", "pyproject.toml"]
        p = Pattern(id="PAT-CLI-001", title="Test", watch_files=watch)

        assert p.watch_files == watch
        assert len(p.watch_files) == 2
        assert "pyproject.toml" in p.watch_files

    def test_pattern_without_watch_files_defaults_to_empty_list(self):
        """Pattern constructed without watch_files defaults to empty list."""
        p = Pattern(id="PAT-CLI-001", title="Test")

        assert p.watch_files == []
        assert isinstance(p.watch_files, list)

    def test_pattern_with_empty_watch_files(self):
        """Pattern constructed with explicit empty list stores empty list."""
        p = Pattern(id="PAT-CLI-001", title="Test", watch_files=[])

        assert p.watch_files == []

    def test_watch_files_does_not_share_default_across_instances(self):
        """Each Pattern instance gets its own default list (no mutable default sharing)."""
        p1 = Pattern(id="PAT-CLI-001", title="First")
        p2 = Pattern(id="PAT-CLI-002", title="Second")

        p1.watch_files.append("foo.py")

        assert p1.watch_files == ["foo.py"]
        assert p2.watch_files == [], "Mutation of p1 must not affect p2"

    def test_pattern_preserves_other_fields_alongside_watch_files(self):
        """Pattern with watch_files still correctly stores all other fields."""
        p = Pattern(
            id="PAT-DAT-001",
            title="Filelock Pattern",
            description="Cross-cutting file locking",
            tags=["data", "locking"],
            applicable_categories=["US-DAT"],
            parameters={"lock_target": {"required": True}},
            verification={"behavioral": {"steps": []}},
            source_file="/tmp/pattern.yml",
            watch_files=["modules/AgenticGuidance/src/**/*.py"],
        )

        assert p.id == "PAT-DAT-001"
        assert p.title == "Filelock Pattern"
        assert p.description == "Cross-cutting file locking"
        assert p.tags == ["data", "locking"]
        assert p.watch_files == ["modules/AgenticGuidance/src/**/*.py"]
        assert p.source_file == "/tmp/pattern.yml"


# ---------------------------------------------------------------------------
# PatternService._parse_file() — YAML loading with watch_files
# ---------------------------------------------------------------------------


class TestPatternServiceParseWatchFiles:
    """PatternService._parse_file() correctly reads watch_files from YAML."""

    @pytest.fixture
    def patterns_dir(self, tmp_path):
        """Create a userstories/Patterns directory structure."""
        d = tmp_path / "userstories" / "Patterns" / "cli"
        d.mkdir(parents=True)
        return d

    @pytest.fixture
    def svc(self, tmp_path):
        """PatternService backed by tmp_path userstories dir."""
        stories_dir = tmp_path / "userstories"
        stories_dir.mkdir(exist_ok=True)
        return PatternService(userstories_dir=stories_dir)

    def test_parse_file_reads_watch_files(self, patterns_dir, svc):
        """_parse_file extracts watch_files from pattern YAML."""
        pattern_file = patterns_dir / "01_test.yml"
        _write_pattern_yaml(pattern_file, [
            {
                "id": "PAT-CLI-099",
                "title": "Test Pattern",
                "watch_files": ["src/**/*.py", "pyproject.toml"],
            }
        ])

        result = svc._parse_file(pattern_file)

        assert len(result) == 1
        assert result[0].watch_files == ["src/**/*.py", "pyproject.toml"]

    def test_parse_file_missing_watch_files_defaults_empty(self, patterns_dir, svc):
        """_parse_file defaults watch_files to empty list when key is absent."""
        pattern_file = patterns_dir / "01_test.yml"
        _write_pattern_yaml(pattern_file, [
            {
                "id": "PAT-CLI-099",
                "title": "No Watch Files Pattern",
                # No watch_files key
            }
        ])

        result = svc._parse_file(pattern_file)

        assert len(result) == 1
        assert result[0].watch_files == []

    def test_parse_file_empty_watch_files_list(self, patterns_dir, svc):
        """_parse_file handles explicit empty watch_files list."""
        pattern_file = patterns_dir / "01_test.yml"
        _write_pattern_yaml(pattern_file, [
            {
                "id": "PAT-CLI-099",
                "title": "Empty Watch Files",
                "watch_files": [],
            }
        ])

        result = svc._parse_file(pattern_file)

        assert len(result) == 1
        assert result[0].watch_files == []

    def test_parse_file_multiple_patterns_with_different_watch_files(self, patterns_dir, svc):
        """_parse_file handles multiple patterns in one file, each with their own watch_files."""
        pattern_file = patterns_dir / "01_test.yml"
        _write_pattern_yaml(pattern_file, [
            {
                "id": "PAT-CLI-001",
                "title": "First",
                "watch_files": ["modules/AgenticCLI/src/**/*.py"],
            },
            {
                "id": "PAT-CLI-002",
                "title": "Second",
                # No watch_files
            },
            {
                "id": "PAT-CLI-003",
                "title": "Third",
                "watch_files": ["docs/**/*.md", "pyproject.toml"],
            },
        ])

        result = svc._parse_file(pattern_file)

        assert len(result) == 3
        assert result[0].watch_files == ["modules/AgenticCLI/src/**/*.py"]
        assert result[1].watch_files == []
        assert result[2].watch_files == ["docs/**/*.md", "pyproject.toml"]

    def test_parse_file_preserves_glob_patterns_as_strings(self, patterns_dir, svc):
        """watch_files glob patterns are stored as exact strings from YAML."""
        globs = [
            "modules/*/pyproject.toml",
            "modules/**/conftest.py",
            "src/**/*.py",
            "*.toml",
        ]
        pattern_file = patterns_dir / "01_test.yml"
        _write_pattern_yaml(pattern_file, [
            {
                "id": "PAT-CLI-099",
                "title": "Glob Patterns",
                "watch_files": globs,
            }
        ])

        result = svc._parse_file(pattern_file)

        assert result[0].watch_files == globs

    def test_parse_file_bad_yaml_returns_empty(self, patterns_dir, svc):
        """_parse_file returns empty list for malformed YAML."""
        pattern_file = patterns_dir / "01_bad.yml"
        pattern_file.write_text(": this is not valid yaml: [unclosed")

        result = svc._parse_file(pattern_file)

        assert result == []

    def test_parse_file_empty_file_returns_empty(self, patterns_dir, svc):
        """_parse_file returns empty list for empty file."""
        pattern_file = patterns_dir / "01_empty.yml"
        pattern_file.write_text("")

        result = svc._parse_file(pattern_file)

        assert result == []

    def test_parse_file_nonexistent_returns_empty(self, svc):
        """_parse_file returns empty list for non-existent file."""
        result = svc._parse_file(Path("/nonexistent/pattern.yml"))

        assert result == []


# ---------------------------------------------------------------------------
# PatternService.load_all() — end-to-end YAML loading with watch_files
# ---------------------------------------------------------------------------


class TestPatternServiceLoadAllWatchFiles:
    """load_all() integrates _parse_file results and watch_files are accessible."""

    @pytest.fixture
    def populated_svc(self, tmp_path):
        """PatternService with a Patterns directory containing test patterns."""
        patterns_dir = tmp_path / "userstories" / "Patterns" / "cli"
        patterns_dir.mkdir(parents=True)

        _write_pattern_yaml(patterns_dir / "01_test.yml", [
            {
                "id": "PAT-CLI-001",
                "title": "JSON Output",
                "watch_files": ["modules/AgenticCLI/src/agenticcli/commands/*.py"],
            },
            {
                "id": "PAT-CLI-002",
                "title": "Project Filter",
                # No watch_files
            },
        ])

        return PatternService(userstories_dir=tmp_path / "userstories")

    def test_load_all_includes_watch_files(self, populated_svc):
        """load_all returns patterns with their watch_files intact."""
        patterns = populated_svc.load_all()

        assert len(patterns) == 2
        p1 = next(p for p in patterns if p.id == "PAT-CLI-001")
        p2 = next(p for p in patterns if p.id == "PAT-CLI-002")

        assert p1.watch_files == ["modules/AgenticCLI/src/agenticcli/commands/*.py"]
        assert p2.watch_files == []

    def test_get_by_id_returns_pattern_with_watch_files(self, populated_svc):
        """get_by_id returns pattern with correct watch_files."""
        p = populated_svc.get_by_id("PAT-CLI-001")

        assert p is not None
        assert p.watch_files == ["modules/AgenticCLI/src/agenticcli/commands/*.py"]

    def test_get_by_id_no_watch_files_pattern(self, populated_svc):
        """get_by_id for pattern without watch_files returns empty list."""
        p = populated_svc.get_by_id("PAT-CLI-002")

        assert p is not None
        assert p.watch_files == []


# ---------------------------------------------------------------------------
# PatternService.get_watch_files_for_story() — collection, merge, dedup
# (P2_008)
# ---------------------------------------------------------------------------


class TestGetWatchFilesForStory:
    """get_watch_files_for_story() collects, merges, and deduplicates watch_files."""

    @pytest.fixture
    def repo_root(self, tmp_path):
        """Create a repo root with files matching various glob patterns."""
        # CLI command files
        cli_commands = tmp_path / "modules" / "AgenticCLI" / "src" / "agenticcli" / "commands"
        cli_commands.mkdir(parents=True)
        (cli_commands / "stories.py").write_text("# stories command")
        (cli_commands / "epic.py").write_text("# epic command")

        # Guidance service files
        guidance_src = tmp_path / "modules" / "AgenticGuidance" / "src" / "agenticguidance" / "services"
        guidance_src.mkdir(parents=True)
        (guidance_src / "story.py").write_text("# story service")
        (guidance_src / "state.py").write_text("# state service")

        # Root config files
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        (tmp_path / "setup.py").write_text("# setup")

        # Docs
        docs = tmp_path / "docs" / "testing"
        docs.mkdir(parents=True)
        (docs / "README.md").write_text("# Testing docs")

        return tmp_path

    @pytest.fixture
    def pattern_svc(self, tmp_path):
        """PatternService with multi-domain pattern files containing watch_files."""
        stories_dir = tmp_path / "userstories"

        # CLI patterns
        cli_dir = stories_dir / "Patterns" / "cli"
        cli_dir.mkdir(parents=True)
        _write_pattern_yaml(cli_dir / "01_patterns.yml", [
            {
                "id": "PAT-CLI-001",
                "title": "JSON Output",
                "watch_files": [
                    "modules/AgenticCLI/src/agenticcli/commands/*.py",
                ],
            },
            {
                "id": "PAT-CLI-002",
                "title": "Project Filter",
                # No watch_files
            },
        ])

        # Data patterns
        data_dir = stories_dir / "Patterns" / "data"
        data_dir.mkdir(parents=True)
        _write_pattern_yaml(data_dir / "01_patterns.yml", [
            {
                "id": "PAT-DAT-001",
                "title": "Filelock",
                "watch_files": [
                    "modules/AgenticGuidance/src/agenticguidance/services/*.py",
                ],
            },
        ])

        # Execution patterns (with overlapping watch_files)
        exec_dir = stories_dir / "Patterns" / "execution"
        exec_dir.mkdir(parents=True)
        _write_pattern_yaml(exec_dir / "01_patterns.yml", [
            {
                "id": "PAT-EXE-001",
                "title": "Test Fix Loop",
                "watch_files": [
                    "modules/AgenticCLI/src/agenticcli/commands/*.py",  # overlaps PAT-CLI-001
                    "pyproject.toml",
                ],
            },
        ])

        return PatternService(userstories_dir=stories_dir)

    def test_single_pattern_with_watch_files(self, pattern_svc, repo_root):
        """Story inheriting 1 pattern with watch_files returns expanded file set."""
        story = Story(
            id="US-TEST-001",
            title="Test Story",
            inherits_patterns=[{"id": "PAT-CLI-001"}],
        )

        result = pattern_svc.get_watch_files_for_story(story, repo_root)

        assert isinstance(result, dict)
        assert len(result) > 0
        # Should contain CLI command files matching the glob
        assert "modules/AgenticCLI/src/agenticcli/commands/stories.py" in result
        assert "modules/AgenticCLI/src/agenticcli/commands/epic.py" in result

    def test_multiple_patterns_merged_and_deduplicated(self, pattern_svc, repo_root):
        """Story inheriting 2 patterns with overlapping globs returns deduplicated union."""
        story = Story(
            id="US-TEST-002",
            title="Multi-Pattern Story",
            inherits_patterns=[
                {"id": "PAT-CLI-001"},   # modules/AgenticCLI/src/.../commands/*.py
                {"id": "PAT-EXE-001"},   # same glob + pyproject.toml
            ],
        )

        result = pattern_svc.get_watch_files_for_story(story, repo_root)

        # CLI commands files appear once even though both patterns match them
        assert "modules/AgenticCLI/src/agenticcli/commands/stories.py" in result
        assert "modules/AgenticCLI/src/agenticcli/commands/epic.py" in result
        # pyproject.toml from PAT-EXE-001
        assert "pyproject.toml" in result
        # Result is a set — inherently deduplicated
        assert isinstance(result, dict)

    def test_patterns_from_different_domains_merged(self, pattern_svc, repo_root):
        """Story inheriting patterns from different domains merges all watch_files."""
        story = Story(
            id="US-TEST-003",
            title="Cross-Domain Story",
            inherits_patterns=[
                {"id": "PAT-CLI-001"},   # CLI commands
                {"id": "PAT-DAT-001"},   # Guidance services
            ],
        )

        result = pattern_svc.get_watch_files_for_story(story, repo_root)

        # CLI files
        assert "modules/AgenticCLI/src/agenticcli/commands/stories.py" in result
        # Guidance files
        assert "modules/AgenticGuidance/src/agenticguidance/services/story.py" in result
        assert "modules/AgenticGuidance/src/agenticguidance/services/state.py" in result

    def test_pattern_with_empty_watch_files_returns_empty(self, pattern_svc, repo_root):
        """Story inheriting pattern without watch_files returns empty set."""
        story = Story(
            id="US-TEST-004",
            title="No Watch Story",
            inherits_patterns=[{"id": "PAT-CLI-002"}],  # No watch_files
        )

        result = pattern_svc.get_watch_files_for_story(story, repo_root)

        assert result == {}

    def test_nonexistent_pattern_id_returns_empty(self, pattern_svc, repo_root):
        """Story referencing non-existent pattern ID gracefully returns empty set."""
        story = Story(
            id="US-TEST-005",
            title="Missing Pattern Story",
            inherits_patterns=[{"id": "PAT-FAKE-999"}],
        )

        result = pattern_svc.get_watch_files_for_story(story, repo_root)

        assert result == {}

    def test_story_with_no_inherits_patterns_returns_empty(self, pattern_svc, repo_root):
        """Story with empty inherits_patterns returns empty set."""
        story = Story(
            id="US-TEST-006",
            title="Plain Story",
            inherits_patterns=[],
        )

        result = pattern_svc.get_watch_files_for_story(story, repo_root)

        assert result == {}

    def test_mix_of_valid_and_missing_patterns(self, pattern_svc, repo_root):
        """Story with both valid and missing pattern IDs collects from valid ones only."""
        story = Story(
            id="US-TEST-007",
            title="Mixed Pattern Story",
            inherits_patterns=[
                {"id": "PAT-CLI-001"},     # valid, has watch_files
                {"id": "PAT-FAKE-999"},    # non-existent
                {"id": "PAT-DAT-001"},     # valid, has watch_files
            ],
        )

        result = pattern_svc.get_watch_files_for_story(story, repo_root)

        # Valid patterns' watch_files are collected
        assert "modules/AgenticCLI/src/agenticcli/commands/stories.py" in result
        assert "modules/AgenticGuidance/src/agenticguidance/services/story.py" in result
        # No crash from the missing pattern
        assert len(result) > 0

    def test_inherits_patterns_with_malformed_ref_skipped(self, pattern_svc, repo_root):
        """Malformed inherits_patterns entries (no 'id' key) are gracefully skipped."""
        story = Story(
            id="US-TEST-008",
            title="Bad Refs Story",
            inherits_patterns=[
                {"id": "PAT-CLI-001"},    # valid
                {"no_id": "bad_entry"},   # malformed — no 'id' key
                {},                        # empty dict
            ],
        )

        result = pattern_svc.get_watch_files_for_story(story, repo_root)

        # Only PAT-CLI-001 files collected
        assert "modules/AgenticCLI/src/agenticcli/commands/stories.py" in result
        assert len(result) >= 2  # At least the 2 CLI command files

    def test_watch_files_glob_no_matching_files_returns_empty(self, tmp_path):
        """Pattern with watch_files globs that match no files returns empty set."""
        stories_dir = tmp_path / "userstories"
        patterns_dir = stories_dir / "Patterns" / "cli"
        patterns_dir.mkdir(parents=True)

        _write_pattern_yaml(patterns_dir / "01_patterns.yml", [
            {
                "id": "PAT-CLI-099",
                "title": "No Match",
                "watch_files": ["nonexistent/**/*.py", "missing/path/*.toml"],
            },
        ])

        svc = PatternService(userstories_dir=stories_dir)
        story = Story(
            id="US-TEST-009",
            title="No Match Story",
            inherits_patterns=[{"id": "PAT-CLI-099"}],
        )

        # Empty repo_root with no matching files
        result = svc.get_watch_files_for_story(story, tmp_path)

        assert result == {}

    def test_returned_paths_are_relative_strings(self, pattern_svc, repo_root):
        """All returned paths are relative (not absolute) string paths."""
        story = Story(
            id="US-TEST-010",
            title="Relative Paths Story",
            inherits_patterns=[
                {"id": "PAT-CLI-001"},
                {"id": "PAT-DAT-001"},
            ],
        )

        result = pattern_svc.get_watch_files_for_story(story, repo_root)

        for path_str in result:
            assert not Path(path_str).is_absolute(), f"Expected relative path, got: {path_str}"
            assert isinstance(path_str, str)
