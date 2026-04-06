"""Integration tests for task completion without auto-archive.

Auto-archive has been removed from CLI task completion commands.
Only the orchestration-loop (via explicit `agentic plan move folder --force`)
should archive plans. These tests verify that completing tasks never triggers
auto-archival.

Covers:
- Folder stays in live/ when tasks are completed (no auto-archive)
- is_plan_fully_completed correctly detects completion state
"""

import pytest
import yaml

pytestmark = [pytest.mark.integration]


class TestNoAutoArchiveOnCompletion:
    """Integration tests verifying auto-archive is removed from task completion."""

    @pytest.fixture
    def plan_with_multiple_tasks(self, temp_repo, tinydb_populator):
        """Create a plan folder with multiple tasks for completion testing.

        Structure:
        - docs/epics/live/260130AA_auto_archive_test/
          - plan_build.yml (3 tasks: 2 pending, 1 in_progress)
        - docs/epics/completed/ (empty, destination for archive)
        """
        plan_path = temp_repo / "docs" / "epics" / "live" / "260130AA_auto_archive_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        # Create completed directory
        completed_dir = temp_repo / "docs" / "epics" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)

        # Create plan file with multiple tasks
        plan_content = {
            "name": "auto-archive-test-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tickets": [
                        {
                            "task_id": "build_01_001",
                            "description": "First task",
                            "status": "pending",
                        },
                        {
                            "task_id": "build_01_002",
                            "description": "Second task",
                            "status": "pending",
                        },
                        {
                            "task_id": "build_01_003",
                            "description": "Third task",
                            "status": "in_progress",
                        },
                    ],
                }
            ],
        }

        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Populate TinyDB with the same data
        tinydb_populator("260130AA_auto_archive_test", plan_path, {
            "name": "auto-archive-test-plan",
            "status": "planning",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [
                        {"id": "build_01_001", "name": "First task", "description": "First task", "status": "pending"},
                        {"id": "build_01_002", "name": "Second task", "description": "Second task", "status": "pending"},
                        {"id": "build_01_003", "name": "Third task", "description": "Third task", "status": "in_progress"},
                    ],
                }
            ],
        })

        return {
            "plan_path": plan_path,
            "completed_dir": completed_dir,
            "plan_file": plan_file,
        }

    @pytest.fixture
    def plan_with_single_task(self, temp_repo, tinydb_populator):
        """Create a plan folder with a single pending task."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260130AA_single_task_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        # Create completed directory
        completed_dir = temp_repo / "docs" / "epics" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)

        plan_content = {
            "name": "single-task-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "pending",
                    "tickets": [
                        {
                            "task_id": "build_01_001",
                            "description": "Only task",
                            "status": "pending",
                        },
                    ],
                }
            ],
        }

        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Populate TinyDB
        tinydb_populator("260130AA_single_task_test", plan_path, {
            "name": "single-task-plan",
            "status": "planning",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [
                        {"id": "build_01_001", "name": "Only task", "description": "Only task", "status": "pending"},
                    ],
                }
            ],
        })

        return {
            "plan_path": plan_path,
            "completed_dir": completed_dir,
            "plan_file": plan_file,
        }

    @pytest.fixture
    def plan_with_tasks_across_files(self, temp_repo, tinydb_populator):
        """Create a plan folder with tasks spread across multiple YAML files."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260130AA_multi_file_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        # Create completed directory
        completed_dir = temp_repo / "docs" / "epics" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)

        # First plan file
        plan_build = {
            "name": "build-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tickets": [
                        {
                            "task_id": "build_01_001",
                            "description": "Build task",
                            "status": "pending",
                        },
                    ],
                }
            ],
        }
        with open(plan_path / "plan_build.yml", "w") as f:
            yaml.dump(plan_build, f)

        # Second plan file
        plan_test = {
            "name": "test-plan",
            "phases": [
                {
                    "phase_id": "test_01",
                    "name": "Test Phase",
                    "status": "pending",
                    "tickets": [
                        {
                            "task_id": "test_01_001",
                            "description": "Test task",
                            "status": "pending",
                        },
                    ],
                }
            ],
        }
        with open(plan_path / "plan_test.yml", "w") as f:
            yaml.dump(plan_test, f)

        # Populate TinyDB with tickets from both files
        tinydb_populator("260130AA_multi_file_test", plan_path, {
            "name": "multi-file-test-plan",
            "status": "planning",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [
                        {"id": "build_01_001", "name": "Build task", "description": "Build task", "status": "pending"},
                    ],
                },
                {
                    "name": "Test Phase",
                    "tickets": [
                        {"id": "test_01_001", "name": "Test task", "description": "Test task", "status": "pending"},
                    ],
                },
            ],
        })

        return {
            "plan_path": plan_path,
            "completed_dir": completed_dir,
        }

    def test_folder_stays_until_all_tasks_completed(
        self, cli_runner, plan_with_multiple_tasks
    ):
        """Test that folder stays in live/ as tasks are completed.

        Scenario: Plan has 3 tasks. Complete first two, verify folder stays.
        """
        plan_path = plan_with_multiple_tasks["plan_path"]
        completed_dir = plan_with_multiple_tasks["completed_dir"]

        # Complete first task
        result = cli_runner([
            "epic", "ticket", "complete", "build_01_001",
            "--plan", str(plan_path),
        ])
        assert result.returncode == 0
        assert "completed" in result.stdout.lower()

        # Verify folder still in live/
        assert plan_path.exists(), "Plan folder should still exist in live/"
        dest_path = completed_dir / plan_path.name
        assert not dest_path.exists(), "Plan folder should NOT be in completed/"

        # Complete second task
        result = cli_runner([
            "epic", "ticket", "complete", "build_01_002",
            "--plan", str(plan_path),
        ])
        assert result.returncode == 0

        # Verify folder still in live/ (third task still pending)
        assert plan_path.exists(), "Plan folder should still exist in live/"
        assert not dest_path.exists(), "Plan folder should NOT be in completed/"

    def test_folder_stays_after_all_tasks_completed(
        self, cli_runner, plan_with_multiple_tasks
    ):
        """Test that folder stays in live/ even when ALL tasks are completed.

        Auto-archive has been removed; the orchestration-loop handles archiving.
        """
        plan_path = plan_with_multiple_tasks["plan_path"]
        completed_dir = plan_with_multiple_tasks["completed_dir"]
        dest_path = completed_dir / plan_path.name

        # Complete all three tasks
        cli_runner(["epic", "ticket", "complete", "build_01_001", "--plan", str(plan_path)])
        cli_runner(["epic", "ticket", "complete", "build_01_002", "--plan", str(plan_path)])
        result = cli_runner(["epic", "ticket", "complete", "build_01_003", "--plan", str(plan_path)])

        assert result.returncode == 0
        assert "completed" in result.stdout.lower()

        # Folder should remain in live/ (no auto-archive)
        assert plan_path.exists(), "Plan folder should still exist in live/ (no auto-archive)"
        assert not dest_path.exists(), "Plan folder should NOT be auto-archived to completed/"

    def test_single_task_plan_stays_after_completion(
        self, cli_runner, plan_with_single_task
    ):
        """Test single-task plan stays in live/ after completing the only task."""
        plan_path = plan_with_single_task["plan_path"]
        completed_dir = plan_with_single_task["completed_dir"]
        dest_path = completed_dir / plan_path.name

        result = cli_runner([
            "epic", "ticket", "complete", "build_01_001",
            "--plan", str(plan_path),
        ])

        assert result.returncode == 0

        # Folder should remain in live/ (no auto-archive)
        assert plan_path.exists(), "Plan folder should still exist in live/ (no auto-archive)"
        assert not dest_path.exists(), "Plan folder should NOT be auto-archived to completed/"

    def test_multi_file_plan_stays_after_all_tasks_completed(
        self, cli_runner, plan_with_tasks_across_files
    ):
        """Test plan with tasks across files stays in live/ after all completed.

        Completing all tasks across multiple plan files should NOT trigger
        auto-archive. The folder stays in live/ for the orchestration-loop.
        """
        plan_path = plan_with_tasks_across_files["plan_path"]
        completed_dir = plan_with_tasks_across_files["completed_dir"]
        dest_path = completed_dir / plan_path.name

        # Complete task in first file
        result = cli_runner([
            "epic", "ticket", "complete", "build_01_001",
            "--plan", str(plan_path),
        ])
        assert result.returncode == 0

        # Verify folder still in live/
        assert plan_path.exists(), "Plan folder should still exist in live/"
        assert not dest_path.exists(), "Plan folder should NOT be in completed/"

        # Complete task in second file
        result = cli_runner([
            "epic", "ticket", "complete", "test_01_001",
            "--plan", str(plan_path),
        ])
        assert result.returncode == 0

        # Folder should remain in live/ (no auto-archive)
        assert plan_path.exists(), "Plan folder should still exist in live/ (no auto-archive)"
        assert not dest_path.exists(), "Plan folder should NOT be auto-archived to completed/"

    def test_no_archive_when_task_not_found(self, temp_repo, cli_runner, tinydb_populator):
        """Test that failing to complete a task doesn't affect the folder."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260130AA_edge_case_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        completed_dir = temp_repo / "docs" / "epics" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)

        plan_content = {
            "name": "edge-case-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tickets": [
                        {
                            "task_id": "build_01_001",
                            "description": "Already done",
                            "status": "completed",
                        },
                        {
                            "task_id": "build_01_002",
                            "description": "Last remaining",
                            "status": "pending",
                        },
                    ],
                }
            ],
        }
        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Populate TinyDB
        tinydb_populator("260130AA_edge_case_test", plan_path, {
            "name": "edge-case-plan",
            "status": "planning",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [
                        {"id": "build_01_001", "name": "Already done", "description": "Already done", "status": "completed"},
                        {"id": "build_01_002", "name": "Last remaining", "description": "Last remaining", "status": "pending"},
                    ],
                }
            ],
        })

        dest_path = completed_dir / plan_path.name

        result = cli_runner([
            "epic", "ticket", "complete", "nonexistent_task",
            "--plan", str(plan_path),
        ])

        # Command should fail
        assert result.returncode != 0

        # Folder should NOT be archived
        assert plan_path.exists(), "Plan folder should still exist in live/"
        assert not dest_path.exists(), "Plan folder should NOT be in completed/"


class TestIsPlanFullyCompleted:
    """Unit tests for is_plan_fully_completed function."""

    @pytest.fixture
    def plan_folder(self, temp_repo):
        """Create a basic plan folder for testing."""
        plan_path = temp_repo / "docs" / "epics" / "live" / "260130AA_completion_check"
        plan_path.mkdir(parents=True, exist_ok=True)
        return plan_path

    def test_returns_false_when_no_plan_files(self, plan_folder):
        """Test returns False when no plan_*.yml files exist and no TinyDB entry."""
        from agenticcli.commands.epic import is_epic_fully_completed as is_plan_fully_completed

        # Empty folder - no plan files, no TinyDB entry
        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_returns_false_when_no_tasks(self, plan_folder, tinydb_populator):
        """Test returns False when TinyDB has no tasks for this epic."""
        from agenticcli.commands.epic import is_epic_fully_completed as is_plan_fully_completed

        # Plan file with no tasks - TinyDB also has no tasks
        plan_content = {
            "name": "empty-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "pending",
                    "tickets": [],  # Empty tickets
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        # Register in TinyDB with no tickets
        tinydb_populator("260130AA_completion_check", plan_folder, {
            "name": "empty-plan",
            "status": "planning",
            "phases": [{"name": "Build Phase", "tickets": []}],
        })

        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_returns_false_with_pending_tasks(self, plan_folder, tinydb_populator):
        """Test returns False when any task is pending."""
        from agenticcli.commands.epic import is_epic_fully_completed as is_plan_fully_completed

        plan_content = {
            "name": "incomplete-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tickets": [
                        {"task_id": "task_001", "description": "Task 1", "status": "completed"},
                        {"task_id": "task_002", "description": "Task 2", "status": "pending"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        tinydb_populator("260130AA_completion_check", plan_folder, {
            "name": "incomplete-plan",
            "status": "planning",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [
                        {"id": "task_001", "name": "Task 1", "description": "Task 1", "status": "completed"},
                        {"id": "task_002", "name": "Task 2", "description": "Task 2", "status": "pending"},
                    ],
                }
            ],
        })

        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_returns_false_with_in_progress_tasks(self, plan_folder, tinydb_populator):
        """Test returns False when any task is in_progress."""
        from agenticcli.commands.epic import is_epic_fully_completed as is_plan_fully_completed

        plan_content = {
            "name": "incomplete-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tickets": [
                        {"task_id": "task_001", "description": "Task 1", "status": "completed"},
                        {"task_id": "task_002", "description": "Task 2", "status": "in_progress"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        tinydb_populator("260130AA_completion_check", plan_folder, {
            "name": "incomplete-plan",
            "status": "planning",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [
                        {"id": "task_001", "name": "Task 1", "description": "Task 1", "status": "completed"},
                        {"id": "task_002", "name": "Task 2", "description": "Task 2", "status": "in_progress"},
                    ],
                }
            ],
        })

        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_returns_true_when_all_completed(self, plan_folder, tinydb_populator):
        """Test returns True when all tasks are completed."""
        from agenticcli.commands.epic import is_epic_fully_completed as is_plan_fully_completed

        plan_content = {
            "name": "completed-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "completed",
                    "tickets": [
                        {"task_id": "task_001", "description": "Task 1", "status": "completed"},
                        {"task_id": "task_002", "description": "Task 2", "status": "completed"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        tinydb_populator("260130AA_completion_check", plan_folder, {
            "name": "completed-plan",
            "status": "planning",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [
                        {"id": "task_001", "name": "Task 1", "description": "Task 1", "status": "completed"},
                        {"id": "task_002", "name": "Task 2", "description": "Task 2", "status": "completed"},
                    ],
                }
            ],
        })

        result = is_plan_fully_completed(plan_folder)
        assert result is True

    def test_checks_all_plan_files(self, plan_folder, tinydb_populator):
        """Test checks tasks across all plan_*.yml files (via TinyDB)."""
        from agenticcli.commands.epic import is_epic_fully_completed as is_plan_fully_completed

        # First file - all completed
        plan_build = {
            "name": "build-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "completed",
                    "tickets": [
                        {"task_id": "build_001", "description": "Build", "status": "completed"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_build, f)

        # Second file - still pending
        plan_test = {
            "name": "test-plan",
            "phases": [
                {
                    "phase_id": "test_01",
                    "name": "Test Phase",
                    "status": "pending",
                    "tickets": [
                        {"task_id": "test_001", "description": "Test", "status": "pending"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_test.yml", "w") as f:
            yaml.dump(plan_test, f)

        # TinyDB has both sets of tickets; one is pending
        tinydb_populator("260130AA_completion_check", plan_folder, {
            "name": "multi-file-plan",
            "status": "planning",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [
                        {"id": "build_001", "name": "Build", "description": "Build", "status": "completed"},
                    ],
                },
                {
                    "name": "Test Phase",
                    "tickets": [
                        {"id": "test_001", "name": "Test", "description": "Test", "status": "pending"},
                    ],
                },
            ],
        })

        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_handles_yaml_parse_errors(self, plan_folder):
        """Test returns False on YAML parse errors (TinyDB returns False when no entry)."""
        from agenticcli.commands.epic import is_epic_fully_completed as is_plan_fully_completed

        # Create invalid YAML (TinyDB has no entry, so returns False)
        (plan_folder / "plan_invalid.yml").write_text("invalid: yaml: content: {{{")

        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_ignores_non_plan_files(self, plan_folder, tinydb_populator):
        """Test ignores non-plan files (TinyDB is the source of truth)."""
        from agenticcli.commands.epic import is_epic_fully_completed as is_plan_fully_completed

        # Create a plan file with completed tasks
        plan_content = {
            "name": "completed-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "completed",
                    "tickets": [
                        {"task_id": "task_001", "description": "Task 1", "status": "completed"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        # Create non-plan file with pending tasks (should be ignored by TinyDB)
        other_content = {
            "name": "other-file",
            "phases": [
                {
                    "phase_id": "other_01",
                    "tickets": [
                        {"task_id": "other_001", "status": "pending"},
                    ],
                }
            ],
        }
        with open(plan_folder / "orchestration.yml", "w") as f:
            yaml.dump(other_content, f)

        # TinyDB only has the completed task (from plan_build.yml context)
        tinydb_populator("260130AA_completion_check", plan_folder, {
            "name": "completed-plan",
            "status": "planning",
            "phases": [
                {
                    "name": "Build Phase",
                    "tickets": [
                        {"id": "task_001", "name": "Task 1", "description": "Task 1", "status": "completed"},
                    ],
                }
            ],
        })

        result = is_plan_fully_completed(plan_folder)
        assert result is True  # Only TinyDB data matters

    def test_handles_legacy_implementation_steps(self, plan_folder):
        """Test returns False for legacy structure with no TinyDB entry."""
        from agenticcli.commands.epic import is_epic_fully_completed as is_plan_fully_completed

        # Legacy structure with implementation_steps (not in TinyDB)
        plan_content = {
            "plan": {
                "name": "legacy-plan",
                "implementation_steps": [
                    {"id": "step_001", "description": "Step 1", "status": "completed"},
                    {"id": "step_002", "description": "Step 2", "status": "pending"},
                ],
            }
        }
        with open(plan_folder / "plan_legacy.yml", "w") as f:
            yaml.dump(plan_content, f)

        # No TinyDB entry - returns False (no tasks found)
        result = is_plan_fully_completed(plan_folder)
        assert result is False
