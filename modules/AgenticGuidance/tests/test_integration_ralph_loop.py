"""End-to-end integration tests for Ralph Loop.

This module tests complete Ralph loop execution scenarios with mock plans,
simulating the full lifecycle from discovery to completion.

Note: dependency-based blocking is not tested here because _parse_dependencies()
always returns [] (dependency data is not stored in TinyDB). Instead, blocking
is tested via question files.
"""

from pathlib import Path

import pytest
import yaml

from agenticguidance.services.ralph import (
    PlanAction,
    RalphLoopService,
)
from agenticguidance.services.epic_repository import EpicRepository


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _get_db_path(tmp_path: Path) -> Path:
    db_path = tmp_path / ".agentic" / "epics.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def make_service(tmp_path: Path) -> tuple[RalphLoopService, EpicRepository]:
    """Create a RalphLoopService with a shared injected EpicRepository.

    Returns:
        (service, repo) tuple. The repo is injected into service._repository.
        Callers MUST use this repo for all TinyDB operations to ensure
        consistent in-memory state.
    """
    db_path = _get_db_path(tmp_path)
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    service = RalphLoopService(epics_dir=tmp_path)
    service._repository = repo
    return service, repo


def add_plan(
    tmp_path: Path,
    repo: EpicRepository,
    name: str,
    has_mmd: bool = True,
    tasks: list[dict] | None = None,
) -> Path:
    """Create a mock plan: filesystem structure + TinyDB entry.

    IMPORTANT: Use the same `repo` instance that is injected into the service.

    Args:
        tmp_path: Base directory for the plan folder.
        repo: EpicRepository instance to write into.
        name: Plan folder name.
        has_mmd: Whether to create an orchestration_*.mmd file.
        tasks: List of task dicts (id, name, status).

    Returns:
        Path to the created plan directory.
    """
    plan_dir = tmp_path / name
    plan_dir.mkdir(exist_ok=True)

    if tasks is None:
        tasks = [{"id": "T1", "name": "Task 1", "status": "pending"}]

    repo.create_epic({
        "epic_folder_name": name,
        "epic_folder": str(plan_dir),
        "name": name,
        "status": "active",
    })
    for task in tasks:
        repo.add_ticket(name, "Phase 1", task)

    if has_mmd:
        # Insert a TinyDB phase with an agent so _has_orchestration_file returns True.
        # The legacy MMD filesystem check has been removed (T3_3).
        repo.add_phase(name, {"name": "Phase 1", "agent": "build-python"})

    return plan_dir


def complete_tasks(repo: EpicRepository, plan_name: str, task_ids: list[str] | None = None) -> None:
    """Mark tasks as completed in the shared TinyDB repo.

    Args:
        repo: The SAME EpicRepository instance injected into the service.
        plan_name: Epic folder name.
        task_ids: Task IDs to complete. If None, completes all tasks.
    """
    tickets = repo.get_tickets(plan_name)
    for ticket in tickets:
        if task_ids is None or ticket.id in task_ids:
            repo.update_ticket_status(plan_name, ticket.id, "completed")


def add_question(plan_dir: Path, question_id: str, severity: str = "blocking") -> None:
    """Write a pending question YAML file into a plan's question queue."""
    pending_dir = plan_dir / "questions" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    question_data = {
        "id": question_id,
        "text": f"Test question {question_id}",
        "context": "integration test",
        "severity": severity,
        "asked_by": "test",
        "created_at": 1700000000.0,
        "status": "pending",
        "answer": None,
        "answered_at": None,
        "answered_by": None,
    }
    (pending_dir / f"{question_id}.yml").write_text(yaml.dump(question_data))


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------

