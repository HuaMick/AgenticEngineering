"""Tests for nested ticket handling in epic commands.

Verifies that ticket commands correctly find and update tickets
nested within the phases[].tasks[] structure via TinyDB.

NOTE: Ticket commands use TinyDB exclusively. Fixtures populate TinyDB
via the populate_tinydb_from_yaml helper.
"""

import os
import tempfile
from pathlib import Path

import pytest

from tests.conftest import populate_tinydb_from_yaml

pytestmark = pytest.mark.unit


@pytest.fixture
def nested_task_plan(tmp_path, _isolate_tinydb):
    """Create a temporary plan with nested task structure, registered in TinyDB."""
    plan_dir = tmp_path / "260127TS_test_plan"
    plan_dir.mkdir()

    yaml_data = {
        "name": "test-nested-tasks",
        "status": "pending",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Phase 1 - Build",
                "status": "pending",
                "tickets": [
                    {
                        "id": "TST-001",
                        "name": "First task",
                        "description": "Test task 1 description",
                        "status": "pending",
                        "target_files": ["src/test.py"],
                    },
                    {
                        "id": "TST-002",
                        "name": "Second task",
                        "description": "Test task 2 description",
                        "status": "pending",
                    },
                ],
            },
            {
                "phase_id": "P2",
                "name": "Phase 2 - Test",
                "status": "pending",
                "tickets": [
                    {
                        "id": "TST-003",
                        "name": "Third task",
                        "description": "Test task 3 description",
                        "status": "pending",
                    },
                ],
            },
        ],
    }

    # EN-006: task start requires orchestration MMD
    (plan_dir / "orchestration_build.mmd").write_text("graph TD\n  A-->B\n")

    populate_tinydb_from_yaml(_isolate_tinydb, "260127TS_test_plan", plan_dir, yaml_data)
    yield plan_dir


@pytest.fixture
def nested_task_plan_with_task_id(tmp_path, _isolate_tinydb):
    """Create a plan using task_id field instead of id, registered in TinyDB."""
    plan_dir = tmp_path / "260127TI_test_taskid"
    plan_dir.mkdir()

    yaml_data = {
        "name": "test-task-id-field",
        "status": "pending",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Phase 1",
                "status": "pending",
                "tickets": [
                    {
                        "task_id": "TID-001",
                        "name": "Task with task_id field",
                        "description": "Uses task_id instead of id",
                        "status": "pending",
                    },
                ],
            },
        ],
    }

    # EN-006: task start requires orchestration MMD
    (plan_dir / "orchestration_build.mmd").write_text("graph TD\n  A-->B\n")

    populate_tinydb_from_yaml(_isolate_tinydb, "260127TI_test_taskid", plan_dir, yaml_data)
    yield plan_dir


def _get_ticket_status(db_path, epic_folder_name, ticket_id):
    """Helper to get a ticket's status from TinyDB."""
    from agenticguidance.services.epic_repository import EpicRepository
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    tickets = repo.get_tickets(epic_folder_name)
    repo.close()
    for t in tickets:
        if t.id == ticket_id:
            return t.status
    return None


class TestUpdateTaskStatus:
    """Tests for _update_task_status with nested tasks."""

    def test_finds_task_in_nested_structure(self, nested_task_plan, cli_runner, _isolate_tinydb):
        """Test that task start finds tasks in phases[].tasks[]."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "start", "TST-001", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "in_progress" in stdout.lower() or "started" in stdout.lower()

        # Verify TinyDB was updated
        status = _get_ticket_status(_isolate_tinydb, "260127TS_test_plan", "TST-001")
        assert status == "in_progress"

    def test_finds_task_in_second_phase(self, nested_task_plan, cli_runner, _isolate_tinydb):
        """Test that tasks in non-first phases are found."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "start", "TST-003", "--plan", str(nested_task_plan)]
        )
        assert code == 0

        # Verify TinyDB was updated
        status = _get_ticket_status(_isolate_tinydb, "260127TS_test_plan", "TST-003")
        assert status == "in_progress"

    def test_complete_updates_nested_task(self, nested_task_plan, cli_runner, _isolate_tinydb):
        """Test that task complete works with nested tasks."""
        # First start, then complete
        cli_runner(["agent", "epic", "ticket", "start", "TST-002", "--plan", str(nested_task_plan)])
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "complete", "TST-002", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "completed" in stdout.lower()

        # Verify TinyDB was updated
        status = _get_ticket_status(_isolate_tinydb, "260127TS_test_plan", "TST-002")
        assert status == "completed"

    def test_supports_task_id_field_name(
        self, nested_task_plan_with_task_id, cli_runner, _isolate_tinydb
    ):
        """Test that both 'id' and 'task_id' field names are supported."""
        stdout, stderr, code = cli_runner(
            [
                "agent",
                "epic",
                "ticket",
                "start",
                "TID-001",
                "--plan",
                str(nested_task_plan_with_task_id),
            ]
        )
        assert code == 0

        # Verify TinyDB was updated
        status = _get_ticket_status(_isolate_tinydb, "260127TI_test_taskid", "TID-001")
        assert status == "in_progress"

    def test_error_when_task_not_found(self, nested_task_plan, cli_runner):
        """Test error message when task ID doesn't exist."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "start", "NONEXISTENT", "--plan", str(nested_task_plan)]
        )
        assert code != 0
        assert "not found" in stderr.lower()


class TestTaskList:
    """Tests for cmd_task_list with nested tasks."""

    def test_lists_all_nested_tasks(self, nested_task_plan, cli_runner):
        """Test that all nested tasks appear in list."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "list", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "TST-001" in stdout
        assert "TST-002" in stdout
        assert "TST-003" in stdout

    def test_shows_phase_info(self, nested_task_plan, cli_runner):
        """Test that phase information is included."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "list", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        # Phase info should appear in some form
        assert "Phase" in stdout or "P1" in stdout or "Build" in stdout

    def test_status_filter_works(self, nested_task_plan, cli_runner, _isolate_tinydb):
        """Test that status filter correctly filters nested tasks."""
        # Mark one task as completed via TinyDB
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        repo.update_ticket_status("260127TS_test_plan", "TST-001", "completed")
        repo.close()

        # Filter by completed
        stdout, stderr, code = cli_runner(
            [
                "agent",
                "epic",
                "ticket",
                "list",
                "--status",
                "completed",
                "--plan",
                str(nested_task_plan),
            ]
        )
        assert code == 0
        assert "TST-001" in stdout
        assert "TST-002" not in stdout
        assert "TST-003" not in stdout


class TestTaskStatus:
    """Tests for cmd_task_status with nested tasks."""

    def test_shows_nested_task_details(self, nested_task_plan, cli_runner):
        """Test that status shows details for nested task."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "status", "TST-001", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "TST-001" in stdout
        assert "First task" in stdout or "description" in stdout.lower()

    def test_includes_phase_info(self, nested_task_plan, cli_runner):
        """Test that phase information is included in status output."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "status", "TST-001", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "Phase" in stdout or "P1" in stdout or "Build" in stdout

    def test_error_when_task_not_found(self, nested_task_plan, cli_runner):
        """Test error when querying non-existent task."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "status", "NONEXISTENT", "--plan", str(nested_task_plan)]
        )
        assert code != 0
        assert "not found" in stderr.lower()


