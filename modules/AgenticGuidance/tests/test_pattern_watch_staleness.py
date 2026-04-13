"""Tests for staleness integration with pattern_watch.

Validates:
- compute_story_status returns 'stale' when pattern-watched files change
- compute_story_flags returns stale_reason='pattern:<PAT-ID>' when only
  pattern-watched files change
- Priority ordering: pattern:<id> > related_file > anchor_unreachable
- No staleness when pattern-watched files are unchanged
- First-matching pattern wins when a story inherits multiple patterns and
  more than one has a hit on changed files (iteration order of
  ``inherits_patterns``).

P2_009 of epic 260411AG_pattern_claimant_watch_files_fold_global_watch.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from agenticguidance.services.story import PatternService, Story, StoryService

pytestmark = pytest.mark.story("US-260411AG-001")

# Module path shortcut for patching git diff
_GIT_CHANGED = "agenticguidance.services.story._git_changed_files_since"


def _make_story(
    related_files: list[str] | None = None,
    last_pass_commit: str = "abc1234",
    test_status: str = "pass",
) -> Story:
    """Create a story that has previously passed (eligible for staleness checks)."""
    return Story(
        id="US-TEST-001",
        title="Staleness test story",
        test_status=test_status,
        last_pass_commit=last_pass_commit,
        related_files=related_files or [],
    )


# ---------------------------------------------------------------------------
# compute_story_status — pattern_watch staleness
# ---------------------------------------------------------------------------


class TestComputeStoryStatusPatternWatch:
    """compute_story_status integrates pattern_watch into staleness detection."""

    def test_stale_when_pattern_watch_file_changed(self, tmp_path):
        """Story becomes stale when a pattern-watched file changes."""
        story = _make_story(related_files=[])
        pattern_watch = {
            "modules/AgenticCLI/src/agenticcli/commands/stories.py": "PAT-CLI-001",
        }

        with patch(_GIT_CHANGED, return_value={"modules/AgenticCLI/src/agenticcli/commands/stories.py"}):
            status = StoryService(userstories_dir=None).compute_story_status(
                story, repo_root=tmp_path, pattern_watch=pattern_watch
            )

        assert status == "stale"

    def test_not_stale_when_pattern_watch_files_unchanged(self, tmp_path):
        """Story remains passing when pattern-watched files are unchanged."""
        story = _make_story(related_files=[])
        pattern_watch = {
            "modules/AgenticCLI/src/agenticcli/commands/stories.py": "PAT-CLI-001",
        }

        with patch(_GIT_CHANGED, return_value={"some/unrelated/file.py"}):
            status = StoryService(userstories_dir=None).compute_story_status(
                story, repo_root=tmp_path, pattern_watch=pattern_watch
            )

        assert status == "passing"

    def test_stale_only_from_pattern_watch_no_related(self, tmp_path):
        """Story with no related_files but pattern_watch changed → stale."""
        story = _make_story(related_files=[])
        pattern_watch = {"pyproject.toml": "PAT-INFRA-002"}

        with patch(_GIT_CHANGED, return_value={"pyproject.toml"}):
            status = StoryService(userstories_dir=None).compute_story_status(
                story, repo_root=tmp_path, pattern_watch=pattern_watch
            )

        assert status == "stale"

    def test_passing_with_empty_pattern_watch(self, tmp_path):
        """Empty pattern_watch dict doesn't change status."""
        story = _make_story(related_files=[])

        with patch(_GIT_CHANGED, return_value={"some/file.py"}):
            status = StoryService(userstories_dir=None).compute_story_status(
                story, repo_root=tmp_path, pattern_watch={}
            )

        assert status == "passing"

    def test_passing_with_none_pattern_watch(self, tmp_path):
        """None pattern_watch doesn't change status."""
        story = _make_story(related_files=[])

        with patch(_GIT_CHANGED, return_value={"some/file.py"}):
            status = StoryService(userstories_dir=None).compute_story_status(
                story, repo_root=tmp_path, pattern_watch=None
            )

        assert status == "passing"

    def test_stale_from_combined_pattern_and_related(self, tmp_path):
        """Story is stale when pattern_watch file changes alongside related_files."""
        story = _make_story(related_files=["modules/foo/bar.py"])
        pattern_watch = {
            "modules/AgenticCLI/src/agenticcli/commands/stories.py": "PAT-CLI-001",
        }

        with patch(_GIT_CHANGED, return_value={"modules/AgenticCLI/src/agenticcli/commands/stories.py"}):
            status = StoryService(userstories_dir=None).compute_story_status(
                story, repo_root=tmp_path, pattern_watch=pattern_watch
            )

        assert status == "stale"


# ---------------------------------------------------------------------------
# compute_story_flags — stale_reason='pattern:<PAT-ID>' attribution
# ---------------------------------------------------------------------------


