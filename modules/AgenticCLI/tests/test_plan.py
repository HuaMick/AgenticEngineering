"""Tests for plan commands."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


class TestPlanStatus:
    """Tests for 'agentic plan status' command."""

    def test_status_with_path(self, cli_runner, temp_repo):
        """Test status with explicit path."""
        plan_path = temp_repo / "docs" / "plans" / "live" / "260103AE_test"
        stdout, stderr, code = cli_runner(["plan", "status", str(plan_path)])
        assert "Plan Status: 260103AE_test" in stdout
        assert "Completed: 1" in stdout or "completed" in stdout.lower()
        assert code == 0

    def test_status_auto_detect(self, cli_runner, mock_cwd):
        """Test status with auto-detection."""
        stdout, stderr, code = cli_runner(["plan", "status"])
        assert "Plan Status:" in stdout
        assert code == 0


class TestPlanValidate:
    """Tests for 'agentic plan validate' command."""

    def test_validate_valid_plan(self, cli_runner, temp_repo):
        """Test validating a valid plan folder."""
        plan_path = temp_repo / "docs" / "plans" / "live" / "260103AE_test"
        stdout, stderr, code = cli_runner(["plan", "validate", str(plan_path)])
        assert "Validating:" in stdout
        assert code == 0

    def test_validate_missing_path(self, cli_runner, temp_dir):
        """Test validating a non-existent path."""
        stdout, stderr, code = cli_runner(["plan", "validate", str(temp_dir / "nonexistent")])
        assert "does not exist" in stderr or code == 1

    def test_validate_missing_live_dir(self, cli_runner, temp_dir):
        """Test validating a plan without live/ directory."""
        plan_path = temp_dir / "invalid_plan"
        plan_path.mkdir()
        stdout, stderr, code = cli_runner(["plan", "validate", str(plan_path)])
        assert "Missing live/" in stdout or code == 1


class TestPlanList:
    """Tests for 'agentic plan list' command."""

    def test_list_plans(self, cli_runner, mock_cwd):
        """Test listing all plans."""
        stdout, stderr, code = cli_runner(["plan", "list"])
        assert "Plans in Repository" in stdout
        assert "260103AE_test" in stdout
        assert code == 0

    def test_list_empty_repo(self, cli_runner, temp_dir):
        """Test listing plans in empty repo."""
        # Create empty plans directory
        plans_dir = temp_dir / "docs" / "plans" / "live"
        plans_dir.mkdir(parents=True)

        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner(["plan", "list"])
            assert "Plans in Repository" in stdout or "No plan folders" in stdout
            assert code == 0
        finally:
            os.chdir(original_cwd)


class TestPlanScaffold:
    """Tests for 'agentic plan scaffold' command."""

    def test_scaffold_creates_structure(self, cli_runner, temp_dir):
        """Test scaffold creates proper folder structure."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner(["plan", "scaffold", "260103AE_new_feature"])

            # Check output
            assert "Created planning folder" in stdout
            assert code == 0

            # Verify structure
            plan_path = temp_dir / "docs" / "plans" / "live" / "260103AE_new_feature"
            assert plan_path.exists()
            assert (plan_path / "live").exists()
            assert (plan_path / "completed").exists()
        finally:
            os.chdir(original_cwd)

    def test_scaffold_existing_folder(self, cli_runner, mock_cwd, temp_repo):
        """Test scaffold fails if folder exists."""
        stdout, stderr, code = cli_runner(["plan", "scaffold", "260103AE_test"])
        assert "already exists" in stderr
        assert code == 1


class TestPlanTask:
    """Tests for 'agentic plan task start/complete' commands."""

    def test_task_start(self, cli_runner, temp_repo):
        """Test starting a task."""
        plan_path = temp_repo / "docs" / "plans" / "live" / "260103AE_test"
        stdout, stderr, code = cli_runner(["plan", "task", "start", "02", "--plan", str(plan_path)])
        assert "in_progress" in stdout
        assert code == 0

        # Verify the file was updated
        plan_file = plan_path / "live" / "plan_test.yml"
        content = yaml.safe_load(plan_file.read_text())
        phases = content["plan"]["phases"]
        phase_02 = next(p for p in phases if p["id"] == "02")
        assert phase_02["status"] == "in_progress"

    def test_task_complete(self, cli_runner, temp_repo):
        """Test completing a task."""
        plan_path = temp_repo / "docs" / "plans" / "live" / "260103AE_test"
        stdout, stderr, code = cli_runner(["plan", "task", "complete", "02", "--plan", str(plan_path)])
        assert "completed" in stdout
        assert code == 0

    def test_task_not_found(self, cli_runner, temp_repo):
        """Test starting a non-existent task."""
        plan_path = temp_repo / "docs" / "plans" / "live" / "260103AE_test"
        stdout, stderr, code = cli_runner(["plan", "task", "start", "99", "--plan", str(plan_path)])
        assert "not found" in stderr
        assert code == 1
