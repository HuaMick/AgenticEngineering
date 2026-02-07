"""Tests for task service."""

import yaml
from pathlib import Path

import pytest

from agenticguidance.services.task import Task, TaskService, TaskStatus


# test_001: Test file structure with fixtures


@pytest.fixture
def sample_plan_path(tmp_path):
    """Create temporary plan directory with sample YAML."""
    plan_dir = tmp_path / "test_plan"
    plan_dir.mkdir()

    # Write plan_build.yml with phases and tasks:
    # - 3 tasks: one pending, one in_progress, one completed
    # - Use phases[].tasks[] structure
    # - Include task without optional fields
    plan_content = {
        "name": "test-plan",
        "status": "active",
        "phases": [
            {
                "name": "Phase 1",
                "tasks": [
                    {
                        "id": "task_001",
                        "name": "First task",
                        "description": "A pending task",
                        "status": "pending",
                        "agent": "builder",
                        "inputs": ["input1.txt"],
                        "target_files": ["output1.py"],
                        "guidance": "Do the first thing",
                    },
                    {
                        "id": "task_002",
                        "name": "Second task",
                        "description": "An in-progress task",
                        "status": "in_progress",
                        "agent": "builder",
                    },
                    {
                        "id": "task_003",
                        "name": "Third task",
                        "description": "A completed task",
                        "status": "completed",
                        "completed_date": "2026-02-03",
                    },
                ],
            }
        ],
    }

    plan_file = plan_dir / "plan_build.yml"
    with open(plan_file, "w", encoding="utf-8") as f:
        yaml.dump(plan_content, f, default_flow_style=False, sort_keys=False)

    return plan_dir


@pytest.fixture
def flat_plan_path(tmp_path):
    """Create plan with root-level tasks[] (legacy flat structure)."""
    plan_dir = tmp_path / "flat_plan"
    plan_dir.mkdir()

    # Write plan_build.yml with root tasks: key
    plan_content = {
        "name": "flat-plan",
        "status": "active",
        "tasks": [
            {
                "id": "flat_001",
                "name": "Flat task",
                "description": "Root-level task",
                "status": "pending",
                "agent": "builder",
            },
            {
                "id": "flat_002",
                "name": "Flat completed",
                "description": "Completed flat task",
                "status": "completed",
                "completed_date": "2026-02-03",
            },
        ],
    }

    plan_file = plan_dir / "plan_build.yml"
    with open(plan_file, "w", encoding="utf-8") as f:
        yaml.dump(plan_content, f, default_flow_style=False, sort_keys=False)

    return plan_dir


@pytest.fixture
def task_service(sample_plan_path):
    """Create TaskService with sample plan."""
    return TaskService(sample_plan_path)


# test_002: Task retrieval tests