class TestRalphLoopFullCycle:
    """Test complete Ralph loop execution scenarios."""

    def test_ralph_loop_full_cycle(self, tmp_path):
        """Test complete Ralph loop execution.

        Setup:
        - PlanA: has orchestration, 2 pending tasks
        - PlanB: no orchestration (needs planning)
        - PlanC: has orchestration, 1 pending task

        Verify:
        - Execute and plan actions cycle through correctly
        - State properly tracked
        - Completion detected correctly
        """
        service, repo = make_service(tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        add_plan(tmp_path, repo, "PlanA", has_mmd=True, tasks=[
            {"id": "A1", "name": "Task A1", "status": "pending"},
            {"id": "A2", "name": "Task A2", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanB", has_mmd=False)
        add_plan(tmp_path, repo, "PlanC", has_mmd=True, tasks=[
            {"id": "C1", "name": "Task C1", "status": "pending"},
        ])

        # Start loop
        state = service.start_loop()
        assert state is not None
        assert state.status == "running"

        # Iteration 1: execute
        action = service.get_next_action()
        assert action is not None
        assert action.action == "execute"
        first_plan = action.plan_name
        service.record_iteration(action, "success")

        # Complete first plan
        complete_tasks(repo, first_plan)

        # Iteration 2: another execute or plan
        action = service.get_next_action()
        assert action is not None
        assert action.action in ("execute", "plan")
        service.record_iteration(action, "success")

        if action.action == "execute":
            second_plan = action.plan_name
            complete_tasks(repo, second_plan)
            # Should get plan action for PlanB
            action = service.get_next_action()
            assert action is not None
            assert action.action == "plan"
            service.record_iteration(action, "success")
            # Create orchestration phase in TinyDB for PlanB (T3_3: no MMD fallback)
            repo.add_phase("PlanB", {"name": "Phase 1", "agent": "build-python"})
            # Execute PlanB
            action = service.get_next_action()
            assert action is not None
            assert action.action == "execute"
            service.record_iteration(action, "success")
            complete_tasks(repo, action.plan_name)
        else:
            # Got plan action for PlanB
            repo.add_phase("PlanB", {"name": "Phase 1", "agent": "build-python"})
            # Execute remaining plans
            for _ in range(2):  # PlanB + whichever of PlanA/PlanC wasn't done
                action = service.get_next_action()
                if action is None:
                    break
                if action.action == "execute":
                    service.record_iteration(action, "success")
                    complete_tasks(repo, action.plan_name)

        # Final check: Should be complete
        assert service.check_all_complete() is True

        # Verify state tracking
        final_state = service.get_state()
        assert final_state is not None
        assert len(final_state.iterations) >= 3
        assert final_state.status == "running"  # Stop not called yet

    def test_all_need_planning(self, tmp_path):
        """Test when all plans need orchestration MMDs."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanA", has_mmd=False)
        add_plan(tmp_path, repo, "PlanB", has_mmd=False)
        add_plan(tmp_path, repo, "PlanC", has_mmd=False)

        # All actions should be plan actions
        queue = service.get_priority_queue()
        plan_actions = [a for a in queue if a.action == "plan"]
        assert len(plan_actions) == 3

        # Get next should return a plan action
        action = service.get_next_action()
        assert action.action == "plan"

        # System is not complete (needs planning)
        assert service.check_all_complete() is False

        # Simulate planning completed: insert TinyDB phases (T3_3: no MMD fallback)
        for plan_name in ["PlanA", "PlanB", "PlanC"]:
            repo.add_phase(plan_name, {"name": "Phase 1", "agent": "build-python"})

        # Now all should be execute actions (they have pending tasks in TinyDB)
        queue = service.get_priority_queue()
        execute_actions = [a for a in queue if a.action == "execute"]
        assert len(execute_actions) == 3

        # Complete all tasks
        for plan_name in ["PlanA", "PlanB", "PlanC"]:
            complete_tasks(repo, plan_name)

        # Now all complete
        assert service.check_all_complete() is True

    def test_all_blocked_by_questions(self, tmp_path):
        """Test when all remaining plans are blocked by questions."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanA", has_mmd=True, tasks=[
            {"id": "A1", "name": "Task A1", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanB", has_mmd=True, tasks=[
            {"id": "B1", "name": "Task B1", "status": "pending"},
        ])

        # Block both plans with questions
        add_question(tmp_path / "PlanA", "Q-A1", severity="blocking")
        add_question(tmp_path / "PlanB", "Q-B1", severity="blocking")

        # All plans should be blocked
        queue = service.get_priority_queue()
        blocked_actions = [a for a in queue if a.action == "blocked"]
        assert len(blocked_actions) == 2

        # No executable actions
        action = service.get_next_action()
        assert action is None

        # check_all_complete returns True (no actionable work)
        assert service.check_all_complete() is True

    def test_mixed_action_sequence(self, tmp_path):
        """Test interleaved execute and plan actions."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanExecute1", has_mmd=True, tasks=[
            {"id": "E1", "name": "Task E1", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanNeeds1", has_mmd=False)
        add_plan(tmp_path, repo, "PlanExecute2", has_mmd=True, tasks=[
            {"id": "E2", "name": "Task E2", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanNeeds2", has_mmd=False)

        # First action should be execute (higher priority)
        action1 = service.get_next_action()
        assert action1.action == "execute"
        assert action1.plan_name in ("PlanExecute1", "PlanExecute2")

        # Complete first execute plan
        complete_tasks(repo, action1.plan_name)

        # Second action should still be execute (the other execute plan)
        action2 = service.get_next_action()
        assert action2.action == "execute"
        assert action2.plan_name in ("PlanExecute1", "PlanExecute2")
        assert action2.plan_name != action1.plan_name

        # Complete second execute plan
        complete_tasks(repo, action2.plan_name)

        # Now should get plan actions
        action3 = service.get_next_action()
        assert action3.action == "plan"
        assert action3.plan_name in ("PlanNeeds1", "PlanNeeds2")

        # Insert TinyDB phase for first plan action (T3_3: no MMD fallback)
        repo.add_phase(action3.plan_name, {"name": "Phase 1", "agent": "build-python"})

        # Should now get execute for the newly planned plan
        action4 = service.get_next_action()
        assert action4.action == "execute"
        assert action4.plan_name == action3.plan_name

        # Complete it
        complete_tasks(repo, action4.plan_name)

        # Final action should be plan for remaining plan
        action5 = service.get_next_action()
        assert action5.action == "plan"

        # Insert TinyDB phase and complete final plan (T3_3: no MMD fallback)
        repo.add_phase(action5.plan_name, {"name": "Phase 1", "agent": "build-python"})
        complete_tasks(repo, action5.plan_name)

        # All complete
        assert service.check_all_complete() is True


class TestStateTransitions:
    """Test loop state transitions through lifecycle."""

    def test_start_to_running(self, tmp_path):
        """start_loop creates running state."""
        service, repo = make_service(tmp_path)
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
        service, repo = make_service(tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        add_plan(tmp_path, repo, "PlanA", has_mmd=True, tasks=[
            {"id": "A1", "name": "Task A1", "status": "pending"},
        ])

        # Start loop
        state = service.start_loop()
        assert state.status == "running"

        # Execute and complete plan
        action = service.get_next_action()
        assert action is not None
        service.record_iteration(action, "success")
        complete_tasks(repo, "PlanA")

        # Verify all complete
        assert service.check_all_complete() is True

        # Stop loop with completion
        service.stop_loop(reason="completed")

        # Verify state transition
        final_state = service.get_state()
        assert final_state.status == "completed"

    def test_running_to_stopped(self, tmp_path):
        """stop_loop transitions to stopped."""
        service, repo = make_service(tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        state = service.start_loop()
        assert state.status == "running"

        service.stop_loop(reason="user_requested")

        stopped_state = service.get_state()
        assert stopped_state.status == "stopped"

    def test_iteration_tracking(self, tmp_path):
        """Iterations are tracked correctly through loop."""
        service, repo = make_service(tmp_path)
        service.state_dir = tmp_path / ".state"
        service.state_dir.mkdir()

        add_plan(tmp_path, repo, "PlanA", has_mmd=True, tasks=[
            {"id": "A1", "name": "Task A1", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanB", has_mmd=False)

        # Start loop
        service.start_loop()

        # Iteration 1
        action1 = service.get_next_action()
        assert action1 is not None
        service.record_iteration(action1, "success")

        state = service.get_state()
        assert state.current_iteration == 1
        assert len(state.iterations) == 1
        assert state.iterations[0].number == 1
        assert state.iterations[0].action_taken == f"{action1.action}:{action1.plan_name}"

        # Complete PlanA and create MMD for PlanB
        complete_tasks(repo, "PlanA")
        (tmp_path / "PlanB" / "orchestration_PlanB.mmd").write_text("graph TD\n  A-->B")

        # Iteration 2
        action2 = service.get_next_action()
        assert action2 is not None
        service.record_iteration(action2, "success")

        state = service.get_state()
        assert state.current_iteration == 2
        assert len(state.iterations) == 2
        assert state.iterations[1].number == 2
        assert state.iterations[1].action_taken == f"{action2.action}:{action2.plan_name}"

        # Iteration 3: Complete remaining
        complete_tasks(repo, "PlanB")
        action3 = PlanAction(action="complete", reason="All done")
        service.record_iteration(action3, "success")

        state = service.get_state()
        assert state.current_iteration == 3
        assert len(state.iterations) == 3


class TestCompletionVerification:
    """Test that completion is verified, not trusted."""

    def test_completion_requires_all_tasks_done(self, tmp_path):
        """check_all_complete only returns True when ALL tasks done."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanA", has_mmd=True, tasks=[
            {"id": "A1", "name": "Task A1", "status": "completed"},
            {"id": "A2", "name": "Task A2", "status": "completed"},
        ])
        add_plan(tmp_path, repo, "PlanB", has_mmd=True, tasks=[
            {"id": "B1", "name": "Task B1", "status": "completed"},
        ])

        # All tasks completed
        assert service.check_all_complete() is True

        # Add a pending task to PlanB via the SAME repo
        repo.add_ticket("PlanB", "Phase 1", {"id": "B2", "name": "Task B2", "status": "pending"})

        # No longer complete
        assert service.check_all_complete() is False

    def test_partial_completion_not_complete(self, tmp_path):
        """Partial task completion doesn't trigger all_complete."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanA", has_mmd=True, tasks=[
            {"id": "A1", "name": "Task A1", "status": "completed"},
            {"id": "A2", "name": "Task A2", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanB", has_mmd=True, tasks=[
            {"id": "B1", "name": "Task B1", "status": "pending"},
        ])

        # Not all complete
        assert service.check_all_complete() is False

        # Complete PlanA fully
        complete_tasks(repo, "PlanA")

        # Still not complete (PlanB pending)
        assert service.check_all_complete() is False

        # Complete PlanB
        complete_tasks(repo, "PlanB")

        # Now complete
        assert service.check_all_complete() is True

    def test_new_plan_added_breaks_completion(self, tmp_path):
        """Adding a new plan while running breaks completion status."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanA", has_mmd=True, tasks=[
            {"id": "A1", "name": "Task A1", "status": "completed"},
        ])

        # Initially complete
        assert service.check_all_complete() is True

        # Add new plan (with TinyDB entry via same repo)
        add_plan(tmp_path, repo, "PlanB", has_mmd=True, tasks=[
            {"id": "B1", "name": "Task B1", "status": "pending"},
        ])

        # No longer complete
        assert service.check_all_complete() is False


class TestErrorRecovery:
    """Test error handling and recovery."""

    def test_corrupted_state_recovery(self, tmp_path):
        """Service handles corrupted state file."""
        service, repo = make_service(tmp_path)
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
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanA", has_mmd=True)
        plan_path = tmp_path / "PlanA"

        # Verify plan discovered
        plans = service.discover_epics()
        assert len(plans) == 1

        # Delete plan directory
        import shutil
        shutil.rmtree(plan_path)

        # Rediscover - should handle gracefully (epic_path doesn't exist)
        plans = service.discover_epics()
        assert len(plans) == 0

        # Service should continue to work
        assert service.check_all_complete() is True

    def test_empty_plan_no_tickets(self, tmp_path):
        """Service with plan that has no tickets returns zero counts."""
        service, repo = make_service(tmp_path)

        plan_dir = tmp_path / "EmptyPlan"
        plan_dir.mkdir()
        repo.create_epic({
            "epic_folder_name": "EmptyPlan",
            "epic_folder": str(plan_dir),
            "name": "EmptyPlan",
            "status": "active",
        })
        # No tickets added, no MMD file

        # Should discover plan but with zero tasks
        plans = service.discover_epics()
        assert len(plans) == 1
        assert plans[0].pending_tasks == 0
        assert plans[0].completed_tasks == 0

        # No tickets + no MMD = needs_planning → not complete
        assert service.check_all_complete() is False

    def test_state_persistence_across_crashes(self, tmp_path):
        """State survives service recreation (simulated crash)."""
        state_dir = tmp_path / ".state"
        state_dir.mkdir()

        # Create and start loop
        service1, repo1 = make_service(tmp_path)
        service1.state_dir = state_dir
        state1 = service1.start_loop(prompt_file="/tmp/prompt.txt")

        # Record some iterations
        action = PlanAction(action="execute", plan_name="TestPlan", task_id="T1")
        service1.record_iteration(action, "success")
        repo1.close()

        # Simulate crash - create new service instance
        service2, repo2 = make_service(tmp_path)
        service2.state_dir = state_dir

        # State should be recoverable
        state2 = service2.get_state()
        assert state2 is not None
        assert state2.loop_id == state1.loop_id
        assert state2.current_iteration == 1
        assert len(state2.iterations) == 1
        assert state2.iterations[0].action_taken == "execute:TestPlan"
        repo2.close()

    def test_max_iterations_tracking(self, tmp_path):
        """Loop tracks iterations against max_iterations limit."""
        service, repo = make_service(tmp_path)
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

    def test_empty_plans_directory(self, tmp_path):
        """Service handles empty epics directory."""
        service, repo = make_service(tmp_path)

        # Should return empty list (no epics in TinyDB)
        plans = service.discover_epics()
        assert plans == []

        # Should consider complete (no work to do)
        assert service.check_all_complete() is True

        # get_next_action should return None
        action = service.get_next_action()
        assert action is None


class TestComplexMultiPlanScenarios:
    """Test scenarios with multiple concurrent plans."""

    def test_sequential_plan_execution(self, tmp_path):
        """Plans execute one after another when both are ready."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanA", has_mmd=True, tasks=[
            {"id": "A1", "name": "Task A1", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanB", has_mmd=True, tasks=[
            {"id": "B1", "name": "Task B1", "status": "pending"},
        ])

        # Both should be in execute queue
        queue = service.get_priority_queue()
        execute_actions = [a for a in queue if a.action == "execute"]
        assert len(execute_actions) == 2

        # Execute first
        action1 = service.get_next_action()
        assert action1.action == "execute"
        complete_tasks(repo, action1.plan_name)

        # Execute second
        action2 = service.get_next_action()
        assert action2.action == "execute"
        assert action2.plan_name != action1.plan_name
        complete_tasks(repo, action2.plan_name)

        # All done
        assert service.check_all_complete() is True

    def test_mixed_completed_and_pending(self, tmp_path):
        """Plans with all-completed tasks don't show as execute actions."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanDone", has_mmd=True, tasks=[
            {"id": "D1", "name": "Done Task", "status": "completed"},
        ])
        add_plan(tmp_path, repo, "PlanPending", has_mmd=True, tasks=[
            {"id": "P1", "name": "Pending Task", "status": "pending"},
        ])

        # Only pending plan should require execution
        queue = service.get_priority_queue()
        execute_actions = [a for a in queue if a.action == "execute"]
        execute_names = [a.plan_name for a in execute_actions]
        assert "PlanPending" in execute_names
        assert "PlanDone" not in execute_names

        # Complete the pending plan
        complete_tasks(repo, "PlanPending")

        # Now all complete
        assert service.check_all_complete() is True

    def test_five_plan_chain_execution(self, tmp_path):
        """Five plans execute as each completes."""
        service, repo = make_service(tmp_path)

        plan_names = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
        for name in plan_names:
            add_plan(tmp_path, repo, name, has_mmd=True, tasks=[
                {"id": f"{name[0]}1", "name": f"Task {name[0]}1", "status": "pending"},
            ])

        # Complete all plans
        for _ in plan_names:
            action = service.get_next_action()
            assert action is not None
            assert action.action == "execute"
            complete_tasks(repo, action.plan_name)

        # All complete
        assert service.check_all_complete() is True


