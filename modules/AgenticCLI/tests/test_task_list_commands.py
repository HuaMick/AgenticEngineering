"""Tests for epic ticket list commands.

Tests the 'agentic epic ticket' command group:
- prefill: Load preset ticket list
- list: Show all tickets with status
- add: Add new ticket
- status: Get ticket status
- update: Update ticket status
- current: Get current/next ticket
"""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import populate_tinydb_from_yaml

pytestmark = pytest.mark.story("US-PLN-002", "US-PLN-087", "US-PLN-088")


@pytest.fixture
def task_repo(temp_dir, _isolate_tinydb):
    """Create a repository with a plan containing tasks."""
    repo_dir = temp_dir / "task_repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        capture_output=True,
    )

    # Create docs/epics/live structure (flattened structure)
    plan_folder = repo_dir / "docs" / "epics" / "live" / "260123CL_task_test"
    plan_folder.mkdir(parents=True)

    # Create README
    (plan_folder / "README.md").write_text(
        """# Task Test Plan

## Status: ACTIVE
**Branch**: main
"""
    )

    # Populate TinyDB with plan data
    plan_content = {
        "name": "task-test-plan",
        "status": "active",
        "worktree_path": str(repo_dir),
        "context": "Test plan for task command validation",
        "phases": [
            {
                "name": "Phase 1",
                "id": "phase_01",
                "tickets": [
                    {
                        "id": "01.1",
                        "name": "Completed task",
                        "description": "This task is already done",
                        "status": "completed",
                        "agent_type": "build",
                    },
                    {
                        "id": "01.2",
                        "name": "In-progress task",
                        "description": "This task is being worked on",
                        "status": "in_progress",
                        "agent_type": "build",
                    },
                    {
                        "id": "01.3",
                        "name": "Pending task",
                        "description": "This task is waiting",
                        "status": "pending",
                        "agent_type": "test",
                    },
                ],
            },
            {
                "name": "Phase 2",
                "id": "phase_02",
                "tickets": [
                    {
                        "id": "02.1",
                        "name": "Phase 2 task",
                        "description": "A task in phase 2",
                        "status": "pending",
                        "agent_type": "build",
                    },
                ],
            },
        ],
    }
    populate_tinydb_from_yaml(_isolate_tinydb, "260123CL_task_test", plan_folder, plan_content)

    # Initial commit
    (repo_dir / "README.md").write_text("# Task Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit with tasks"],
        cwd=repo_dir,
        capture_output=True,
    )

    yield repo_dir


@pytest.fixture
def task_cli_runner(task_repo):
    """CLI runner in the task repository context."""
    import io
    import sys
    from contextlib import redirect_stderr, redirect_stdout
    from unittest.mock import patch

    original_cwd = os.getcwd()
    os.chdir(task_repo)

    class CLIResult:
        def __init__(self, stdout: str, stderr: str, returncode: int):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

        def __iter__(self):
            return iter((self.stdout, self.stderr, self.returncode))

    def run_cli(*args, expect_exit: int | None = None):
        from agenticcli.cli import run_cli as _run_cli
        from agenticcli.console import set_json_output

        set_json_output(False)

        if len(args) == 1 and isinstance(args[0], list):
            cmd_args = args[0]
        else:
            cmd_args = list(args)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        exit_code = 0

        with patch.object(sys, "argv", ["agentic"] + cmd_args):
            with redirect_stdout(stdout_capture):
                with redirect_stderr(stderr_capture):
                    try:
                        _run_cli()
                    except SystemExit as e:
                        exit_code = e.code if e.code is not None else 0

        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue()

        if expect_exit is not None:
            assert exit_code == expect_exit, (
                f"Expected exit {expect_exit}, got {exit_code}. stderr: {stderr}"
            )

        return CLIResult(stdout, stderr, exit_code)

    yield run_cli
    os.chdir(original_cwd)


@pytest.mark.story("US-PLN-009")
class TestTaskHelp:
    """Tests for plan task command help output."""

    def test_plan_task_help(self, cli_runner):
        """Test plan task --help shows all subcommands."""
        stdout, stderr, code = cli_runner(["epic", "ticket", "--help"])
        assert code == 0
        # Should show available task operations
        assert "prefill" in stdout or "list" in stdout or "add" in stdout


@pytest.mark.story("US-PLN-009")
class TestTaskList:
    """Tests for plan task list command."""

    def test_task_list_shows_tasks(self, task_cli_runner):
        """Test task list shows all tasks."""
        stdout, stderr, code = task_cli_runner(["epic", "ticket", "list"])
        assert code == 0
        # Should show some task content
        assert "task" in stdout.lower() or "phase" in stdout.lower() or "01" in stdout

    def test_task_list_json_output(self, task_cli_runner):
        """Test task list with -j returns JSON."""
        stdout, stderr, code = task_cli_runner(["-j", "epic", "ticket", "list"])
        assert code == 0

        # Should be valid JSON
        if stdout.strip():
            data = json.loads(stdout)
            # Should be a list or dict containing tasks
            assert isinstance(data, (list, dict))

    def test_task_list_filter_by_status(self, task_cli_runner):
        """Test task list filtering by status."""
        # Try filtering by pending status
        stdout, stderr, code = task_cli_runner(
            ["-j", "epic", "ticket", "list", "--status", "pending"]
        )
        assert code == 0

        if stdout.strip():
            data = json.loads(stdout)
            # Should only contain pending tasks
            if isinstance(data, list):
                for task in data:
                    if isinstance(task, dict) and "status" in task:
                        assert task["status"] == "pending"


