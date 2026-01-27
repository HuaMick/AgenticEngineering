"""Tests for nested task handling in plan commands.

Verifies that task commands correctly find and update tasks
nested within the phases[].tasks[] structure.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit


@pytest.fixture
def nested_task_plan():
    """Create a temporary plan with nested task structure."""
    plan_content = {
        "name": "test-nested-tasks",
        "status": "pending",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Phase 1 - Build",
                "status": "pending",
                "tasks": [
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
                "tasks": [
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

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260127TS_test_plan"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        yield plan_dir


@pytest.fixture
def nested_task_plan_with_task_id():
    """Create a plan using task_id field instead of id."""
    plan_content = {
        "name": "test-task-id-field",
        "status": "pending",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Phase 1",
                "status": "pending",
                "tasks": [
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

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260127TI_test_taskid"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        yield plan_dir


class TestUpdateTaskStatus:
    """Tests for _update_task_status with nested tasks."""

    def test_finds_task_in_nested_structure(self, nested_task_plan, cli_runner):
        """Test that task start finds tasks in phases[].tasks[]."""
        stdout, stderr, code = cli_runner(
            ["plan", "task", "start", "TST-001", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "in_progress" in stdout.lower() or "started" in stdout.lower()

        # Verify YAML was updated
        plan_file = nested_task_plan / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        task = data["phases"][0]["tasks"][0]
        assert task["status"] == "in_progress"

    def test_finds_task_in_second_phase(self, nested_task_plan, cli_runner):
        """Test that tasks in non-first phases are found."""
        stdout, stderr, code = cli_runner(
            ["plan", "task", "start", "TST-003", "--plan", str(nested_task_plan)]
        )
        assert code == 0

        # Verify YAML was updated
        plan_file = nested_task_plan / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        task = data["phases"][1]["tasks"][0]
        assert task["status"] == "in_progress"

    def test_complete_updates_nested_task(self, nested_task_plan, cli_runner):
        """Test that task complete works with nested tasks."""
        # First start, then complete
        cli_runner(["plan", "task", "start", "TST-002", "--plan", str(nested_task_plan)])
        stdout, stderr, code = cli_runner(
            ["plan", "task", "complete", "TST-002", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "completed" in stdout.lower()

        # Verify YAML was updated
        plan_file = nested_task_plan / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        task = data["phases"][0]["tasks"][1]
        assert task["status"] == "completed"

    def test_supports_task_id_field_name(
        self, nested_task_plan_with_task_id, cli_runner
    ):
        """Test that both 'id' and 'task_id' field names are supported."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "task",
                "start",
                "TID-001",
                "--plan",
                str(nested_task_plan_with_task_id),
            ]
        )
        assert code == 0

        plan_file = nested_task_plan_with_task_id / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        task = data["phases"][0]["tasks"][0]
        assert task["status"] == "in_progress"

    def test_error_when_task_not_found(self, nested_task_plan, cli_runner):
        """Test error message when task ID doesn't exist."""
        stdout, stderr, code = cli_runner(
            ["plan", "task", "start", "NONEXISTENT", "--plan", str(nested_task_plan)]
        )
        assert code != 0
        assert "not found" in stderr.lower()


