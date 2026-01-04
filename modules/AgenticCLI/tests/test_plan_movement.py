"""Tests for plan movement workflow."""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def plan_folder(temp_repo):
    """Create a plan folder with test structure."""
    plan_path = temp_repo / "docs" / "plans" / "live" / "260103AE_test"
    live_dir = plan_path / "live"
    completed_dir = plan_path / "completed"

    live_dir.mkdir(parents=True, exist_ok=True)
    completed_dir.mkdir(parents=True, exist_ok=True)

    # Create a feature file with tasks
    feature_file = live_dir / "feature_test.yml"
    feature_data = {
        "feature": {
            "name": "Test Feature",
            "phases": [
                {"id": "12.1", "title": "First task", "status": "completed"},
                {"id": "12.2", "title": "Second task", "status": "in_progress"},
                {"id": "12.3", "title": "Third task", "status": "pending"},
            ],
        }
    }
    with open(feature_file, "w") as f:
        yaml.dump(feature_data, f)

    # Create placeholder completed file
    completed_file = completed_dir / "plan_completed.yml"
    completed_file.write_text("# Completed tasks\n")

    return plan_path


class TestPlanMovementWorkflow:
    """Tests for PlanMovementWorkflow class."""

    def test_move_completed_task(self, plan_folder):
        """Test moving a completed task to plan_completed.yml."""
        from agenticcli.workflows.plan_workflow import MoveResult, PlanMovementWorkflow

        workflow = PlanMovementWorkflow(plan_folder)
        result = workflow.move_task_to_completed("12.1", force=True)

        assert result.result == MoveResult.SUCCESS
        assert result.source_file == "feature_test.yml"
        assert result.target_file == "plan_completed.yml"

    def test_move_non_completed_task_skipped(self, plan_folder):
        """Test that non-completed tasks are skipped."""
        from agenticcli.workflows.plan_workflow import MoveResult, PlanMovementWorkflow

        workflow = PlanMovementWorkflow(plan_folder)
        result = workflow.move_task_to_completed("12.2", force=True)

        assert result.result == MoveResult.SKIPPED
        assert "in_progress" in result.message

    def test_move_nonexistent_task_fails(self, plan_folder):
        """Test that non-existent tasks fail."""
        from agenticcli.workflows.plan_workflow import MoveResult, PlanMovementWorkflow

        workflow = PlanMovementWorkflow(plan_folder)
        result = workflow.move_task_to_completed("99.99", force=True)

        assert result.result == MoveResult.FAILED
        assert "not found" in result.message

    def test_move_task_dry_run(self, plan_folder):
        """Test dry run doesn't make changes."""
        from agenticcli.workflows.plan_workflow import MoveResult, PlanMovementWorkflow

        workflow = PlanMovementWorkflow(plan_folder)
        result = workflow.move_task_to_completed("12.1", dry_run=True, force=True)

        assert result.result == MoveResult.SUCCESS
        assert "dry-run" in result.message

        # Verify no changes were made
        completed_file = plan_folder / "completed" / "plan_completed.yml"
        data = yaml.safe_load(completed_file.read_text())
        assert data is None or "completed_tasks" not in data

    def test_move_task_creates_completed_file(self, plan_folder):
        """Test that completed file is created if missing."""
        from agenticcli.workflows.plan_workflow import MoveResult, PlanMovementWorkflow

        # Remove existing completed file
        completed_file = plan_folder / "completed" / "plan_completed.yml"
        completed_file.unlink()

        workflow = PlanMovementWorkflow(plan_folder)
        result = workflow.move_task_to_completed("12.1", force=True)

        assert result.result == MoveResult.SUCCESS
        assert completed_file.exists()

        data = yaml.safe_load(completed_file.read_text())
        assert "completed_tasks" in data
        assert len(data["completed_tasks"]) == 1
        assert data["completed_tasks"][0]["id"] == "12.1"

    def test_move_all_completed_tasks(self, plan_folder):
        """Test moving all completed tasks at once."""
        from agenticcli.workflows.plan_workflow import MoveResult, PlanMovementWorkflow

        workflow = PlanMovementWorkflow(plan_folder)
        results = workflow.move_all_completed_tasks(force=True)

        # There may be multiple completed tasks from test fixtures
        # Check that all are successfully moved
        assert len(results) >= 1
        assert all(r.result == MoveResult.SUCCESS for r in results)
        # 12.1 should be one of them
        task_ids = [r.task_id for r in results]
        assert "12.1" in task_ids

    def test_get_completed_tasks(self, plan_folder):
        """Test getting list of completed tasks."""
        from agenticcli.workflows.plan_workflow import PlanMovementWorkflow

        workflow = PlanMovementWorkflow(plan_folder)
        completed = workflow.get_completed_tasks()

        # There may be multiple completed tasks
        assert len(completed) >= 1
        ids = [t["id"] for t in completed]
        assert "12.1" in ids
        # All returned should be completed
        assert all(t["status"] == "completed" for t in completed)


