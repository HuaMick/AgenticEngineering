"""Tests for phase commands in plan management.

Unit tests for 'agentic plan phase add/list/update' commands.
Tests cover adding phases to plans, listing phases, and updating
phase status and names.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit


@pytest.fixture
def empty_plan():
    """Create a temporary plan with no phases."""
    plan_content = {
        "name": "test-empty-plan",
        "status": "pending",
        "phases": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260128EP_empty_plan"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        yield plan_dir


@pytest.fixture
def plan_with_phases():
    """Create a temporary plan with existing phases."""
    plan_content = {
        "name": "test-with-phases",
        "status": "in_progress",
        "phases": [
            {
                "phase_id": "P1",
                "name": "Phase 1 - Setup",
                "status": "completed",
                "tasks": [
                    {"id": "T1", "name": "Task 1", "status": "completed"},
                ],
            },
            {
                "phase_id": "P2",
                "name": "Phase 2 - Build",
                "status": "in_progress",
                "tasks": [
                    {"id": "T2", "name": "Task 2", "status": "pending"},
                    {"id": "T3", "name": "Task 3", "status": "pending"},
                ],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260128WP_with_phases"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        yield plan_dir


@pytest.fixture
def plan_with_nested_structure():
    """Create a plan with phases nested under 'plan' key."""
    plan_content = {
        "plan": {
            "name": "test-nested-structure",
            "status": "pending",
            "phases": [
                {
                    "phase_id": "NP1",
                    "name": "Nested Phase 1",
                    "status": "pending",
                    "tasks": [],
                },
            ],
        }
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir) / "260128NS_nested"
        plan_dir.mkdir()
        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False)
        yield plan_dir


class TestPhaseAddToEmptyPlan:
    """Tests for adding phases to an empty plan."""

    def test_phase_add_to_empty_plan(self, empty_plan, cli_runner):
        """Test adding a phase to a plan with no phases."""
        stdout, stderr, code = cli_runner(
            ["plan", "phase", "add", "--id", "P1", "--name", "Initial Setup", "--plan", str(empty_plan)]
        )
        assert code == 0
        assert "Added phase" in stdout
        assert "P1" in stdout

        # Verify YAML was updated correctly
        plan_file = empty_plan / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        assert len(data["phases"]) == 1
        assert data["phases"][0]["phase_id"] == "P1"
        assert data["phases"][0]["name"] == "Initial Setup"
        assert data["phases"][0]["status"] == "pending"
        assert data["phases"][0]["tasks"] == []

    def test_phase_add_with_description(self, empty_plan, cli_runner):
        """Test adding a phase with a description."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "add",
                "--id", "P1",
                "--name", "Setup Phase",
                "--description",
                "Initialize project dependencies",
                "--plan",
                str(empty_plan),
            ]
        )
        assert code == 0

        plan_file = empty_plan / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        assert data["phases"][0]["description"] == "Initialize project dependencies"


