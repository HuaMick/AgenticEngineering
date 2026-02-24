"""Tests for Ralph Loop Service."""

import json
import subprocess
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agenticguidance.services.ralph import (
    IterationRecord,
    PlanAction,
    PlanInfo,
    RalphLoopService,
    RalphState,
)


# Fixtures

@pytest.fixture
def clean_state_dir():
    """Clean state directory before and after tests."""
    state_dir = Path.home() / ".agentic" / "ralph"
    state_file = state_dir / "state.json"

    # Clean before test
    if state_file.exists():
        state_file.unlink()

    yield

    # Clean after test
    if state_file.exists():
        state_file.unlink()


@pytest.fixture
def isolated_service(tmp_path):
    """Create service with isolated state directory."""
    # Use tmp_path for state to avoid conflicts
    service = RalphLoopService(plans_dir=tmp_path)
    # Override state_dir to use tmp_path
    service.state_dir = tmp_path / ".state"
    service.state_dir.mkdir(parents=True, exist_ok=True)
    return service


# Helper Functions

def create_test_plan(
    tmp_path: Path,
    name: str,
    has_mmd: bool = True,
    task_statuses: list[dict] | None = None,
    dependencies: list[str] | None = None,
    status: str = "active",
) -> Path:
    """Create a test plan directory with plan_build.yml and optional MMD.

    Args:
        tmp_path: Temporary path for test plans.
        name: Name of the plan directory.
        has_mmd: Whether to create orchestration MMD file.
        task_statuses: List of task dicts with id and status.
        dependencies: List of plan dependencies.
        status: Plan status (active, completed, deferred).

    Returns:
        Path to the created plan directory.
    """
    plan_dir = tmp_path / name
    plan_dir.mkdir()

    # Create plan_build.yml
    tasks = task_statuses or [{"id": "T1", "status": "pending"}]
    plan_data = {
        "name": name,
        "status": status,
        "phases": [{"tasks": tasks}],
    }

    # Add dependencies if provided
    if dependencies:
        plan_data["dependencies"] = {"depends_on": dependencies}

    (plan_dir / "plan_build.yml").write_text(yaml.dump(plan_data))

    # Create MMD if requested
    if has_mmd:
        (plan_dir / f"orchestration_{name}.mmd").write_text("graph TD\n  A-->B")

    return plan_dir


# Test Classes

class TestPlanDiscovery:
    """Test plan discovery functionality."""

    def test_discover_empty_dir(self, tmp_path):
        """Empty directory returns empty list."""
        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert plans == []

    def test_discover_single_plan(self, tmp_path):
        """Single plan with plan_build.yml is discovered."""
        create_test_plan(tmp_path, "test_plan")

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].name == "test_plan"
        assert plans[0].path == tmp_path / "test_plan"

    def test_discover_multiple_plans(self, tmp_path):
        """Multiple plans are all discovered."""
        create_test_plan(tmp_path, "plan_one")
        create_test_plan(tmp_path, "plan_two")
        create_test_plan(tmp_path, "plan_three")

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 3
        plan_names = {p.name for p in plans}
        assert plan_names == {"plan_one", "plan_two", "plan_three"}

    def test_discover_with_orchestration(self, tmp_path):
        """Plan with orchestration_*.mmd has has_orchestration=True."""
        create_test_plan(tmp_path, "test_plan", has_mmd=True)

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].has_orchestration is True

    def test_discover_without_orchestration(self, tmp_path):
        """Plan without orchestration MMD has has_orchestration=False."""
        create_test_plan(tmp_path, "test_plan", has_mmd=False)

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].has_orchestration is False

    def test_action_required_execute(self, tmp_path):
        """Plan with MMD and pending tasks gets action_required='execute'."""
        create_test_plan(
            tmp_path,
            "test_plan",
            has_mmd=True,
            task_statuses=[
                {"id": "T1", "status": "pending"},
                {"id": "T2", "status": "pending"},
            ],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].action_required == "execute"
        assert plans[0].pending_tasks == 2

    def test_action_required_needs_planning(self, tmp_path):
        """Plan without MMD gets action_required='needs_planning'."""
        create_test_plan(tmp_path, "test_plan", has_mmd=False)

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].action_required == "needs_planning"

    def test_action_required_completed(self, tmp_path):
        """Plan with all tasks completed gets action_required='completed'."""
        create_test_plan(
            tmp_path,
            "test_plan",
            has_mmd=True,
            task_statuses=[
                {"id": "T1", "status": "completed"},
                {"id": "T2", "status": "completed"},
            ],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].action_required == "completed"
        assert plans[0].pending_tasks == 0
        assert plans[0].completed_tasks == 2

    def test_discover_skips_hidden_directories(self, tmp_path):
        """Hidden directories are skipped."""
        create_test_plan(tmp_path, ".hidden_plan")
        create_test_plan(tmp_path, "visible_plan")

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].name == "visible_plan"

    def test_discover_skips_non_plan_directories(self, tmp_path):
        """Directories without plan_*.yml are skipped."""
        # Create dir without plan file
        non_plan = tmp_path / "not_a_plan"
        non_plan.mkdir()
        (non_plan / "README.md").write_text("Not a plan")

        # Create valid plan
        create_test_plan(tmp_path, "valid_plan")

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].name == "valid_plan"

    def test_discover_current_task(self, tmp_path):
        """Current task is detected correctly."""
        create_test_plan(
            tmp_path,
            "test_plan",
            task_statuses=[
                {"id": "T1", "status": "completed"},
                {"id": "T2", "status": "pending"},
                {"id": "T3", "status": "pending"},
            ],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].current_task == "T2"

    def test_discover_status_from_yaml(self, tmp_path):
        """Plan status is read from YAML."""
        create_test_plan(tmp_path, "deferred_plan", status="deferred")

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].status == "deferred"