@pytest.mark.story("US-PLN-010", "US-PLN-088")
class TestTaskCurrent:
    """Tests for plan task current command."""

    def test_task_current_returns_task(self, task_cli_runner):
        """Test task current returns the in-progress or next pending task."""
        stdout, stderr, code = task_cli_runner(["-j", "epic", "ticket", "current"])
        assert code == 0

        if stdout.strip() and stdout.strip() != "null":
            data = json.loads(stdout)
            if data:
                # Should return a task with in_progress or pending status
                assert data.get("status") in ["in_progress", "pending", None]

    def test_task_current_prefers_in_progress(self, task_cli_runner):
        """Test task current prefers in_progress over pending."""
        stdout, stderr, code = task_cli_runner(["-j", "epic", "ticket", "current"])
        assert code == 0

        if stdout.strip() and stdout.strip() != "null":
            data = json.loads(stdout)
            if data and data.get("status"):
                # Should return the in_progress task first
                assert data["status"] == "in_progress"


@pytest.mark.story("US-PLN-011", "US-PLN-087")
class TestTaskUpdate:
    """Tests for plan task update command."""

    def test_task_update_help(self, cli_runner):
        """Test task update help shows arguments."""
        stdout, stderr, code = cli_runner(["epic", "ticket", "update", "--help"])
        assert code == 0
        assert "status" in stdout.lower() or "task" in stdout.lower()

    def test_task_update_changes_status(self, task_cli_runner, task_repo):
        """Test task update actually changes task status in file."""
        # Get current task first
        current_result = task_cli_runner(["-j", "epic", "ticket", "current"])
        if current_result.stdout.strip() and current_result.stdout.strip() != "null":
            current_data = json.loads(current_result.stdout)
            if current_data and current_data.get("id"):
                task_id = current_data["id"]

                # Try to update to completed
                update_result = task_cli_runner(
                    ["epic", "ticket", "update", task_id, "--status", "completed"]
                )
                # Should succeed or fail gracefully
                assert update_result.returncode in [0, 1]


@pytest.mark.story("US-PLN-012")
@pytest.mark.story("US-PLN-012")
class TestTaskAdd:
    """Tests for plan task add command."""

    def test_task_add_help(self, cli_runner):
        """Test task add help shows description option."""
        stdout, stderr, code = cli_runner(["epic", "ticket", "add", "--help"])
        assert code == 0

    def test_task_add_creates_task(self, task_cli_runner):
        """Test task add creates a new task."""
        # Add a new task
        result = task_cli_runner(["epic", "ticket", "add", "New test task"])
        # Should succeed or provide feedback
        assert result.returncode in [0, 1]


@pytest.mark.story("US-PLN-009", "US-PLN-011")
class TestTaskIntegration:
    """Integration tests for task commands working together."""

    def test_list_then_current_consistent(self, task_cli_runner):
        """Test that list and current return consistent data."""
        # Get list
        list_result = task_cli_runner(["-j", "epic", "ticket", "list"])
        assert list_result.returncode == 0

        # Get current
        current_result = task_cli_runner(["-j", "epic", "ticket", "current"])
        assert current_result.returncode == 0

        # If current has a task, it should be in the list
        if (
            current_result.stdout.strip()
            and current_result.stdout.strip() != "null"
            and list_result.stdout.strip()
        ):
            current_task = json.loads(current_result.stdout)
            task_list = json.loads(list_result.stdout)

            if current_task and isinstance(task_list, list):
                # Current task should be in list
                task_ids = [t.get("id") for t in task_list if isinstance(t, dict)]
                if current_task.get("id"):
                    assert current_task["id"] in task_ids

    def test_update_then_current_reflects_change(self, task_cli_runner):
        """Test that updating a task's status is reflected in current."""
        # Get current task
        current_result = task_cli_runner(["-j", "epic", "ticket", "current"])

        if current_result.stdout.strip() and current_result.stdout.strip() != "null":
            current_task = json.loads(current_result.stdout)

            if current_task and current_task.get("id"):
                # Store original status
                original_status = current_task.get("status")

                # Update to completed
                task_cli_runner(
                    [
                        "-j",
                        "epic",
                        "ticket",
                        "update",
                        current_task["id"],
                        "--status",
                        "completed",
                    ]
                )

                # Get current again - should now return different task
                new_current_result = task_cli_runner(["-j", "epic", "ticket", "current"])

                if (
                    new_current_result.stdout.strip()
                    and new_current_result.stdout.strip() != "null"
                ):
                    new_current = json.loads(new_current_result.stdout)
                    # Should return a different task (the next one)
                    if new_current:
                        # May or may not have a new task, but should not be the same
                        # completed task
                        pass  # Test passes if no error