class TestQuestionBlockedFlow:
    """Test question-blocked plan handling in the Ralph loop."""

    def test_ralph_loop_skips_question_blocked_plan(self, tmp_path):
        """get_next_action returns the executable plan, not the question-blocked one."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanReady", has_mmd=True, tasks=[
            {"id": "R1", "name": "Task R1", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanBlocked", has_mmd=True, tasks=[
            {"id": "B1", "name": "Task B1", "status": "pending"},
        ])

        # Add a blocking question to PlanBlocked
        add_question(tmp_path / "PlanBlocked", "Q-001", severity="blocking")

        action = service.get_next_action()

        assert action is not None
        assert action.action == "execute"
        assert action.plan_name == "PlanReady"

        # The blocked plan should NOT appear in executable actions
        queue = service.get_priority_queue()
        executable = [a for a in queue if a.action != "blocked"]
        assert all(a.plan_name != "PlanBlocked" for a in executable)

    def test_ralph_status_includes_question_summary(self, tmp_path):
        """discover_epics reports accurate blocking_questions counts."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanA", has_mmd=True, tasks=[
            {"id": "A1", "name": "Task A1", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanB", has_mmd=True, tasks=[
            {"id": "B1", "name": "Task B1", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanC", has_mmd=True, tasks=[
            {"id": "C1", "name": "Task C1", "status": "pending"},
        ])
        add_plan(tmp_path, repo, "PlanD", has_mmd=True, tasks=[
            {"id": "D1", "name": "Task D1", "status": "pending"},
        ])

        # PlanA: 2 blocking questions
        add_question(tmp_path / "PlanA", "Q-A1", severity="blocking")
        add_question(tmp_path / "PlanA", "Q-A2", severity="blocking")

        # PlanB: 1 blocking + 1 medium
        add_question(tmp_path / "PlanB", "Q-B1", severity="blocking")
        add_question(tmp_path / "PlanB", "Q-B2", severity="medium")

        # PlanC: 1 medium only (non-blocking)
        add_question(tmp_path / "PlanC", "Q-C1", severity="medium")

        # PlanD: no questions

        plans = service.discover_epics()
        plans_by_name = {p.name: p for p in plans}

        assert plans_by_name["PlanA"].blocking_questions == 2
        assert plans_by_name["PlanA"].action_required == "blocked"

        assert plans_by_name["PlanB"].blocking_questions == 1
        assert plans_by_name["PlanB"].action_required == "blocked"

        assert plans_by_name["PlanC"].blocking_questions == 0
        assert plans_by_name["PlanC"].action_required == "execute"

        assert plans_by_name["PlanD"].blocking_questions == 0
        assert plans_by_name["PlanD"].action_required == "execute"

    def test_priority_queue_question_blocked_reason(self, tmp_path):
        """Blocked action's reason mentions questions when plan is question-blocked."""
        service, repo = make_service(tmp_path)

        add_plan(tmp_path, repo, "PlanQ", has_mmd=True, tasks=[
            {"id": "Q1", "name": "Task Q1", "status": "pending"},
        ])
        add_question(tmp_path / "PlanQ", "Q-001", severity="blocking")
        add_question(tmp_path / "PlanQ", "Q-002", severity="blocking")
        add_question(tmp_path / "PlanQ", "Q-003", severity="blocking")

        queue = service.get_priority_queue()

        blocked_actions = [a for a in queue if a.action == "blocked"]
        assert len(blocked_actions) == 1

        blocked = blocked_actions[0]
        assert blocked.plan_name == "PlanQ"
        assert "question" in blocked.reason.lower()
        assert "3" in blocked.reason
