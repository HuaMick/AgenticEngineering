"""End-to-end integration tests for Ralph Loop.

This module tests complete Ralph loop execution scenarios with mock plans,
simulating the full lifecycle from discovery to completion.
"""

import json
import time
from pathlib import Path

import pytest
import yaml

from agenticguidance.services.ralph import (
    PlanAction,
    RalphLoopService,
)


# Helper Functions

def create_mock_plan(
    tmp_path: Path,
    name: str,
    has_mmd: bool = True,
    tasks: list[dict] | None = None,
    depends_on: list[str] | None = None,
) -> Path:
    """Create a mock plan for testing.

    Args:
        tmp_path: Temporary path for the plan directory.
        name: Name of the plan directory.
        has_mmd: Whether to create orchestration MMD file.
        tasks: List of task dicts with id, name, and status.
        depends_on: List of plan IDs this plan depends on.

    Returns:
        Path to the created plan directory.
    """
    plan_dir = tmp_path / name
    plan_dir.mkdir(exist_ok=True)

    # Default tasks
    if tasks is None:
        tasks = [{"id": "T1", "name": "Task 1", "status": "pending"}]

    # Create plan_build.yml
    plan_data = {
        "name": name,
        "status": "active",
        "phases": [{"name": "Phase 1", "tasks": tasks}],
    }

    # Add dependencies if provided
    if depends_on:
        plan_data["dependencies"] = {"depends_on": depends_on}

    (plan_dir / "plan_build.yml").write_text(yaml.dump(plan_data))

    # Create MMD if requested
    if has_mmd:
        mmd_content = f"%% GOAL: Test plan {name}\ngraph TD\n  A-->B"
        (plan_dir / f"orchestration_{name}.mmd").write_text(mmd_content)

    return plan_dir


def complete_plan_tasks(plan_dir: Path, task_ids: list[str] | None = None) -> None:
    """Mark tasks as completed in a plan.

    Args:
        plan_dir: Path to the plan directory.
        task_ids: List of task IDs to complete. If None, completes all tasks.
    """
    plan_file = plan_dir / "plan_build.yml"
    plan_data = yaml.safe_load(plan_file.read_text())

    for phase in plan_data.get("phases", []):
        for task in phase.get("tasks", []):
            if task_ids is None or task["id"] in task_ids:
                task["status"] = "completed"

    plan_file.write_text(yaml.dump(plan_data))


# Test Classes