class TestTaskRetrieval:
    """Tests for task retrieval methods."""

    def test_get_task_returns_task_by_id(self, task_service):
        """Test getting a task by ID returns correct task."""
        task = task_service.get_task("task_001")

        assert task is not None
        assert task.id == "task_001"
        assert task.name == "First task"
        assert task.description == "A pending task"
        assert task.status == TaskStatus.PENDING
        assert task.agent == "builder"
        assert task.inputs == ["input1.txt"]
        assert task.target_files == ["output1.py"]
        assert task.guidance == "Do the first thing"

    def test_get_task_returns_none_for_invalid_id(self, task_service):
        """Test getting a non-existent task returns None."""
        task = task_service.get_task("nonexistent_task")

        assert task is None

    def test_list_tasks_returns_all_tasks(self, task_service):
        """Test listing all tasks returns all tasks."""
        tasks = task_service.list_tasks()

        assert len(tasks) == 3
        task_ids = [t.id for t in tasks]
        assert "task_001" in task_ids
        assert "task_002" in task_ids
        assert "task_003" in task_ids

    def test_list_tasks_filters_by_status_pending(self, task_service):
        """Test listing tasks filtered by pending status."""
        tasks = task_service.list_tasks(status=TaskStatus.PENDING)

        assert len(tasks) == 1
        assert tasks[0].id == "task_001"
        assert tasks[0].status == TaskStatus.PENDING

    def test_list_tasks_filters_by_status_in_progress(self, task_service):
        """Test listing tasks filtered by in_progress status."""
        tasks = task_service.list_tasks(status=TaskStatus.IN_PROGRESS)

        assert len(tasks) == 1
        assert tasks[0].id == "task_002"
        assert tasks[0].status == TaskStatus.IN_PROGRESS

    def test_list_tasks_filters_by_status_completed(self, task_service):
        """Test listing tasks filtered by completed status."""
        tasks = task_service.list_tasks(status=TaskStatus.COMPLETED)

        assert len(tasks) == 1
        assert tasks[0].id == "task_003"
        assert tasks[0].status == TaskStatus.COMPLETED

    def test_get_current_task_returns_in_progress(self, task_service):
        """Test getting current task returns in_progress task."""
        task = task_service.get_current_task()

        assert task is not None
        assert task.id == "task_002"
        assert task.status == TaskStatus.IN_PROGRESS

    def test_get_current_task_returns_pending_when_none_in_progress(self, tmp_path):
        """Test current task returns pending when no in_progress tasks."""
        plan_dir = tmp_path / "pending_plan"
        plan_dir.mkdir()

        plan_content = {
            "name": "pending-plan",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {
                            "id": "task_001",
                            "name": "Pending task",
                            "description": "A pending task",
                            "status": "pending",
                        },
                    ],
                }
            ],
        }

        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w", encoding="utf-8") as f:
            yaml.dump(plan_content, f, default_flow_style=False, sort_keys=False)

        service = TaskService(plan_dir)
        task = service.get_current_task()

        assert task is not None
        assert task.id == "task_001"
        assert task.status == TaskStatus.PENDING

    def test_get_current_task_returns_none_for_nonexistent_file(self, tmp_path):
        """Test current task returns None when plan file doesn't exist."""
        plan_dir = tmp_path / "missing_plan"
        plan_dir.mkdir()

        service = TaskService(plan_dir)
        task = service.get_current_task()

        assert task is None

    def test_get_current_task_works_with_flat_structure(self, flat_plan_path):
        """Test current task works with flat (root-level tasks) structure."""
        service = TaskService(flat_plan_path)
        task = service.get_current_task()

        # Should return pending task since no in_progress in flat structure
        assert task is not None
        assert task.id == "flat_001"
        assert task.status == TaskStatus.PENDING

    def test_get_current_task_returns_none_when_all_completed(self, tmp_path):
        """Test current task returns None when all tasks are completed."""
        plan_dir = tmp_path / "completed_plan"
        plan_dir.mkdir()

        plan_content = {
            "name": "completed-plan",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {
                            "id": "task_001",
                            "name": "Completed task",
                            "description": "A completed task",
                            "status": "completed",
                            "completed_date": "2026-02-03",
                        },
                    ],
                }
            ],
        }

        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w", encoding="utf-8") as f:
            yaml.dump(plan_content, f, default_flow_style=False, sort_keys=False)

        service = TaskService(plan_dir)
        task = service.get_current_task()

        assert task is None


# test_003: Task update tests


class TestTaskUpdates:
    """Tests for task update methods."""

    def test_update_task_status_changes_status(self, task_service):
        """Test updating task status changes the status."""
        result = task_service.update_task_status("task_001", TaskStatus.IN_PROGRESS)

        assert result is True

        # Verify the change
        task = task_service.get_task("task_001")
        assert task.status == TaskStatus.IN_PROGRESS

    def test_update_task_status_adds_completed_date(self, task_service):
        """Test updating to completed status adds completed_date."""
        result = task_service.update_task_status("task_001", TaskStatus.COMPLETED)

        assert result is True

        # Verify the change
        task = task_service.get_task("task_001")
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_date is not None
        # Check date format (YYYY-MM-DD)
        assert len(task.completed_date) == 10
        assert task.completed_date.count("-") == 2

    def test_update_task_status_returns_false_for_invalid_id(self, task_service):
        """Test updating non-existent task returns False."""
        result = task_service.update_task_status("nonexistent", TaskStatus.COMPLETED)

        assert result is False

    def test_start_task_sets_in_progress(self, task_service):
        """Test start_task convenience method sets status to in_progress."""
        result = task_service.start_task("task_001")

        assert result is True

        # Verify the change
        task = task_service.get_task("task_001")
        assert task.status == TaskStatus.IN_PROGRESS

    def test_complete_task_sets_completed_with_date(self, task_service):
        """Test complete_task convenience method sets completed status with date."""
        result = task_service.complete_task("task_001")

        assert result is True

        # Verify the change
        task = task_service.get_task("task_001")
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_date is not None

    def test_yaml_persists_after_update(self, task_service):
        """Test that updates are persisted to YAML file."""
        # Update task
        task_service.update_task_status("task_001", TaskStatus.COMPLETED)

        # Create new service instance (re-read file)
        new_service = TaskService(task_service.plan_path)
        task = new_service.get_task("task_001")

        # Verify persisted change
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_date is not None

    def test_complete_task_works_with_flat_structure(self, flat_plan_path):
        """Test completing a task in flat structure adds completed date."""
        service = TaskService(flat_plan_path)

        # Complete flat task
        result = service.complete_task("flat_001")
        assert result is True

        # Verify the change
        task = service.get_task("flat_001")
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_date is not None


