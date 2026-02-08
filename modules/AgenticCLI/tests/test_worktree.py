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
        """Test that planning folder structure is created (flattened)."""
        from agenticcli.commands.worktree import create_planning_folder

        plan_path = temp_dir / "test_plan"
        create_planning_folder(plan_path)

        # Flattened: plan_path is the main directory
        assert plan_path.exists()

    def test_creates_placeholder_files(self, temp_dir):
        """Test that placeholder YAML files are created (flattened)."""
        from agenticcli.commands.worktree import create_planning_folder

        plan_path = temp_dir / "test_plan"
        create_planning_folder(plan_path)

        # Flattened: files directly in plan_path
        assert (plan_path / "plan_teach.yml").exists()
        assert (plan_path / "plan_test.yml").exists()
        assert (plan_path / "plan_audit_clean.yml").exists()

    def test_creates_completed_placeholder(self, temp_dir):
        """Test that completed placeholder is created (flattened)."""
        from agenticcli.commands.worktree import create_planning_folder

        plan_path = temp_dir / "test_plan"
        create_planning_folder(plan_path)

        # Flattened: plan_completed.yml directly in plan_path
        assert (plan_path / "plan_completed.yml").exists()

    def test_does_not_overwrite_existing(self, temp_dir):
        """Test that existing files are not overwritten (flattened)."""
        from agenticcli.commands.worktree import create_planning_folder

        plan_path = temp_dir / "test_plan"
        plan_path.mkdir(parents=True)

        # Create existing file with custom content (flattened naming)
        existing_file = plan_path / "plan_teach.yml"
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


class TestStubTemplates:
    """Tests for stub template generation and detection (FF-007)."""

    def test_stub_templates_have_header(self, temp_dir):
        """Test that generated stub files contain template header (flattened)."""
        from agenticcli.commands.worktree import STUB_TEMPLATE_HEADER, create_planning_folder

        plan_path = temp_dir / "test_plan_stubs"
        create_planning_folder(plan_path)

        # Flattened: files directly in plan_path
        for filename in ["plan_teach.yml", "plan_test.yml", "plan_audit_clean.yml"]:
            content = (plan_path / filename).read_text()
            assert "TEMPLATE FILE - ACTION REQUIRED" in content
            assert "OPTIONS:" in content
            assert "POPULATE:" in content
            assert "DELETE:" in content

    def test_stub_templates_have_status_field(self, temp_dir):
        """Test that generated stub files contain _template_status: stub field (flattened)."""
        from agenticcli.commands.worktree import create_planning_folder

        plan_path = temp_dir / "test_plan_stubs"
        create_planning_folder(plan_path)

        # Flattened: files directly in plan_path
        for filename in ["plan_teach.yml", "plan_test.yml", "plan_audit_clean.yml"]:
            content = (plan_path / filename).read_text()
            assert "_template_status: stub" in content

    def test_stub_templates_have_todo_markers(self, temp_dir):
        """Test that generated stub files contain TODO markers with guidance (flattened)."""
        from agenticcli.commands.worktree import create_planning_folder

        plan_path = temp_dir / "test_plan_stubs"
        create_planning_folder(plan_path)

        # Flattened: files directly in plan_path
        for filename in ["plan_teach.yml", "plan_test.yml", "plan_audit_clean.yml"]:
            content = (plan_path / filename).read_text()
            assert "TODO:" in content


