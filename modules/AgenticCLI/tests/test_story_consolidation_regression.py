"""Regression tests for story storage consolidation (260402AG).

Validates that stories are read from docs/userstories/EpicStories/ (the single
source of truth) and NOT from epic-local stories.yml files.

Key scenarios:
1. get_epic_stories_path returns correct canonical path
2. Stories in EpicStories/ survive epic archiving (they're outside epic folder)
3. Deprecation warning when old stories.yml still exists
4. StoryService discovers stories from EpicStories/
5. _parse_story_categories reads from EpicStories/ path

@story US-STR-009
"""

import os
import shutil
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.story("US-STR-001")


# ---------------------------------------------------------------------------
# T1: Canonical path resolver
# ---------------------------------------------------------------------------

class TestGetEpicStoriesPath:
    """get_epic_stories_path returns correct canonical path."""

    def test_returns_path_under_epic_stories_dir(self, tmp_path, monkeypatch):
        """Path always points to docs/userstories/EpicStories/{name}.yml."""
        from agenticguidance.services.story import get_epic_stories_path

        # Set up a repo root with docs/userstories/
        repo_root = tmp_path / "repo"
        (repo_root / "docs" / "userstories").mkdir(parents=True)
        monkeypatch.setenv("AGENTIC_REPO_ROOT", str(repo_root))

        result = get_epic_stories_path("260401XX_my_epic")

        assert result == repo_root / "docs" / "userstories" / "EpicStories" / "260401XX_my_epic.yml"
        assert result.parent.name == "EpicStories"
        assert result.suffix == ".yml"

    def test_fallback_path_when_no_repo_root(self, monkeypatch):
        """When repo root is not found, returns relative fallback path."""
        from agenticguidance.services.story import get_epic_stories_path

        monkeypatch.delenv("AGENTIC_REPO_ROOT", raising=False)
        # Set cwd to a place without docs/userstories
        monkeypatch.chdir("/tmp")

        result = get_epic_stories_path("260401XX_test")

        # Falls back to relative path
        assert str(result).endswith("EpicStories/260401XX_test.yml")

    def test_path_is_deterministic(self, tmp_path, monkeypatch):
        """Same epic name always returns same path."""
        from agenticguidance.services.story import get_epic_stories_path

        repo_root = tmp_path / "repo"
        (repo_root / "docs" / "userstories").mkdir(parents=True)
        monkeypatch.setenv("AGENTIC_REPO_ROOT", str(repo_root))

        path1 = get_epic_stories_path("260401XX_test")
        path2 = get_epic_stories_path("260401XX_test")

        assert path1 == path2


# ---------------------------------------------------------------------------
# T2: Stories survive epic archiving
# ---------------------------------------------------------------------------

class TestStoriesSurviveArchiving:
    """Stories in EpicStories/ persist when epic folder is archived/moved."""

    def test_stories_persist_after_epic_folder_deleted(self, tmp_path):
        """Deleting the epic folder does NOT remove stories in EpicStories/."""
        # Create both structures
        epic_folder = tmp_path / "docs" / "epics" / "live" / "260401XX_test"
        epic_folder.mkdir(parents=True)

        epic_stories_dir = tmp_path / "docs" / "userstories" / "EpicStories"
        epic_stories_dir.mkdir(parents=True)

        # Write stories to consolidated location
        stories = {"stories": [{"id": "US-001", "title": "Test"}], "categories": []}
        (epic_stories_dir / "260401XX_test.yml").write_text(yaml.dump(stories))

        # Simulate epic archiving (folder moves/deletes)
        shutil.rmtree(epic_folder)

        # Stories remain
        assert (epic_stories_dir / "260401XX_test.yml").exists()
        data = yaml.safe_load((epic_stories_dir / "260401XX_test.yml").read_text())
        assert data["stories"][0]["id"] == "US-001"

    def test_stories_persist_after_epic_folder_moved(self, tmp_path):
        """Moving epic folder to completed/ does NOT affect stories in EpicStories/."""
        live_dir = tmp_path / "docs" / "epics" / "live"
        completed_dir = tmp_path / "docs" / "epics" / "completed"
        live_dir.mkdir(parents=True)
        completed_dir.mkdir(parents=True)

        epic_folder = live_dir / "260401XX_test"
        epic_folder.mkdir()

        epic_stories_dir = tmp_path / "docs" / "userstories" / "EpicStories"
        epic_stories_dir.mkdir(parents=True)

        stories = {"stories": [{"id": "US-001", "title": "Test"}]}
        (epic_stories_dir / "260401XX_test.yml").write_text(yaml.dump(stories))

        # Simulate archiving: move epic folder
        shutil.move(str(epic_folder), str(completed_dir / "260401XX_test"))

        # Stories remain at original location
        assert (epic_stories_dir / "260401XX_test.yml").exists()
        assert not (live_dir / "260401XX_test").exists()
        assert (completed_dir / "260401XX_test").exists()