# test_004: Edge case tests


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_empty_plan_file(self, tmp_path):
        """Test handling of empty plan file."""
        plan_dir = tmp_path / "empty_plan"
        plan_dir.mkdir()

        plan_file = plan_dir / "plan_build.yml"
        plan_file.write_text("")

        service = TaskService(plan_dir)

        # Should not crash
        tasks = service.list_tasks()
        assert tasks == []

        task = service.get_task("any_id")
        assert task is None

        current = service.get_current_task()
        assert current is None

    def test_handles_missing_phases_key(self, tmp_path):
        """Test handling of plan without phases key."""
        plan_dir = tmp_path / "no_phases_plan"
        plan_dir.mkdir()

        plan_content = {
            "name": "no-phases-plan",
            "status": "active",
        }

        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w", encoding="utf-8") as f:
            yaml.dump(plan_content, f, default_flow_style=False, sort_keys=False)

        service = TaskService(plan_dir)

        # Should not crash
        tasks = service.list_tasks()
        assert tasks == []

    def test_handles_task_without_optional_fields(self, tmp_path):
        """Test handling of task with minimal fields."""
        plan_dir = tmp_path / "minimal_plan"
        plan_dir.mkdir()

        plan_content = {
            "name": "minimal-plan",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {
                            "id": "minimal_001",
                            "name": "Minimal task",
                            "description": "Task without optional fields",
                            "status": "pending",
                            # No agent, inputs, target_files, guidance, completed_date
                        },
                    ],
                }
            ],
        }

        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w", encoding="utf-8") as f:
            yaml.dump(plan_content, f, default_flow_style=False, sort_keys=False)

        service = TaskService(plan_dir)
        task = service.get_task("minimal_001")

        assert task is not None
        assert task.id == "minimal_001"
        assert task.agent is None
        assert task.inputs == []
        assert task.target_files == []
        assert task.guidance is None
        assert task.completed_date is None

    def test_handles_malformed_yaml(self, tmp_path):
        """Test handling of malformed YAML file."""
        plan_dir = tmp_path / "malformed_plan"
        plan_dir.mkdir()

        plan_file = plan_dir / "plan_build.yml"
        plan_file.write_text("invalid: yaml: content: [unclosed")

        service = TaskService(plan_dir)

        # Should not crash, returns None/empty
        task = service.get_task("any_id")
        assert task is None

        tasks = service.list_tasks()
        assert tasks == []

    def test_handles_nonexistent_plan_file(self, tmp_path):
        """Test handling of non-existent plan file."""
        plan_dir = tmp_path / "nonexistent_plan"
        plan_dir.mkdir()

        # Don't create plan_build.yml
        service = TaskService(plan_dir)

        # Should not crash
        task = service.get_task("any_id")
        assert task is None

        tasks = service.list_tasks()
        assert tasks == []

        # Update should fail gracefully
        result = service.update_task_status("any_id", TaskStatus.COMPLETED)
        assert result is False

    def test_supports_both_nested_and_flat_task_structures(self, flat_plan_path):
        """Test that service handles both modern and legacy structures."""
        service = TaskService(flat_plan_path)

        # Should retrieve flat tasks
        tasks = service.list_tasks()
        assert len(tasks) == 2

        task = service.get_task("flat_001")
        assert task is not None
        assert task.id == "flat_001"
        assert task.name == "Flat task"

        # Should update flat tasks
        result = service.start_task("flat_001")
        assert result is True

        task = service.get_task("flat_001")
        assert task.status == TaskStatus.IN_PROGRESS

    def test_handles_invalid_status_value(self, tmp_path):
        """Test handling of invalid status value in YAML."""
        plan_dir = tmp_path / "invalid_status_plan"
        plan_dir.mkdir()

        plan_content = {
            "name": "invalid-status-plan",
            "phases": [
                {
                    "name": "Phase 1",
                    "tasks": [
                        {
                            "id": "task_001",
                            "name": "Task with invalid status",
                            "description": "Status is not valid",
                            "status": "invalid_status_value",
                        },
                    ],
                }
            ],
        }

        plan_file = plan_dir / "plan_build.yml"
        with open(plan_file, "w", encoding="utf-8") as f:
            yaml.dump(plan_content, f, default_flow_style=False, sort_keys=False)

        service = TaskService(plan_dir)
        task = service.get_task("task_001")

        # Should default to PENDING for invalid status
        assert task is not None
        assert task.status == TaskStatus.PENDING