class TestIsStubTemplate:
    """Tests for is_stub_template() detection function."""

    def test_detects_template_status_stub(self):
        """Test detection via _template_status: stub field."""
        from agenticcli.commands.plan import is_stub_template

        content = {
            "_template_status": "stub",
            "plan": {"name": "Test", "phases": []},
        }
        assert is_stub_template(content) is True

    def test_detects_legacy_empty_stub(self):
        """Test detection of legacy empty stubs with TODO in objective."""
        from agenticcli.commands.plan import is_stub_template

        content = {
            "plan": {
                "name": "Test",
                "objective": "TODO: Describe the objective",
                "phases": [],
            }
        }
        assert is_stub_template(content) is True

    def test_rejects_active_plan(self):
        """Test that active plans are not flagged as stubs."""
        from agenticcli.commands.plan import is_stub_template

        content = {
            "_template_status": "active",
            "plan": {
                "name": "Real Plan",
                "objective": "Implement user authentication",
                "phases": [{"name": "Phase 1", "tasks": []}],
            },
        }
        assert is_stub_template(content) is False

    def test_rejects_populated_plan(self):
        """Test that populated plans without _template_status are not flagged."""
        from agenticcli.commands.plan import is_stub_template

        content = {
            "plan": {
                "name": "Real Plan",
                "objective": "Implement something useful",
                "phases": [{"name": "Phase 1", "tasks": []}],
            }
        }
        assert is_stub_template(content) is False

    def test_handles_empty_content(self):
        """Test handling of empty/None content."""
        from agenticcli.commands.plan import is_stub_template

        assert is_stub_template(None) is False
        assert is_stub_template({}) is False