# ---------------------------------------------------------------------------
# T3: Deprecation warning for old stories.yml
# ---------------------------------------------------------------------------

class TestDeprecationWarning:
    """Deprecation warning fires when old stories.yml exists at epic-folder location."""

    def test_parse_story_categories_warns_on_old_path(self, tmp_path, monkeypatch, caplog):
        """_parse_story_categories logs deprecation when old stories.yml exists."""
        import logging
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow
        import agenticcli.workflows.planner_loop as _plmod

        epic_folder = "my_old_epic"

        # Create epic folder with old-style stories.yml
        (tmp_path / epic_folder).mkdir()
        (tmp_path / epic_folder / "stories.yml").write_text(yaml.dump({
            "stories": [{"id": "US-001"}],
        }))

        # Set up the EpicStories path with new-style file
        epic_stories_dir = tmp_path / "userstories" / "EpicStories"
        epic_stories_dir.mkdir(parents=True)
        (epic_stories_dir / f"{epic_folder}.yml").write_text(yaml.dump({
            "stories": [{"id": "US-001"}],
            "categories": [{"name": "default", "story_ids": ["US-001"]}],
        }))

        monkeypatch.setattr(_plmod, "get_epic_stories_path",
                            lambda name: epic_stories_dir / f"{name}.yml")

        workflow = PlannerLoopWorkflow(epics_dir=tmp_path)
        runner = PlannerLoopRunner(workflow=workflow)

        with caplog.at_level(logging.WARNING):
            result = runner._parse_story_categories(epic_folder)

        assert result is not None
        assert any("DEPRECATED" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# T4: StoryService discovers EpicStories
# ---------------------------------------------------------------------------

class TestStoryServiceDiscoversEpicStories:
    """StoryService.load_all() discovers stories from EpicStories/ directory."""

    def test_load_all_finds_epic_stories(self, tmp_path, monkeypatch):
        """Stories in EpicStories/ are discovered by StoryService.load_all()."""
        from agenticguidance.services.story import StoryService

        # Create userstories structure
        userstories_dir = tmp_path / "docs" / "userstories"
        userstories_dir.mkdir(parents=True)

        # Create 00_metadata.yml
        (userstories_dir / "00_metadata.yml").write_text(yaml.dump({
            "module": "userstories",
            "prefix": "US",
        }))

        # Create a manual story category
        manual_dir = userstories_dir / "ManualStories"
        manual_dir.mkdir()
        (manual_dir / "00_metadata.yml").write_text(yaml.dump({
            "module": "ManualStories",
            "prefix": "US-MAN",
        }))
        (manual_dir / "manual.yml").write_text(yaml.dump({
            "stories": [{"id": "US-MAN-001", "title": "Manual story"}],
        }))

        # Create EpicStories category
        epic_dir = userstories_dir / "EpicStories"
        epic_dir.mkdir()
        (epic_dir / "00_metadata.yml").write_text(yaml.dump({
            "module": "EpicStories",
            "prefix": "US-EPC",
        }))
        (epic_dir / "260401XX_test.yml").write_text(yaml.dump({
            "stories": [
                {"id": "US-001", "title": "Epic story 1"},
                {"id": "US-002", "title": "Epic story 2"},
            ],
        }))

        monkeypatch.setenv("AGENTIC_REPO_ROOT", str(tmp_path))

        service = StoryService(userstories_dir)
        all_stories = service.load_all()

        # Should include both manual and epic stories
        story_ids = {s.id for s in all_stories}
        assert "US-MAN-001" in story_ids
        assert "US-001" in story_ids
        assert "US-002" in story_ids
        assert len(all_stories) >= 3


# ---------------------------------------------------------------------------
# T5: No old-path reads in production code
# ---------------------------------------------------------------------------

class TestNoOldPathReads:
    """Production code does NOT read from epic-folder stories.yml (except deprecation check)."""

    def test_planner_loop_reads_from_epic_stories_dir(self, tmp_path, monkeypatch):
        """_parse_story_categories reads from get_epic_stories_path, not epic_folder/stories.yml."""
        from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow
        import agenticcli.workflows.planner_loop as _plmod

        epic_folder = "my_epic"

        # Only write to EpicStories — NOT to epic_folder/stories.yml
        epic_stories_dir = tmp_path / "userstories" / "EpicStories"
        epic_stories_dir.mkdir(parents=True)
        categories = [{"name": "infra", "story_ids": ["US-001"]}]
        (epic_stories_dir / f"{epic_folder}.yml").write_text(yaml.dump({
            "stories": [{"id": "US-001"}],
            "categories": categories,
        }))

        monkeypatch.setattr(_plmod, "get_epic_stories_path",
                            lambda name: epic_stories_dir / f"{name}.yml")

        workflow = PlannerLoopWorkflow(epics_dir=tmp_path)
        runner = PlannerLoopRunner(workflow=workflow)
        result = runner._parse_story_categories(epic_folder)

        assert result == categories

    def test_cmd_audit_reads_from_epic_stories_dir(self, tmp_path, monkeypatch, _isolate_tinydb):
        """cmd_audit reads stories from EpicStories/, not epic_folder/stories.yml."""
        from agenticcli.commands.stories import cmd_audit
        from agenticguidance.services.epic_repository import EpicRepository
        from types import SimpleNamespace
        from unittest.mock import patch

        db_path = _isolate_tinydb
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

        epic_folder = tmp_path / "docs" / "epics" / "live" / "260401XX_test"
        epic_folder.mkdir(parents=True)

        repo.create_epic({
            "epic_folder_name": "260401XX_test",
            "epic_folder": str(epic_folder),
            "name": "Test Epic",
            "status": "planning",
        })
        repo.add_phase("260401XX_test", {
            "name": "Build", "agent": "build-python", "status": "pending",
        })
        repo.add_ticket("260401XX_test", "Build", {
            "id": "T1", "name": "Task 1", "status": "proposed", "story_ids": ["US-001"],
        })

        # Write stories ONLY to EpicStories/
        epic_stories_dir = tmp_path / "docs" / "userstories" / "EpicStories"
        epic_stories_dir.mkdir(parents=True)
        (epic_stories_dir / "260401XX_test.yml").write_text(yaml.dump({
            "stories": [{"id": "US-001", "title": "Story 1"}],
        }))

        # Monkeypatch get_epic_stories_path in stories module
        import agenticcli.commands.stories as _stories_mod
        monkeypatch.setattr(_stories_mod, "get_epic_stories_path",
                            lambda name: epic_stories_dir / f"{name}.yml")

        args = SimpleNamespace(epic=str(epic_folder))

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                with patch("agenticcli.commands.epic.find_epic_folder",
                           return_value=epic_folder):
                    cmd_audit(args)

                result = mock_json.call_args[0][0]

        # Stories were found (not missing)
        assert result["summary"]["stories_yml_missing"] is False
        assert result["summary"]["total_stories"] == 1
        assert result["summary"]["fully_covered"] is True

        repo.close()