class TestPhaseAddToExistingPhases:
    """Tests for adding phases to plans with existing phases."""

    def test_phase_add_to_existing_phases(self, plan_with_phases, cli_runner):
        """Test adding a new phase to a plan that already has phases."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "add",
                "--id", "P3",
                "--name", "Phase 3 - Testing",
                "--plan",
                str(plan_with_phases),
            ]
        )
        assert code == 0
        assert "Added phase" in stdout
        assert "P3" in stdout

        # Verify new phase was appended
        plan_file = plan_with_phases / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        assert len(data["phases"]) == 3
        # Original phases should be intact
        assert data["phases"][0]["phase_id"] == "P1"
        assert data["phases"][1]["phase_id"] == "P2"
        # New phase should be at the end
        assert data["phases"][2]["phase_id"] == "P3"
        assert data["phases"][2]["name"] == "Phase 3 - Testing"

    def test_phase_add_duplicate_id_error(self, plan_with_phases, cli_runner):
        """Test that adding a phase with an existing ID fails."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "add",
                "--id", "P1",
                "--name", "Duplicate Phase",
                "--plan",
                str(plan_with_phases),
            ]
        )
        assert code != 0
        assert "already exists" in stderr

        # Verify no changes were made
        plan_file = plan_with_phases / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        assert len(data["phases"]) == 2

    def test_phase_add_to_nested_structure(self, plan_with_nested_structure, cli_runner):
        """Test adding phase to plan with nested 'plan' key structure."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "add",
                "--id", "NP2",
                "--name", "Nested Phase 2",
                "--plan",
                str(plan_with_nested_structure),
            ]
        )
        assert code == 0

        plan_file = plan_with_nested_structure / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        # Should add to nested structure
        assert len(data["plan"]["phases"]) == 2
        assert data["plan"]["phases"][1]["phase_id"] == "NP2"


class TestPhaseListEmpty:
    """Tests for listing phases when plan has no phases."""

    def test_phase_list_empty(self, empty_plan, cli_runner):
        """Test listing phases on a plan with no phases."""
        stdout, stderr, code = cli_runner(
            ["plan", "phase", "list", "--plan", str(empty_plan)]
        )
        # Should succeed but show no phases message
        assert code == 0
        assert "No phases" in stdout or "0 phases" in stdout.lower()


class TestPhaseListWithPhases:
    """Tests for listing phases when plan has phases."""

    def test_phase_list_with_phases(self, plan_with_phases, cli_runner):
        """Test listing phases shows all phase information."""
        stdout, stderr, code = cli_runner(
            ["plan", "phase", "list", "--plan", str(plan_with_phases)]
        )
        assert code == 0
        assert "P1" in stdout
        assert "P2" in stdout
        assert "Phase 1 - Setup" in stdout or "Setup" in stdout
        assert "Phase 2 - Build" in stdout or "Build" in stdout

    def test_phase_list_shows_status(self, plan_with_phases, cli_runner):
        """Test that phase list shows status for each phase."""
        stdout, stderr, code = cli_runner(
            ["plan", "phase", "list", "--plan", str(plan_with_phases)]
        )
        assert code == 0
        # Status values should appear
        assert "completed" in stdout.lower() or "in_progress" in stdout.lower()

    def test_phase_list_shows_task_count(self, plan_with_phases, cli_runner):
        """Test that phase list shows task count for each phase."""
        stdout, stderr, code = cli_runner(
            ["plan", "phase", "list", "--plan", str(plan_with_phases)]
        )
        assert code == 0
        # Should show task counts (P1 has 1 task, P2 has 2 tasks)
        assert "1" in stdout and "2" in stdout

    def test_phase_list_json_output(self, plan_with_phases, cli_runner):
        """Test phase list with JSON output flag."""
        import json

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "phase", "list", "--plan", str(plan_with_phases)]
        )
        assert code == 0
        result = json.loads(stdout)
        assert "phases" in result
        assert "count" in result
        assert result["count"] == 2
        assert len(result["phases"]) == 2

    def test_phase_list_nested_structure(self, plan_with_nested_structure, cli_runner):
        """Test listing phases from nested 'plan' key structure."""
        stdout, stderr, code = cli_runner(
            ["plan", "phase", "list", "--plan", str(plan_with_nested_structure)]
        )
        assert code == 0
        assert "NP1" in stdout
        assert "Nested Phase 1" in stdout


class TestPhaseUpdateStatus:
    """Tests for updating phase status."""

    def test_phase_update_status(self, plan_with_phases, cli_runner):
        """Test updating phase status from pending to in_progress."""
        # P1 is currently completed, update P2 from in_progress to completed
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "update",
                "P2",
                "--status",
                "completed",
                "--plan",
                str(plan_with_phases),
            ]
        )
        assert code == 0
        assert "Updated phase" in stdout
        assert "completed" in stdout.lower()

        # Verify YAML was updated
        plan_file = plan_with_phases / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        phase_p2 = next(p for p in data["phases"] if p["phase_id"] == "P2")
        assert phase_p2["status"] == "completed"

    def test_phase_update_to_blocked(self, plan_with_phases, cli_runner):
        """Test updating phase status to blocked."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "update",
                "P2",
                "--status",
                "blocked",
                "--plan",
                str(plan_with_phases),
            ]
        )
        assert code == 0

        plan_file = plan_with_phases / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        phase_p2 = next(p for p in data["phases"] if p["phase_id"] == "P2")
        assert phase_p2["status"] == "blocked"

    def test_phase_update_to_pending(self, plan_with_phases, cli_runner):
        """Test updating phase status back to pending (rollback)."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "update",
                "P1",
                "--status",
                "pending",
                "--plan",
                str(plan_with_phases),
            ]
        )
        assert code == 0

        plan_file = plan_with_phases / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        phase_p1 = next(p for p in data["phases"] if p["phase_id"] == "P1")
        assert phase_p1["status"] == "pending"


class TestPhaseUpdateName:
    """Tests for updating phase name."""

    def test_phase_update_name(self, plan_with_phases, cli_runner):
        """Test updating just the phase name."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "update",
                "P1",
                "--name",
                "Phase 1 - Initialization Complete",
                "--plan",
                str(plan_with_phases),
            ]
        )
        assert code == 0
        assert "Updated phase" in stdout

        plan_file = plan_with_phases / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        phase_p1 = next(p for p in data["phases"] if p["phase_id"] == "P1")
        assert phase_p1["name"] == "Phase 1 - Initialization Complete"
        # Status should remain unchanged
        assert phase_p1["status"] == "completed"

    def test_phase_update_name_and_status(self, plan_with_phases, cli_runner):
        """Test updating both name and status together."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "update",
                "P2",
                "--name",
                "Phase 2 - Implementation",
                "--status",
                "completed",
                "--plan",
                str(plan_with_phases),
            ]
        )
        assert code == 0

        plan_file = plan_with_phases / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        phase_p2 = next(p for p in data["phases"] if p["phase_id"] == "P2")
        assert phase_p2["name"] == "Phase 2 - Implementation"
        assert phase_p2["status"] == "completed"


class TestPhaseUpdateNotFound:
    """Tests for error handling when phase is not found."""

    def test_phase_update_not_found(self, plan_with_phases, cli_runner):
        """Test error when updating a non-existent phase."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "update",
                "P99",
                "--status",
                "completed",
                "--plan",
                str(plan_with_phases),
            ]
        )
        assert code != 0
        assert "not found" in stderr.lower()

    def test_phase_update_no_changes_error(self, plan_with_phases, cli_runner):
        """Test error when neither status nor name is provided."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "update",
                "P1",
                "--plan",
                str(plan_with_phases),
            ]
        )
        assert code != 0
        assert "status" in stderr.lower() or "name" in stderr.lower()

    def test_phase_update_on_empty_plan(self, empty_plan, cli_runner):
        """Test error when updating phase in plan with no phases."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "update",
                "P1",
                "--status",
                "completed",
                "--plan",
                str(empty_plan),
            ]
        )
        assert code != 0
        assert "not found" in stderr.lower() or "No phases" in stderr


