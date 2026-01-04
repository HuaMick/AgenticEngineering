"""Tests for worktree commands."""

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestWorktreeHelpers:
    """Tests for worktree helper functions."""

    def test_get_repo_abbreviation_camelcase(self):
        """Test abbreviation for CamelCase names."""
        from agenticcli.commands.worktree import get_repo_abbreviation

        assert get_repo_abbreviation("AgenticEngineering") == "AE"
        assert get_repo_abbreviation("MyProject") == "MP"
        assert get_repo_abbreviation("TestRepo") == "TR"

    def test_get_repo_abbreviation_single_cap(self):
        """Test abbreviation for single capital letter names."""
        from agenticcli.commands.worktree import get_repo_abbreviation

        # Falls back to first two chars
        assert get_repo_abbreviation("Test") == "TE"
        assert get_repo_abbreviation("A") == "A"

    def test_get_repo_abbreviation_no_caps(self):
        """Test abbreviation for lowercase names."""
        from agenticcli.commands.worktree import get_repo_abbreviation

        assert get_repo_abbreviation("myproject") == "MY"

    def test_generate_plan_folder_name(self, temp_dir):
        """Test plan folder name generation."""
        from agenticcli.commands.worktree import generate_plan_folder_name

        # Create a mock repo root
        repo_root = temp_dir / "AgenticEngineering-test"
        repo_root.mkdir()

        name = generate_plan_folder_name("feature-auth", repo_root)
        # Should be YYMMDDAE_feature-auth format
        assert name.endswith("_feature-auth")
        assert "AE" in name
        assert len(name.split("_")[0]) == 8  # YYMMDDAE

    def test_generate_plan_folder_name_simple_repo(self, temp_dir):
        """Test plan folder name for simple repo name."""
        from agenticcli.commands.worktree import generate_plan_folder_name

        repo_root = temp_dir / "SimpleProject"
        repo_root.mkdir()

        name = generate_plan_folder_name("main", repo_root)
        assert name.endswith("_main")
        assert "SP" in name or "SI" in name

    @patch("subprocess.run")
    def test_get_repo_root_success(self, mock_run):
        """Test get_repo_root returns correct path."""
        from agenticcli.commands.worktree import get_repo_root

        mock_run.return_value = MagicMock(stdout="/home/user/myrepo\n", returncode=0)

        root = get_repo_root()
        assert root == Path("/home/user/myrepo")

    @patch("subprocess.run")
    def test_get_repo_root_not_in_repo(self, mock_run):
        """Test get_repo_root exits when not in git repo."""
        from agenticcli.commands.worktree import get_repo_root

        mock_run.side_effect = subprocess.CalledProcessError(128, "git")

        with pytest.raises(SystemExit) as exc_info:
            get_repo_root()
        assert exc_info.value.code == 1


class TestCreatePlanningFolder:
    """Tests for create_planning_folder function."""

    def test_creates_directory_structure(self, temp_dir):
        """Test that planning folder structure is created."""
        from agenticcli.commands.worktree import create_planning_folder

        plan_path = temp_dir / "test_plan"
        create_planning_folder(plan_path)

        assert (plan_path / "live").exists()
        assert (plan_path / "completed").exists()

    def test_creates_placeholder_files(self, temp_dir):
        """Test that placeholder YAML files are created."""
        from agenticcli.commands.worktree import create_planning_folder

        plan_path = temp_dir / "test_plan"
        create_planning_folder(plan_path)

        live_dir = plan_path / "live"
        assert (live_dir / "plan_live_teach.yml").exists()
        assert (live_dir / "plan_live_test.yml").exists()
        assert (live_dir / "plan_live_audit_clean.yml").exists()

    def test_creates_completed_placeholder(self, temp_dir):
        """Test that completed placeholder is created."""
        from agenticcli.commands.worktree import create_planning_folder

        plan_path = temp_dir / "test_plan"
        create_planning_folder(plan_path)

        assert (plan_path / "completed" / "plan_completed.yml").exists()

    def test_does_not_overwrite_existing(self, temp_dir):
        """Test that existing files are not overwritten."""
        from agenticcli.commands.worktree import create_planning_folder

        plan_path = temp_dir / "test_plan"
        live_dir = plan_path / "live"
        live_dir.mkdir(parents=True)

        # Create existing file with custom content
        existing_file = live_dir / "plan_live_teach.yml"
        existing_file.write_text("# Custom content\n")

        create_planning_folder(plan_path)

        # Should preserve existing content
        assert existing_file.read_text() == "# Custom content\n"


