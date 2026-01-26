"""Tests for plan service."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticguidance.services.plan import (
    FolderMoveResult,
    GitSafetyChecker,
    MoveResult,
    PlanMovementWorkflow,
    TaskMoveResult,
)


class TestMoveResult:
    """Tests for MoveResult enum."""

    def test_result_values(self):
        """Test move result enum values."""
        assert MoveResult.SUCCESS.value == "success"
        assert MoveResult.SKIPPED.value == "skipped"
        assert MoveResult.FAILED.value == "failed"


class TestTaskMoveResult:
    """Tests for TaskMoveResult dataclass."""

    def test_create_result(self):
        """Test creating a task move result."""
        result = TaskMoveResult(
            task_id="task_001",
            result=MoveResult.SUCCESS,
            message="Task moved successfully",
            source_file="plan_live.yml",
            target_file="plan_completed.yml",
        )

        assert result.task_id == "task_001"
        assert result.result == MoveResult.SUCCESS
        assert result.message == "Task moved successfully"


class TestFolderMoveResult:
    """Tests for FolderMoveResult dataclass."""

    def test_create_result(self):
        """Test creating a folder move result."""
        result = FolderMoveResult(
            source="/docs/plans/live/feature",
            destination="/docs/plans/completed/feature",
            result=MoveResult.SUCCESS,
            message="Folder archived",
        )

        assert result.source == "/docs/plans/live/feature"
        assert result.result == MoveResult.SUCCESS


class TestGitSafetyChecker:
    """Tests for GitSafetyChecker class."""

    @patch("subprocess.run")
    def test_has_uncommitted_changes_returns_true(self, mock_run):
        """Test returns True when there are uncommitted changes."""
        mock_run.return_value = MagicMock(stdout="M file.py\n", returncode=0)

        checker = GitSafetyChecker()
        result = checker.has_uncommitted_changes()

        assert result is True

    @patch("subprocess.run")
    def test_has_uncommitted_changes_returns_false(self, mock_run):
        """Test returns False when no uncommitted changes."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)

        checker = GitSafetyChecker()
        result = checker.has_uncommitted_changes()

        assert result is False

    @patch("subprocess.run")
    def test_has_uncommitted_changes_handles_error(self, mock_run):
        """Test returns True on git error (conservative)."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        checker = GitSafetyChecker()
        result = checker.has_uncommitted_changes()

        assert result is True

    @patch("subprocess.run")
    def test_is_clean_returns_true_when_clean(self, mock_run):
        """Test is_clean returns True when no changes."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)

        checker = GitSafetyChecker()
        result = checker.is_clean()

        assert result is True

    @patch("subprocess.run")
    def test_get_status_returns_file_list(self, mock_run):
        """Test get_status returns list of changed files."""
        mock_run.return_value = MagicMock(
            stdout=" M file1.py\n A file2.py\n",
            returncode=0,
        )

        checker = GitSafetyChecker()
        result = checker.get_status()

        # The result strips first 3 chars from each line
        assert len(result) == 2


class TestPlanMovementWorkflow:
    """Tests for PlanMovementWorkflow class."""

    def test_init_sets_paths(self, tmp_path):
        """Test initialization sets correct paths."""
        plan_path = tmp_path / "docs" / "plans" / "live" / "feature"
        plan_path.mkdir(parents=True)

        workflow = PlanMovementWorkflow(plan_path)

        assert workflow.plan_path == plan_path
        assert workflow.live_dir == plan_path / "live"
        assert workflow.completed_dir == plan_path / "completed"

    def test_find_repo_root(self, tmp_path):
        """Test _find_repo_root finds git directory."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        subdir = tmp_path / "sub" / "dir"
        subdir.mkdir(parents=True)

        result = PlanMovementWorkflow._find_repo_root(subdir)

        assert result == tmp_path

    def test_get_completed_tasks(self, tmp_path):
        """Test get_completed_tasks finds completed tasks."""
        plan_path = tmp_path / "plan"
        live_dir = plan_path / "live"
        live_dir.mkdir(parents=True)

        # Using 'tasks' at the plan level (not nested in phases)
        plan_content = """
