"""Tests for CLI lifecycle commands: promote, deprecate, archive, code."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.story("US-STR-005")


@pytest.fixture
def story_dir(tmp_path):
    """Create a temp userstories dir with a test story."""
    stories_dir = tmp_path / "docs" / "userstories"
    stories_dir.mkdir(parents=True)
    story_file = stories_dir / "test_stories.yml"
    story_file.write_text(yaml.dump({
        "stories": [{
            "id": "US-TST-001",
            "title": "Test Story",
            "lifecycle": "proposal",
        }, {
            "id": "US-TST-002",
            "title": "Implemented Story",
            "lifecycle": "implemented",
        }]
    }))
    return stories_dir


def _make_args(command, story_id):
    return SimpleNamespace(stories_command=command, story_id=story_id)


def _patch_stories_dir(story_dir):
    return patch("agenticcli.commands.stories._find_userstories_dir", return_value=story_dir)


def _patch_json_off():
    """Patch is_json_output at the console module level to return False."""
    return patch("agenticcli.console.is_json_output", return_value=False)


def _patch_json_on():
    """Patch is_json_output at the console module level to return True."""
    return patch("agenticcli.console.is_json_output", return_value=True)


class TestPromote:
    def test_promote_proposal_to_under_construction(self, story_dir):
        from agenticcli.commands.stories import cmd_promote

        with _patch_stories_dir(story_dir), _patch_json_off():
            cmd_promote(_make_args("promote", "US-TST-001"))

        content = yaml.safe_load((story_dir / "test_stories.yml").read_text())
        story = next(s for s in content["stories"] if s["id"] == "US-TST-001")
        assert story["lifecycle"] == "under-construction"

    def test_promote_under_construction_to_implemented(self, story_dir):
        from agenticcli.commands.stories import cmd_promote

        # Set up under-construction
        story_file = story_dir / "test_stories.yml"
        content = yaml.safe_load(story_file.read_text())
        for s in content["stories"]:
            if s["id"] == "US-TST-001":
                s["lifecycle"] = "under-construction"
        story_file.write_text(yaml.dump(content))

        with _patch_stories_dir(story_dir), _patch_json_off():
            cmd_promote(_make_args("promote", "US-TST-001"))

        content = yaml.safe_load(story_file.read_text())
        story = next(s for s in content["stories"] if s["id"] == "US-TST-001")
        assert story["lifecycle"] == "implemented"

    def test_promote_implemented_fails(self, story_dir):
        from agenticcli.commands.stories import cmd_promote

        with _patch_stories_dir(story_dir), _patch_json_off():
            with pytest.raises(SystemExit):
                cmd_promote(_make_args("promote", "US-TST-002"))

    def test_promote_nonexistent_story(self, story_dir):
        from agenticcli.commands.stories import cmd_promote

        with _patch_stories_dir(story_dir), _patch_json_off():
            with pytest.raises(SystemExit):
                cmd_promote(_make_args("promote", "US-NOPE-999"))


class TestDeprecate:
    def test_deprecate_implemented(self, story_dir):
        from agenticcli.commands.stories import cmd_deprecate

        with _patch_stories_dir(story_dir), _patch_json_off():
            cmd_deprecate(_make_args("deprecate", "US-TST-002"))

        content = yaml.safe_load((story_dir / "test_stories.yml").read_text())
        story = next(s for s in content["stories"] if s["id"] == "US-TST-002")
        assert story["lifecycle"] == "deprecated"

    def test_deprecate_proposal_fails(self, story_dir):
        from agenticcli.commands.stories import cmd_deprecate

        with _patch_stories_dir(story_dir), _patch_json_off():
            with pytest.raises(SystemExit):
                cmd_deprecate(_make_args("deprecate", "US-TST-001"))


class TestArchive:
    def test_archive_deprecated(self, story_dir):
        from agenticcli.commands.stories import cmd_archive

        story_file = story_dir / "test_stories.yml"
        content = yaml.safe_load(story_file.read_text())
        for s in content["stories"]:
            if s["id"] == "US-TST-002":
                s["lifecycle"] = "deprecated"
        story_file.write_text(yaml.dump(content))

        with _patch_stories_dir(story_dir), _patch_json_off():
            cmd_archive(_make_args("archive", "US-TST-002"))

        content = yaml.safe_load(story_file.read_text())
        story = next(s for s in content["stories"] if s["id"] == "US-TST-002")
        assert story["lifecycle"] == "archived"

    def test_archive_implemented_fails(self, story_dir):
        from agenticcli.commands.stories import cmd_archive

        with _patch_stories_dir(story_dir), _patch_json_off():
            with pytest.raises(SystemExit):
                cmd_archive(_make_args("archive", "US-TST-002"))


class TestCode:
    def test_code_with_results(self, tmp_path):
        from agenticcli.commands.stories import cmd_code
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "test.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.sync_story_code({"US-TST-001": ["src/foo.py::my_func"]})
        repo.close()

        captured = {}

        def fake_print_json(data):
            captured.update(data)

        with patch("agenticcli.commands.stories._get_repo_db_path", return_value=db_path), \
             _patch_json_on(), \
             patch("agenticcli.console.print_json", side_effect=fake_print_json):
            cmd_code(SimpleNamespace(stories_command="code", story_id="US-TST-001"))

        assert captured["story_id"] == "US-TST-001"
        assert captured["count"] == 1

    def test_code_no_results(self, tmp_path):
        from agenticcli.commands.stories import cmd_code
        from agenticguidance.services.epic_repository import EpicRepository

        db_path = tmp_path / "test.db"
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.close()

        captured = {}

        def fake_print_json(data):
            captured.update(data)

        with patch("agenticcli.commands.stories._get_repo_db_path", return_value=db_path), \
             _patch_json_on(), \
             patch("agenticcli.console.print_json", side_effect=fake_print_json):
            cmd_code(SimpleNamespace(stories_command="code", story_id="US-NOPE-999"))

        assert captured["count"] == 0


class TestFullLifecycle:
    """Integration test: full lifecycle from proposal through archived."""

    def test_full_lifecycle(self, story_dir):
        from agenticcli.commands.stories import cmd_archive, cmd_deprecate, cmd_promote

        with _patch_stories_dir(story_dir), _patch_json_off():
            # proposal -> under-construction
            cmd_promote(_make_args("promote", "US-TST-001"))
            # under-construction -> implemented
            cmd_promote(_make_args("promote", "US-TST-001"))
            # implemented -> deprecated
            cmd_deprecate(_make_args("deprecate", "US-TST-001"))
            # deprecated -> archived
            cmd_archive(_make_args("archive", "US-TST-001"))

        content = yaml.safe_load((story_dir / "test_stories.yml").read_text())
        story = next(s for s in content["stories"] if s["id"] == "US-TST-001")
        assert story["lifecycle"] == "archived"