class TestComputeStoryFlagsPatternWatch:
    """compute_story_flags correctly attributes stale_reason to pattern:<id>."""

    def test_stale_reason_pattern_id_when_only_pattern_files_changed(self, tmp_path):
        """stale_reason='pattern:<PAT-ID>' when only pattern-watched files changed."""
        story = _make_story(related_files=["modules/foo/widget.py"])
        pattern_watch = {
            "modules/AgenticCLI/src/agenticcli/commands/stories.py": "PAT-CLI-001",
        }

        with patch(_GIT_CHANGED, return_value={"modules/AgenticCLI/src/agenticcli/commands/stories.py"}):
            flags = StoryService(userstories_dir=None).compute_story_flags(
                story, repo_root=tmp_path, pattern_watch=pattern_watch
            )

        assert flags["stale_reason"] == "pattern:PAT-CLI-001"

    def test_stale_reason_none_when_nothing_changed(self, tmp_path):
        """stale_reason=None when no watched files changed."""
        story = _make_story(related_files=["modules/foo/widget.py"])
        pattern_watch = {
            "modules/AgenticCLI/src/agenticcli/commands/stories.py": "PAT-CLI-001",
        }

        with patch(_GIT_CHANGED, return_value=set()):
            flags = StoryService(userstories_dir=None).compute_story_flags(
                story, repo_root=tmp_path, pattern_watch=pattern_watch
            )

        assert flags["stale_reason"] is None

    def test_stale_reason_related_file_when_only_related_changed(self, tmp_path):
        """stale_reason='related_file' when only related_files changed (not pattern_watch)."""
        story = _make_story(related_files=["modules/foo/widget.py"])
        pattern_watch = {
            "modules/AgenticCLI/src/agenticcli/commands/stories.py": "PAT-CLI-001",
        }

        with patch(_GIT_CHANGED, return_value={"modules/foo/widget.py"}):
            flags = StoryService(userstories_dir=None).compute_story_flags(
                story, repo_root=tmp_path, pattern_watch=pattern_watch
            )

        assert flags["stale_reason"] == "related_file"


# ---------------------------------------------------------------------------
# Priority ordering: pattern:<id> > related_file
# ---------------------------------------------------------------------------


class TestStaleReasonPriority:
    """Verify priority ordering: pattern:<id> > related_file."""

    def test_pattern_watch_takes_precedence_over_related_file(self, tmp_path):
        """When both pattern_watch and related_files changed, stale_reason='pattern:<id>'."""
        story = _make_story(related_files=["modules/foo/widget.py"])
        pattern_watch = {
            "modules/AgenticCLI/src/agenticcli/commands/stories.py": "PAT-CLI-001",
        }

        with patch(_GIT_CHANGED, return_value={
            "modules/AgenticCLI/src/agenticcli/commands/stories.py",
            "modules/foo/widget.py",
        }):
            flags = StoryService(userstories_dir=None).compute_story_flags(
                story, repo_root=tmp_path,
                pattern_watch=pattern_watch,
            )

        assert flags["stale_reason"] == "pattern:PAT-CLI-001"

    def test_pattern_watch_file_also_in_related_files_is_pattern_watch(self, tmp_path):
        """File in both pattern_watch and related_files: pattern_watch wins (higher priority)."""
        # Edge case: same file appears in both sets
        shared_file = "modules/foo/widget.py"
        story = _make_story(related_files=[shared_file])
        pattern_watch = {shared_file: "PAT-CLI-001"}

        with patch(_GIT_CHANGED, return_value={shared_file}):
            flags = StoryService(userstories_dir=None).compute_story_flags(
                story, repo_root=tmp_path,
                pattern_watch=pattern_watch,
            )

        assert flags["stale_reason"] == "pattern:PAT-CLI-001"


# ---------------------------------------------------------------------------
# First-match-wins across multiple inherited patterns
# ---------------------------------------------------------------------------


class TestMultiplePatternFirstMatchWins:
    """When a story inherits multiple patterns and multiple have hits on
    changed files, the first-matching pattern (by iteration order of
    ``story.inherits_patterns``) owns the stale_reason."""

    def _write_pattern_yaml(self, path: Path, patterns: list[dict]) -> None:
        import yaml
        path.write_text(yaml.dump({"patterns": patterns}, sort_keys=False))

    def test_first_inherited_pattern_wins(self, tmp_path):
        """A story inheriting [PAT-A, PAT-B] where both have watch_files that
        hit changed files reports stale_reason='pattern:PAT-A'."""
        stories_dir = tmp_path / "docs" / "userstories"

        # Two minimal patterns, each with its own watch_files glob pointing at
        # a distinct, concrete file on disk.
        patterns_dir = stories_dir / "Patterns" / "demo"
        patterns_dir.mkdir(parents=True)
        self._write_pattern_yaml(patterns_dir / "01_patterns.yml", [
            {
                "id": "PAT-A",
                "title": "Pattern A",
                "watch_files": ["modules/a/file_a.py"],
            },
            {
                "id": "PAT-B",
                "title": "Pattern B",
                "watch_files": ["modules/b/file_b.py"],
            },
        ])

        # Create files on disk so glob expansion is deterministic.
        (tmp_path / "modules" / "a").mkdir(parents=True)
        (tmp_path / "modules" / "a" / "file_a.py").write_text("# a")
        (tmp_path / "modules" / "b").mkdir(parents=True)
        (tmp_path / "modules" / "b" / "file_b.py").write_text("# b")

        story = Story(
            id="US-MP-001",
            title="Multi-pattern story",
            test_status="pass",
            last_pass_commit="abc1234",
            related_files=[],
            inherits_patterns=[{"id": "PAT-A"}, {"id": "PAT-B"}],
        )

        # Resolve pattern_watch the same way cmd_health does.
        pat_svc = PatternService(userstories_dir=stories_dir)
        pattern_watch = pat_svc.get_watch_files_for_story(story, repo_root=tmp_path)

        # Sanity: both patterns resolved at least one watched file.
        assert "modules/a/file_a.py" in pattern_watch
        assert "modules/b/file_b.py" in pattern_watch
        assert pattern_watch["modules/a/file_a.py"] == "PAT-A"
        assert pattern_watch["modules/b/file_b.py"] == "PAT-B"

        with patch(_GIT_CHANGED, return_value={
            "modules/a/file_a.py",
            "modules/b/file_b.py",
        }):
            flags = StoryService(userstories_dir=stories_dir).compute_story_flags(
                story, repo_root=tmp_path, pattern_watch=pattern_watch
            )

        # First inherited pattern (PAT-A) wins.
        assert flags["stale_reason"] == "pattern:PAT-A"
