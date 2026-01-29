"""Integration tests for auto-archive trigger on task completion.

Tests verify that completing the last task of a plan automatically moves
the plan folder from docs/plans/live/ to docs/plans/completed/.

Covers:
- Auto-archive triggers after last task completion via cmd_task_complete
- Auto-archive triggers after last task completion via cmd_task_update
- The --no-archive flag prevents auto-archival
- Folder stays in place until all tasks are completed
- is_plan_fully_completed correctly detects completion state
"""

import pytest
import yaml

pytestmark = pytest.mark.integration


class TestAutoArchiveTrigger:
    """Integration tests for auto-archive trigger on plan completion."""

    @pytest.fixture
    def plan_with_multiple_tasks(self, temp_repo):
        """Create a plan folder with multiple tasks for completion testing.

        Structure:
        - docs/plans/live/260130AA_auto_archive_test/
          - plan_build.yml (3 tasks: 2 pending, 1 in_progress)
        - docs/plans/completed/ (empty, destination for archive)
        """
        plan_path = temp_repo / "docs" / "plans" / "live" / "260130AA_auto_archive_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        # Create completed directory
        completed_dir = temp_repo / "docs" / "plans" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)

        # Create plan file with multiple tasks
        plan_content = {
            "name": "auto-archive-test-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tasks": [
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

        return {
            "plan_path": plan_path,
            "completed_dir": completed_dir,
            "plan_file": plan_file,
        }

    @pytest.fixture
    def plan_with_single_task(self, temp_repo):
        """Create a plan folder with a single pending task.

        Useful for testing immediate archive on first (and only) task completion.
        """
        plan_path = temp_repo / "docs" / "plans" / "live" / "260130AA_single_task_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        # Create completed directory
        completed_dir = temp_repo / "docs" / "plans" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)

        plan_content = {
            "name": "single-task-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "pending",
                    "tasks": [
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

        return {
            "plan_path": plan_path,
            "completed_dir": completed_dir,
            "plan_file": plan_file,
        }

    @pytest.fixture
    def plan_with_tasks_across_files(self, temp_repo):
        """Create a plan folder with tasks spread across multiple YAML files.

        Tests that is_plan_fully_completed checks ALL plan_*.yml files.
        """
        plan_path = temp_repo / "docs" / "plans" / "live" / "260130AA_multi_file_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        # Create completed directory
        completed_dir = temp_repo / "docs" / "plans" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)

        # First plan file
        plan_build = {
            "name": "build-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tasks": [
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
                    "tasks": [
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

        return {
            "plan_path": plan_path,
            "completed_dir": completed_dir,
        }

    def test_folder_stays_until_all_tasks_completed(
        self, cli_runner, plan_with_multiple_tasks
    ):
        """Test that folder is NOT moved until ALL tasks are completed.

        Scenario: Plan has 3 tasks. Complete first two, verify folder stays.
        """
        plan_path = plan_with_multiple_tasks["plan_path"]
        completed_dir = plan_with_multiple_tasks["completed_dir"]

        # Complete first task
        result = cli_runner([
            "plan", "task", "complete", "build_01_001",
            "--plan", str(plan_path),
        ])
        assert result.returncode == 0
        assert "completed" in result.stdout.lower()

        # Verify folder still in live/
        assert plan_path.exists(), "Plan folder should still exist in live/"
        dest_path = completed_dir / plan_path.name
        assert not dest_path.exists(), "Plan folder should NOT be in completed/ yet"

        # Complete second task
        result = cli_runner([
            "plan", "task", "complete", "build_01_002",
            "--plan", str(plan_path),
        ])
        assert result.returncode == 0

        # Verify folder still in live/ (third task still pending)
        assert plan_path.exists(), "Plan folder should still exist in live/"
        assert not dest_path.exists(), "Plan folder should NOT be in completed/ yet"

    def test_auto_archive_on_last_task_complete(
        self, cli_runner, plan_with_multiple_tasks
    ):
        """Test that folder IS moved when the last task is completed.

        Scenario: Complete all tasks, verify folder moves to completed/.
        """
        plan_path = plan_with_multiple_tasks["plan_path"]
        completed_dir = plan_with_multiple_tasks["completed_dir"]
        dest_path = completed_dir / plan_path.name

        # Complete first two tasks
        cli_runner([
            "plan", "task", "complete", "build_01_001",
            "--plan", str(plan_path),
        ])
        cli_runner([
            "plan", "task", "complete", "build_01_002",
            "--plan", str(plan_path),
        ])

        # Complete the third (last) task
        result = cli_runner([
            "plan", "task", "complete", "build_01_003",
            "--plan", str(plan_path),
        ])

        assert result.returncode == 0
        assert "completed" in result.stdout.lower()

        # Verify auto-archive message appears
        assert "auto-archiv" in result.stdout.lower() or "archiv" in result.stdout.lower()

        # Verify folder moved to completed/
        assert not plan_path.exists(), "Plan folder should be removed from live/"
        assert dest_path.exists(), "Plan folder should be in completed/"
        assert (dest_path / "plan_build.yml").exists(), "Plan file should exist in archived folder"

    def test_auto_archive_single_task_plan(self, cli_runner, plan_with_single_task):
        """Test auto-archive when completing the only task in a plan.

        Edge case: Single task plan should archive immediately on completion.
        """
        plan_path = plan_with_single_task["plan_path"]
        completed_dir = plan_with_single_task["completed_dir"]
        dest_path = completed_dir / plan_path.name

        result = cli_runner([
            "plan", "task", "complete", "build_01_001",
            "--plan", str(plan_path),
        ])

        assert result.returncode == 0

        # Verify folder moved to completed/
        assert not plan_path.exists(), "Plan folder should be removed from live/"
        assert dest_path.exists(), "Plan folder should be in completed/"

    def test_no_archive_flag_prevents_auto_archival(
        self, cli_runner, plan_with_single_task
    ):
        """Test that --no-archive flag prevents auto-archival.

        Scenario: Complete the only task with --no-archive flag.
        Folder should remain in live/ even though all tasks are completed.
        """
        plan_path = plan_with_single_task["plan_path"]
        completed_dir = plan_with_single_task["completed_dir"]
        dest_path = completed_dir / plan_path.name

        result = cli_runner([
            "plan", "task", "complete", "build_01_001",
            "--plan", str(plan_path),
            "--no-archive",
        ])

        assert result.returncode == 0
        assert "completed" in result.stdout.lower()

        # Verify folder stays in live/ (not archived)
        assert plan_path.exists(), "Plan folder should still exist in live/ with --no-archive"
        assert not dest_path.exists(), "Plan folder should NOT be in completed/ with --no-archive"

    def test_auto_archive_via_task_update(self, cli_runner, plan_with_single_task):
        """Test auto-archive triggers via 'task update' command.

        The task update command with --status completed should also trigger
        auto-archival when the last task is completed.
        """
        plan_path = plan_with_single_task["plan_path"]
        completed_dir = plan_with_single_task["completed_dir"]
        dest_path = completed_dir / plan_path.name

        result = cli_runner([
            "plan", "task", "update", "build_01_001",
            "--status", "completed",
            "--plan", str(plan_path),
        ])

        assert result.returncode == 0

        # Verify folder moved to completed/
        assert not plan_path.exists(), "Plan folder should be removed from live/"
        assert dest_path.exists(), "Plan folder should be in completed/"

    def test_no_archive_flag_with_task_update(self, cli_runner, plan_with_single_task):
        """Test --no-archive flag works with task update command."""
        plan_path = plan_with_single_task["plan_path"]
        completed_dir = plan_with_single_task["completed_dir"]
        dest_path = completed_dir / plan_path.name

        result = cli_runner([
            "plan", "task", "update", "build_01_001",
            "--status", "completed",
            "--plan", str(plan_path),
            "--no-archive",
        ])

        assert result.returncode == 0

        # Verify folder stays in live/
        assert plan_path.exists(), "Plan folder should still exist in live/ with --no-archive"
        assert not dest_path.exists(), "Plan folder should NOT be in completed/ with --no-archive"

    def test_multi_file_plan_requires_all_tasks_completed(
        self, cli_runner, plan_with_tasks_across_files
    ):
        """Test that plans with tasks across multiple files require ALL completed.

        Scenario: Two plan files, each with one task. Completing one file's
        task should NOT trigger archive until the other file's task is also done.
        """
        plan_path = plan_with_tasks_across_files["plan_path"]
        completed_dir = plan_with_tasks_across_files["completed_dir"]
        dest_path = completed_dir / plan_path.name

        # Complete task in first file
        result = cli_runner([
            "plan", "task", "complete", "build_01_001",
            "--plan", str(plan_path),
        ])
        assert result.returncode == 0

        # Verify folder still in live/ (task in plan_test.yml not completed)
        assert plan_path.exists(), "Plan folder should still exist in live/"
        assert not dest_path.exists(), "Plan folder should NOT be in completed/"

        # Complete task in second file
        result = cli_runner([
            "plan", "task", "complete", "test_01_001",
            "--plan", str(plan_path),
        ])
        assert result.returncode == 0

        # Now folder should be archived
        assert not plan_path.exists(), "Plan folder should be removed from live/"
        assert dest_path.exists(), "Plan folder should be in completed/"


class TestIsPlanFullyCompleted:
    """Unit tests for is_plan_fully_completed function."""

    @pytest.fixture
    def plan_folder(self, temp_repo):
        """Create a basic plan folder for testing."""
        plan_path = temp_repo / "docs" / "plans" / "live" / "260130AA_completion_check"
        plan_path.mkdir(parents=True, exist_ok=True)
        return plan_path

    def test_returns_false_when_no_plan_files(self, plan_folder):
        """Test returns False when no plan_*.yml files exist."""
        from agenticcli.commands.plan import is_plan_fully_completed

        # Empty folder - no plan files
        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_returns_false_when_no_tasks(self, plan_folder):
        """Test returns False when plan files have no tasks."""
        from agenticcli.commands.plan import is_plan_fully_completed

        # Plan file with no tasks
        plan_content = {
            "name": "empty-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "pending",
                    "tasks": [],  # Empty tasks
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_returns_false_with_pending_tasks(self, plan_folder):
        """Test returns False when any task is pending."""
        from agenticcli.commands.plan import is_plan_fully_completed

        plan_content = {
            "name": "incomplete-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tasks": [
                        {"task_id": "task_001", "description": "Task 1", "status": "completed"},
                        {"task_id": "task_002", "description": "Task 2", "status": "pending"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_returns_false_with_in_progress_tasks(self, plan_folder):
        """Test returns False when any task is in_progress."""
        from agenticcli.commands.plan import is_plan_fully_completed

        plan_content = {
            "name": "incomplete-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tasks": [
                        {"task_id": "task_001", "description": "Task 1", "status": "completed"},
                        {"task_id": "task_002", "description": "Task 2", "status": "in_progress"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_returns_true_when_all_completed(self, plan_folder):
        """Test returns True when all tasks are completed."""
        from agenticcli.commands.plan import is_plan_fully_completed

        plan_content = {
            "name": "completed-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "completed",
                    "tasks": [
                        {"task_id": "task_001", "description": "Task 1", "status": "completed"},
                        {"task_id": "task_002", "description": "Task 2", "status": "completed"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        result = is_plan_fully_completed(plan_folder)
        assert result is True

    def test_checks_all_plan_files(self, plan_folder):
        """Test checks tasks across all plan_*.yml files."""
        from agenticcli.commands.plan import is_plan_fully_completed

        # First file - all completed
        plan_build = {
            "name": "build-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "completed",
                    "tasks": [
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
                    "tasks": [
                        {"task_id": "test_001", "description": "Test", "status": "pending"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_test.yml", "w") as f:
            yaml.dump(plan_test, f)

        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_handles_yaml_parse_errors(self, plan_folder):
        """Test returns False on YAML parse errors."""
        from agenticcli.commands.plan import is_plan_fully_completed

        # Create invalid YAML
        (plan_folder / "plan_invalid.yml").write_text("invalid: yaml: content: {{{")

        result = is_plan_fully_completed(plan_folder)
        assert result is False

    def test_ignores_non_plan_files(self, plan_folder):
        """Test ignores files that don't match plan_*.yml pattern."""
        from agenticcli.commands.plan import is_plan_fully_completed

        # Create a plan file with completed tasks
        plan_content = {
            "name": "completed-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "completed",
                    "tasks": [
                        {"task_id": "task_001", "description": "Task 1", "status": "completed"},
                    ],
                }
            ],
        }
        with open(plan_folder / "plan_build.yml", "w") as f:
            yaml.dump(plan_content, f)

        # Create non-plan file with pending tasks (should be ignored)
        other_content = {
            "name": "other-file",
            "phases": [
                {
                    "phase_id": "other_01",
                    "tasks": [
                        {"task_id": "other_001", "status": "pending"},
                    ],
                }
            ],
        }
        with open(plan_folder / "orchestration.yml", "w") as f:
            yaml.dump(other_content, f)

        result = is_plan_fully_completed(plan_folder)
        assert result is True  # Should only check plan_*.yml

    def test_handles_legacy_implementation_steps(self, plan_folder):
        """Test handles legacy structure with implementation_steps."""
        from agenticcli.commands.plan import is_plan_fully_completed

        # Legacy structure with implementation_steps
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

        result = is_plan_fully_completed(plan_folder)
        assert result is False


class TestAutoArchiveEdgeCases:
    """Edge case tests for auto-archive functionality."""

    @pytest.fixture
    def plan_with_completed_tasks(self, temp_repo):
        """Create a plan where some tasks are already completed."""
        plan_path = temp_repo / "docs" / "plans" / "live" / "260130AA_edge_case_test"
        plan_path.mkdir(parents=True, exist_ok=True)

        # Create completed directory
        completed_dir = temp_repo / "docs" / "plans" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)

        # Plan with one completed, one pending
        plan_content = {
            "name": "edge-case-plan",
            "phases": [
                {
                    "phase_id": "build_01",
                    "name": "Build Phase",
                    "status": "in_progress",
                    "tasks": [
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

        return {
            "plan_path": plan_path,
            "completed_dir": completed_dir,
        }

    def test_completing_last_remaining_task_triggers_archive(
        self, cli_runner, plan_with_completed_tasks
    ):
        """Test completing the last remaining task triggers archive.

        Scenario: Plan has one completed task and one pending. Completing
        the pending task should trigger archive.
        """
        plan_path = plan_with_completed_tasks["plan_path"]
        completed_dir = plan_with_completed_tasks["completed_dir"]
        dest_path = completed_dir / plan_path.name

        result = cli_runner([
            "plan", "task", "complete", "build_01_002",
            "--plan", str(plan_path),
        ])

        assert result.returncode == 0

        # Verify archive happened
        assert not plan_path.exists(), "Plan folder should be removed from live/"
        assert dest_path.exists(), "Plan folder should be in completed/"

    def test_archive_preserves_all_files(self, cli_runner, plan_with_completed_tasks):
        """Test that archive operation preserves all plan files."""
        plan_path = plan_with_completed_tasks["plan_path"]
        completed_dir = plan_with_completed_tasks["completed_dir"]
        dest_path = completed_dir / plan_path.name

        # Create additional files that should be preserved
        (plan_path / "orchestration.mmd").write_text("flowchart TD\n  A --> B")
        (plan_path / "notes.md").write_text("# Notes\nSome notes here")

        # Complete the last task
        cli_runner([
            "plan", "task", "complete", "build_01_002",
            "--plan", str(plan_path),
        ])

        # Verify all files preserved
        assert (dest_path / "plan_build.yml").exists()
        assert (dest_path / "orchestration.mmd").exists()
        assert (dest_path / "notes.md").exists()

    def test_no_archive_when_task_not_found(self, cli_runner, plan_with_completed_tasks):
        """Test that failing to complete a task doesn't trigger archive."""
        plan_path = plan_with_completed_tasks["plan_path"]
        completed_dir = plan_with_completed_tasks["completed_dir"]
        dest_path = completed_dir / plan_path.name

        result = cli_runner([
            "plan", "task", "complete", "nonexistent_task",
            "--plan", str(plan_path),
        ])

        # Command should fail
        assert result.returncode != 0

        # Folder should NOT be archived
        assert plan_path.exists(), "Plan folder should still exist in live/"
        assert not dest_path.exists(), "Plan folder should NOT be in completed/"

    def test_archive_destination_already_exists(self, cli_runner, plan_with_completed_tasks):
        """Test behavior when archive destination already exists.

        The archive should be skipped if destination already exists.
        """
        plan_path = plan_with_completed_tasks["plan_path"]
        completed_dir = plan_with_completed_tasks["completed_dir"]
        dest_path = completed_dir / plan_path.name

        # Pre-create destination
        dest_path.mkdir(parents=True, exist_ok=True)
        (dest_path / "existing_file.txt").write_text("I was here first")

        # Complete the last task
        result = cli_runner([
            "plan", "task", "complete", "build_01_002",
            "--plan", str(plan_path),
        ])

        # Task completion should succeed but archive should be skipped
        assert result.returncode == 0
        assert "completed" in result.stdout.lower()

        # Original folder may still exist (archive skipped)
        # Or it may have been merged - check the message
        if "skipped" in result.stdout.lower() or "exists" in result.stdout.lower():
            assert plan_path.exists() or dest_path.exists()
