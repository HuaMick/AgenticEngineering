"""Tests for plan commands.

NOTE: The 'agentic plan' command has been removed. All plan functionality
has been migrated to 'agentic epic'. These tests verify that the old plan
commands correctly print an error message and exit with code 1.
"""

import yaml


class TestPlanStatus:
    """Tests for 'agentic plan status' command - now removed."""

    def test_status_with_path(self, cli_runner, temp_repo):
        """Test plan status now returns command-removed error."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260103AE_test"
        stdout, stderr, code = cli_runner(["plan", "status", str(plan_path)])
        assert code == 1
        assert "Command removed" in stderr or "agentic epic" in stderr

    def test_status_auto_detect(self, cli_runner, mock_cwd):
        """Test plan status auto-detect now returns command-removed error."""
        stdout, stderr, code = cli_runner(["plan", "status"])
        assert code == 1
        assert "Command removed" in stderr or "agentic epic" in stderr


class TestPlanValidate:
    """Tests for 'agentic plan validate' command - now removed."""

    def test_validate_valid_plan(self, cli_runner, temp_repo):
        """Test plan validate now returns command-removed error."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260103AE_test"
        stdout, stderr, code = cli_runner(["agent", "plan", "validate", str(plan_path)])
        assert code == 1
        assert "Command removed" in stderr or "agentic epic" in stderr

    def test_validate_missing_path(self, cli_runner, temp_dir):
        """Test plan validate with non-existent path now returns command-removed error."""
        stdout, stderr, code = cli_runner(["agent", "plan", "validate", str(temp_dir / "nonexistent")])
        assert code == 1

    def test_validate_missing_plan_files(self, cli_runner, temp_dir):
        """Test plan validate without plan files now returns command-removed error."""
        plan_path = temp_dir / "invalid_plan"
        plan_path.mkdir()
        stdout, stderr, code = cli_runner(["agent", "plan", "validate", str(plan_path)])
        assert code == 1


class TestPlanList:
    """Tests for 'agentic plan list' command - now removed."""

    def test_list_plans(self, cli_runner, mock_cwd):
        """Test plan list now returns command-removed error."""
        stdout, stderr, code = cli_runner(["plan", "list"])
        assert code == 1
        assert "Command removed" in stderr or "agentic epic" in stderr

    def test_list_empty_repo(self, cli_runner, temp_repo):
        """Test plan list in empty repo now returns command-removed error."""
        stdout, stderr, code = cli_runner(["plan", "list"])
        assert code == 1
        assert "Command removed" in stderr or "agentic epic" in stderr


class TestPlanScaffold:
    """Tests for 'agentic plan scaffold' command - now removed."""

    def test_scaffold_creates_structure(self, cli_runner, temp_repo):
        """Test plan scaffold now returns command-removed error."""
        stdout, stderr, code = cli_runner(["agent", "plan", "scaffold", "260103AE_new_feature"])
        assert code == 1
        assert "Command removed" in stderr or "agentic epic" in stderr

    def test_scaffold_existing_folder(self, cli_runner, mock_cwd, temp_repo):
        """Test plan scaffold for existing folder now returns command-removed error."""
        stdout, stderr, code = cli_runner(["agent", "plan", "scaffold", "260103AE_test"])
        assert code == 1
        assert "Command removed" in stderr or "agentic epic" in stderr


class TestPlanTask:
    """Tests for 'agentic plan task start/complete' commands - now removed."""

    def test_task_start(self, cli_runner, temp_repo):
        """Test plan task start now returns command-removed error."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260103AE_test"
        stdout, stderr, code = cli_runner(["agent", "plan", "task", "start", "02", "--plan", str(plan_path)])
        assert code == 1
        assert "Command removed" in stderr or "agentic epic" in stderr

    def test_task_complete(self, cli_runner, temp_repo):
        """Test plan task complete now returns command-removed error."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260103AE_test"
        stdout, stderr, code = cli_runner(
            ["agent", "plan", "task", "complete", "02", "--plan", str(plan_path)]
        )
        assert code == 1
        assert "Command removed" in stderr or "agentic epic" in stderr

    def test_task_not_found(self, cli_runner, temp_repo):
        """Test plan task with nonexistent task now returns command-removed error."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260103AE_test"
        stdout, stderr, code = cli_runner(["agent", "plan", "task", "start", "99", "--plan", str(plan_path)])
        assert code == 1
        assert "Command removed" in stderr or "agentic epic" in stderr