class TestWorktreeValidate:
    """Tests for worktree validate helpers and cmd_validate logic (WS-007)."""

    # --- Helper function tests ---

    @patch("subprocess.run")
    def test_get_actual_worktrees_parses_porcelain(self, mock_run, temp_dir):
        """Test that porcelain output is correctly parsed into dicts."""
        from agenticcli.commands.worktree import get_actual_worktrees

        mock_run.return_value = MagicMock(
            stdout=(
                "worktree /home/code/Repo\n"
                "HEAD abc1234\n"
                "branch refs/heads/main\n"
                "\n"
                "worktree /home/code/Repo-feature\n"
                "HEAD def5678\n"
                "branch refs/heads/feature-x\n"
                "\n"
            ),
            returncode=0,
        )

        result = get_actual_worktrees(temp_dir)
        assert len(result) == 2
        assert result[0] == {"path": "/home/code/Repo", "branch": "main"}
        assert result[1] == {"path": "/home/code/Repo-feature", "branch": "feature-x"}

    @patch("subprocess.run")
    def test_get_actual_worktrees_empty_on_error(self, mock_run, temp_dir):
        """Test that subprocess failure returns empty list."""
        from agenticcli.commands.worktree import get_actual_worktrees

        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        result = get_actual_worktrees(temp_dir)
        assert result == []

    def test_get_live_plan_folders_finds_dirs(self, temp_dir):
        """Test that plan directories are discovered and returned sorted."""
        from agenticcli.commands.worktree import get_live_plan_folders

        plan_dir = temp_dir / "docs" / "plans" / "live"
        plan_dir.mkdir(parents=True)
        (plan_dir / "260208WS_worktree_sync").mkdir()
        (plan_dir / "260207AB_other_plan").mkdir()
        # Also add a file to make sure it's excluded
        (plan_dir / "README.md").write_text("# Plans\n")

        result = get_live_plan_folders(temp_dir)
        assert result == ["260207AB_other_plan", "260208WS_worktree_sync"]

    def test_get_live_plan_folders_empty_if_no_dir(self, temp_dir):
        """Test that missing plan directory returns empty list."""
        from agenticcli.commands.worktree import get_live_plan_folders

        result = get_live_plan_folders(temp_dir)
        assert result == []

    # --- Validation logic tests (mock helpers) ---

    @patch("agenticcli.commands.worktree.get_repo_root")
    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.worktree.load_worktree_registry")
    @patch("agenticcli.commands.worktree.get_live_plan_folders")
    @patch("agenticcli.console.is_json_output", return_value=True)
    @patch("agenticcli.console.print_json")
    def test_validate_all_clean(
        self, mock_pj, mock_json, mock_plans, mock_registry, mock_wts, mock_root, temp_dir
    ):
        """Test validation passes when everything is in sync."""
        from agenticcli.commands.worktree import cmd_validate

        mock_root.return_value = temp_dir
        mock_wts.return_value = [
            {"path": str(temp_dir), "branch": "main"},
            {"path": str(temp_dir / "feat"), "branch": "feature-x"},
        ]
        mock_registry.return_value = [
            {"branch": "feature-x", "abbreviation": "FX"},
        ]
        mock_plans.return_value = ["260208FX_feature-x"]

        with pytest.raises(SystemExit) as exc_info:
            cmd_validate(MagicMock())
        assert exc_info.value.code == 0

    @patch("agenticcli.commands.worktree.get_repo_root")
    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.worktree.load_worktree_registry")
    @patch("agenticcli.commands.worktree.get_live_plan_folders")
    @patch("agenticcli.console.is_json_output", return_value=True)
    @patch("agenticcli.console.print_json")
    def test_validate_orphaned_plans(
        self, mock_pj, mock_json, mock_plans, mock_registry, mock_wts, mock_root, temp_dir
    ):
        """Test detection of plan folders with no matching worktree."""
        from agenticcli.commands.worktree import cmd_validate

        mock_root.return_value = temp_dir
        # Only main worktree exists
        mock_wts.return_value = [
            {"path": str(temp_dir), "branch": "main"},
        ]
        mock_registry.return_value = []
        # Plan exists but no worktree for it
        mock_plans.return_value = ["260208AB_old_feature"]

        with pytest.raises(SystemExit) as exc_info:
            cmd_validate(MagicMock())
        assert exc_info.value.code == 1

    @patch("agenticcli.commands.worktree.get_repo_root")
    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.worktree.load_worktree_registry")
    @patch("agenticcli.commands.worktree.get_live_plan_folders")
    @patch("agenticcli.console.is_json_output", return_value=True)
    @patch("agenticcli.console.print_json")
    def test_validate_stale_worktrees(
        self, mock_pj, mock_json, mock_plans, mock_registry, mock_wts, mock_root, temp_dir
    ):
        """Test detection of worktrees with no matching plan."""
        from agenticcli.commands.worktree import cmd_validate

        mock_root.return_value = temp_dir
        mock_wts.return_value = [
            {"path": str(temp_dir), "branch": "main"},
            {"path": str(temp_dir / "stale"), "branch": "stale-branch"},
        ]
        mock_registry.return_value = [
            {"branch": "stale-branch", "abbreviation": "SB"},
        ]
        # No plans at all
        mock_plans.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            cmd_validate(MagicMock())
        assert exc_info.value.code == 1

    @patch("agenticcli.commands.worktree.get_repo_root")
    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.worktree.load_worktree_registry")
    @patch("agenticcli.commands.worktree.get_live_plan_folders")
    @patch("agenticcli.console.is_json_output", return_value=True)
    @patch("agenticcli.console.print_json")
    def test_validate_registry_drift_missing(
        self, mock_pj, mock_json, mock_plans, mock_registry, mock_wts, mock_root, temp_dir
    ):
        """Test detection of registry entries for non-existent worktrees."""
        from agenticcli.commands.worktree import cmd_validate

        mock_root.return_value = temp_dir
        # Only main worktree actually exists
        mock_wts.return_value = [
            {"path": str(temp_dir), "branch": "main"},
        ]
        # Registry has an entry for a worktree that doesn't exist
        mock_registry.return_value = [
            {"branch": "deleted-branch", "abbreviation": "DB"},
        ]
        mock_plans.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            cmd_validate(MagicMock())
        assert exc_info.value.code == 1

    @patch("agenticcli.commands.worktree.get_repo_root")
    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.worktree.load_worktree_registry")
    @patch("agenticcli.commands.worktree.get_live_plan_folders")
    @patch("agenticcli.console.is_json_output", return_value=True)
    @patch("agenticcli.console.print_json")
    def test_validate_registry_drift_unregistered(
        self, mock_pj, mock_json, mock_plans, mock_registry, mock_wts, mock_root, temp_dir
    ):
        """Test detection of actual worktrees not in registry."""
        from agenticcli.commands.worktree import cmd_validate

        mock_root.return_value = temp_dir
        mock_wts.return_value = [
            {"path": str(temp_dir), "branch": "main"},
            {"path": str(temp_dir / "unreg"), "branch": "unregistered-branch"},
        ]
        # Empty registry - the worktree is unregistered
        mock_registry.return_value = []
        mock_plans.return_value = []

        with pytest.raises(SystemExit) as exc_info:
            cmd_validate(MagicMock())
        assert exc_info.value.code == 1

    @patch("agenticcli.commands.worktree.get_repo_root")
    @patch("agenticcli.commands.worktree.get_actual_worktrees")
    @patch("agenticcli.commands.worktree.load_worktree_registry")
    @patch("agenticcli.commands.worktree.get_live_plan_folders")
    @patch("agenticcli.console.is_json_output", return_value=True)
    @patch("agenticcli.console.print_json")
    def test_validate_json_output(
        self, mock_print_json, mock_json, mock_plans, mock_registry, mock_wts, mock_root, temp_dir
    ):
        """Test that JSON output contains expected structure."""
        from agenticcli.commands.worktree import cmd_validate

        mock_root.return_value = temp_dir
        mock_wts.return_value = [
            {"path": str(temp_dir), "branch": "main"},
            {"path": str(temp_dir / "feat"), "branch": "feature-y"},
        ]
        mock_registry.return_value = [
            {"branch": "feature-y", "abbreviation": "FY"},
            {"branch": "ghost", "abbreviation": "GH"},
        ]
        mock_plans.return_value = ["260208FY_feature-y", "260208ZZ_orphan"]

        with pytest.raises(SystemExit):
            cmd_validate(MagicMock())

        mock_print_json.assert_called_once()
        data = mock_print_json.call_args[0][0]

        assert "orphaned_plans" in data
        assert "stale_worktrees" in data
        assert "registry_drift" in data
        assert "valid" in data
        assert "missing_worktrees" in data["registry_drift"]
        assert "unregistered" in data["registry_drift"]
        # Verify specific findings
        assert "260208ZZ_orphan" in data["orphaned_plans"]
        assert data["valid"] is False


