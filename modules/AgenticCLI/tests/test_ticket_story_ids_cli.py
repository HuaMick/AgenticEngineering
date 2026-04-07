"""Tests for CLI --story-ids flag on epic ticket add/update commands (P4-T2).

Validates the --story-ids flag added to:
- agentic epic ticket add --story-ids "US-CLI-110,US-CLI-111"
- agentic epic ticket update <id> --story-ids "US-CLI-110"

Tests focus on:
- Comma-separated parsing of story IDs
- TinyDB persistence of story_ids via CLI commands
- JSON output includes story_ids
- story_ids appears in update output
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agenticguidance.services.epic_repository import EpicRepository

pytestmark = pytest.mark.story("US-STR-011")


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def epic_repo(tmp_path, _isolate_tinydb):
    """Create an epic with a phase in the isolated TinyDB for testing."""
    db_path = _isolate_tinydb
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    epic_folder = tmp_path / "docs" / "epics" / "live" / "260308PD_test"
    epic_folder.mkdir(parents=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    repo.create_epic({
        "epic_folder_name": "260308PD_test",
        "epic_folder": str(epic_folder),
        "name": "Test Epic",
        "status": "planning",
    })
    repo.add_phase("260308PD_test", {
        "name": "Build Phase",
        "status": "pending",
    })

    yield {
        "repo": repo,
        "db_path": db_path,
        "epic_folder": epic_folder,
        "epic_folder_name": "260308PD_test",
        "phase_name": "Build Phase",
    }

    repo.close()


# ---------------------------------------------------------------------------
# Tests for cmd_task_add with --story-ids
# ---------------------------------------------------------------------------

@pytest.mark.story("US-STR-011")
class TestCmdTaskAddStoryIds:
    """Test cmd_task_add correctly handles the --story-ids flag."""

    def test_add_ticket_with_story_ids(self, epic_repo, tmp_path):
        """Verify adding a ticket with --story-ids persists the IDs."""
        from agenticcli.commands.epic import cmd_task_add

        args = SimpleNamespace(
            description="Build the feature",
            plan=str(epic_repo["epic_folder"]),
            phase="Build Phase",
            id="T1",
            priority="medium",
            agent="build-python",
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids="US-CLI-110,US-CLI-111",
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                cmd_task_add(args)
                mock_json.assert_called_once()
                result = mock_json.call_args[0][0]
                assert result["story_ids"] == ["US-CLI-110", "US-CLI-111"]
                assert result["task_id"] == "T1"

        # Verify persistence in TinyDB
        ticket = epic_repo["repo"].get_ticket("260308PD_test", "T1")
        assert ticket is not None
        assert ticket.story_ids == ["US-CLI-110", "US-CLI-111"]

    def test_add_ticket_without_story_ids(self, epic_repo, tmp_path):
        """Verify adding a ticket without --story-ids defaults to empty list."""
        from agenticcli.commands.epic import cmd_task_add

        args = SimpleNamespace(
            description="Simple task",
            plan=str(epic_repo["epic_folder"]),
            phase="Build Phase",
            id="T2",
            priority="medium",
            agent=None,
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                cmd_task_add(args)
                result = mock_json.call_args[0][0]
                assert result["story_ids"] == []

        # Verify persistence
        ticket = epic_repo["repo"].get_ticket("260308PD_test", "T2")
        assert ticket is not None
        assert ticket.story_ids == []

    def test_add_ticket_story_ids_whitespace_stripped(self, epic_repo, tmp_path):
        """Verify whitespace around story IDs is stripped."""
        from agenticcli.commands.epic import cmd_task_add

        args = SimpleNamespace(
            description="Whitespace test",
            plan=str(epic_repo["epic_folder"]),
            phase="Build Phase",
            id="T3",
            priority="medium",
            agent=None,
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids=" US-CLI-110 , US-CLI-111 ",
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                cmd_task_add(args)
                result = mock_json.call_args[0][0]
                assert result["story_ids"] == ["US-CLI-110", "US-CLI-111"]

    def test_add_ticket_single_story_id(self, epic_repo, tmp_path):
        """Verify single story ID (no comma) works correctly."""
        from agenticcli.commands.epic import cmd_task_add

        args = SimpleNamespace(
            description="Single story",
            plan=str(epic_repo["epic_folder"]),
            phase="Build Phase",
            id="T4",
            priority="medium",
            agent=None,
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids="US-ORCH-001",
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                cmd_task_add(args)
                result = mock_json.call_args[0][0]
                assert result["story_ids"] == ["US-ORCH-001"]


# ---------------------------------------------------------------------------
# Tests for cmd_task_update with --story-ids
# ---------------------------------------------------------------------------

@pytest.mark.story("US-STR-011")
class TestCmdTaskUpdateStoryIds:
    """Test cmd_task_update correctly handles the --story-ids flag."""

    def _create_ticket(self, epic_repo):
        """Create a ticket to update."""
        epic_repo["repo"].add_ticket(
            epic_repo["epic_folder_name"],
            epic_repo["phase_name"],
            {
                "id": "T1",
                "name": "Original task",
                "description": "Original description",
                "status": "proposed",
            },
        )

    def test_update_ticket_with_story_ids(self, epic_repo, tmp_path):
        """Verify updating a ticket with --story-ids persists new IDs."""
        from agenticcli.commands.epic import cmd_task_update

        self._create_ticket(epic_repo)

        args = SimpleNamespace(
            task_id="T1",
            plan=str(epic_repo["epic_folder"]),
            status=None,
            note=None,
            description=None,
            name=None,
            agent=None,
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids="US-CLI-110,US-CLI-111",
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                cmd_task_update(args)
                result = mock_json.call_args[0][0]
                assert result["story_ids"] == ["US-CLI-110", "US-CLI-111"]

        # Verify persistence
        ticket = epic_repo["repo"].get_ticket("260308PD_test", "T1")
        assert ticket is not None
        assert ticket.story_ids == ["US-CLI-110", "US-CLI-111"]

    def test_update_ticket_story_ids_only(self, epic_repo, tmp_path):
        """Verify --story-ids alone is sufficient update (no other fields required)."""
        from agenticcli.commands.epic import cmd_task_update

        self._create_ticket(epic_repo)

        args = SimpleNamespace(
            task_id="T1",
            plan=str(epic_repo["epic_folder"]),
            status=None,
            note=None,
            description=None,
            name=None,
            agent=None,
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids="US-CLI-110",
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                cmd_task_update(args)
                # Should not fail — story_ids alone counts as a valid update
                mock_json.assert_called_once()
                result = mock_json.call_args[0][0]
                assert result["task_id"] == "T1"

    def test_update_ticket_no_fields_raises(self, epic_repo, tmp_path):
        """Verify update with no fields at all raises error."""
        from agenticcli.commands.epic import cmd_task_update

        self._create_ticket(epic_repo)

        args = SimpleNamespace(
            task_id="T1",
            plan=str(epic_repo["epic_folder"]),
            status=None,
            note=None,
            description=None,
            name=None,
            agent=None,
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with pytest.raises(SystemExit) as exc_info:
                cmd_task_update(args)
            assert exc_info.value.code == 1

    def test_update_ticket_story_ids_whitespace_stripped(self, epic_repo, tmp_path):
        """Verify whitespace around story IDs is stripped in update."""
        from agenticcli.commands.epic import cmd_task_update

        self._create_ticket(epic_repo)

        args = SimpleNamespace(
            task_id="T1",
            plan=str(epic_repo["epic_folder"]),
            status=None,
            note=None,
            description=None,
            name=None,
            agent=None,
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids=" US-GD-001 , US-GD-002 ",
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json"):
                cmd_task_update(args)

        ticket = epic_repo["repo"].get_ticket("260308PD_test", "T1")
        assert ticket.story_ids == ["US-GD-001", "US-GD-002"]

    def test_update_ticket_story_ids_in_text_output(self, epic_repo, tmp_path):
        """Verify story_ids appears in text mode output."""
        from agenticcli.commands.epic import cmd_task_update

        self._create_ticket(epic_repo)

        args = SimpleNamespace(
            task_id="T1",
            plan=str(epic_repo["epic_folder"]),
            status=None,
            note=None,
            description=None,
            name=None,
            agent=None,
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids="US-CLI-110,US-CLI-111",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("agenticcli.console.print_success") as mock_success:
                cmd_task_update(args)

        mock_success.assert_called_once()
        call_msg = mock_success.call_args[0][0]
        assert "story_ids" in call_msg


# ---------------------------------------------------------------------------
# Tests for build-plan story_ids enforcement (TS_002)
# ---------------------------------------------------------------------------

@pytest.fixture
def build_epic_repo(tmp_path, _isolate_tinydb):
    """Create a build-plan epic (phase with build-python agent) for enforcement tests."""
    db_path = _isolate_tinydb
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    epic_folder = tmp_path / "docs" / "epics" / "live" / "260327XX_build_epic"
    epic_folder.mkdir(parents=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    repo.create_epic({
        "epic_folder_name": "260327XX_build_epic",
        "epic_folder": str(epic_folder),
        "name": "Build Epic",
        "status": "planning",
    })
    repo.add_phase("260327XX_build_epic", {
        "name": "Build Phase",
        "agent": "build-python",
        "status": "pending",
    })

    yield {
        "repo": repo,
        "db_path": db_path,
        "epic_folder": epic_folder,
        "epic_folder_name": "260327XX_build_epic",
        "phase_name": "Build Phase",
    }

    repo.close()


@pytest.fixture
def infra_epic_repo(tmp_path, _isolate_tinydb):
    """Create an infra/guidance epic (phase with teacher agent) for bypass tests."""
    db_path = _isolate_tinydb
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    epic_folder = tmp_path / "docs" / "epics" / "live" / "260327XX_infra_epic"
    epic_folder.mkdir(parents=True)
    (tmp_path / ".git").mkdir(exist_ok=True)

    repo.create_epic({
        "epic_folder_name": "260327XX_infra_epic",
        "epic_folder": str(epic_folder),
        "name": "Infra Epic",
        "status": "planning",
    })
    repo.add_phase("260327XX_infra_epic", {
        "name": "Guidance Phase",
        "agent": "teacher-update-guidance",
        "status": "pending",
    })

    yield {
        "repo": repo,
        "db_path": db_path,
        "epic_folder": epic_folder,
        "epic_folder_name": "260327XX_infra_epic",
        "phase_name": "Guidance Phase",
    }

    repo.close()


@pytest.mark.story("US-STR-011")
class TestStoryIdsEnforcement:
    """Test cmd_task_add enforcement: build-plan tickets require --story-ids."""

    def test_build_plan_rejects_without_story_ids(self, build_epic_repo):
        """Build-plan epic + ticket add without --story-ids → sys.exit(1)."""
        from agenticcli.commands.epic import cmd_task_add

        args = SimpleNamespace(
            description="Feature without stories",
            plan=str(build_epic_repo["epic_folder"]),
            phase="Build Phase",
            id="T1",
            priority="medium",
            agent="build-python",
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("agenticcli.console.print_error") as mock_error:
                with pytest.raises(SystemExit) as exc_info:
                    cmd_task_add(args)
                assert exc_info.value.code == 1
                mock_error.assert_called_once()
                error_msg = mock_error.call_args[0][0]
                assert "story_ids" in error_msg.lower() or "--story-ids" in error_msg
                assert "build" in error_msg.lower()

    def test_build_plan_succeeds_with_story_ids(self, build_epic_repo):
        """Build-plan epic + ticket add WITH --story-ids → success."""
        from agenticcli.commands.epic import cmd_task_add

        args = SimpleNamespace(
            description="Feature with stories",
            plan=str(build_epic_repo["epic_folder"]),
            phase="Build Phase",
            id="T1",
            priority="medium",
            agent="build-python",
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids="US-PLN-073,US-STR-011",
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                cmd_task_add(args)
                mock_json.assert_called_once()
                result = mock_json.call_args[0][0]
                assert result["story_ids"] == ["US-PLN-073", "US-STR-011"]
                assert result["task_id"] == "T1"

        # Verify persistence
        ticket = build_epic_repo["repo"].get_ticket("260327XX_build_epic", "T1")
        assert ticket is not None
        assert ticket.story_ids == ["US-PLN-073", "US-STR-011"]

    def test_infra_epic_bypasses_without_story_ids(self, infra_epic_repo):
        """Infra/guidance epic + ticket add without --story-ids → success (bypass)."""
        from agenticcli.commands.epic import cmd_task_add

        args = SimpleNamespace(
            description="Guidance task no stories",
            plan=str(infra_epic_repo["epic_folder"]),
            phase="Guidance Phase",
            id="T1",
            priority="medium",
            agent="teacher-update-guidance",
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            with patch("agenticcli.console.print_json") as mock_json:
                cmd_task_add(args)
                mock_json.assert_called_once()
                result = mock_json.call_args[0][0]
                assert result["story_ids"] == []
                assert result["task_id"] == "T1"

    def test_build_plan_error_message_mentions_story_ids_flag(self, build_epic_repo):
        """Error message should mention --story-ids and build-plan."""
        from agenticcli.commands.epic import cmd_task_add

        args = SimpleNamespace(
            description="Another feature",
            plan=str(build_epic_repo["epic_folder"]),
            phase="Build Phase",
            id="T2",
            priority="medium",
            agent=None,
            target_files=None,
            success_criteria=None,
            guidance=None,
            inputs=None,
            story_ids=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("agenticcli.console.print_error") as mock_error:
                with pytest.raises(SystemExit):
                    cmd_task_add(args)
                error_msg = mock_error.call_args[0][0]
                assert "--story-ids" in error_msg
                assert "build" in error_msg.lower()