class TestRalphLoopFullCycle:
    """Test complete Ralph loop execution scenarios."""

    def test_ralph_loop_full_cycle(self, tmp_path):
        """Test complete Ralph loop execution.

        Setup:
        1. Create mock plans in tmp_path:
           - Plan A: has orchestration, 2 pending tasks (ready to execute)
           - Plan B: no orchestration (needs planning)
           - Plan C: depends on Plan A (blocked initially)

        Test:
        1. ralph next → returns execute:PlanA
        2. Simulate task completion for Plan A
        3. ralph next → returns execute:PlanC (now unblocked) or plan:PlanB
        4. Continue until ralph next → complete

        Verify:
        - Correct action sequence
        - Dependencies respected
        - State properly tracked
        - Completion detected correctly
        """
        # Setup: Create mock plans
        create_mock_plan(
            tmp_path,
            "PlanA",
            has_mmd=True,
            tasks=[
                {"id": "A1", "name": "Task A1", "status": "pending"},
                {"id": "A2", "name": "Task A2", "status": "pending"},
            ],
        )
        create_mock_plan(tmp_path, "PlanB", has_mmd=False)
        create_mock_plan(
            tmp_path,
            "PlanC",
            has_mmd=True,
            tasks=[{"id": "C1", "name": "Task C1", "status": "pending"}],
            depends_on=["PlanA"],
        )

        # Initialize service
        service = RalphLoopService(plans_dir=tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        # Start loop
        state = service.start_loop()
        assert state is not None
        assert state.status == "running"

        # Iteration 1: Should return execute:PlanA
        action = service.get_next_action()
        assert action is not None
        assert action.action == "execute"
        assert action.plan_name == "PlanA"
        assert action.task_id == "A1"

        # Record iteration
        service.record_iteration(action, "success")

        # Simulate completion of Plan A tasks
        complete_plan_tasks(tmp_path / "PlanA")

        # Iteration 2: Should return plan:PlanB or execute:PlanC (now unblocked)
        action = service.get_next_action()
        assert action is not None
        assert action.action in ("execute", "plan")

        if action.action == "execute":
            # Got PlanC (unblocked after PlanA completion)
            assert action.plan_name == "PlanC"
            service.record_iteration(action, "success")

            # Complete Plan C
            complete_plan_tasks(tmp_path / "PlanC")

            # Next should be plan:PlanB
            action = service.get_next_action()
            assert action is not None
            assert action.action == "plan"
            assert action.plan_name == "PlanB"
            service.record_iteration(action, "success")

            # Simulate MMD creation for PlanB
            (tmp_path / "PlanB" / "orchestration_PlanB.mmd").write_text("graph TD\n  A-->B")

            # Next should be execute:PlanB
            action = service.get_next_action()
            assert action is not None
            assert action.action == "execute"
            assert action.plan_name == "PlanB"
            service.record_iteration(action, "success")

            # Complete Plan B
            complete_plan_tasks(tmp_path / "PlanB")

        else:
            # Got PlanB (needs planning)
            assert action.plan_name == "PlanB"
            service.record_iteration(action, "success")

            # Simulate MMD creation
            (tmp_path / "PlanB" / "orchestration_PlanB.mmd").write_text("graph TD\n  A-->B")

            # Next should be execute:PlanC (unblocked) or execute:PlanB
            action = service.get_next_action()
            assert action is not None
            assert action.action == "execute"
            service.record_iteration(action, "success")

            # Complete both remaining plans
            complete_plan_tasks(tmp_path / "PlanB")
            complete_plan_tasks(tmp_path / "PlanC")

        # Final check: Should be complete
        assert service.check_all_complete() is True

        # No more actions
        action = service.get_next_action()
        assert action is None

        # Verify state tracking
        final_state = service.get_state()
        assert final_state is not None
        assert len(final_state.iterations) >= 3
        assert final_state.status == "running"  # Stop not called yet

    def test_dependency_unblocking(self, tmp_path):
        """Test that completing a plan unblocks its dependents."""
        # Create dependency chain: A <- B <- C
        create_mock_plan(
            tmp_path,
            "PlanA",
            has_mmd=True,
            tasks=[{"id": "A1", "name": "Task A1", "status": "pending"}],
        )
        create_mock_plan(
            tmp_path,
            "PlanB",
            has_mmd=True,
            tasks=[{"id": "B1", "name": "Task B1", "status": "pending"}],
            depends_on=["PlanA"],
        )
        create_mock_plan(
            tmp_path,
            "PlanC",
            has_mmd=True,
            tasks=[{"id": "C1", "name": "Task C1", "status": "pending"}],
            depends_on=["PlanB"],
        )

        service = RalphLoopService(plans_dir=tmp_path)

        # Initially: Only PlanA is executable
        action = service.get_next_action()
        assert action.action == "execute"
        assert action.plan_name == "PlanA"

        # Check that B and C are blocked
        queue = service.get_priority_queue()
        blocked_plans = [a.plan_name for a in queue if a.action == "blocked"]
        assert "PlanB" in blocked_plans
        assert "PlanC" in blocked_plans

        # Complete Plan A
        complete_plan_tasks(tmp_path / "PlanA")

        # Now PlanB should be unblocked
        action = service.get_next_action()
        assert action.action == "execute"
        assert action.plan_name == "PlanB"

        # PlanC should still be blocked
        queue = service.get_priority_queue()
        blocked_plans = [a.plan_name for a in queue if a.action == "blocked"]
        assert "PlanC" in blocked_plans

        # Complete Plan B
        complete_plan_tasks(tmp_path / "PlanB")

        # Now PlanC should be unblocked
        action = service.get_next_action()
        assert action.action == "execute"
        assert action.plan_name == "PlanC"

        # Complete Plan C
        complete_plan_tasks(tmp_path / "PlanC")

        # All complete
        assert service.check_all_complete() is True

    def test_all_need_planning(self, tmp_path):
        """Test when all plans need orchestration MMDs."""
        # Create multiple plans without MMDs
        create_mock_plan(tmp_path, "PlanA", has_mmd=False)
        create_mock_plan(tmp_path, "PlanB", has_mmd=False)
        create_mock_plan(tmp_path, "PlanC", has_mmd=False)

        service = RalphLoopService(plans_dir=tmp_path)

        # All actions should be plan actions
        queue = service.get_priority_queue()
        plan_actions = [a for a in queue if a.action == "plan"]
        assert len(plan_actions) == 3

        # Get next should return a plan action
        action = service.get_next_action()
        assert action.action == "plan"

        # System is not complete (needs planning)
        assert service.check_all_complete() is False

        # Simulate creating MMDs for all plans
        for plan_name in ["PlanA", "PlanB", "PlanC"]:
            mmd_path = tmp_path / plan_name / f"orchestration_{plan_name}.mmd"
            mmd_path.write_text("graph TD\n  A-->B")

        # Now all should be execute actions
        queue = service.get_priority_queue()
        execute_actions = [a for a in queue if a.action == "execute"]
        assert len(execute_actions) == 3

        # Complete all tasks
        for plan_name in ["PlanA", "PlanB", "PlanC"]:
            complete_plan_tasks(tmp_path / plan_name)

        # Now all complete
        assert service.check_all_complete() is True

    def test_all_blocked(self, tmp_path):
        """Test when all remaining plans are blocked."""
        # Create plans where all have unmet dependencies
        create_mock_plan(
            tmp_path,
            "PlanA",
            has_mmd=True,
            tasks=[{"id": "A1", "name": "Task A1", "status": "pending"}],
            depends_on=["NonExistentPlan"],
        )
        create_mock_plan(
            tmp_path,
            "PlanB",
            has_mmd=True,
            tasks=[{"id": "B1", "name": "Task B1", "status": "pending"}],
            depends_on=["AnotherMissingPlan"],
        )

        service = RalphLoopService(plans_dir=tmp_path)

        # All plans should be blocked
        queue = service.get_priority_queue()
        blocked_actions = [a for a in queue if a.action == "blocked"]
        assert len(blocked_actions) == 2

        # No executable actions
        action = service.get_next_action()
        assert action is None

        # check_all_complete should return True (no actionable work)
        assert service.check_all_complete() is True

    def test_mixed_action_sequence(self, tmp_path):
        """Test interleaved execute and plan actions."""
        # Create mix of plans with and without MMDs
        create_mock_plan(
            tmp_path,
            "PlanExecute1",
            has_mmd=True,
            tasks=[{"id": "E1", "name": "Task E1", "status": "pending"}],
        )
        create_mock_plan(tmp_path, "PlanNeeds1", has_mmd=False)
        create_mock_plan(
            tmp_path,
            "PlanExecute2",
            has_mmd=True,
            tasks=[{"id": "E2", "name": "Task E2", "status": "pending"}],
        )
        create_mock_plan(tmp_path, "PlanNeeds2", has_mmd=False)

        service = RalphLoopService(plans_dir=tmp_path)

        # First two actions should be execute (higher priority)
        action1 = service.get_next_action()
        assert action1.action == "execute"
        assert action1.plan_name in ("PlanExecute1", "PlanExecute2")

        # Complete first execute plan
        complete_plan_tasks(tmp_path / action1.plan_name)

        # Second action should still be execute
        action2 = service.get_next_action()
        assert action2.action == "execute"
        assert action2.plan_name in ("PlanExecute1", "PlanExecute2")
        assert action2.plan_name != action1.plan_name

        # Complete second execute plan
        complete_plan_tasks(tmp_path / action2.plan_name)

        # Now should get plan actions
        action3 = service.get_next_action()
        assert action3.action == "plan"
        assert action3.plan_name in ("PlanNeeds1", "PlanNeeds2")

        # Create MMD for first plan action
        mmd_path = tmp_path / action3.plan_name / f"orchestration_{action3.plan_name}.mmd"
        mmd_path.write_text("graph TD\n  A-->B")

        # Should now get execute for the newly planned plan
        action4 = service.get_next_action()
        assert action4.action == "execute"
        assert action4.plan_name == action3.plan_name

        # Complete it
        complete_plan_tasks(tmp_path / action4.plan_name)

        # Final action should be plan for remaining plan
        action5 = service.get_next_action()
        assert action5.action == "plan"

        # Create MMD and complete final plan
        mmd_path = tmp_path / action5.plan_name / f"orchestration_{action5.plan_name}.mmd"
        mmd_path.write_text("graph TD\n  A-->B")
        complete_plan_tasks(tmp_path / action5.plan_name)

        # All complete
        assert service.check_all_complete() is True


class TestStateTransitions:
    """Test loop state transitions through lifecycle."""

    def test_start_to_running(self, tmp_path):
        """start_loop creates running state."""
        service = RalphLoopService(plans_dir=tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        state = service.start_loop()

        assert state.status == "running"
        assert state.current_iteration == 0
        assert len(state.iterations) == 0

        # Verify persistence
        loaded_state = service.get_state()
        assert loaded_state is not None
        assert loaded_state.status == "running"
        assert loaded_state.loop_id == state.loop_id

    def test_running_to_completed(self, tmp_path):
        """Loop transitions to completed when all done."""
        service = RalphLoopService(plans_dir=tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        # Create a plan
        create_mock_plan(
            tmp_path,
            "PlanA",
            has_mmd=True,
            tasks=[{"id": "A1", "name": "Task A1", "status": "pending"}],
        )

        # Start loop
        state = service.start_loop()
        assert state.status == "running"

        # Execute and complete plan
        action = service.get_next_action()
        service.record_iteration(action, "success")
        complete_plan_tasks(tmp_path / "PlanA")

        # Verify all complete
        assert service.check_all_complete() is True

        # Stop loop with completion
        service.stop_loop(reason="completed")

        # Verify state transition
        final_state = service.get_state()
        assert final_state.status == "completed"

    def test_running_to_stopped(self, tmp_path):
        """stop_loop transitions to stopped."""
        service = RalphLoopService(plans_dir=tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        state = service.start_loop()
        assert state.status == "running"

        # Stop loop
        service.stop_loop(reason="user_requested")

        # Verify state
        stopped_state = service.get_state()
        assert stopped_state.status == "stopped"

    def test_iteration_tracking(self, tmp_path):
        """Iterations are tracked correctly through loop."""
        create_mock_plan(
            tmp_path,
            "PlanA",
            has_mmd=True,
            tasks=[{"id": "A1", "name": "Task A1", "status": "pending"}],
        )
        create_mock_plan(tmp_path, "PlanB", has_mmd=False)

        service = RalphLoopService(plans_dir=tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        # Start loop
        service.start_loop()

        # Iteration 1
        action1 = service.get_next_action()
        service.record_iteration(action1, "success")

        state = service.get_state()
        assert state.current_iteration == 1
        assert len(state.iterations) == 1
        assert state.iterations[0].number == 1
        assert state.iterations[0].action_taken == f"{action1.action}:{action1.plan_name}"

        # Iteration 2
        (tmp_path / "PlanB" / "orchestration_PlanB.mmd").write_text("graph TD\n  A-->B")
        action2 = service.get_next_action()
        service.record_iteration(action2, "success")

        state = service.get_state()
        assert state.current_iteration == 2
        assert len(state.iterations) == 2
        assert state.iterations[1].number == 2
        assert state.iterations[1].action_taken == f"{action2.action}:{action2.plan_name}"

        # Iteration 3
        complete_plan_tasks(tmp_path / "PlanA")
        complete_plan_tasks(tmp_path / "PlanB")
        action3 = PlanAction(action="complete", reason="All done")
        service.record_iteration(action3, "success")

        state = service.get_state()
        assert state.current_iteration == 3
        assert len(state.iterations) == 3


class TestCompletionVerification:
    """Test that completion is verified, not trusted."""

    def test_completion_requires_all_tasks_done(self, tmp_path):
        """check_all_complete only returns True when ALL tasks done."""
        create_mock_plan(
            tmp_path,
            "PlanA",
            has_mmd=True,
            tasks=[
                {"id": "A1", "name": "Task A1", "status": "completed"},
                {"id": "A2", "name": "Task A2", "status": "completed"},
            ],
        )
        create_mock_plan(
            tmp_path,
            "PlanB",
            has_mmd=True,
            tasks=[
                {"id": "B1", "name": "Task B1", "status": "completed"},
            ],
        )

        service = RalphLoopService(plans_dir=tmp_path)

        # All tasks completed
        assert service.check_all_complete() is True

        # Add a pending task to PlanB
        plan_file = tmp_path / "PlanB" / "plan_build.yml"
        plan_data = yaml.safe_load(plan_file.read_text())
        plan_data["phases"][0]["tasks"].append(
            {"id": "B2", "name": "Task B2", "status": "pending"}
        )
        plan_file.write_text(yaml.dump(plan_data))

        # No longer complete
        assert service.check_all_complete() is False

    def test_partial_completion_not_complete(self, tmp_path):
        """Partial task completion doesn't trigger all_complete."""
        create_mock_plan(
            tmp_path,
            "PlanA",
            has_mmd=True,
            tasks=[
                {"id": "A1", "name": "Task A1", "status": "completed"},
                {"id": "A2", "name": "Task A2", "status": "pending"},
            ],
        )
        create_mock_plan(
            tmp_path,
            "PlanB",
            has_mmd=True,
            tasks=[
                {"id": "B1", "name": "Task B1", "status": "pending"},
            ],
        )

        service = RalphLoopService(plans_dir=tmp_path)

        # Not all complete
        assert service.check_all_complete() is False

        # Complete PlanA fully
        complete_plan_tasks(tmp_path / "PlanA")

        # Still not complete (PlanB pending)
        assert service.check_all_complete() is False

        # Complete PlanB
        complete_plan_tasks(tmp_path / "PlanB")

        # Now complete
        assert service.check_all_complete() is True

    def test_new_plan_added_breaks_completion(self, tmp_path):
        """Adding a new plan while running breaks completion status."""
        create_mock_plan(
            tmp_path,
            "PlanA",
            has_mmd=True,
            tasks=[{"id": "A1", "name": "Task A1", "status": "completed"}],
        )

        service = RalphLoopService(plans_dir=tmp_path)

        # Initially complete
        assert service.check_all_complete() is True

        # Add new plan
        create_mock_plan(
            tmp_path,
            "PlanB",
            has_mmd=True,
            tasks=[{"id": "B1", "name": "Task B1", "status": "pending"}],
        )

        # No longer complete
        assert service.check_all_complete() is False


class TestErrorRecovery:
    """Test error handling and recovery."""

    def test_corrupted_state_recovery(self, tmp_path):
        """Service handles corrupted state file."""
        service = RalphLoopService(plans_dir=tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        # Create corrupted state file
        state_file = service.state_dir / "state.json"
        state_file.write_text("invalid json {{{")

        # Should return None instead of crashing
        state = service.get_state()
        assert state is None

        # Should be able to start new loop
        new_state = service.start_loop()
        assert new_state is not None
        assert new_state.status == "running"

    def test_missing_plan_graceful(self, tmp_path):
        """Missing plan directory handled gracefully."""
        # Create plan reference but delete directory
        create_mock_plan(tmp_path, "PlanA", has_mmd=True)
        plan_path = tmp_path / "PlanA"

        service = RalphLoopService(plans_dir=tmp_path)

        # Verify plan discovered
        plans = service.discover_plans()
        assert len(plans) == 1

        # Delete plan directory
        import shutil
        shutil.rmtree(plan_path)

        # Rediscover - should handle gracefully
        plans = service.discover_plans()
        assert len(plans) == 0

        # Service should continue to work
        assert service.check_all_complete() is True

    def test_corrupted_plan_yaml_recovery(self, tmp_path):
        """Service handles corrupted plan YAML files."""
        plan_dir = tmp_path / "CorruptedPlan"
        plan_dir.mkdir()

        # Create corrupted plan_build.yml
        (plan_dir / "plan_build.yml").write_text("invalid: yaml: [[[")

        service = RalphLoopService(plans_dir=tmp_path)

        # Should discover plan but with zero tasks
        plans = service.discover_plans()
        assert len(plans) == 1
        assert plans[0].pending_tasks == 0
        assert plans[0].completed_tasks == 0

        # check_all_complete should handle gracefully
        assert service.check_all_complete() is True

    def test_state_persistence_across_crashes(self, tmp_path):
        """State survives service recreation (simulated crash)."""
        state_dir = tmp_path / ".state"
        state_dir.mkdir()

        # Create and start loop
        service1 = RalphLoopService(plans_dir=tmp_path)
        service1.state_dir = state_dir
        state1 = service1.start_loop(prompt_file="/tmp/prompt.txt")

        # Record some iterations
        action = PlanAction(action="execute", plan_name="TestPlan", task_id="T1")
        service1.record_iteration(action, "success")

        # Simulate crash - create new service instance
        service2 = RalphLoopService(plans_dir=tmp_path)
        service2.state_dir = state_dir

        # State should be recoverable
        state2 = service2.get_state()
        assert state2 is not None
        assert state2.loop_id == state1.loop_id
        assert state2.current_iteration == 1
        assert len(state2.iterations) == 1
        assert state2.iterations[0].action_taken == "execute:TestPlan"

    def test_max_iterations_tracking(self, tmp_path):
        """Loop tracks iterations against max_iterations limit."""
        service = RalphLoopService(plans_dir=tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        # Start with low max
        state = service.start_loop(max_iterations=3)
        assert state.max_iterations == 3

        # Record iterations
        for i in range(3):
            action = PlanAction(action="execute", plan_name=f"Plan{i}", task_id=f"T{i}")
            service.record_iteration(action, "success")

        # Check iteration count
        final_state = service.get_state()
        assert final_state.current_iteration == 3
        assert final_state.current_iteration == final_state.max_iterations

        # Note: Enforcement of max_iterations is done by orchestrator, not service
        # Service just tracks the count

    def test_empty_plans_directory(self, tmp_path):
        """Service handles empty plans directory."""
        service = RalphLoopService(plans_dir=tmp_path)

        # Should return empty list
        plans = service.discover_plans()
        assert plans == []

        # Should consider complete (no work to do)
        assert service.check_all_complete() is True

        # get_next_action should return None
        action = service.get_next_action()
        assert action is None


class TestComplexDependencyScenarios:
    """Test complex dependency scenarios."""

    def test_diamond_dependency_pattern(self, tmp_path):
        """Test diamond dependency pattern: A <- B,C <- D."""
        # D depends on both B and C, which both depend on A
        create_mock_plan(
            tmp_path,
            "PlanA",
            has_mmd=True,
            tasks=[{"id": "A1", "name": "Task A1", "status": "pending"}],
        )
        create_mock_plan(
            tmp_path,
            "PlanB",
            has_mmd=True,
            tasks=[{"id": "B1", "name": "Task B1", "status": "pending"}],
            depends_on=["PlanA"],
        )
        create_mock_plan(
            tmp_path,
            "PlanC",
            has_mmd=True,
            tasks=[{"id": "C1", "name": "Task C1", "status": "pending"}],
            depends_on=["PlanA"],
        )
        create_mock_plan(
            tmp_path,
            "PlanD",
            has_mmd=True,
            tasks=[{"id": "D1", "name": "Task D1", "status": "pending"}],
            depends_on=["PlanB", "PlanC"],
        )

        service = RalphLoopService(plans_dir=tmp_path)

        # Only A should be executable
        action = service.get_next_action()
        assert action.plan_name == "PlanA"

        # B, C, D should be blocked
        queue = service.get_priority_queue()
        blocked = [a.plan_name for a in queue if a.action == "blocked"]
        assert "PlanB" in blocked
        assert "PlanC" in blocked
        assert "PlanD" in blocked

        # Complete A
        complete_plan_tasks(tmp_path / "PlanA")

        # Now B and C should be unblocked, D still blocked
        action = service.get_next_action()
        assert action.plan_name in ("PlanB", "PlanC")
        first_plan = action.plan_name

        queue = service.get_priority_queue()
        blocked = [a.plan_name for a in queue if a.action == "blocked"]
        assert "PlanD" in blocked

        # Complete first of B/C
        complete_plan_tasks(tmp_path / first_plan)

        # D still blocked (needs both B and C)
        queue = service.get_priority_queue()
        blocked = [a.plan_name for a in queue if a.action == "blocked"]
        assert "PlanD" in blocked

        # Complete the other of B/C
        second_plan = "PlanB" if first_plan == "PlanC" else "PlanC"
        complete_plan_tasks(tmp_path / second_plan)

        # Now D should be unblocked
        action = service.get_next_action()
        assert action.plan_name == "PlanD"

        # Complete D
        complete_plan_tasks(tmp_path / "PlanD")

        # All complete
        assert service.check_all_complete() is True

    def test_transitive_dependency_resolution(self, tmp_path):
        """Test that transitive dependencies are handled correctly."""
        # Long chain: A <- B <- C <- D <- E
        for i, name in enumerate(["PlanA", "PlanB", "PlanC", "PlanD", "PlanE"]):
            deps = None if i == 0 else [f"Plan{chr(65 + i - 1)}"]  # Previous plan
            create_mock_plan(
                tmp_path,
                name,
                has_mmd=True,
                tasks=[{"id": f"{name[-1]}1", "name": f"Task {name[-1]}1", "status": "pending"}],
                depends_on=deps,
            )

        service = RalphLoopService(plans_dir=tmp_path)

        # Only A should be executable
        action = service.get_next_action()
        assert action.plan_name == "PlanA"

        # Complete plans in order
        for plan_name in ["PlanA", "PlanB", "PlanC", "PlanD"]:
            complete_plan_tasks(tmp_path / plan_name)
            next_action = service.get_next_action()
            # Next plan should be unblocked
            if plan_name != "PlanD":
                next_plan = f"Plan{chr(ord(plan_name[-1]) + 1)}"
                assert next_action.plan_name == next_plan

        # Complete final plan
        complete_plan_tasks(tmp_path / "PlanE")

        # All complete
        assert service.check_all_complete() is True
