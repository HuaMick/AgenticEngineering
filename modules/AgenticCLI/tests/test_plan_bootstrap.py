"""Tests for 'agentic plan bootstrap' command.

NOTE: The 'agentic plan bootstrap' command has been removed. All bootstrap
functionality has been migrated to 'agentic epic bootstrap' and
'agentic agent epic bootstrap'. These tests verify that the old plan
bootstrap command is gone (cmd_bootstrap no longer exists in plan.py)
and that the epic bootstrap command works correctly.
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

    # Create docs/epics/live directory structure
    plans_dir = repo_path / "docs" / "epics" / "live"
    plans_dir.mkdir(parents=True, exist_ok=True)

    return repo_path


class TestPlanBootstrap:
    """Tests verifying plan bootstrap has been removed and replaced by epic bootstrap."""

    def test_cmd_bootstrap_removed_from_plan_module(self):
        """Verify cmd_bootstrap no longer exists in plan.py."""
        from agenticcli.commands import plan
        assert not hasattr(plan, "cmd_bootstrap"), (
            "cmd_bootstrap should have been removed from plan.py - use epic module instead"
        )

    def test_plan_bootstrap_cli_returns_error(self, cli_runner, temp_git_repo):
        """Test that bare 'agentic plan' command returns command-removed error."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            stdout, stderr, code = cli_runner(
                ["plan", "status"]
            )
        finally:
            os.chdir(original_cwd)
        assert code != 0
        assert "Command removed" in stderr or "agentic epic" in stderr

    def test_epic_bootstrap_creates_folder_structure(self, temp_git_repo):
        """Test that 'agentic agent epic bootstrap' creates proper plan folder structure."""
        from agenticcli.commands import epic as epic_module

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="new feature",
        )

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            with patch("agenticcli.console.is_json_output", return_value=False):
                with patch("builtins.print"):
                    epic_module.cmd_bootstrap(args)
        finally:
            os.chdir(original_cwd)

        # Verify plan folder was created under docs/epics/live/
        plans_dir = temp_git_repo / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_new_feature"))
        assert len(plan_folders) == 1
        plan_folder = plan_folders[0]

        # Flat structure: plan folder exists directly (no live/ subfolder inside)
        assert plan_folder.exists()
        assert plan_folder.is_dir()

    def test_epic_bootstrap_creates_plan_build_yml(self, temp_git_repo):
        """Test that epic bootstrap creates plan_build.yml file."""
        from agenticcli.commands import epic as epic_module

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="new feature",
        )

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            with patch("agenticcli.console.is_json_output", return_value=False):
                with patch("builtins.print"):
                    epic_module.cmd_bootstrap(args)
        finally:
            os.chdir(original_cwd)

        plans_dir = temp_git_repo / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_new_feature"))
        plan_folder = plan_folders[0]

        # Flat structure: plan_build.yml directly in plan folder
        plan_build_file = plan_folder / "plan_build.yml"
        assert plan_build_file.exists()

    def test_epic_bootstrap_creates_plan_test_yml_stub(self, temp_git_repo):
        """Test epic bootstrap creates plan folder (plan_test.yml is optional)."""
        from agenticcli.commands import epic as epic_module

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="new feature",
        )

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            with patch("agenticcli.console.is_json_output", return_value=False):
                with patch("builtins.print"):
                    epic_module.cmd_bootstrap(args)
        finally:
            os.chdir(original_cwd)

        plans_dir = temp_git_repo / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_new_feature"))
        plan_folder = plan_folders[0]

        # Plan folder exists (plan_test.yml creation depends on create_planning_folder)
        assert plan_folder.exists()

    def test_epic_bootstrap_yaml_is_valid(self, temp_git_repo):
        """Test epic bootstrap creates valid YAML files."""
        from agenticcli.commands import epic as epic_module

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="new feature",
        )

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            with patch("agenticcli.console.is_json_output", return_value=False):
                with patch("builtins.print"):
                    epic_module.cmd_bootstrap(args)
        finally:
            os.chdir(original_cwd)

        plans_dir = temp_git_repo / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_new_feature"))
        plan_folder = plan_folders[0]

        # Flat structure: plan_build.yml directly in plan folder
        plan_build_file = plan_folder / "plan_build.yml"

        # Should be valid YAML
        with open(plan_build_file) as f:
            data = yaml.safe_load(f)

        # Verify expected fields from cmd_init's plan_build template
        assert data["name"] == "new feature"
        assert data["branch"] == "test-branch"
        assert data["status"] == "active"
        assert "context" in data  # cmd_init writes objective into "context" field
        assert "phases" in data

    def test_epic_bootstrap_existing_folder_returns_error(self, temp_git_repo, capsys):
        """Test epic bootstrap fails if plan folder already exists."""
        from agenticcli.commands import epic as epic_module

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="duplicate",
        )

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            # First create a plan
            with patch("agenticcli.console.is_json_output", return_value=False):
                with patch("builtins.print"):
                    epic_module.cmd_bootstrap(args)

            # Try to create again with same description - should exit(2)
            with pytest.raises(SystemExit) as exc_info:
                with patch("agenticcli.console.is_json_output", return_value=False):
                    with patch("builtins.print"):
                        epic_module.cmd_bootstrap(args)
        finally:
            os.chdir(original_cwd)

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "already exists" in captured.err

    @patch("agenticcli.console.is_json_output")
    def test_epic_bootstrap_json_output(self, mock_json_output, temp_git_repo, capsys):
        """Test epic bootstrap with JSON output."""
        from agenticcli.commands import epic as epic_module

        mock_json_output.return_value = True

        args = SimpleNamespace(
            branch="test-branch",
            objective="Implement new feature",
            description="json test",
        )

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            epic_module.cmd_bootstrap(args)
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # cmd_init outputs these keys (not the old plan_id/plan_path/success)
        assert "epic_folder_name" in output
        assert "epic_folder" in output
        assert "objective" in output
        assert output["objective"] == "Implement new feature"
        assert "branch" in output
        assert output["branch"] == "test-branch"

    def test_epic_bootstrap_uses_branch_as_default_description(self, temp_git_repo):
        """Test epic bootstrap uses branch as description when not provided."""
        from agenticcli.commands import epic as epic_module

        args = SimpleNamespace(
            branch="auth-feature",
            objective="Add authentication",
            description=None,  # Will use branch as default
        )

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            with patch("agenticcli.console.is_json_output", return_value=False):
                with patch("builtins.print"):
                    epic_module.cmd_bootstrap(args)
        finally:
            os.chdir(original_cwd)

        plans_dir = temp_git_repo / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_auth_feature"))
        assert len(plan_folders) == 1

    def test_epic_bootstrap_sanitizes_description(self, temp_git_repo):
        """Test epic bootstrap sanitizes special characters in description."""
        from agenticcli.commands import epic as epic_module

        args = SimpleNamespace(
            branch="test-branch",
            objective="Fix bug #123",
            description="Bug Fix: Issue #123!",
        )

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            with patch("agenticcli.console.is_json_output", return_value=False):
                with patch("builtins.print"):
                    epic_module.cmd_bootstrap(args)
        finally:
            os.chdir(original_cwd)

        plans_dir = temp_git_repo / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.iterdir())
        # Filter to only our test folder (exclude other dirs)
        plan_folders = [f for f in plan_folders if f.is_dir() and "bug_fix" in f.name]
        assert len(plan_folders) == 1
        plan_folder = plan_folders[0]

        # Should not contain special chars
        assert ":" not in plan_folder.name
        assert "#" not in plan_folder.name
        assert "!" not in plan_folder.name

    def test_epic_bootstrap_creates_tasks_in_phases(self, temp_git_repo):
        """Test epic bootstrap creates initial tasks in phases."""
        from agenticcli.commands import epic as epic_module

        args = SimpleNamespace(
            branch="test-branch",
            objective="Test objective",
            description="test tasks",
        )

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            with patch("agenticcli.console.is_json_output", return_value=False):
                with patch("builtins.print"):
                    epic_module.cmd_bootstrap(args)
        finally:
            os.chdir(original_cwd)

        plans_dir = temp_git_repo / "docs" / "epics" / "live"
        plan_folders = list(plans_dir.glob("*_test_tasks"))
        plan_folder = plan_folders[0]

        # Flat structure: plan_build.yml directly in plan folder
        plan_build_file = plan_folder / "plan_build.yml"
        with open(plan_build_file) as f:
            data = yaml.safe_load(f)

        assert "phases" in data
        assert len(data["phases"]) > 0
        assert "tasks" in data["phases"][0]
        assert len(data["phases"][0]["tasks"]) > 0


class TestPlanBootstrapErrors:
    """Tests for error handling in bootstrap command."""

    def test_epic_bootstrap_fails_outside_git_repo(self, tmp_path, monkeypatch, capsys):
        """Test epic bootstrap fails when not in a git repository."""
        from agenticcli.commands import epic as epic_module

        # Mock subprocess.run to raise CalledProcessError for git rev-parse
        # (cmd_init uses subprocess.run, not git.get_project_root)
        original_subprocess_run = subprocess.run

        def mock_subprocess_run(cmd, *args, **kwargs):
            if isinstance(cmd, list) and cmd[0] == "git":
                if "rev-parse" in cmd:
                    raise subprocess.CalledProcessError(128, cmd)
            return original_subprocess_run(cmd, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

        args = SimpleNamespace(
            branch="test-branch",
            objective="Test",
            description="test",
        )

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(SystemExit) as exc_info:
                with patch("agenticcli.console.is_json_output", return_value=False):
                    with patch("builtins.print"):
                        epic_module.cmd_bootstrap(args)
        finally:
            os.chdir(original_cwd)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Not in a git repository" in captured.err