# test_005: Additional tests for Task dataclass


class TestTaskDataclass:
    """Tests for Task dataclass."""

    def test_task_creation_with_defaults(self):
        """Test creating Task with default values."""
        task = Task(
            id="test_001",
            name="Test Task",
            description="Test description",
            status=TaskStatus.PENDING,
        )

        assert task.id == "test_001"
        assert task.name == "Test Task"
        assert task.description == "Test description"
        assert task.status == TaskStatus.PENDING
        assert task.agent is None
        assert task.inputs == []
        assert task.target_files == []
        assert task.guidance is None
        assert task.completed_date is None

    def test_task_creation_with_all_fields(self):
        """Test creating Task with all fields."""
        task = Task(
            id="test_001",
            name="Test Task",
            description="Test description",
            status=TaskStatus.IN_PROGRESS,
            agent="builder",
            inputs=["input1.txt", "input2.txt"],
            target_files=["output.py"],
            guidance="Do something specific",
            completed_date="2026-02-03",
        )

        assert task.agent == "builder"
        assert len(task.inputs) == 2
        assert len(task.target_files) == 1
        assert task.guidance == "Do something specific"
        assert task.completed_date == "2026-02-03"


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"

    def test_status_from_string(self):
        """Test creating TaskStatus from string."""
        assert TaskStatus("pending") == TaskStatus.PENDING
        assert TaskStatus("in_progress") == TaskStatus.IN_PROGRESS
        assert TaskStatus("completed") == TaskStatus.COMPLETED


# Integration tests with real plan files