class TestGitSafetyChecker:
    """Tests for GitSafetyChecker class."""

    def test_is_clean_in_clean_repo(self, temp_dir):
        """Test is_clean returns True in a clean repo."""
        import subprocess

        from agenticcli.workflows.plan_workflow import GitSafetyChecker

        # Create a fresh git repo with no uncommitted files
        repo = temp_dir / "clean_repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
        (repo / "test.txt").write_text("test")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)

        checker = GitSafetyChecker(repo)
        assert checker.is_clean() is True

    def test_has_uncommitted_changes(self, temp_repo):
        """Test detecting uncommitted changes."""
        from agenticcli.workflows.plan_workflow import GitSafetyChecker

        # Create an untracked file
        test_file = temp_repo / "untracked.txt"
        test_file.write_text("test")

        checker = GitSafetyChecker(temp_repo)
        assert checker.has_uncommitted_changes() is True

    def test_get_status(self, temp_dir):
        """Test getting list of changed files."""
        import subprocess

        from agenticcli.workflows.plan_workflow import GitSafetyChecker

        # Create a fresh git repo
        repo = temp_dir / "status_repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
        (repo / "initial.txt").write_text("initial")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True)

        # Create an untracked file
        (repo / "newfile.txt").write_text("test")

        checker = GitSafetyChecker(repo)
        changes = checker.get_status()

        assert "newfile.txt" in changes


class TestFolderArchive:
    """Tests for folder archival."""

    def test_archive_plan_folder(self, plan_folder):
        """Test archiving a plan folder."""
        from agenticcli.workflows.plan_workflow import MoveResult, PlanMovementWorkflow

        workflow = PlanMovementWorkflow(plan_folder)
        result = workflow.archive_plan_folder(force=True)

        assert result.result == MoveResult.SUCCESS

        # Check destination exists
        dest = Path(result.destination)
        assert dest.exists()
        assert (dest / "live").exists()
        assert (dest / "completed").exists()

    def test_archive_dry_run(self, plan_folder):
        """Test archive dry run doesn't make changes."""
        from agenticcli.workflows.plan_workflow import MoveResult, PlanMovementWorkflow

        workflow = PlanMovementWorkflow(plan_folder)
        result = workflow.archive_plan_folder(dry_run=True, force=True)

        assert result.result == MoveResult.SUCCESS
        assert "dry-run" in result.message

        # Destination should not exist
        dest = Path(result.destination)
        assert not dest.exists()

    def test_archive_already_exists(self, plan_folder):
        """Test archive fails if destination exists."""
        from agenticcli.workflows.plan_workflow import MoveResult, PlanMovementWorkflow

        # Create destination manually
        dest = plan_folder.parent.parent / "completed" / plan_folder.name
        dest.mkdir(parents=True)

        workflow = PlanMovementWorkflow(plan_folder)
        result = workflow.archive_plan_folder(force=True)

        assert result.result == MoveResult.SKIPPED
        assert "already exists" in result.message


class TestMoveCommands:
    """Tests for plan move CLI commands."""

    def test_move_task_not_found(self, cli_runner, temp_repo):
        """Test plan move task with non-existent task."""
        # Create minimal plan structure
        plan_dir = temp_repo / "docs" / "plans" / "live" / "test_plan"
        live_dir = plan_dir / "live"
        completed_dir = plan_dir / "completed"
        live_dir.mkdir(parents=True)
        completed_dir.mkdir(parents=True)

        # Create empty feature file
        (live_dir / "feature.yml").write_text("feature: {phases: []}\n")

        stdout, stderr, code = cli_runner(["plan", "move", "task", "99.99", "--force"])
        assert code == 1
        assert "not found" in stderr.lower()

    def test_move_no_subcommand(self, cli_runner, temp_repo):
        """Test plan move without subcommand shows usage."""
        # Create minimal structure
        plan_dir = temp_repo / "docs" / "plans" / "live" / "test_plan"
        (plan_dir / "live").mkdir(parents=True)
        (plan_dir / "completed").mkdir(parents=True)

        stdout, stderr, code = cli_runner(["plan", "move"])
        # Should show usage
        assert code == 1