class TestTaskList:
    """Tests for cmd_task_list with nested tasks."""

    def test_lists_all_nested_tasks(self, nested_task_plan, cli_runner):
        """Test that all nested tasks appear in list."""
        stdout, stderr, code = cli_runner(
            ["plan", "task", "list", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "TST-001" in stdout
        assert "TST-002" in stdout
        assert "TST-003" in stdout

    def test_shows_phase_info(self, nested_task_plan, cli_runner):
        """Test that phase information is included."""
        stdout, stderr, code = cli_runner(
            ["plan", "task", "list", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "P1" in stdout or "P2" in stdout

    def test_status_filter_works(self, nested_task_plan, cli_runner):
        """Test that status filter correctly filters nested tasks."""
        # Mark one task as completed
        cli_runner(
            ["plan", "task", "complete", "TST-001", "--plan", str(nested_task_plan)]
        )

        # Filter by completed
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "task",
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
            ["plan", "task", "status", "TST-001", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "TST-001" in stdout
        assert "First task" in stdout or "description" in stdout.lower()

    def test_includes_phase_info(self, nested_task_plan, cli_runner):
        """Test that phase information is included in status output."""
        stdout, stderr, code = cli_runner(
            ["plan", "task", "status", "TST-001", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        assert "Phase" in stdout or "P1" in stdout

    def test_error_when_task_not_found(self, nested_task_plan, cli_runner):
        """Test error when querying non-existent task."""
        stdout, stderr, code = cli_runner(
            ["plan", "task", "status", "NONEXISTENT", "--plan", str(nested_task_plan)]
        )
        assert code != 0
        assert "not found" in stderr.lower()


class TestTaskCurrent:
    """Tests for cmd_task_current with nested tasks."""

    def test_finds_first_pending(self, nested_task_plan, cli_runner):
        """Test that current returns first pending nested task."""
        stdout, stderr, code = cli_runner(
            ["plan", "task", "current", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        # First pending should be TST-001
        assert "TST-001" in stdout

    def test_finds_in_progress_first(self, nested_task_plan, cli_runner):
        """Test that in_progress task is returned before pending."""
        # Start the second task
        cli_runner(
            ["plan", "task", "start", "TST-002", "--plan", str(nested_task_plan)]
        )

        stdout, stderr, code = cli_runner(
            ["plan", "task", "current", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        # in_progress task should be returned
        assert "TST-002" in stdout

    def test_includes_task_guidance(self, nested_task_plan, cli_runner):
        """Test that guidance is included in current task output."""
        # Add guidance to the plan
        plan_file = nested_task_plan / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        data["phases"][0]["tasks"][0]["guidance"] = "Test guidance for task"
        with open(plan_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        stdout, stderr, code = cli_runner(
            ["plan", "task", "current", "--plan", str(nested_task_plan)]
        )
        assert code == 0
        # Output should include guidance section
        assert "Guidance" in stdout or "guidance" in stdout.lower()


class TestEdgeCases:
    """Tests for edge cases in nested task handling."""

    def test_handles_empty_phases(self, cli_runner):
        """Test handling of plan with empty phases array."""
        plan_content = {
            "name": "empty-phases",
            "status": "pending",
            "phases": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260127EP_empty"
            plan_dir.mkdir()
            plan_file = plan_dir / "plan_build.yml"
            with open(plan_file, "w") as f:
                yaml.dump(plan_content, f, default_flow_style=False)

            stdout, stderr, code = cli_runner(
                ["plan", "task", "list", "--plan", str(plan_dir)]
            )
            # Should not crash, just show no tasks
            assert code == 0 or "no tasks" in stdout.lower()

    def test_handles_phase_without_tasks(self, cli_runner):
        """Test handling of phase that has no tasks key."""
        plan_content = {
            "name": "no-tasks-key",
            "status": "pending",
            "phases": [
                {
                    "phase_id": "P1",
                    "name": "Phase without tasks",
                    "status": "pending",
                    # No 'tasks' key
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260127NT_notasks"
            plan_dir.mkdir()
            plan_file = plan_dir / "plan_build.yml"
            with open(plan_file, "w") as f:
                yaml.dump(plan_content, f, default_flow_style=False)

            stdout, stderr, code = cli_runner(
                ["plan", "task", "list", "--plan", str(plan_dir)]
            )
            # Should not crash
            assert code == 0 or "no tasks" in stdout.lower()

    def test_task_id_with_special_chars(self, cli_runner):
        """Test task IDs with dashes and underscores work."""
        plan_content = {
            "name": "special-chars",
            "status": "pending",
            "phases": [
                {
                    "phase_id": "P1",
                    "name": "Phase 1",
                    "status": "pending",
                    "tasks": [
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

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260127SC_special"
            plan_dir.mkdir()
            plan_file = plan_dir / "plan_build.yml"
            with open(plan_file, "w") as f:
                yaml.dump(plan_content, f, default_flow_style=False)

            stdout, stderr, code = cli_runner(
                ["plan", "task", "start", "TEST-TASK_001-v2", "--plan", str(plan_dir)]
            )
            assert code == 0

            # Verify update worked
            data = yaml.safe_load(plan_file.read_text())
            assert data["phases"][0]["tasks"][0]["status"] == "in_progress"