class TestPhaseUpdateNestedStructure:
    """Tests for updating phases in nested 'plan' key structure."""

    def test_phase_update_nested_status(self, plan_with_nested_structure, cli_runner):
        """Test updating status in nested structure."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "update",
                "NP1",
                "--status",
                "in_progress",
                "--plan",
                str(plan_with_nested_structure),
            ]
        )
        assert code == 0

        plan_file = plan_with_nested_structure / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        assert data["plan"]["phases"][0]["status"] == "in_progress"

    def test_phase_update_nested_name(self, plan_with_nested_structure, cli_runner):
        """Test updating name in nested structure."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "update",
                "NP1",
                "--name",
                "Updated Nested Phase",
                "--plan",
                str(plan_with_nested_structure),
            ]
        )
        assert code == 0

        plan_file = plan_with_nested_structure / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        assert data["plan"]["phases"][0]["name"] == "Updated Nested Phase"


class TestPhaseAddEdgeCases:
    """Edge case tests for phase add command."""

    def test_phase_add_without_plan_build_yml(self, cli_runner):
        """Test error when plan_build.yml doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260128NB_no_build"
            plan_dir.mkdir()
            # Create a different plan file, not plan_build.yml
            plan_file = plan_dir / "plan_test.yml"
            with open(plan_file, "w") as f:
                yaml.dump({"name": "test"}, f)

            stdout, stderr, code = cli_runner(
                ["plan", "phase", "add", "--id", "P1", "--name", "Test Phase", "--plan", str(plan_dir)]
            )
            assert code != 0
            assert "plan_build.yml not found" in stderr

    def test_phase_add_special_characters_in_id(self, empty_plan, cli_runner):
        """Test adding phase with special characters in ID."""
        stdout, stderr, code = cli_runner(
            [
                "plan",
                "phase",
                "add",
                "--id", "P1-BUILD_V2",
                "--name", "Build Phase V2",
                "--plan",
                str(empty_plan),
            ]
        )
        assert code == 0

        plan_file = empty_plan / "plan_build.yml"
        data = yaml.safe_load(plan_file.read_text())
        assert data["phases"][0]["phase_id"] == "P1-BUILD_V2"

    def test_phase_add_json_output(self, empty_plan, cli_runner):
        """Test phase add with JSON output flag."""
        import json

        stdout, stderr, code = cli_runner(
            ["-j", "plan", "phase", "add", "--id", "P1", "--name", "Test Phase", "--plan", str(empty_plan)]
        )
        assert code == 0
        result = json.loads(stdout)
        assert result["phase_id"] == "P1"
        assert result["name"] == "Test Phase"
        assert "plan_path" in result


class TestPhaseListEdgeCases:
    """Edge case tests for phase list command."""

    def test_phase_list_without_plan_build_yml(self, cli_runner):
        """Test error when plan_build.yml doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260128NB_no_build"
            plan_dir.mkdir()
            # Create a different plan file
            plan_file = plan_dir / "plan_test.yml"
            with open(plan_file, "w") as f:
                yaml.dump({"name": "test"}, f)

            stdout, stderr, code = cli_runner(
                ["plan", "phase", "list", "--plan", str(plan_dir)]
            )
            assert code != 0
            assert "plan_build.yml not found" in stderr

    def test_phase_list_with_empty_file(self, cli_runner):
        """Test error when plan_build.yml is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260128EF_empty_file"
            plan_dir.mkdir()
            plan_file = plan_dir / "plan_build.yml"
            plan_file.write_text("")

            stdout, stderr, code = cli_runner(
                ["plan", "phase", "list", "--plan", str(plan_dir)]
            )
            assert code != 0
            assert "empty" in stderr.lower()

    def test_phase_list_with_phases_without_tasks(self, cli_runner):
        """Test listing phases where some have no tasks key."""
        plan_content = {
            "name": "test-no-tasks-key",
            "status": "pending",
            "phases": [
                {
                    "phase_id": "P1",
                    "name": "Phase without tasks key",
                    "status": "pending",
                    # No 'tasks' key intentionally
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "260128NT_no_tasks"
            plan_dir.mkdir()
            plan_file = plan_dir / "plan_build.yml"
            with open(plan_file, "w") as f:
                yaml.dump(plan_content, f, default_flow_style=False)

            stdout, stderr, code = cli_runner(
                ["plan", "phase", "list", "--plan", str(plan_dir)]
            )
            # Should succeed and show 0 tasks
            assert code == 0
            assert "P1" in stdout
            assert "0" in stdout  # 0 tasks