class TestIntegrationRealPlan:
    """Integration tests using real plan files from the repository."""

    def test_reads_real_plan_file(self):
        """Test reading actual plan file from repository."""
        # Use the actual TaskService plan file
        real_plan_path = Path("/home/code/AgenticEngineering/docs/plans/completed/260203TS_task_service")

        # Verify plan folder exists
        assert real_plan_path.exists(), f"Plan folder not found: {real_plan_path}"
        assert (real_plan_path / "plan_build.yml").exists(), "Plan file not found"

        # Create TaskService with real plan
        service = TaskService(real_plan_path)

        # List all tasks
        tasks = service.list_tasks()

        # The plan has impl_001-004, test_001-005, integ_001, audit_001-002
        # Total: 4 + 5 + 1 + 2 = 12 tasks
        assert len(tasks) >= 12, f"Expected at least 12 tasks, got {len(tasks)}"

        # Verify Task objects have correct data types
        for task in tasks:
            assert isinstance(task.id, str)
            assert isinstance(task.name, str)
            assert isinstance(task.description, str)
            assert isinstance(task.status, TaskStatus)
            assert task.agent is None or isinstance(task.agent, str)
            assert isinstance(task.inputs, list)
            assert isinstance(task.target_files, list)
            assert task.guidance is None or isinstance(task.guidance, str)
            assert task.completed_date is None or isinstance(task.completed_date, str)

        # Verify we can find specific tasks
        task_ids = {t.id for t in tasks}
        assert "impl_001" in task_ids
        assert "impl_002" in task_ids
        assert "impl_003" in task_ids
        assert "impl_004" in task_ids
        assert "test_001" in task_ids
        assert "test_005" in task_ids
        assert "integ_001" in task_ids
        assert "audit_001" in task_ids

    def test_get_task_from_real_plan(self):
        """Test retrieving specific task from real plan."""
        real_plan_path = Path("/home/code/AgenticEngineering/docs/plans/completed/260203TS_task_service")
        service = TaskService(real_plan_path)

        # Get a specific task
        task = service.get_task("audit_001")

        assert task is not None
        assert task.id == "audit_001"
        assert task.name == "Test quality audit"
        assert task.description == "Review tests for proper assertions and real behavior validation"
        # Note: Status may vary based on execution state
        assert task.status in [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED]
        assert task.agent == "test-audit"

        # Check inputs field exists and is a list
        assert isinstance(task.inputs, list)
        assert len(task.inputs) >= 2

        # Verify guidance is present
        assert task.guidance is not None
        assert len(task.guidance) > 0

    def test_status_update_on_copy_of_real_plan(self, tmp_path):
        """Test updating task status on a copy of the real plan preserves YAML."""
        import shutil

        # Copy the real plan folder to tmp_path
        real_plan_path = Path("/home/code/AgenticEngineering/docs/plans/completed/260203TS_task_service")
        temp_plan_path = tmp_path / "test_plan_copy"
        shutil.copytree(real_plan_path, temp_plan_path)

        # Create TaskService pointing to temp copy
        service = TaskService(temp_plan_path)

        # Get a task that's currently completed
        task = service.get_task("impl_001")
        original_status = task.status

        # Update status (use a non-destructive change for a task that's already completed)
        # Let's find a pending task and start it
        pending_tasks = service.list_tasks(status=TaskStatus.PENDING)
        if pending_tasks:
            test_task_id = pending_tasks[0].id

            # Update the task
            result = service.start_task(test_task_id)
            assert result is True

            # Re-read the YAML file directly and verify change persisted
            plan_file = temp_plan_path / "plan_build.yml"
            with open(plan_file, "r", encoding="utf-8") as f:
                plan_data = yaml.safe_load(f)

            # Find the task in the YAML
            found = False
            for phase in plan_data.get("phases", []):
                for task_data in phase.get("tasks", []):
                    if task_data.get("id") == test_task_id:
                        assert task_data.get("status") == "in_progress"
                        found = True
                        break
                if found:
                    break

            assert found, f"Task {test_task_id} not found in YAML after update"

            # Verify YAML formatting preserved - check that other fields are still present
            assert "name" in plan_data
            assert "phases" in plan_data
            assert "inputs" in plan_data
            assert "open_questions" in plan_data

    def test_round_trip_preserves_yaml(self, tmp_path):
        """Test that load-update-save-reload cycle preserves data."""
        import shutil

        # Copy the real plan folder to tmp_path
        real_plan_path = Path("/home/code/AgenticEngineering/docs/plans/completed/260203TS_task_service")
        temp_plan_path = tmp_path / "roundtrip_plan"
        shutil.copytree(real_plan_path, temp_plan_path)

        # First load: get all tasks
        service1 = TaskService(temp_plan_path)
        original_tasks = service1.list_tasks()
        original_count = len(original_tasks)

        # Find a pending task and complete it
        pending_tasks = service1.list_tasks(status=TaskStatus.PENDING)
        if pending_tasks:
            test_task_id = pending_tasks[0].id

            # Update status
            result = service1.complete_task(test_task_id)
            assert result is True

            # Verify with same service instance
            updated_task = service1.get_task(test_task_id)
            assert updated_task.status == TaskStatus.COMPLETED
            assert updated_task.completed_date is not None

            # Create NEW service instance (simulates reload)
            service2 = TaskService(temp_plan_path)

            # Re-load the same task
            reloaded_task = service2.get_task(test_task_id)

            # Verify data is still intact
            assert reloaded_task is not None
            assert reloaded_task.id == test_task_id
            assert reloaded_task.status == TaskStatus.COMPLETED
            assert reloaded_task.completed_date is not None
            assert reloaded_task.name == updated_task.name
            assert reloaded_task.description == updated_task.description

            # Verify total task count unchanged
            reloaded_tasks = service2.list_tasks()
            assert len(reloaded_tasks) == original_count

            # Verify other tasks unchanged
            for orig_task in original_tasks:
                if orig_task.id != test_task_id:
                    reloaded = service2.get_task(orig_task.id)
                    assert reloaded.status == orig_task.status
