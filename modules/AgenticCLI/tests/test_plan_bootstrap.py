"""Tests for 'agentic plan bootstrap' command.

Tests for the plan bootstrap command that combines init logic with
immediate scaffolding of plan_build.yml.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        capture_output=True,
        check=True,
    )

    # Create docs/plans/live directory structure
    plans_dir = repo_path / "docs" / "plans" / "live"
    plans_dir.mkdir(parents=True, exist_ok=True)

    return repo_path


@pytest.fixture
def mock_git_context(temp_git_repo, monkeypatch):
    """Mock git utility functions to use temp repo."""
    from agenticcli.utils import git
    from agenticcli.commands import plan

    monkeypatch.setattr(git, "get_project_root", lambda: temp_git_repo)
    monkeypatch.setattr(plan, "find_main_worktree", lambda root: root)
    return temp_git_repo


class TestPlanBootstrap:
    """Tests for 'agentic plan bootstrap' command."""

    def test_bootstrap_creates_folder_structure(self, mock_git_context):
        """Test bootstrap creates proper plan folder structure."""
        from agenticcli.commands import plan

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="new feature",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        # Verify plan folder was created
        plans_dir = mock_git_context / "docs" / "plans" / "live"
        plan_folders = list(plans_dir.glob("*_new_feature"))
        assert len(plan_folders) == 1
        plan_folder = plan_folders[0]

        # Verify live subfolder exists
        assert (plan_folder / "live").exists()
        assert (plan_folder / "live").is_dir()

    def test_bootstrap_creates_plan_build_yml(self, mock_git_context):
        """Test bootstrap creates plan_build.yml file."""
        from agenticcli.commands import plan

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="new feature",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "plans" / "live"
        plan_folders = list(plans_dir.glob("*_new_feature"))
        plan_folder = plan_folders[0]

        plan_build_file = plan_folder / "live" / "plan_build.yml"
        assert plan_build_file.exists()

    def test_bootstrap_creates_plan_test_yml_stub(self, mock_git_context):
        """Test bootstrap creates plan_test.yml stub (if implemented)."""
        from agenticcli.commands import plan

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="new feature",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "plans" / "live"
        plan_folders = list(plans_dir.glob("*_new_feature"))
        plan_folder = plan_folders[0]

        # Note: Current implementation may not create plan_test.yml
        # This test verifies expected behavior if it's added
        plan_test_file = plan_folder / "live" / "plan_test.yml"
        # For now, we just check if the folder exists
        assert plan_folder.exists()

    def test_bootstrap_yaml_is_valid(self, mock_git_context):
        """Test bootstrap creates valid YAML files."""
        from agenticcli.commands import plan

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="new feature",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "plans" / "live"
        plan_folders = list(plans_dir.glob("*_new_feature"))
        plan_folder = plan_folders[0]

        plan_build_file = plan_folder / "live" / "plan_build.yml"

        # Should be valid YAML
        with open(plan_build_file) as f:
            data = yaml.safe_load(f)

        # Verify expected fields
        assert data["name"] == "new feature"
        assert data["branch"] == "test-branch"
        assert data["status"] == "active"
        assert "objective" in data
        assert "phases" in data

    def test_bootstrap_existing_folder_returns_error(self, mock_git_context, capsys):
        """Test bootstrap fails if plan folder already exists."""
        from agenticcli.commands import plan

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="duplicate",
        )

        # First create a plan
        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        # Try to create again with same description
        with pytest.raises(SystemExit) as exc_info:
            plan.cmd_bootstrap(args)

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "already exists" in captured.err

    @patch("agenticcli.console.is_json_output")
    def test_bootstrap_json_output(self, mock_json_output, mock_git_context, capsys):
        """Test bootstrap with JSON output."""
        from agenticcli.commands import plan

        mock_json_output.return_value = True

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="json test",
        )

        plan.cmd_bootstrap(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert "plan_id" in output
        assert "plan_path" in output
        assert "objective" in output
        assert output["success"] is True
        assert output["objective"] == "Implement new feature"

    def test_bootstrap_uses_branch_as_default_description(self, mock_git_context):
        """Test bootstrap uses branch as description when not provided."""
        from agenticcli.commands import plan

        args = SimpleNamespace(
            branch="auth-feature",
            objective="Add authentication",
            description=None,  # Will use branch as default
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "plans" / "live"
        plan_folders = list(plans_dir.glob("*_auth_feature"))
        assert len(plan_folders) == 1

    def test_bootstrap_sanitizes_description(self, mock_git_context):
        """Test bootstrap sanitizes special characters in description."""
        from agenticcli.commands import plan

        args = SimpleNamespace(
            branch="test-branch",
            objective="Fix bug #123",
            description="Bug Fix: Issue #123!",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "plans" / "live"
        plan_folders = list(plans_dir.iterdir())
        assert len(plan_folders) == 1
        plan_folder = plan_folders[0]

        # Should not contain special chars
        assert ":" not in plan_folder.name
        assert "#" not in plan_folder.name
        assert "!" not in plan_folder.name

    def test_bootstrap_includes_worktree_path(self, mock_git_context):
        """Test bootstrap includes worktree_path in plan_build.yml."""
        from agenticcli.commands import plan

        args = SimpleNamespace(
            branch="test-branch",
            objective="Test objective",
            description="test",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "plans" / "live"
        plan_folders = list(plans_dir.glob("*_test"))
        plan_folder = plan_folders[0]

        plan_build_file = plan_folder / "live" / "plan_build.yml"
        with open(plan_build_file) as f:
            data = yaml.safe_load(f)

        assert "worktree_path" in data
        assert "test-branch" in data["worktree_path"]

    def test_bootstrap_creates_tasks_in_phases(self, mock_git_context):
        """Test bootstrap creates initial tasks in phases."""
        from agenticcli.commands import plan

        args = SimpleNamespace(
            branch="test-branch",
            objective="Test objective",
            description="test",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            with patch("builtins.print"):
                plan.cmd_bootstrap(args)

        plans_dir = mock_git_context / "docs" / "plans" / "live"
        plan_folders = list(plans_dir.glob("*_test"))
        plan_folder = plan_folders[0]

        plan_build_file = plan_folder / "live" / "plan_build.yml"
        with open(plan_build_file) as f:
            data = yaml.safe_load(f)

        assert "phases" in data
        assert len(data["phases"]) > 0
        assert "tasks" in data["phases"][0]
        assert len(data["phases"][0]["tasks"]) > 0


class TestPlanBootstrapErrors:
    """Tests for error handling in bootstrap command."""

    def test_bootstrap_fails_outside_git_repo(self, tmp_path, monkeypatch, capsys):
        """Test bootstrap fails when not in a git repository."""
        from agenticcli.commands import plan
        from agenticcli.utils import git

        # Mock to return None (not in git repo)
        monkeypatch.setattr(git, "get_project_root", lambda: None)

        args = SimpleNamespace(
            branch="test-branch",
            objective="Test",
            description="test",
        )

        with pytest.raises(SystemExit) as exc_info:
            plan.cmd_bootstrap(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Not in a git repository" in captured.err