class TestPriorityQueue:
    """Test priority queue ordering."""

    def test_execute_before_plan(self, tmp_path):
        """Execute actions come before plan actions."""
        # Plan needing planning
        create_test_plan(tmp_path, "plan_needs_planning", has_mmd=False)

        # Plan ready to execute
        create_test_plan(
            tmp_path,
            "plan_ready",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        queue = service.get_priority_queue()

        assert len(queue) == 2
        # Execute action should be first
        assert queue[0].action == "execute"
        assert queue[0].plan_name == "plan_ready"
        # Plan action should be second
        assert queue[1].action == "plan"
        assert queue[1].plan_name == "plan_needs_planning"

    def test_blocked_plans_at_end(self, tmp_path):
        """Blocked plans appear at end of queue."""
        # Create dependency plan (not completed)
        create_test_plan(
            tmp_path,
            "dep_plan",
            task_statuses=[{"id": "T1", "status": "pending"}],
        )

        # Create blocked plan
        create_test_plan(
            tmp_path,
            "blocked_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
            dependencies=["dep_plan"],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        queue = service.get_priority_queue()

        # Should have execute action for dep_plan and blocked action for blocked_plan
        assert len(queue) == 2
        assert queue[0].action == "execute"
        assert queue[0].plan_name == "dep_plan"
        assert queue[1].action == "blocked"
        assert queue[1].plan_name == "blocked_plan"

    def test_empty_queue_when_all_complete(self, tmp_path):
        """Empty queue when all plans complete."""
        create_test_plan(
            tmp_path,
            "completed_plan",
            task_statuses=[{"id": "T1", "status": "completed"}],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        queue = service.get_priority_queue()

        # Blocked actions are included in queue but not executable
        # Filter to executable only
        executable = [a for a in queue if a.action != "blocked"]
        assert len(executable) == 0

    def test_priority_order_multiple_actions(self, tmp_path):
        """Multiple execute and plan actions are ordered correctly."""
        # Two plans ready to execute
        create_test_plan(
            tmp_path,
            "execute_one",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_test_plan(
            tmp_path,
            "execute_two",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )

        # Two plans needing planning
        create_test_plan(tmp_path, "plan_one", has_mmd=False)
        create_test_plan(tmp_path, "plan_two", has_mmd=False)

        service = RalphLoopService(plans_dir=tmp_path)
        queue = service.get_priority_queue()

        # First two should be execute actions
        assert queue[0].action == "execute"
        assert queue[1].action == "execute"

        # Next two should be plan actions
        assert queue[2].action == "plan"
        assert queue[3].action == "plan"


class TestDependencyResolution:
    """Test dependency parsing and resolution."""

    def test_parse_dependencies_empty(self, tmp_path):
        """Plan without dependencies returns empty list."""
        create_test_plan(tmp_path, "test_plan")

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].dependencies == []

    def test_parse_dependencies_list(self, tmp_path):
        """Dependencies list is parsed correctly."""
        create_test_plan(
            tmp_path,
            "test_plan",
            dependencies=["dep1", "dep2"],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].dependencies == ["dep1", "dep2"]

    def test_dependencies_met(self, tmp_path):
        """Dependencies met when all deps are completed."""
        # Create completed dependency
        create_test_plan(
            tmp_path,
            "dep_plan",
            task_statuses=[{"id": "T1", "status": "completed"}],
        )

        # Create dependent plan
        create_test_plan(
            tmp_path,
            "dependent_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
            dependencies=["dep_plan"],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        # Find dependent plan
        dependent = next(p for p in plans if p.name == "dependent_plan")
        assert dependent.action_required == "execute"  # Not blocked

    def test_dependencies_not_met(self, tmp_path):
        """Dependencies not met when some deps pending."""
        # Create pending dependency
        create_test_plan(
            tmp_path,
            "dep_plan",
            task_statuses=[{"id": "T1", "status": "pending"}],
        )

        # Create dependent plan
        create_test_plan(
            tmp_path,
            "dependent_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
            dependencies=["dep_plan"],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        # Find dependent plan
        dependent = next(p for p in plans if p.name == "dependent_plan")
        assert dependent.action_required == "blocked"

    def test_blocked_reason_shows_deps(self, tmp_path):
        """Blocked reason shows which dependencies are unmet."""
        # Create pending dependency
        create_test_plan(
            tmp_path,
            "unmet_dep",
            task_statuses=[{"id": "T1", "status": "pending"}],
        )

        # Create dependent plan
        create_test_plan(
            tmp_path,
            "blocked_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
            dependencies=["unmet_dep"],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        queue = service.get_priority_queue()

        # Find blocked action
        blocked = next(a for a in queue if a.action == "blocked")
        assert "unmet_dep" in blocked.reason
        assert "Waiting for:" in blocked.reason

    def test_blocked_reason_questions_only(self, tmp_path):
        """Blocked reason shows blocking questions when no dep issues."""
        plan_dir = create_test_plan(
            tmp_path,
            "question_blocked",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(plan_dir, severity="blocking", question_id="Q-20260221-120000-a1b2")
        create_question_file(plan_dir, severity="blocking", question_id="Q-20260221-120001-c3d4")

        service = RalphLoopService(plans_dir=tmp_path)
        queue = service.get_priority_queue()

        blocked = next(a for a in queue if a.action == "blocked")
        assert blocked.reason == "Blocked by 2 pending blocking question(s)"

    def test_blocked_reason_deps_and_questions(self, tmp_path):
        """Blocked reason combines deps and questions when both present."""
        # Create pending dependency
        create_test_plan(
            tmp_path,
            "unmet_dep",
            task_statuses=[{"id": "T1", "status": "pending"}],
        )

        # Create plan blocked by both deps and questions
        plan_dir = create_test_plan(
            tmp_path,
            "double_blocked",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
            dependencies=["unmet_dep"],
        )
        create_question_file(plan_dir, severity="blocking", question_id="Q-20260221-130000-e5f6")

        service = RalphLoopService(plans_dir=tmp_path)
        queue = service.get_priority_queue()

        blocked = next(a for a in queue if a.plan_name == "double_blocked")
        assert blocked.reason == "Waiting for: unmet_dep; also blocked by 1 question(s)"

    def test_dependencies_dict_format(self, tmp_path):
        """Dependencies with dict format are parsed correctly."""
        plan_dir = tmp_path / "test_plan"
        plan_dir.mkdir()

        # Create plan with dict-style dependencies
        plan_data = {
            "name": "test_plan",
            "status": "active",
            "phases": [{"tasks": [{"id": "T1", "status": "pending"}]}],
            "dependencies": {
                "depends_on": [
                    {"plan_id": "dep1", "description": "First dependency"},
                    {"plan_id": "dep2", "description": "Second dependency"},
                ]
            },
        }
        (plan_dir / "plan_build.yml").write_text(yaml.dump(plan_data))

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].dependencies == ["dep1", "dep2"]

    def test_partial_dependency_match(self, tmp_path):
        """Dependencies can match by plan ID prefix."""
        # Create completed dependency with full name
        create_test_plan(
            tmp_path,
            "260203QF_question_foundation",
            task_statuses=[{"id": "T1", "status": "completed"}],
        )

        # Create dependent plan with short ID dependency
        create_test_plan(
            tmp_path,
            "dependent_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
            dependencies=["260203QF"],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        # Find dependent plan
        dependent = next(p for p in plans if p.name == "dependent_plan")
        assert dependent.action_required == "execute"  # Not blocked


class TestStateManagement:
    """Test loop state management."""

    def test_start_loop_creates_state(self, isolated_service):
        """start_loop creates state file."""
        state = isolated_service.start_loop()

        state_file = isolated_service.state_dir / "state.json"
        assert state_file.exists()

    def test_start_loop_generates_id(self, isolated_service):
        """start_loop generates unique loop_id."""
        state = isolated_service.start_loop()

        assert state.loop_id is not None
        assert len(state.loop_id) == 12  # hex[:12]

    def test_start_loop_prevents_duplicate(self, isolated_service):
        """Cannot start loop when one already running."""
        isolated_service.start_loop()

        # Attempting to start again should raise
        with pytest.raises(RuntimeError) as exc_info:
            isolated_service.start_loop()

        assert "already running" in str(exc_info.value)

    def test_record_iteration(self, tmp_path, isolated_service):
        """record_iteration adds to iterations list."""
        state = isolated_service.start_loop()

        action = PlanAction(
            action="execute",
            plan_name="test_plan",
            plan_path=tmp_path / "test_plan",
            task_id="T1",
        )

        isolated_service.record_iteration(action, "success")

        # Load state and verify
        updated_state = isolated_service.get_state()
        assert updated_state is not None
        assert len(updated_state.iterations) == 1
        assert updated_state.current_iteration == 1
        assert updated_state.iterations[0].action_taken == "execute:test_plan"
        assert updated_state.iterations[0].result == "success"

    def test_get_state_returns_none_initially(self, isolated_service):
        """get_state returns None when no state file."""
        state = isolated_service.get_state()

        assert state is None

    def test_get_state_returns_state(self, isolated_service):
        """get_state returns state after start_loop."""
        started_state = isolated_service.start_loop()

        retrieved_state = isolated_service.get_state()

        assert retrieved_state is not None
        assert retrieved_state.loop_id == started_state.loop_id
        assert retrieved_state.status == "running"

    def test_stop_loop_updates_status(self, isolated_service):
        """stop_loop changes status to stopped."""
        isolated_service.start_loop()

        isolated_service.stop_loop(reason="completed")

        state = isolated_service.get_state()
        assert state is not None
        assert state.status == "completed"

    def test_state_persists(self, tmp_path):
        """State survives service recreation."""
        # Create isolated state dir for this test
        state_dir = tmp_path / ".state"
        state_dir.mkdir()

        # Create and start loop
        service1 = RalphLoopService(plans_dir=tmp_path)
        service1.state_dir = state_dir
        state1 = service1.start_loop(prompt_file="/tmp/prompt.txt")

        # Create new service instance and retrieve state
        service2 = RalphLoopService(plans_dir=tmp_path)
        service2.state_dir = state_dir
        state2 = service2.get_state()

        assert state2 is not None
        assert state2.loop_id == state1.loop_id
        assert state2.prompt_file == "/tmp/prompt.txt"

    def test_start_loop_with_params(self, isolated_service):
        """start_loop accepts prompt_file and max_iterations."""
        state = isolated_service.start_loop(prompt_file="/tmp/prompt.txt", max_iterations=10)

        assert state.prompt_file == "/tmp/prompt.txt"
        assert state.max_iterations == 10
        assert state.status == "running"
        assert state.current_iteration == 0

    def test_stop_loop_without_state_raises(self, isolated_service):
        """stop_loop raises when no state exists."""
        with pytest.raises(RuntimeError) as exc_info:
            isolated_service.stop_loop()

        assert "No active Ralph loop state" in str(exc_info.value)

    def test_record_iteration_without_state_raises(self, tmp_path, isolated_service):
        """record_iteration raises when no state exists."""
        action = PlanAction(action="execute", plan_name="test")

        with pytest.raises(RuntimeError) as exc_info:
            isolated_service.record_iteration(action, "success")

        assert "No active Ralph loop state" in str(exc_info.value)

    def test_stop_loop_with_different_reasons(self, tmp_path):
        """stop_loop sets correct status based on reason."""
        # Use isolated state dir
        state_dir = tmp_path / ".state"
        state_dir.mkdir()

        # Test completed
        service = RalphLoopService(plans_dir=tmp_path)
        service.state_dir = state_dir
        service.start_loop()
        service.stop_loop(reason="completed")
        assert service.get_state().status == "completed"

        # Clean state for next test
        (service.state_dir / "state.json").unlink()

        # Test failed
        service.start_loop()
        service.stop_loop(reason="failed")
        assert service.get_state().status == "failed"

        # Clean state for next test
        (service.state_dir / "state.json").unlink()

        # Test user_requested (default to stopped)
        service.start_loop()
        service.stop_loop(reason="user_requested")
        assert service.get_state().status == "stopped"


class TestDataclasses:
    """Test dataclass serialization."""

    def test_plan_action_to_dict(self):
        """PlanAction.to_dict() serializes correctly."""
        action = PlanAction(
            action="execute",
            plan_name="test_plan",
            plan_path=Path("/tmp/test_plan"),
            task_id="T1",
            reason="Ready to execute",
        )

        result = action.to_dict()

        assert result["action"] == "execute"
        assert result["plan"] == "test_plan"
        assert result["path"] == "/tmp/test_plan"
        assert result["task"] == "T1"
        assert result["reason"] == "Ready to execute"

    def test_plan_action_to_dict_with_none_values(self):
        """PlanAction.to_dict() handles None values."""
        action = PlanAction(action="complete")

        result = action.to_dict()

        assert result["action"] == "complete"
        assert result["plan"] is None
        assert result["path"] is None
        assert result["task"] is None

    def test_ralph_state_to_dict(self):
        """RalphState.to_dict() serializes correctly."""
        iteration = IterationRecord(
            number=1,
            started_at=1000.0,
            ended_at=1005.0,
            action_taken="execute:plan",
            result="success",
        )

        state = RalphState(
            loop_id="abc123",
            started_at=1000.0,
            current_iteration=1,
            max_iterations=20,
            status="running",
            prompt_file="/tmp/prompt.txt",
            tmux_session="ralph-session",
            iterations=[iteration],
        )

        result = state.to_dict()

        assert result["loop_id"] == "abc123"
        assert result["started_at"] == 1000.0
        assert result["current_iteration"] == 1
        assert result["max_iterations"] == 20
        assert result["status"] == "running"
        assert result["prompt_file"] == "/tmp/prompt.txt"
        assert result["tmux_session"] == "ralph-session"
        assert len(result["iterations"]) == 1
        assert result["iterations"][0]["number"] == 1

    def test_ralph_state_from_dict(self):
        """RalphState.from_dict() deserializes correctly."""
        data = {
            "loop_id": "abc123",
            "started_at": 1000.0,
            "current_iteration": 1,
            "max_iterations": 20,
            "status": "running",
            "prompt_file": "/tmp/prompt.txt",
            "tmux_session": "ralph-session",
            "iterations": [
                {
                    "number": 1,
                    "started_at": 1000.0,
                    "ended_at": 1005.0,
                    "action_taken": "execute:plan",
                    "result": "success",
                    "plans_completed": ["plan1"],
                    "output_file": "/tmp/output.log",
                }
            ],
        }

        state = RalphState.from_dict(data)

        assert state.loop_id == "abc123"
        assert state.started_at == 1000.0
        assert state.current_iteration == 1
        assert state.max_iterations == 20
        assert state.status == "running"
        assert state.prompt_file == "/tmp/prompt.txt"
        assert state.tmux_session == "ralph-session"
        assert len(state.iterations) == 1
        assert state.iterations[0].number == 1
        assert state.iterations[0].action_taken == "execute:plan"

    def test_ralph_state_round_trip(self):
        """to_dict/from_dict round trip preserves data."""
        original = RalphState(
            loop_id="test123",
            started_at=2000.0,
            current_iteration=5,
            max_iterations=10,
            status="running",
            iterations=[
                IterationRecord(
                    number=1,
                    started_at=2000.0,
                    ended_at=2001.0,
                    action_taken="execute:plan1",
                    result="success",
                ),
                IterationRecord(
                    number=2,
                    started_at=2001.0,
                    ended_at=2002.0,
                    action_taken="plan:plan2",
                    result="success",
                ),
            ],
        )

        # Round trip
        data = original.to_dict()
        restored = RalphState.from_dict(data)

        assert restored.loop_id == original.loop_id
        assert restored.started_at == original.started_at
        assert restored.current_iteration == original.current_iteration
        assert restored.max_iterations == original.max_iterations
        assert restored.status == original.status
        assert len(restored.iterations) == len(original.iterations)
        assert restored.iterations[0].number == original.iterations[0].number
        assert restored.iterations[1].action_taken == original.iterations[1].action_taken

    def test_iteration_record_to_dict(self):
        """IterationRecord.to_dict() serializes correctly."""
        iteration = IterationRecord(
            number=3,
            started_at=3000.0,
            ended_at=3010.0,
            action_taken="execute:my_plan",
            result="success",
            plans_completed=["plan1", "plan2"],
            output_file="/tmp/iteration3.log",
        )

        result = iteration.to_dict()

        assert result["number"] == 3
        assert result["started_at"] == 3000.0
        assert result["ended_at"] == 3010.0
        assert result["action_taken"] == "execute:my_plan"
        assert result["result"] == "success"
        assert result["plans_completed"] == ["plan1", "plan2"]
        assert result["output_file"] == "/tmp/iteration3.log"

    def test_iteration_record_from_dict(self):
        """IterationRecord.from_dict() deserializes correctly."""
        data = {
            "number": 3,
            "started_at": 3000.0,
            "ended_at": 3010.0,
            "action_taken": "execute:my_plan",
            "result": "success",
            "plans_completed": ["plan1", "plan2"],
            "output_file": "/tmp/iteration3.log",
        }

        iteration = IterationRecord.from_dict(data)

        assert iteration.number == 3
        assert iteration.started_at == 3000.0
        assert iteration.ended_at == 3010.0
        assert iteration.action_taken == "execute:my_plan"
        assert iteration.result == "success"
        assert iteration.plans_completed == ["plan1", "plan2"]
        assert iteration.output_file == "/tmp/iteration3.log"

    def test_plan_info_to_dict(self):
        """PlanInfo.to_dict() serializes correctly."""
        info = PlanInfo(
            name="test_plan",
            path=Path("/tmp/test_plan"),
            status="active",
            has_orchestration=True,
            action_required="execute",
            dependencies=["dep1", "dep2"],
            pending_tasks=3,
            completed_tasks=2,
            current_task="T4",
        )

        result = info.to_dict()

        assert result["name"] == "test_plan"
        assert result["path"] == "/tmp/test_plan"
        assert result["status"] == "active"
        assert result["has_orchestration"] is True
        assert result["action_required"] == "execute"
        assert result["dependencies"] == ["dep1", "dep2"]
        assert result["pending_tasks"] == 3
        assert result["completed_tasks"] == 2
        assert result["current_task"] == "T4"


class TestGetNextAction:
    """Test get_next_action method."""

    def test_get_next_action_execute_first(self, tmp_path):
        """get_next_action returns first execute action."""
        create_test_plan(
            tmp_path,
            "plan1",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_test_plan(tmp_path, "plan2", has_mmd=False)

        service = RalphLoopService(plans_dir=tmp_path)
        action = service.get_next_action()

        assert action is not None
        assert action.action == "execute"
        assert action.plan_name == "plan1"

    def test_get_next_action_plan_when_no_execute(self, tmp_path):
        """get_next_action returns plan action when no execute actions."""
        create_test_plan(tmp_path, "plan1", has_mmd=False)

        service = RalphLoopService(plans_dir=tmp_path)
        action = service.get_next_action()

        assert action is not None
        assert action.action == "plan"
        assert action.plan_name == "plan1"

    def test_get_next_action_none_when_all_complete(self, tmp_path):
        """get_next_action returns None when all plans complete."""
        create_test_plan(
            tmp_path,
            "plan1",
            task_statuses=[{"id": "T1", "status": "completed"}],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        action = service.get_next_action()

        assert action is None

    def test_get_next_action_skips_blocked(self, tmp_path):
        """get_next_action skips blocked plans."""
        # Create unmet dependency
        create_test_plan(
            tmp_path,
            "dep_plan",
            task_statuses=[{"id": "T1", "status": "pending"}],
        )

        # Create blocked plan
        create_test_plan(
            tmp_path,
            "blocked_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
            dependencies=["dep_plan"],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        action = service.get_next_action()

        # Should return execute action for dep_plan, not blocked_plan
        assert action is not None
        assert action.action == "execute"
        assert action.plan_name == "dep_plan"


class TestCheckAllComplete:
    """Test check_all_complete method."""

    def test_check_all_complete_true_when_all_done(self, tmp_path):
        """check_all_complete returns True when all plans completed."""
        create_test_plan(
            tmp_path,
            "plan1",
            task_statuses=[{"id": "T1", "status": "completed"}],
        )
        create_test_plan(
            tmp_path,
            "plan2",
            task_statuses=[{"id": "T1", "status": "completed"}],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        result = service.check_all_complete()

        assert result is True

    def test_check_all_complete_false_with_execute(self, tmp_path):
        """check_all_complete returns False when execute actions remain."""
        create_test_plan(
            tmp_path,
            "plan1",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        result = service.check_all_complete()

        assert result is False

    def test_check_all_complete_false_with_needs_planning(self, tmp_path):
        """check_all_complete returns False when planning needed."""
        create_test_plan(tmp_path, "plan1", has_mmd=False)

        service = RalphLoopService(plans_dir=tmp_path)
        result = service.check_all_complete()

        assert result is False

    def test_check_all_complete_true_with_only_blocked(self, tmp_path):
        """check_all_complete returns True when only blocked plans remain."""
        # Create blocked plan with no dependency satisfied
        create_test_plan(
            tmp_path,
            "blocked_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
            dependencies=["nonexistent_dep"],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        result = service.check_all_complete()

        # All executable work is done (blocked plans don't count)
        assert result is True

    def test_check_all_complete_empty_directory(self, tmp_path):
        """check_all_complete returns True when no plans exist."""
        service = RalphLoopService(plans_dir=tmp_path)
        result = service.check_all_complete()

        assert result is True


class TestServiceInitialization:
    """Test RalphLoopService initialization."""

    def test_init_with_custom_plans_dir(self, tmp_path):
        """Service accepts custom plans_dir."""
        service = RalphLoopService(plans_dir=tmp_path)

        assert service.plans_dir == tmp_path

    @patch("subprocess.run")
    def test_init_without_plans_dir_finds_git_root(self, mock_run, tmp_path):
        """Service finds git root when plans_dir not provided."""
        mock_run.return_value = MagicMock(
            stdout=str(tmp_path) + "\n",
            returncode=0,
        )

        service = RalphLoopService()

        assert service.plans_dir == tmp_path / "docs" / "plans" / "live"

    @patch("subprocess.run")
    def test_init_without_plans_dir_fallback_on_git_error(self, mock_run, tmp_path):
        """Service falls back to cwd when git command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        service = RalphLoopService()

        # Should fall back to cwd/docs/plans/live
        expected = Path.cwd() / "docs" / "plans" / "live"
        assert service.plans_dir == expected

    def test_state_dir_created(self, tmp_path):
        """State directory is created on initialization."""
        service = RalphLoopService(plans_dir=tmp_path)

        assert service.state_dir.exists()
        assert service.state_dir.is_dir()
        assert service.state_dir == Path.home() / ".agentic" / "ralph"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_corrupted_plan_yaml_skipped(self, tmp_path):
        """Plans with corrupted YAML are handled gracefully."""
        plan_dir = tmp_path / "corrupted_plan"
        plan_dir.mkdir()
        (plan_dir / "plan_build.yml").write_text("invalid: yaml: [unclosed")

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        # Corrupted plan is discovered but with zero tasks
        # (yaml.safe_load returns None on error, handled by _analyze_plan_file)
        assert len(plans) == 1
        assert plans[0].pending_tasks == 0
        assert plans[0].completed_tasks == 0

    def test_plan_with_in_progress_tasks(self, tmp_path):
        """Plan with in_progress tasks shows correct counts."""
        create_test_plan(
            tmp_path,
            "test_plan",
            task_statuses=[
                {"id": "T1", "status": "completed"},
                {"id": "T2", "status": "in_progress"},
                {"id": "T3", "status": "pending"},
            ],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].pending_tasks == 2  # in_progress + pending
        assert plans[0].completed_tasks == 1
        assert plans[0].current_task == "T2"  # in_progress is current

    def test_empty_plan_build_file(self, tmp_path):
        """Plan with empty plan_build.yml is handled gracefully."""
        plan_dir = tmp_path / "empty_plan"
        plan_dir.mkdir()
        (plan_dir / "plan_build.yml").write_text("")

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        # Empty plan should still be discovered but with zero tasks
        assert len(plans) == 1
        assert plans[0].pending_tasks == 0
        assert plans[0].completed_tasks == 0

    def test_plan_with_no_tasks(self, tmp_path):
        """Plan with no tasks section is handled correctly."""
        plan_dir = tmp_path / "no_tasks"
        plan_dir.mkdir()
        plan_data = {"name": "no_tasks", "status": "active", "phases": []}
        (plan_dir / "plan_build.yml").write_text(yaml.dump(plan_data))

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].pending_tasks == 0
        assert plans[0].completed_tasks == 0

    def test_multiple_iterations_recorded(self, isolated_service):
        """Multiple iterations are recorded correctly."""
        isolated_service.start_loop()

        # Record multiple iterations
        for i in range(1, 4):
            action = PlanAction(
                action="execute",
                plan_name=f"plan{i}",
                task_id=f"T{i}",
            )
            isolated_service.record_iteration(action, "success")

        state = isolated_service.get_state()
        assert state is not None
        assert len(state.iterations) == 3
        assert state.current_iteration == 3
        assert state.iterations[0].number == 1
        assert state.iterations[1].number == 2
        assert state.iterations[2].number == 3

    def test_atomic_state_write(self, isolated_service):
        """State writes use atomic temp file pattern."""
        state = isolated_service.start_loop()

        state_file = isolated_service.state_dir / "state.json"
        assert state_file.exists()

        # No temp files should remain
        temp_files = list(isolated_service.state_dir.glob("*.tmp.*"))
        assert len(temp_files) == 0

    def test_invalid_state_file_returns_none(self, isolated_service):
        """Corrupted state file returns None from get_state."""
        # Create corrupted state file
        state_file = isolated_service.state_dir / "state.json"
        state_file.write_text("invalid json {")

        state = isolated_service.get_state()
        assert state is None


# Helper for question tests

def create_question_file(plan_dir: Path, severity: str = "blocking", question_id: str = "Q-20260221-120000-a1b2") -> Path:
    """Create a question YAML file in a plan's questions/pending/ directory."""
    pending_dir = plan_dir / "questions" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)

    question_data = {
        "id": question_id,
        "text": "Test question?",
        "context": "Test context",
        "severity": severity,
        "asked_by": "agent",
        "created_at": 1740100000.0,
        "status": "pending",
    }

    question_file = pending_dir / f"{question_id}.yml"
    question_file.write_text(yaml.dump(question_data))
    return question_file


class TestBlockingQuestions:
    """Test blocking question detection."""

    def test_has_blocking_questions_returns_true_when_blocking_exist(self, tmp_path):
        """_has_blocking_questions returns (True, 1) when blocking question exists."""
        plan_dir = create_test_plan(tmp_path, "test_plan")
        create_question_file(plan_dir, severity="blocking")

        service = RalphLoopService(plans_dir=tmp_path)
        has_blocking, count = service._has_blocking_questions(plan_dir)

        assert has_blocking is True
        assert count == 1

    def test_has_blocking_questions_returns_false_when_no_blocking(self, tmp_path):
        """_has_blocking_questions returns (False, 0) when no blocking questions."""
        plan_dir = create_test_plan(tmp_path, "test_plan")
        create_question_file(plan_dir, severity="medium")

        service = RalphLoopService(plans_dir=tmp_path)
        has_blocking, count = service._has_blocking_questions(plan_dir)

        assert has_blocking is False
        assert count == 0

    def test_has_blocking_questions_missing_dir(self, tmp_path):
        """_has_blocking_questions returns (False, 0) when no questions directory."""
        plan_dir = create_test_plan(tmp_path, "test_plan")
        # No questions directory created - just the plan

        service = RalphLoopService(plans_dir=tmp_path)
        has_blocking, count = service._has_blocking_questions(plan_dir)

        assert has_blocking is False
        assert count == 0

    def test_discover_plans_blocks_on_questions(self, tmp_path):
        """discover_plans sets action_required='blocked' when blocking questions exist."""
        plan_dir = create_test_plan(
            tmp_path,
            "test_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(plan_dir, severity="blocking")

        service = RalphLoopService(plans_dir=tmp_path)
        plans = service.discover_plans()

        assert len(plans) == 1
        assert plans[0].action_required == "blocked"
        assert plans[0].blocking_questions > 0


class TestDetermineAction:
    """Test _determine_action_required edge cases."""

    def test_determine_action_empty_plan_no_mmd(self, tmp_path):
        """Empty plan without orchestration returns 'needs_planning'."""
        service = RalphLoopService(plans_dir=tmp_path)
        action = service._determine_action_required(
            has_orchestration=False,
            pending_tasks=0,
            completed_tasks=0,
        )

        assert action == "needs_planning"

    def test_determine_action_empty_plan_with_mmd(self, tmp_path):
        """Empty plan with orchestration returns 'completed'."""
        service = RalphLoopService(plans_dir=tmp_path)
        action = service._determine_action_required(
            has_orchestration=True,
            pending_tasks=0,
            completed_tasks=0,
        )

        assert action == "completed"


class TestCompletionStatus:
    """Test get_completion_status method."""

    def test_get_completion_status_blocked_by_questions(self, tmp_path):
        """Completion status counts plans blocked by questions."""
        plan_dir = create_test_plan(
            tmp_path,
            "test_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(plan_dir, severity="blocking")

        service = RalphLoopService(plans_dir=tmp_path)
        status = service.get_completion_status()

        assert status["blocked_by_questions"] == 1
        assert status["can_emit_promise"] is False

    def test_get_completion_status_all_complete(self, tmp_path):
        """Completion status shows can_emit_promise when all plans complete."""
        create_test_plan(
            tmp_path,
            "plan_one",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "completed"}],
        )
        create_test_plan(
            tmp_path,
            "plan_two",
            has_mmd=True,
            task_statuses=[
                {"id": "T1", "status": "completed"},
                {"id": "T2", "status": "completed"},
            ],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        status = service.get_completion_status()

        assert status["can_emit_promise"] is True
        assert status["all_complete"] is True
        assert status["in_progress"] == 0
        assert status["blocked_by_questions"] == 0
        assert status["blocked_by_deps"] == 0
        assert status["completed"] == 2

    def test_get_completion_status_blocked_by_deps(self, tmp_path):
        """Completion status counts plans blocked by unmet dependencies."""
        # Create pending dependency plan
        create_test_plan(
            tmp_path,
            "dep_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        # Create plan blocked by dependency
        create_test_plan(
            tmp_path,
            "blocked_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
            dependencies=["dep_plan"],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        status = service.get_completion_status()

        assert status["blocked_by_deps"] == 1
        assert status["in_progress"] == 1  # dep_plan is executable
        assert status["can_emit_promise"] is False

    def test_get_completion_status_can_emit_with_dep_blocked(self, tmp_path):
        """can_emit_promise is True even with dep-blocked plans (deps may be external)."""
        # Only a dep-blocked plan, no in_progress or question-blocked
        create_test_plan(
            tmp_path,
            "blocked_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
            dependencies=["nonexistent_external_dep"],
        )

        service = RalphLoopService(plans_dir=tmp_path)
        status = service.get_completion_status()

        assert status["blocked_by_deps"] == 1
        assert status["in_progress"] == 0
        assert status["blocked_by_questions"] == 0
        assert status["can_emit_promise"] is True
        assert status["all_complete"] is False  # not truly all complete

    def test_get_completion_status_in_progress_count(self, tmp_path):
        """in_progress counts both execute and needs_planning plans."""
        create_test_plan(
            tmp_path,
            "exec_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_test_plan(
            tmp_path,
            "needs_plan",
            has_mmd=False,
        )

        service = RalphLoopService(plans_dir=tmp_path)
        status = service.get_completion_status()

        assert status["in_progress"] == 2
        assert status["can_emit_promise"] is False

    def test_get_completion_status_empty_dir(self, tmp_path):
        """Empty directory returns all zeros and can_emit_promise True."""
        service = RalphLoopService(plans_dir=tmp_path)
        status = service.get_completion_status()

        assert status["all_complete"] is True
        assert status["blocked_by_deps"] == 0
        assert status["blocked_by_questions"] == 0
        assert status["in_progress"] == 0
        assert status["completed"] == 0
        assert status["can_emit_promise"] is True