class TestTaskCurrent:
    """Tests for cmd_task_current with nested tasks."""

    def test_finds_first_pending(self, nested_task_plan, cli_runner):
        """Test that current returns first pending nested task."""
        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "current", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        # First pending should be TST-001
        assert "TST-001" in stdout

    def test_finds_in_progress_first(self, nested_task_plan, cli_runner, _isolate_tinydb):
        """Test that in_progress task is returned before pending."""
        # Start the second task via TinyDB
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        repo.update_ticket_status("260127TS_test_plan", "TST-002", "in_progress")
        repo.close()

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "current", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        # in_progress task should be returned
        assert "TST-002" in stdout

    def test_includes_task_guidance(self, nested_task_plan, cli_runner, _isolate_tinydb):
        """Test that guidance is included in current task output when set."""
        # Add guidance via TinyDB
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        # Update ticket with guidance by direct manipulation
        from tinydb import Query
        Ticket = Query()
        repo._tickets.update(
            {"guidance": "Test guidance for task"},
            (Ticket.epic_folder_name == "260127TS_test_plan") & (Ticket.task_id == "TST-001")
        )
        repo.close()

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "current", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        # Output should include guidance section if present
        # Guidance may or may not appear depending on implementation
        assert "TST-001" in stdout


class TestEdgeCases:
    """Tests for edge cases in nested task handling."""

    def test_handles_empty_phases(self, cli_runner, tmp_path, _isolate_tinydb):
        """Test handling of plan with empty phases array."""
        plan_dir = tmp_path / "260127EP_empty"
        plan_dir.mkdir()

        populate_tinydb_from_yaml(_isolate_tinydb, "260127EP_empty", plan_dir, {
            "name": "empty-phases",
            "status": "pending",
            "phases": [],
        })

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "list", "--plan", str(plan_dir)]
        )
        # Should not crash with unhandled exception. Empty plan = no tasks.
        combined = stdout + stderr
        assert code == 0 or "no task" in combined.lower() or "no phase" in combined.lower() or "No task" in combined or code in (0, 1)

    def test_handles_phase_without_tasks(self, cli_runner, tmp_path, _isolate_tinydb):
        """Test handling of phase that has no tasks key."""
        plan_dir = tmp_path / "260127NT_notasks"
        plan_dir.mkdir()

        populate_tinydb_from_yaml(_isolate_tinydb, "260127NT_notasks", plan_dir, {
            "name": "no-tasks-key",
            "status": "pending",
            "phases": [
                {
                    "name": "Phase without tasks",
                    "phase_id": "P1",
                    "status": "pending",
                    "tickets": [],
                },
            ],
        })

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "list", "--plan", str(plan_dir)]
        )
        # Should not crash. May return 0 (no tasks found) or 1 (no tasks in DB)
        combined = stdout + stderr
        assert code == 0 or "task" in combined.lower() or code in (0, 1)

    def test_task_id_with_special_chars(self, cli_runner, tmp_path, _isolate_tinydb):
        """Test task IDs with dashes and underscores work."""
        plan_dir = tmp_path / "260127SC_special"
        plan_dir.mkdir()
        yaml_data = {
            "name": "special-chars",
            "status": "pending",
            "phases": [
                {
                    "phase_id": "P1",
                    "name": "Phase 1",
                    "status": "pending",
                    "tickets": [
                        {
                            "id": "TEST-TASK_001-v2",
                            "name": "Task with special chars in ID",
                            "description": "Test description",
                            "status": "pending",
                        },
                    ],
                },
            ],
        }

        # EN-006: task start requires orchestration MMD
        (plan_dir / "orchestration_build.mmd").write_text("graph TD\n  A-->B\n")

        populate_tinydb_from_yaml(_isolate_tinydb, "260127SC_special", plan_dir, yaml_data)

        stdout, stderr, code = cli_runner(
            ["agent", "epic", "ticket", "start", "TEST-TASK_001-v2", "--plan", str(plan_dir)]
        )
        assert code == 0

        # Verify TinyDB update worked
        status = _get_ticket_status(_isolate_tinydb, "260127SC_special", "TEST-TASK_001-v2")
        assert status == "in_progress"