plan:
  tasks:
    - id: task_001
      name: Task 1
      status: completed
    - id: task_002
      name: Task 2
      status: pending
"""
        (live_dir / "plan_live.yml").write_text(plan_content)

        workflow = PlanMovementWorkflow(plan_path)
        completed = workflow.get_completed_tasks()

        assert len(completed) == 1
        assert completed[0]["id"] == "task_001"

    def test_get_archived_tasks_empty_when_no_file(self, tmp_path):
        """Test get_archived_tasks returns empty when no completed file."""
        plan_path = tmp_path / "plan"
        plan_path.mkdir()

        workflow = PlanMovementWorkflow(plan_path)
        archived = workflow.get_archived_tasks()

        assert archived == []

    @patch.object(GitSafetyChecker, "has_uncommitted_changes", return_value=False)
    def test_move_task_to_completed_dry_run(self, mock_git, tmp_path):
        """Test move_task_to_completed with dry_run."""
        plan_path = tmp_path / "plan"
        live_dir = plan_path / "live"
        live_dir.mkdir(parents=True)

        plan_content = """
plan:
  tasks:
    - id: task_001
      name: Task 1
      status: completed
"""
        (live_dir / "plan_live.yml").write_text(plan_content)

        workflow = PlanMovementWorkflow(plan_path)
        result = workflow.move_task_to_completed("task_001", dry_run=True)

        assert result.result == MoveResult.SUCCESS
        assert "[dry-run]" in result.message

    def test_move_task_fails_for_non_completed(self, tmp_path):
        """Test move_task_to_completed fails for non-completed task."""
        plan_path = tmp_path / "plan"
        live_dir = plan_path / "live"
        live_dir.mkdir(parents=True)

        plan_content = """
plan:
  tasks:
    - id: task_001
      name: Task 1
      status: pending
"""
        (live_dir / "plan_live.yml").write_text(plan_content)

        workflow = PlanMovementWorkflow(plan_path)
        result = workflow.move_task_to_completed("task_001")

        assert result.result == MoveResult.SKIPPED
        assert "pending" in result.message

    def test_move_task_fails_for_missing(self, tmp_path):
        """Test move_task_to_completed fails for missing task."""
        plan_path = tmp_path / "plan"
        live_dir = plan_path / "live"
        live_dir.mkdir(parents=True)
        (live_dir / "plan_live.yml").write_text("plan:\n  phases: []\n")

        workflow = PlanMovementWorkflow(plan_path)
        result = workflow.move_task_to_completed("nonexistent")

        assert result.result == MoveResult.FAILED
        assert "not found" in result.message

    @patch.object(GitSafetyChecker, "has_uncommitted_changes", return_value=False)
    def test_archive_plan_folder_dry_run(self, mock_git, tmp_path):
        """Test archive_plan_folder with dry_run."""
        plan_path = tmp_path / "docs" / "plans" / "live" / "feature"
        plan_path.mkdir(parents=True)

        workflow = PlanMovementWorkflow(plan_path)
        result = workflow.archive_plan_folder(dry_run=True)

        assert result.result == MoveResult.SUCCESS
        assert "[dry-run]" in result.message

    @patch.object(GitSafetyChecker, "has_uncommitted_changes", return_value=True)
    def test_archive_skipped_with_uncommitted(self, mock_git, tmp_path):
        """Test archive is skipped when uncommitted changes exist."""
        plan_path = tmp_path / "docs" / "plans" / "live" / "feature"
        plan_path.mkdir(parents=True)

        workflow = PlanMovementWorkflow(plan_path)
        result = workflow.archive_plan_folder()

        assert result.result == MoveResult.SKIPPED
        assert "Uncommitted" in result.message
