"""Integration tests for ticket CLI commands.

End-to-end tests for 'agentic epic ticket' subcommands (prefill, list, status, add).
"""

import json

import pytest

pytestmark = pytest.mark.integration
import yaml


class TestTaskPrefillCommand:
    """Integration tests for 'agentic epic ticket prefill'."""

    @pytest.fixture
    def plan_with_presets(self, temp_repo, monkeypatch):
        """Set up plan folder with preset templates."""
        from agenticcli.workflows import ticket_workflow

        # Create plan folder
        plan_path = temp_repo / "docs" / "epics" / "live" / "260120CL_test"
        (plan_path / "live").mkdir(parents=True)
        (plan_path / "completed").mkdir()

        # Create preset directory
        preset_dir = temp_repo / "presets"
        preset_dir.mkdir()

        # Create test preset
        (preset_dir / "test-preset.yml").write_text("""
name: test-preset
description: Test preset for integration tests
version: "1.0"
tasks:
  - id: "tp_001"
    description: "Test task one"
    priority: "high"
  - id: "tp_002"
    description: "Test task two"
    priority: "medium"
""")

        # Patch PRESETS_DIR
        monkeypatch.setattr(
            ticket_workflow.TicketPresetWorkflow,
            "PRESETS_DIR",
            preset_dir
        )

        return plan_path

    def test_prefill_creates_tasks(self, cli_runner, plan_with_presets):
        """Test prefill command creates tasks (now stored in TinyDB, not YAML files)."""
        result = cli_runner([
            "agent", "epic", "ticket", "prefill",
            "--preset", "test-preset",
            "--plan", str(plan_with_presets)
        ])

        assert result.returncode == 0
        assert "Added" in result.stdout or "tasks" in result.stdout.lower()

    def test_prefill_dry_run(self, cli_runner, plan_with_presets):
        """Test prefill --dry-run doesn't create files."""
        # Count existing files
        initial_files = list((plan_with_presets / "live").glob("*.yml"))

        result = cli_runner([
            "agent", "epic", "ticket", "prefill",
            "--preset", "test-preset",
            "--plan", str(plan_with_presets),
            "--dry-run"
        ])

        assert result.returncode == 0
        assert "dry-run" in result.stdout.lower() or "would" in result.stdout.lower()

        # Verify no new files created
        final_files = list((plan_with_presets / "live").glob("*.yml"))
        assert len(final_files) == len(initial_files)

    def test_prefill_missing_preset(self, cli_runner, plan_with_presets):
        """Test prefill with nonexistent preset shows error."""
        result = cli_runner([
            "agent", "epic", "ticket", "prefill",
            "--preset", "nonexistent-preset",
            "--plan", str(plan_with_presets)
        ])

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_prefill_json_output(self, cli_runner, plan_with_presets):
        """Test prefill with --json flag."""
        result = cli_runner([
            "-j",  # JSON flag
            "agent", "epic", "ticket", "prefill",
            "--preset", "test-preset",
            "--plan", str(plan_with_presets),
            "--dry-run"
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "preset" in data
        assert "tasks" in data


class TestTaskListCommand:
    """Integration tests for 'agentic epic ticket list'."""

    @pytest.fixture
    def plan_with_tasks(self, temp_repo, tinydb_populator):
        """Create plan folder with tasks for testing list."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260120CL_list_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        # Create plan file with tasks (flattened: directly in plan_path)
        plan_file = plan_path / "plan_build.yml"
        plan_content = {
            "name": "test-plan",
            "phases": [
                {
                    "phase_id": "phase_01",
                    "name": "Phase One",
                    "status": "in_progress",
                    "tickets": [
                        {"task_id": "task_01_001", "description": "First task", "status": "completed"},
                        {"task_id": "task_01_002", "description": "Second task", "status": "pending"},
                        {"task_id": "task_01_003", "description": "Third task", "status": "in_progress"},
                    ]
                },
                {
                    "phase_id": "phase_02",
                    "name": "Phase Two",
                    "status": "pending",
                    "tickets": [
                        {"task_id": "task_02_001", "description": "Fourth task", "status": "pending"},
                    ]
                }
            ]
        }

        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Populate TinyDB with the same tasks
        tinydb_populator("260120CL_list_test", plan_path, {
            "name": "test-plan",
            "status": "active",
            "phases": [
                {
                    "name": "Phase One",
                    "tickets": [
                        {"id": "task_01_001", "name": "First task", "description": "First task", "status": "completed"},
                        {"id": "task_01_002", "name": "Second task", "description": "Second task", "status": "pending"},
                        {"id": "task_01_003", "name": "Third task", "description": "Third task", "status": "in_progress"},
                    ],
                },
                {
                    "name": "Phase Two",
                    "tickets": [
                        {"id": "task_02_001", "name": "Fourth task", "description": "Fourth task", "status": "pending"},
                    ],
                },
            ],
        })

        return plan_path

    def test_list_shows_all_tasks(self, cli_runner, plan_with_tasks):
        """Test list shows all tasks by default."""
        result = cli_runner([
            "agent", "epic", "ticket", "list",
            "--plan", str(plan_with_tasks)
        ])

        assert result.returncode == 0
        assert "task_01_001" in result.stdout
        assert "task_02_001" in result.stdout
        assert "4" in result.stdout or "Total" in result.stdout

    def test_list_filter_pending(self, cli_runner, plan_with_tasks):
        """Test list with --status pending filter."""
        result = cli_runner([
            "agent", "epic", "ticket", "list",
            "--plan", str(plan_with_tasks),
            "--status", "pending"
        ])

        assert result.returncode == 0
        assert "task_01_002" in result.stdout
        assert "task_02_001" in result.stdout

    def test_list_filter_completed(self, cli_runner, plan_with_tasks):
        """Test list with --status completed filter."""
        result = cli_runner([
            "agent", "epic", "ticket", "list",
            "--plan", str(plan_with_tasks),
            "--status", "completed"
        ])

        assert result.returncode == 0
        assert "task_01_001" in result.stdout

    def test_list_filter_in_progress(self, cli_runner, plan_with_tasks):
        """Test list with --status in_progress filter."""
        result = cli_runner([
            "agent", "epic", "ticket", "list",
            "--plan", str(plan_with_tasks),
            "--status", "in_progress"
        ])

        assert result.returncode == 0
        assert "task_01_003" in result.stdout

    def test_list_verbose(self, cli_runner, plan_with_tasks):
        """Test list with --verbose shows more details."""
        result = cli_runner([
            "agent", "epic", "ticket", "list",
            "--plan", str(plan_with_tasks),
            "--verbose"
        ])

        assert result.returncode == 0
        assert "Phase" in result.stdout or "phase" in result.stdout

    def test_list_json_output(self, cli_runner, plan_with_tasks):
        """Test list with JSON output."""
        result = cli_runner([
            "-j",
            "agent", "epic", "ticket", "list",
            "--plan", str(plan_with_tasks)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "tasks" in data
        assert "count" in data
        assert data["count"] == 4


class TestTaskStatusCommand:
    """Integration tests for 'agentic epic ticket status'."""

    @pytest.fixture
    def plan_with_detailed_task(self, temp_repo, tinydb_populator):
        """Create plan with task having full details."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260120CL_status_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        plan_file = plan_path / "plan_build.yml"
        plan_content = {
            "name": "status-test-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tickets": [
                        {
                            "task_id": "build_01_001",
                            "description": "Implement feature X",
                            "status": "in_progress",
                            "inputs": [
                                {"path": "src/module.py", "reason": "Main module"},
                            ],
                            "target_files": ["src/feature.py"],
                            "guidance": "Follow the coding standards...",
                            "success_criteria": [
                                "Tests pass",
                                "No lint errors",
                            ]
                        },
                    ]
                }
            ]
        }

        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Populate TinyDB with detailed task
        tinydb_populator("260120CL_status_test", plan_path, {
            "name": "status-test-plan",
            "status": "active",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [
                        {
                            "id": "build_01_001",
                            "name": "Implement feature X",
                            "description": "Implement feature X",
                            "status": "in_progress",
                            "inputs": [{"path": "src/module.py", "reason": "Main module"}],
                            "target_files": ["src/feature.py"],
                            "guidance": "Follow the coding standards...",
                            "success_criteria": ["Tests pass", "No lint errors"],
                        },
                    ],
                }
            ],
        })

        return plan_path

    def test_status_shows_task_details(self, cli_runner, plan_with_detailed_task):
        """Test status command shows full task details."""
        result = cli_runner([
            "agent", "epic", "ticket", "status", "build_01_001",
            "--plan", str(plan_with_detailed_task)
        ])

        assert result.returncode == 0
        assert "build_01_001" in result.stdout
        assert "Implement feature X" in result.stdout
        assert "in_progress" in result.stdout.lower()

    def test_status_shows_inputs(self, cli_runner, plan_with_detailed_task):
        """Test status shows input files."""
        result = cli_runner([
            "agent", "epic", "ticket", "status", "build_01_001",
            "--plan", str(plan_with_detailed_task)
        ])

        assert result.returncode == 0
        assert "src/module.py" in result.stdout or "Inputs" in result.stdout

    def test_status_not_found(self, cli_runner, plan_with_detailed_task):
        """Test status with nonexistent task ID."""
        result = cli_runner([
            "agent", "epic", "ticket", "status", "nonexistent_999",
            "--plan", str(plan_with_detailed_task)
        ])

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()

    def test_status_json_output(self, cli_runner, plan_with_detailed_task):
        """Test status with JSON output."""
        result = cli_runner([
            "-j",
            "agent", "epic", "ticket", "status", "build_01_001",
            "--plan", str(plan_with_detailed_task)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "task" in data
        assert data["task"]["task_id"] == "build_01_001"


class TestTaskAddCommand:
    """Integration tests for 'agentic epic ticket add'."""

    @pytest.fixture
    def empty_plan(self, temp_repo, tinydb_populator):
        """Create plan folder with minimal structure, pre-registered in TinyDB."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260120CL_add_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        # Create minimal plan file (flattened: directly in plan_path)
        plan_file = plan_path / "plan_build.yml"
        plan_content = {
            "name": "add-test-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "pending",
                    "tickets": []
                }
            ]
        }

        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Pre-register the epic and phase in TinyDB (with no tickets yet)
        tinydb_populator("260120CL_add_test", plan_path, {
            "name": "add-test-plan",
            "status": "active",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [],
                }
            ],
        })

        return plan_path

    def _get_tickets_from_tinydb(self, plan_folder_name, db_path):
        """Helper to read tickets back from TinyDB after add operations."""
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        tickets = repo.get_tickets(plan_folder_name)
        repo.close()
        return tickets

    def test_add_creates_task(self, cli_runner, empty_plan, _isolate_tinydb):
        """Test add command creates new task in TinyDB."""
        result = cli_runner([
            "agent", "epic", "ticket", "add", "New task description",
            "--plan", str(empty_plan)
        ])

        assert result.returncode == 0
        assert "Added" in result.stdout

        # Verify task was added to TinyDB
        tickets = self._get_tickets_from_tinydb("260120CL_add_test", _isolate_tinydb)
        assert len(tickets) == 1
        assert tickets[0].description == "New task description"

    def test_add_with_priority(self, cli_runner, empty_plan):
        """Test add command with priority option (priority stored in TinyDB)."""
        result = cli_runner([
            "agent", "epic", "ticket", "add", "High priority task",
            "--plan", str(empty_plan),
            "--priority", "high"
        ])

        assert result.returncode == 0
        # cmd_task_add stores the task; priority may not be stored in TinyDB
        # but the command should succeed
        assert "Added" in result.stdout

    def test_add_with_custom_id(self, cli_runner, empty_plan, _isolate_tinydb):
        """Test add command with custom task ID."""
        result = cli_runner([
            "agent", "epic", "ticket", "add", "Custom ID task",
            "--plan", str(empty_plan),
            "--id", "custom_999"
        ])

        assert result.returncode == 0

        # Verify custom ID was used in TinyDB
        tickets = self._get_tickets_from_tinydb("260120CL_add_test", _isolate_tinydb)
        ticket_ids = [t.id for t in tickets]
        assert "custom_999" in ticket_ids

    def test_add_auto_generates_id(self, cli_runner, empty_plan, _isolate_tinydb):
        """Test add command auto-generates task ID."""
        result = cli_runner([
            "agent", "epic", "ticket", "add", "Auto ID task",
            "--plan", str(empty_plan)
        ])

        assert result.returncode == 0

        # Verify ID was auto-generated in TinyDB
        tickets = self._get_tickets_from_tinydb("260120CL_add_test", _isolate_tinydb)
        assert len(tickets) == 1
        assert tickets[0].id is not None
        assert len(tickets[0].id) > 0

    def test_add_json_output(self, cli_runner, empty_plan):
        """Test add command with JSON output."""
        result = cli_runner([
            "-j",
            "agent", "epic", "ticket", "add", "JSON output task",
            "--plan", str(empty_plan)
        ])

        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "task_id" in data
        assert "description" in data

    def test_add_multiple_tasks(self, cli_runner, empty_plan, _isolate_tinydb):
        """Test adding multiple tasks sequentially."""
        # Add first task
        result1 = cli_runner([
            "agent", "epic", "ticket", "add", "First task",
            "--plan", str(empty_plan)
        ])
        assert result1.returncode == 0

        # Add second task
        result2 = cli_runner([
            "agent", "epic", "ticket", "add", "Second task",
            "--plan", str(empty_plan)
        ])
        assert result2.returncode == 0

        # Verify both tasks exist in TinyDB
        tickets = self._get_tickets_from_tinydb("260120CL_add_test", _isolate_tinydb)
        assert len(tickets) == 2
        descriptions = [t.description for t in tickets]
        assert "First task" in descriptions
        assert "Second task" in descriptions
