"""Tests for epic init (formerly bootstrap) command.

These tests verify that cmd_init creates TinyDB records correctly.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

pytestmark = pytest.mark.story("US-PLN-001")


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


@pytest.mark.story("US-PLN-002", "US-PLN-005")
class TestPlanBootstrap:
    """Tests verifying plan bootstrap has been removed and replaced by epic bootstrap."""

    def test_cmd_bootstrap_removed_from_plan_module(self):
        """Verify plan module no longer exists (fully deleted)."""
        import importlib
        try:
            importlib.import_module("agenticcli.commands.plan")
            assert False, "plan module should have been deleted"
        except ImportError:
            pass  # Expected — plan.py was fully removed

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
        # 'plan' command is fully removed; Typer returns "No such command" error
        assert "Command removed" in stderr or "agentic epic" in stderr or "No such command" in stderr

    def test_epic_bootstrap_creates_folder_structure(self, temp_git_repo, _isolate_tinydb):
        """Test that 'agentic agent epic bootstrap' creates TinyDB record."""
        from agenticcli.commands import epic as epic_module
        from agenticguidance.services.epic_repository import EpicRepository

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
                    epic_module.cmd_init(args)
        finally:
            os.chdir(original_cwd)

        # Verify epic is registered in TinyDB (no folder created on disk)
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        matching = [e for e in epics if "new_feature" in e.epic_folder_name]
        repo.close()
        assert len(matching) == 1

    def test_epic_bootstrap_creates_plan_build_yml(self, temp_git_repo, _isolate_tinydb):
        """Test that epic bootstrap creates the epic folder and TinyDB entry.

        With TinyDB as the sole data store, plan_build.yml is no longer written.
        The test now verifies the epic folder and TinyDB record are created.
        """
        from agenticcli.commands import epic as epic_module
        from agenticguidance.services.epic_repository import EpicRepository

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
                    epic_module.cmd_init(args)
        finally:
            os.chdir(original_cwd)

        # Epic is recorded in TinyDB (no folder created on disk)
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        matching = [e for e in epics if "new_feature" in e.epic_folder_name]
        repo.close()
        assert len(matching) == 1, f"Expected 1 matching epic, found {len(matching)}"

    def test_epic_bootstrap_creates_plan_test_yml_stub(self, temp_git_repo, _isolate_tinydb):
        """Test epic bootstrap creates TinyDB record (no YAML files)."""
        from agenticcli.commands import epic as epic_module
        from agenticguidance.services.epic_repository import EpicRepository

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
                    epic_module.cmd_init(args)
        finally:
            os.chdir(original_cwd)

        # Epic is registered in TinyDB
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        matching = [e for e in epics if "new_feature" in e.epic_folder_name]
        repo.close()
        assert len(matching) == 1

    def test_epic_bootstrap_yaml_is_valid(self, temp_git_repo, _isolate_tinydb):
        """Test epic bootstrap stores valid data in TinyDB.

        With TinyDB as the sole data store, plan_build.yml is no longer written.
        The test now verifies the expected fields are stored in TinyDB.
        """
        from agenticcli.commands import epic as epic_module
        from agenticguidance.services.epic_repository import EpicRepository

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
                    epic_module.cmd_init(args)
        finally:
            os.chdir(original_cwd)

        # Verify expected fields are stored in TinyDB
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        matching = [e for e in epics if "new_feature" in e.epic_folder_name]
        assert len(matching) == 1
        epic = matching[0]
        repo.close()
        assert epic.name == "new feature"
        assert epic.branch == "test-branch"
        assert epic.status == "active"
        # objective is stored via 'context' key in epic_data by cmd_init

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
                    epic_module.cmd_init(args)

            # Try to create again with same description - should exit(2)
            with pytest.raises(SystemExit) as exc_info:
                with patch("agenticcli.console.is_json_output", return_value=False):
                    with patch("builtins.print"):
                        epic_module.cmd_init(args)
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
            epic_module.cmd_init(args)
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

    def test_epic_bootstrap_uses_branch_as_default_description(self, temp_git_repo, _isolate_tinydb):
        """Test epic bootstrap uses branch as description when not provided."""
        from agenticcli.commands import epic as epic_module
        from agenticguidance.services.epic_repository import EpicRepository

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
                    epic_module.cmd_init(args)
        finally:
            os.chdir(original_cwd)

        # Folder creation is no longer performed by cmd_init (TinyDB is the sole data store).
        # Verify the epic was registered in TinyDB with a name derived from the branch.
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        repo.close()
        matching = [e for e in epics if "auth_feature" in e.epic_folder_name]
        assert len(matching) == 1, (
            f"Expected 1 epic with 'auth_feature' in folder name, got: {[e.epic_folder_name for e in epics]}"
        )

    def test_epic_bootstrap_sanitizes_description(self, temp_git_repo, _isolate_tinydb):
        """Test epic bootstrap sanitizes special characters in description."""
        from agenticcli.commands import epic as epic_module
        from agenticguidance.services.epic_repository import EpicRepository

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
                    epic_module.cmd_init(args)
        finally:
            os.chdir(original_cwd)

        # Folder creation is no longer performed by cmd_init (TinyDB is the sole data store).
        # Verify the epic was registered in TinyDB with special chars stripped from the folder name.
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        repo.close()
        matching = [e for e in epics if "bug_fix" in e.epic_folder_name]
        assert len(matching) == 1, (
            f"Expected 1 epic with 'bug_fix' in folder name, got: {[e.epic_folder_name for e in epics]}"
        )
        folder_name = matching[0].epic_folder_name

        # Should not contain special chars
        assert ":" not in folder_name
        assert "#" not in folder_name
        assert "!" not in folder_name

    def test_epic_bootstrap_creates_tasks_in_phases(self, temp_git_repo, _isolate_tinydb):
        """Test epic bootstrap creates initial tasks in TinyDB phases.

        With TinyDB as the sole data store, the initial IM_001 stub ticket
        is created in TinyDB rather than written to plan_build.yml.
        """
        from agenticcli.commands import epic as epic_module
        from agenticguidance.services.epic_repository import EpicRepository

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
                    epic_module.cmd_init(args)
        finally:
            os.chdir(original_cwd)

        # Folder creation is no longer performed by cmd_init (TinyDB is the sole data store).
        # Find the epic via TinyDB instead of scanning the filesystem.
        repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
        epics = repo.list_epics()
        matching = [e for e in epics if "test_tasks" in e.epic_folder_name]
        assert len(matching) == 1, (
            f"Expected 1 epic with 'test_tasks' in folder name, got: {[e.epic_folder_name for e in epics]}"
        )
        epic_folder_name = matching[0].epic_folder_name

        # Verify initial stub ticket was created in TinyDB
        tickets = repo.get_tickets(epic_folder_name)
        repo.close()
        assert len(tickets) > 0, "Expected at least one stub ticket in TinyDB"
        ticket_ids = [t.id for t in tickets]
        assert "IM_001" in ticket_ids, f"Expected IM_001 stub ticket, got: {ticket_ids}"


@pytest.mark.story("US-PLN-002")
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
                        epic_module.cmd_init(args)
        finally:
            os.chdir(original_cwd)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Not in a git repository" in captured.err
