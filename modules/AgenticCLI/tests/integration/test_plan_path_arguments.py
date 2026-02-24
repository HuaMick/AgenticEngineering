"""Integration tests for standardized plan path arguments.

Tests the --plan/-p flag and positional path arguments for plan subcommands:
- plan status
- plan validate
- plan archive

These tests verify backward compatibility (positional args) and new flag-based arguments.
"""

import json

import pytest
import yaml

pytestmark = pytest.mark.integration


class TestPlanStatusPathArguments:
    """Integration tests for 'agentic plan status' path arguments."""

    @pytest.fixture
    def plan_with_status(self, temp_repo):
        """Create plan folder with tasks for status testing."""
        plan_path = temp_repo / "docs" / "plans" / "live" / "260202CL_status_test"
        plan_path.mkdir(parents=True)

        # Create plan file with tasks
        plan_file = plan_path / "plan_test.yml"
        plan_content = {
            "plan": {
                "name": "Status Test Plan",
                "status": "in_progress",
                "phases": [
                    {
                        "id": "phase_01",
                        "name": "Phase One",
                        "status": "in_progress",
                        "tasks": [
                            {"id": "01", "description": "Task 1", "status": "completed"},
                            {"id": "02", "description": "Task 2", "status": "pending"},
                        ]
                    }
                ]
            }
        }

        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        return plan_path

    def test_status_with_plan_flag(self, cli_runner, plan_with_status):
        """Test plan status with --plan flag."""
        result = cli_runner([
            "plan", "status",
            "--plan", str(plan_with_status)
        ])

        assert result.returncode == 0
        assert "260202CL_status_test" in result.stdout or "Status Test Plan" in result.stdout

    def test_status_with_short_plan_flag(self, cli_runner, plan_with_status):
        """Test plan status with -p short flag."""
        result = cli_runner([
            "plan", "status",
            "-p", str(plan_with_status)
        ])

        assert result.returncode == 0
        assert "260202CL_status_test" in result.stdout or "Status Test Plan" in result.stdout

    def test_status_with_positional_path(self, cli_runner, plan_with_status):
        """Test plan status with positional path argument (backward compatibility)."""
        result = cli_runner([
            "plan", "status",
            str(plan_with_status)
        ])

        assert result.returncode == 0
        assert "260202CL_status_test" in result.stdout or "Status Test Plan" in result.stdout

    def test_status_with_folder_name_match(self, cli_runner, plan_with_status):
        """Test plan status with partial folder name (searches in docs/plans/live)."""
        result = cli_runner([
            "plan", "status",
            "--plan", "260202CL_status_test"
        ])

        assert result.returncode == 0
        assert "260202CL_status_test" in result.stdout or "Status Test Plan" in result.stdout

    def test_status_with_plan_flag_json_output(self, cli_runner, plan_with_status):
        """Test plan status with --plan flag and JSON output."""
        result = cli_runner([
            "-j",
            "plan", "status",
            "--plan", str(plan_with_status)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "plan_folder" in data or "status" in data

    def test_status_plan_flag_priority_over_positional(self, cli_runner, plan_with_status, temp_repo):
        """Test that --plan flag takes priority over positional argument."""
        # Create a second plan folder
        other_plan = temp_repo / "docs" / "plans" / "live" / "260202CL_other_plan"
        other_plan.mkdir(parents=True)

        other_plan_file = other_plan / "plan_other.yml"
        other_content = {
            "plan": {
                "name": "Other Plan",
                "status": "pending",
                "phases": []
            }
        }
        with open(other_plan_file, "w") as f:
            yaml.dump(other_content, f)

        # Pass both positional and --plan flag; --plan should win
        result = cli_runner([
            "plan", "status",
            str(other_plan),  # positional (should be ignored)
            "--plan", str(plan_with_status)  # flag (should be used)
        ])

        assert result.returncode == 0
        # Should show the plan_with_status, not other_plan
        assert "Status Test Plan" in result.stdout or "260202CL_status_test" in result.stdout

    def test_status_nonexistent_plan(self, cli_runner):
        """Test plan status with nonexistent plan path."""
        result = cli_runner([
            "plan", "status",
            "--plan", "/nonexistent/plan/folder"
        ])

        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


class TestPlanValidatePathArguments:
    """Integration tests for 'agentic plan validate' path arguments."""

    @pytest.fixture
    def plan_to_validate(self, temp_repo):
        """Create plan folder for validation testing."""
        plan_path = temp_repo / "docs" / "plans" / "live" / "260202CL_validate_test"
        plan_path.mkdir(parents=True)

        # Create valid plan file
        plan_file = plan_path / "plan_build.yml"
        plan_content = {
            "plan": {
                "name": "Validate Test Plan",
                "status": "in_progress",
                "phases": [
                    {
                        "id": "build_01",
                        "name": "Build Phase",
                        "status": "pending",
                        "tasks": []
                    }
                ]
            }
        }

        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        return plan_path

    def test_validate_with_plan_flag(self, cli_runner, plan_to_validate):
        """Test plan validate with --plan flag."""
        result = cli_runner([
            "agent", "plan", "validate",
            "--plan", str(plan_to_validate)
        ])

        assert result.returncode == 0
        assert "valid" in result.stdout.lower() or "pass" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_validate_with_short_plan_flag(self, cli_runner, plan_to_validate):
        """Test plan validate with -p short flag."""
        result = cli_runner([
            "agent", "plan", "validate",
            "-p", str(plan_to_validate)
        ])

        assert result.returncode == 0
        assert "valid" in result.stdout.lower() or "pass" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_validate_with_positional_path(self, cli_runner, plan_to_validate):
        """Test plan validate with positional path argument (backward compatibility)."""
        result = cli_runner([
            "agent", "plan", "validate",
            str(plan_to_validate)
        ])

        assert result.returncode == 0
        assert "valid" in result.stdout.lower() or "pass" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_validate_with_folder_name_match(self, cli_runner, plan_to_validate):
        """Test plan validate with partial folder name."""
        result = cli_runner([
            "agent", "plan", "validate",
            "--plan", "260202CL_validate_test"
        ])

        assert result.returncode == 0
        assert "valid" in result.stdout.lower() or "pass" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_validate_with_strict_flag(self, cli_runner, plan_to_validate):
        """Test plan validate with --strict option.

        Strict mode requires orchestration_*.mmd files. Since the test fixture
        doesn't include one, strict validation should fail with an error about
        missing orchestration file.
        """
        result = cli_runner([
            "agent", "plan", "validate",
            "--plan", str(plan_to_validate),
            "--strict"
        ])

        # Strict mode should fail because fixture lacks orchestration_*.mmd
        assert result.returncode == 1
        assert "orchestration" in result.stdout.lower() or "missing" in result.stdout.lower()

    def test_validate_with_plan_flag_json_output(self, cli_runner, plan_to_validate):
        """Test plan validate with --plan flag and JSON output."""
        result = cli_runner([
            "-j",
            "agent", "plan", "validate",
            "--plan", str(plan_to_validate)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "valid" in data or "errors" in data or "status" in data

    def test_validate_plan_flag_priority(self, cli_runner, plan_to_validate, temp_repo):
        """Test that --plan flag takes priority over positional argument."""
        # Create a second plan folder with invalid YAML
        invalid_plan = temp_repo / "docs" / "plans" / "live" / "260202CL_invalid_plan"
        invalid_plan.mkdir(parents=True)

        invalid_file = invalid_plan / "plan_invalid.yml"
        invalid_file.write_text("invalid: [unclosed bracket")

        # Pass both; --plan should win (valid plan)
        result = cli_runner([
            "agent", "plan", "validate",
            str(invalid_plan),  # positional (should be ignored)
            "--plan", str(plan_to_validate)  # flag (should be used)
        ])

        assert result.returncode == 0
        assert "valid" in result.stdout.lower() or "pass" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_validate_nonexistent_plan(self, cli_runner):
        """Test plan validate with nonexistent plan path."""
        result = cli_runner([
            "agent", "plan", "validate",
            "--plan", "/nonexistent/validate/folder"
        ])

        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


class TestPlanArchivePathArguments:
    """Integration tests for 'agentic plan archive' path arguments."""

    @pytest.fixture
    def plan_to_archive(self, temp_repo):
        """Create plan folder for archival testing."""
        # Create completed directory
        completed_dir = temp_repo / "docs" / "plans" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)

        # Create plan folder to archive
        plan_path = temp_repo / "docs" / "plans" / "live" / "260202CL_archive_test"
        plan_path.mkdir(parents=True)

        # Create plan file
        plan_file = plan_path / "plan_completed.yml"
        plan_content = {
            "plan": {
                "name": "Archive Test Plan",
                "status": "completed",
                "phases": [
                    {
                        "id": "test_01",
                        "name": "Test Phase",
                        "status": "completed",
                        "tasks": [
                            {"id": "01", "description": "Done", "status": "completed"}
                        ]
                    }
                ]
            }
        }

        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        return plan_path

    def test_archive_with_plan_flag(self, cli_runner, plan_to_archive, temp_repo):
        """Test plan archive with --plan flag."""
        result = cli_runner([
            "agent", "plan", "archive",
            "--plan", str(plan_to_archive)
        ])

        assert result.returncode == 0
        assert "archived" in result.stdout.lower() or "completed" in result.stdout.lower()

        # Verify archived folder exists
        archived_path = temp_repo / "docs" / "plans" / "completed" / "260202CL_archive_test"
        assert archived_path.exists()

    def test_archive_with_short_plan_flag(self, cli_runner, plan_to_archive, temp_repo):
        """Test plan archive with -p short flag."""
        result = cli_runner([
            "agent", "plan", "archive",
            "-p", str(plan_to_archive)
        ])

        assert result.returncode == 0
        assert "archived" in result.stdout.lower() or "completed" in result.stdout.lower()

        # Verify archived folder exists
        archived_path = temp_repo / "docs" / "plans" / "completed" / "260202CL_archive_test"
        assert archived_path.exists()

    def test_archive_with_positional_path(self, cli_runner, plan_to_archive, temp_repo):
        """Test plan archive with positional path argument (backward compatibility)."""
        result = cli_runner([
            "agent", "plan", "archive",
            str(plan_to_archive)
        ])

        assert result.returncode == 0
        assert "archived" in result.stdout.lower() or "completed" in result.stdout.lower()

        # Verify archived folder exists
        archived_path = temp_repo / "docs" / "plans" / "completed" / "260202CL_archive_test"
        assert archived_path.exists()

    def test_archive_with_folder_name_match(self, cli_runner, plan_to_archive, temp_repo):
        """Test plan archive with partial folder name."""
        result = cli_runner([
            "agent", "plan", "archive",
            "--plan", "260202CL_archive_test"
        ])

        assert result.returncode == 0
        assert "archived" in result.stdout.lower() or "completed" in result.stdout.lower()

        # Verify archived folder exists
        archived_path = temp_repo / "docs" / "plans" / "completed" / "260202CL_archive_test"
        assert archived_path.exists()

    def test_archive_without_path_argument_fails(self, cli_runner):
        """Test plan archive without any path argument fails."""
        result = cli_runner([
            "agent", "plan", "archive"
        ])

        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_archive_nonexistent_plan(self, cli_runner):
        """Test plan archive with nonexistent plan path."""
        result = cli_runner([
            "agent", "plan", "archive",
            "--plan", "/nonexistent/archive/folder"
        ])

        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_archive_plan_flag_priority(self, cli_runner, plan_to_archive, temp_repo):
        """Test that --plan flag takes priority over positional argument."""
        # Create a second plan folder
        other_plan = temp_repo / "docs" / "plans" / "live" / "260202CL_other_archive"
        other_plan.mkdir(parents=True)

        other_plan_file = other_plan / "plan_completed.yml"
        other_content = {
            "plan": {
                "name": "Other Archive Plan",
                "status": "completed",
                "phases": []
            }
        }
        with open(other_plan_file, "w") as f:
            yaml.dump(other_content, f)

        # Pass both positional and --plan flag; --plan should win
        result = cli_runner([
            "agent", "plan", "archive",
            str(other_plan),  # positional (should be ignored)
            "--plan", str(plan_to_archive)  # flag (should be used)
        ])

        assert result.returncode == 0
        assert "archived" in result.stdout.lower() or "completed" in result.stdout.lower()

        # Verify the correct plan was archived
        archived_path = temp_repo / "docs" / "plans" / "completed" / "260202CL_archive_test"
        assert archived_path.exists()

        # Verify the other plan was NOT archived
        other_archived = temp_repo / "docs" / "plans" / "completed" / "260202CL_other_archive"
        assert not other_archived.exists()