class TestWorktreeList:
    """Tests for 'agentic worktree list' command."""

    def test_list_help(self, cli_runner):
        """Test worktree list --help output."""
        stdout, stderr, code = cli_runner(["worktree", "list", "--help"])
        assert "list" in stdout.lower()
        assert code == 0

    def test_list_not_in_git_repo(self, cli_runner, temp_dir):
        """Test list when not in a git repo."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner(["worktree", "list"])
            # Should handle gracefully - either error or empty list
            assert code in [0, 1]
        finally:
            os.chdir(original_cwd)


class TestWorktreeCreate:
    """Tests for 'agentic worktree create' command."""

    def test_create_help(self, cli_runner):
        """Test worktree create --help output."""
        stdout, stderr, code = cli_runner(["worktree", "create", "--help"])
        assert "create" in stdout.lower()
        assert "branch" in stdout
        assert "--base" in stdout
        assert "--no-plan" in stdout
        assert code == 0

    def test_create_missing_branch(self, cli_runner):
        """Test create without branch argument."""
        stdout, stderr, code = cli_runner(["worktree", "create"])
        # Should show usage error
        assert code == 2  # argparse error


class TestWorktreeRemove:
    """Tests for 'agentic worktree remove' command."""

    def test_remove_help(self, cli_runner):
        """Test worktree remove --help output."""
        stdout, stderr, code = cli_runner(["worktree", "remove", "--help"])
        assert "remove" in stdout.lower()
        assert "branch" in stdout
        assert "--force" in stdout
        assert code == 0

    def test_remove_missing_branch(self, cli_runner):
        """Test remove without branch argument."""
        stdout, stderr, code = cli_runner(["worktree", "remove"])
        # Should show usage error
        assert code == 2  # argparse error


class TestWorktreeStatus:
    """Tests for 'agentic worktree status' command."""

    def test_status_help(self, cli_runner):
        """Test worktree status --help output."""
        stdout, stderr, code = cli_runner(["worktree", "status", "--help"])
        assert "status" in stdout.lower()
        assert code == 0

    def test_status_in_git_repo(self, cli_runner):
        """Test status in current git repo."""
        stdout, stderr, code = cli_runner(["worktree", "status"])
        # Should show status info
        assert "Worktree Status" in stdout or "branch" in stdout.lower()
        assert code == 0

    def test_status_json_output(self, cli_runner):
        """Test status with --json flag."""
        stdout, stderr, code = cli_runner(["--json", "worktree", "status"])
        assert code == 0
        # Should be valid JSON with expected fields
        import json

        data = json.loads(stdout)
        assert "path" in data
        assert "branch" in data
        assert "changes" in data

    def test_status_not_in_git_repo(self, temp_dir):
        """Test status when not in a git repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout
        from unittest.mock import patch

        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            exit_code = 0

            with patch.object(sys, "argv", ["agentic", "worktree", "status"]):
                with redirect_stdout(stdout_capture):
                    with redirect_stderr(stderr_capture):
                        try:
                            from agenticcli.cli import run_cli

                            run_cli()
                        except SystemExit as e:
                            exit_code = e.code if e.code is not None else 0

            stdout = stdout_capture.getvalue()
            stderr = stderr_capture.getvalue()
            combined = stdout.lower() + stderr.lower()
            assert exit_code == 1
            assert "error" in combined or "project" in combined
        finally:
            os.chdir(original_cwd)