class TestWorktreeValidateCLI:
    """CLI integration tests for worktree validate (WS-008)."""

    def test_validate_help(self, cli_runner):
        """Test worktree validate --help shows usage."""
        stdout, stderr, code = cli_runner(["worktree", "validate", "--help"])
        assert code == 0
        assert "validate" in stdout.lower() or "validate" in stderr.lower()

    def test_validate_in_git_repo(self, cli_runner, temp_repo):
        """Test validate runs in a git repo and reports orphaned plans."""
        import shutil

        # Remove pre-created plan folder so we get a clean state
        plans_dir = temp_repo / "docs" / "plans" / "live"
        if plans_dir.exists():
            shutil.rmtree(plans_dir)

        stdout, stderr, code = cli_runner(["worktree", "validate"])
        # No plans, no feature worktrees, no registry -> clean
        assert code == 0

    def test_validate_json_output(self, cli_runner, temp_repo):
        """Test validate with --json returns valid JSON with expected keys."""
        import json as json_mod
        import shutil

        # Remove pre-created plan folder so we get a clean state
        plans_dir = temp_repo / "docs" / "plans" / "live"
        if plans_dir.exists():
            shutil.rmtree(plans_dir)

        stdout, stderr, code = cli_runner(["--json", "worktree", "validate"])
        assert code == 0
        data = json_mod.loads(stdout)
        assert "orphaned_plans" in data
        assert "stale_worktrees" in data
        assert "registry_drift" in data
        assert "valid" in data
        assert data["valid"] is True
