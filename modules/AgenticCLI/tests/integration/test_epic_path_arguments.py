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


@pytest.mark.story("US-PLN-001")
class TestPlanStatusPathArguments:
    """Integration tests for 'agentic plan status' path arguments."""

    @pytest.fixture
    def plan_with_status(self, temp_repo, tinydb_populator):
        """Create plan folder with tasks for status testing."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260202CL_status_test"
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
                        "tickets": [
                            {"id": "01", "description": "Task 1", "status": "completed"},
                            {"id": "02", "description": "Task 2", "status": "pending"},
                        ]
                    }
                ]
            }
        }

        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Populate TinyDB so cmd_status can find the epic
        tinydb_populator("260202CL_status_test", plan_path, {
            "name": "Status Test Plan",
            "status": "in_progress",
            "phases": [
                {
                    "name": "Phase One",
                    "tickets": [
                        {"id": "01", "name": "Task 1", "description": "Task 1", "status": "completed"},
                        {"id": "02", "name": "Task 2", "description": "Task 2", "status": "pending"},
                    ],
                }
            ],
        })

        return plan_path

    def test_status_with_plan_flag(self, cli_runner, plan_with_status):
        """Test plan status with --plan flag."""
        result = cli_runner([
            "epic", "status",
            "--plan", str(plan_with_status)
        ])

        assert result.returncode == 0
        assert "260202CL_status_test" in result.stdout or "Status Test Plan" in result.stdout

    def test_status_with_short_plan_flag(self, cli_runner, plan_with_status):
        """Test plan status with -p short flag."""
        result = cli_runner([
            "epic", "status",
            "-p", str(plan_with_status)
        ])

        assert result.returncode == 0
        assert "260202CL_status_test" in result.stdout or "Status Test Plan" in result.stdout

    def test_status_with_positional_path(self, cli_runner, plan_with_status):
        """Test plan status with positional path argument (backward compatibility)."""
        result = cli_runner([
            "epic", "status",
            str(plan_with_status)
        ])

        assert result.returncode == 0
        assert "260202CL_status_test" in result.stdout or "Status Test Plan" in result.stdout

    def test_status_with_folder_name_match(self, cli_runner, plan_with_status):
        """Test plan status with partial folder name (searches in docs/epics/live)."""
        result = cli_runner([
            "epic", "status",
            "--plan", "260202CL_status_test"
        ])

        assert result.returncode == 0
        assert "260202CL_status_test" in result.stdout or "Status Test Plan" in result.stdout

    def test_status_with_plan_flag_json_output(self, cli_runner, plan_with_status):
        """Test plan status with --plan flag and JSON output."""
        result = cli_runner([
            "-j",
            "epic", "status",
            "--plan", str(plan_with_status)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "plan_folder" in data or "status" in data

    def test_status_plan_flag_priority_over_positional(self, cli_runner, plan_with_status, temp_repo, tinydb_populator):
        """Test that --plan flag takes priority over positional argument."""
        # Create a second plan folder
        other_plan = temp_repo / "docs" / "epics" / "live" / "260202CL_other_plan"
        other_plan.mkdir(parents=True)

        other_plan_file = other_plan / "plan_other.yml"
        other_content = {
            "plan": {
                "name": "Other Plan",
                "status": "planning",
                "phases": []
            }
        }
        with open(other_plan_file, "w") as f:
            yaml.dump(other_content, f)

        # Also register other plan in TinyDB
        tinydb_populator("260202CL_other_plan", other_plan, {
            "name": "Other Plan",
            "status": "planning",
            "phases": [],
        })

        # Pass both positional and --plan flag; --plan should win
        result = cli_runner([
            "epic", "status",
            str(other_plan),  # positional (should be ignored)
            "--plan", str(plan_with_status)  # flag (should be used)
        ])

        assert result.returncode == 0
        # Should show the plan_with_status, not other_plan
        assert "Status Test Plan" in result.stdout or "260202CL_status_test" in result.stdout

    def test_status_nonexistent_plan(self, cli_runner):
        """Test plan status with nonexistent plan path."""
        result = cli_runner([
            "epic", "status",
            "--plan", "/nonexistent/plan/folder"
        ])

        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


@pytest.mark.story("US-PLN-001")
class TestPlanValidatePathArguments:
    """Integration tests for 'agentic epic status --validate' path arguments."""

    @pytest.fixture
    def plan_to_validate(self, temp_repo, tinydb_populator):
        """Create plan folder for validation testing."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260202CL_validate_test"
        plan_path.mkdir(parents=True)

        # Register in TinyDB so cmd_status finds the epic
        tinydb_populator("260202CL_validate_test", plan_path, {
            "name": "Validate Test Plan",
            "status": "in_progress",
            "phases": [
                {"name": "Build Phase", "tickets": []},
            ],
        })

        return plan_path

    def test_validate_with_plan_flag(self, cli_runner, plan_to_validate):
        """Test epic status --validate with --plan flag."""
        result = cli_runner([
            "epic", "status",
            "--validate",
            "--plan", str(plan_to_validate)
        ])

        assert result.returncode == 0
        combined = result.stdout.lower() + result.stderr.lower()
        assert "validation" in combined or "pass" in combined or "status" in combined

    def test_validate_with_short_plan_flag(self, cli_runner, plan_to_validate):
        """Test epic status --validate with -p short flag."""
        result = cli_runner([
            "epic", "status",
            "--validate",
            "-p", str(plan_to_validate)
        ])

        assert result.returncode == 0

    def test_validate_with_positional_path(self, cli_runner, plan_to_validate):
        """Test epic status --validate with positional path argument."""
        result = cli_runner([
            "epic", "status",
            "--validate",
            str(plan_to_validate)
        ])

        assert result.returncode == 0

    def test_validate_with_folder_name_match(self, cli_runner, plan_to_validate):
        """Test epic status --validate with partial folder name."""
        result = cli_runner([
            "epic", "status",
            "--validate",
            "--plan", "260202CL_validate_test"
        ])

        assert result.returncode == 0

    def test_validate_with_strict_flag(self, cli_runner, plan_to_validate):
        """Test epic status --validate --strict.

        Strict mode requires orchestration phases in TinyDB. Since the test fixture
        doesn't include them, strict validation should fail.
        """
        result = cli_runner([
            "epic", "status",
            "--validate", "--strict",
            "--plan", str(plan_to_validate),
        ])

        # Strict mode should fail because fixture lacks orchestration phases
        assert result.returncode == 1

    def test_validate_with_plan_flag_json_output(self, cli_runner, plan_to_validate):
        """Test epic status --validate with JSON output."""
        result = cli_runner([
            "-j",
            "epic", "status",
            "--validate",
            "--plan", str(plan_to_validate)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "validation" in data or "status" in data

    def test_validate_nonexistent_plan(self, cli_runner):
        """Test epic status --validate with nonexistent plan path."""
        result = cli_runner([
            "epic", "status",
            "--validate",
            "--plan", "/nonexistent/validate/folder"
        ])

        assert result.returncode != 0


class TestPlanArchivePathArguments:
    """Integration tests for 'agentic plan archive' path arguments."""

    @pytest.fixture
    def plan_to_archive(self, temp_repo, tinydb_populator):
        """Create plan folder for archival testing."""
        # Create completed directory
        completed_dir = temp_repo / "docs" / "epics" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)

        # Create plan folder to archive
        plan_path = temp_repo / "docs" / "epics" / "live" / "260202CL_archive_test"
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
                        "tickets": [
                            {"id": "01", "description": "Done", "status": "completed"}
                        ]
                    }
                ]
            }
        }

        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Register epic in TinyDB so archive command can find and update it
        tinydb_populator("260202CL_archive_test", plan_path, {
            "name": "Archive Test Plan",
            "status": "completed",
            "phases": [
                {
                    "name": "Test Phase",
                    "tickets": [
                        {"id": "01", "name": "Done", "status": "completed"},
                    ],
                }
            ],
        })

        return plan_path

    def test_archive_with_plan_flag(self, cli_runner, plan_to_archive, temp_repo):
        """Test plan archive with --plan flag."""
        result = cli_runner([
            "epic", "archive",
            "--plan", str(plan_to_archive)
        ])

        assert result.returncode == 0
        assert "archived" in result.stdout.lower() or "completed" in result.stdout.lower()

    def test_archive_with_short_plan_flag(self, cli_runner, plan_to_archive, temp_repo):
        """Test plan archive with -p short flag."""
        result = cli_runner([
            "epic", "archive",
            "-p", str(plan_to_archive)
        ])

        assert result.returncode == 0
        assert "archived" in result.stdout.lower() or "completed" in result.stdout.lower()

    def test_archive_with_positional_path(self, cli_runner, plan_to_archive, temp_repo):
        """Test plan archive with positional path argument (backward compatibility)."""
        result = cli_runner([
            "epic", "archive",
            str(plan_to_archive)
        ])

        assert result.returncode == 0
        assert "archived" in result.stdout.lower() or "completed" in result.stdout.lower()

    def test_archive_with_folder_name_match(self, cli_runner, plan_to_archive, temp_repo):
        """Test plan archive with partial folder name."""
        result = cli_runner([
            "epic", "archive",
            "--plan", "260202CL_archive_test"
        ])

        assert result.returncode == 0
        assert "archived" in result.stdout.lower() or "completed" in result.stdout.lower()

    def test_archive_without_path_argument_fails(self, cli_runner):
        """Test plan archive without any path argument fails."""
        result = cli_runner([
            "epic", "archive"
        ])

        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_archive_nonexistent_plan(self, cli_runner):
        """Test plan archive with nonexistent plan path."""
        result = cli_runner([
            "epic", "archive",
            "--plan", "/nonexistent/archive/folder"
        ])

        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_archive_plan_flag_priority(self, cli_runner, plan_to_archive, temp_repo):
        """Test that --plan flag takes priority over positional argument."""
        # Create a second plan folder
        other_plan = temp_repo / "docs" / "epics" / "live" / "260202CL_other_archive"
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
            "epic", "archive",
            str(other_plan),  # positional (should be ignored)
            "--plan", str(plan_to_archive)  # flag (should be used)
        ])

        assert result.returncode == 0
        assert "archived" in result.stdout.lower() or "completed" in result.stdout.lower()
