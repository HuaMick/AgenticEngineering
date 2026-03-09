"""Tests for Ralph Loop Service.

Tests use TinyDB-backed EpicRepository as the sole data store.
The create_test_plan helper populates both filesystem and TinyDB.
"""

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
    EpicAction,
    EpicInfo,
    RalphLoopService,
    RalphState,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
def isolated_service(tmp_path, _isolate_tinydb):
    """Create service with isolated state and TinyDB."""
    service = RalphLoopService(epics_dir=tmp_path)
    service.state_dir = tmp_path / ".state"
    service.state_dir.mkdir(parents=True, exist_ok=True)
    # Inject isolated repository so tests don't hit the real DB
    from agenticguidance.services.epic_repository import EpicRepository
    service._repository = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
    return service


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def create_test_plan(
    tmp_path: Path,
    name: str,
    has_mmd: bool = True,
    task_statuses: list[dict] | None = None,
    dependencies: list[str] | None = None,
    status: str = "active",
    db_path: Path | None = None,
) -> Path:
    """Create a test plan directory and populate TinyDB.

    Creates filesystem artifacts (YAML + optional MMD) and registers the epic
    and all tickets in TinyDB so RalphLoopService can discover them.

    Args:
        tmp_path: Temporary path for test plans.
        name: Name of the plan directory.
        has_mmd: Whether to create orchestration MMD file.
        task_statuses: List of task dicts with id and status.
        dependencies: Ignored (deps not tracked in TinyDB; kept for API compat).
        status: Plan status (active, completed, deferred).
        db_path: Path to TinyDB DB file. If None, derived from tmp_path.

    Returns:
        Path to the created plan directory.
    """
    from agenticguidance.services.epic_repository import EpicRepository

    plan_dir = tmp_path / name
    plan_dir.mkdir(exist_ok=True)

    # Create plan_build.yml (may still be needed for some tests)
    tasks = task_statuses or [{"id": "T1", "status": "pending"}]
    plan_data = {
        "name": name,
        "status": status,
        "phases": [{"name": "Phase 1", "tickets": tasks}],
    }
    if dependencies:
        plan_data["dependencies"] = {"depends_on": dependencies}
    (plan_dir / "plan_build.yml").write_text(yaml.dump(plan_data))

    # Derive db_path if not given (use tmp_path as "repo root")
    if db_path is None:
        db_path = tmp_path / ".agentic" / "epics.db"

    # Populate TinyDB
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    repo.create_epic({
        "epic_folder_name": name,
        "epic_folder": str(plan_dir),
        "name": name,
        "status": status,
    })
    for task in tasks:
        repo.add_ticket(name, "Phase 1", task)

    # If has_mmd is True, also insert a TinyDB phase with an agent so that
    # _has_orchestration_file / _check_has_orchestration returns True.
    # The MMD filesystem check has been removed (T3_1, T3_3).
    if has_mmd:
        repo.add_phase(name, {"name": "Phase 1", "agent": "build-python"})

    repo.close()

    return plan_dir


def make_service(tmp_path: Path, epics_dir: Path | None = None) -> RalphLoopService:
    """Create a RalphLoopService with the test-local isolated TinyDB.

    Args:
        tmp_path: The pytest tmp_path fixture value.
        epics_dir: Override for epics directory. Defaults to tmp_path.

    Returns:
        RalphLoopService with injected isolated EpicRepository.
    """
    from agenticguidance.services.epic_repository import EpicRepository

    service = RalphLoopService(epics_dir=epics_dir or tmp_path)
    db_path = tmp_path / ".agentic" / "epics.db"
    service._repository = EpicRepository(db_path=db_path, auto_bootstrap=False)
    return service


def create_question_file(
    plan_dir: Path,
    severity: str = "blocking",
    question_id: str | None = None,
) -> None:
    """Create a question YAML file in the plan's pending questions directory.

    Args:
        plan_dir: Path to the plan folder.
        severity: Severity level ("blocking", "high", "medium", "low").
        question_id: Optional question ID. Generates one if not given.
    """
    if question_id is None:
        question_id = f"Q-test-{uuid.uuid4().hex[:8]}"
    pending_dir = plan_dir / "questions" / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    question_data = {
        "id": question_id,
        "text": f"Test question {question_id}",
        "context": "unit test",
        "severity": severity,
        "asked_by": "test",
        "created_at": time.time(),
        "status": "pending",
        "answer": None,
        "answered_at": None,
        "answered_by": None,
    }
    (pending_dir / f"{question_id}.yml").write_text(yaml.dump(question_data))


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------

class TestEpicDiscovery:
    """Test epic discovery functionality."""

    def test_discover_empty_dir(self, tmp_path):
        """Empty directory returns empty list."""
        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert plans == []

    def test_discover_single_plan(self, tmp_path):
        """Single plan with plan_build.yml is discovered."""
        create_test_plan(tmp_path, "test_plan")

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        assert plans[0].name == "test_plan"
        assert plans[0].path == tmp_path / "test_plan"

    def test_discover_multiple_plans(self, tmp_path):
        """Multiple plans are all discovered."""
        create_test_plan(tmp_path, "plan_one")
        create_test_plan(tmp_path, "plan_two")
        create_test_plan(tmp_path, "plan_three")

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 3
        plan_names = {p.name for p in plans}
        assert plan_names == {"plan_one", "plan_two", "plan_three"}

    def test_discover_with_orchestration(self, tmp_path):
        """Plan with orchestration_*.mmd has has_orchestration=True."""
        create_test_plan(tmp_path, "test_plan", has_mmd=True)

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        assert plans[0].has_orchestration is True

    def test_discover_without_orchestration(self, tmp_path):
        """Plan without orchestration MMD has has_orchestration=False."""
        create_test_plan(tmp_path, "test_plan", has_mmd=False)

        service = make_service(tmp_path)
        plans = service.discover_epics()

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

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        assert plans[0].action_required == "execute"
        assert plans[0].pending_tasks == 2

    def test_action_required_needs_planning(self, tmp_path):
        """Plan without MMD gets action_required='needs_planning'."""
        create_test_plan(tmp_path, "test_plan", has_mmd=False)

        service = make_service(tmp_path)
        plans = service.discover_epics()

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

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        assert plans[0].action_required == "completed"
        assert plans[0].pending_tasks == 0
        assert plans[0].completed_tasks == 2

    def test_discover_skips_hidden_directories(self, tmp_path):
        """Hidden directories are skipped (not in TinyDB)."""
        # Hidden dirs are not registered in TinyDB, so they won't appear.
        # Also register the visible plan normally.
        create_test_plan(tmp_path, "visible_plan")
        # Do NOT register .hidden_plan in TinyDB

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        assert plans[0].name == "visible_plan"

    def test_discover_skips_non_plan_directories(self, tmp_path):
        """Directories not registered in TinyDB are skipped."""
        # Create dir without plan registration in TinyDB
        non_plan = tmp_path / "not_a_plan"
        non_plan.mkdir()
        (non_plan / "README.md").write_text("Not a plan")

        # Create valid plan with TinyDB entry
        create_test_plan(tmp_path, "valid_plan")

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        assert plans[0].name == "valid_plan"

    def test_discover_current_task(self, tmp_path):
        """Current task is detected correctly from TinyDB."""
        create_test_plan(
            tmp_path,
            "test_plan",
            task_statuses=[
                {"id": "T1", "status": "completed"},
                {"id": "T2", "status": "pending"},
                {"id": "T3", "status": "pending"},
            ],
        )

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        assert plans[0].current_task == "T2"

    def test_discover_status_from_tinydb(self, tmp_path):
        """Plan status is read from TinyDB."""
        create_test_plan(tmp_path, "deferred_plan", status="deferred")

        service = make_service(tmp_path)
        plans = service.discover_epics()

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

        service = make_service(tmp_path)
        queue = service.get_priority_queue()

        assert len(queue) == 2
        # Execute action should be first
        assert queue[0].action == "execute"
        assert queue[0].plan_name == "plan_ready"
        # Plan action should be second
        assert queue[1].action == "plan"
        assert queue[1].plan_name == "plan_needs_planning"

    def test_blocked_plans_at_end(self, tmp_path):
        """Question-blocked plans are marked blocked in queue."""
        # Plan ready to execute
        create_test_plan(
            tmp_path,
            "ready_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )

        # Create plan that is question-blocked
        blocked_dir = create_test_plan(
            tmp_path,
            "question_blocked",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(blocked_dir, severity="blocking")

        service = make_service(tmp_path)
        queue = service.get_priority_queue()

        assert len(queue) == 2
        # Execute action should be first
        assert queue[0].action == "execute"
        assert queue[0].plan_name == "ready_plan"
        # Blocked plan last
        assert queue[1].action == "blocked"
        assert queue[1].plan_name == "question_blocked"

    def test_empty_queue_when_all_complete(self, tmp_path):
        """Empty queue when all plans complete."""
        create_test_plan(
            tmp_path,
            "completed_plan",
            task_statuses=[{"id": "T1", "status": "completed"}],
        )

        service = make_service(tmp_path)
        queue = service.get_priority_queue()

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

        service = make_service(tmp_path)
        queue = service.get_priority_queue()

        # First two should be execute actions
        assert queue[0].action == "execute"
        assert queue[1].action == "execute"

        # Next two should be plan actions
        assert queue[2].action == "plan"
        assert queue[3].action == "plan"


class TestDependencyResolution:
    """Test dependency parsing and resolution.

    Note: _parse_dependencies() currently returns [] for all plans since
    dependency data is not stored in TinyDB. Tests reflect this behavior.
    Question-based blocking is fully functional.
    """

    def test_parse_dependencies_empty(self, tmp_path):
        """Plan without dependencies returns empty list."""
        create_test_plan(tmp_path, "test_plan")

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        # _parse_dependencies always returns [] in the TinyDB-only model
        assert plans[0].dependencies == []

    def test_parse_dependencies_returns_empty_list(self, tmp_path):
        """_parse_dependencies returns [] regardless of YAML content (TinyDB-only)."""
        create_test_plan(
            tmp_path,
            "test_plan",
            dependencies=["dep1", "dep2"],
        )

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        # TinyDB-only: dependencies are not stored/read from YAML
        assert plans[0].dependencies == []

    def test_plan_with_deps_in_yaml_not_blocked(self, tmp_path):
        """Plan listed as dependent in YAML is not blocked (deps not in TinyDB)."""
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
            dependencies=["dep_plan"],  # This is ignored in TinyDB-only mode
        )

        service = make_service(tmp_path)
        plans = service.discover_epics()

        # Find dependent plan - should NOT be blocked since deps aren't tracked
        dependent = next(p for p in plans if p.name == "dependent_plan")
        assert dependent.action_required == "execute"

    def test_question_blocked_plan(self, tmp_path):
        """Plan with blocking questions is marked blocked."""
        plan_dir = create_test_plan(
            tmp_path,
            "question_blocked",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(plan_dir, severity="blocking")

        service = make_service(tmp_path)
        plans = service.discover_epics()

        question_blocked = next(p for p in plans if p.name == "question_blocked")
        assert question_blocked.action_required == "blocked"

    def test_blocked_reason_shows_questions(self, tmp_path):
        """Blocked reason shows blocking questions when present."""
        plan_dir = create_test_plan(
            tmp_path,
            "question_blocked",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(plan_dir, severity="blocking", question_id="Q-20260221-120000-a1b2")
        create_question_file(plan_dir, severity="blocking", question_id="Q-20260221-120001-c3d4")

        service = make_service(tmp_path)
        queue = service.get_priority_queue()

        # Find blocked action
        blocked = next(a for a in queue if a.action == "blocked")
        assert "question" in blocked.reason.lower()
        assert "2" in blocked.reason

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

        service = make_service(tmp_path)
        queue = service.get_priority_queue()

        blocked = next(a for a in queue if a.action == "blocked")
        assert blocked.reason == "Blocked by 2 pending blocking question(s)"


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

        action = EpicAction(
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
        service1 = make_service(tmp_path)
        service1.state_dir = state_dir
        state1 = service1.start_loop(prompt_file="/tmp/prompt.txt")

        # Create new service instance and retrieve state
        service2 = make_service(tmp_path)
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
        action = EpicAction(action="execute", plan_name="test")

        with pytest.raises(RuntimeError) as exc_info:
            isolated_service.record_iteration(action, "success")

        assert "No active Ralph loop state" in str(exc_info.value)

    def test_stop_loop_with_different_reasons(self, tmp_path):
        """stop_loop sets correct status based on reason."""
        # Use isolated state dir
        state_dir = tmp_path / ".state"
        state_dir.mkdir()

        # Test completed
        service = make_service(tmp_path)
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
        """EpicAction.to_dict() serializes correctly."""
        action = EpicAction(
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
        """EpicAction.to_dict() handles None values."""
        action = EpicAction(action="complete")

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
        """EpicInfo.to_dict() serializes correctly."""
        info = EpicInfo(
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

        service = make_service(tmp_path)
        action = service.get_next_action()

        assert action is not None
        assert action.action == "execute"
        assert action.plan_name == "plan1"

    def test_get_next_action_plan_when_no_execute(self, tmp_path):
        """get_next_action returns plan action when no execute actions."""
        create_test_plan(tmp_path, "plan1", has_mmd=False)

        service = make_service(tmp_path)
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

        service = make_service(tmp_path)
        action = service.get_next_action()

        assert action is None

    def test_get_next_action_skips_question_blocked(self, tmp_path):
        """get_next_action skips question-blocked plans."""
        # Create unblocked plan
        create_test_plan(
            tmp_path,
            "ready_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )

        # Create question-blocked plan
        blocked_dir = create_test_plan(
            tmp_path,
            "blocked_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(blocked_dir, severity="blocking")

        service = make_service(tmp_path)
        action = service.get_next_action()

        # Should return execute action for ready_plan, not blocked_plan
        assert action is not None
        assert action.action == "execute"
        assert action.plan_name == "ready_plan"


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

        service = make_service(tmp_path)
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

        service = make_service(tmp_path)
        result = service.check_all_complete()

        assert result is False

    def test_check_all_complete_false_with_needs_planning(self, tmp_path):
        """check_all_complete returns False when planning needed."""
        create_test_plan(tmp_path, "plan1", has_mmd=False)

        service = make_service(tmp_path)
        result = service.check_all_complete()

        assert result is False

    def test_check_all_complete_with_question_blocked_plan(self, tmp_path):
        """check_all_complete returns True when a plan is blocked by questions.

        A blocked plan cannot execute, so it does not count as 'incomplete' in the
        sense of check_all_complete (which only returns False for 'execute' or
        'needs_planning' actions).
        """
        # Create plan with blocking question (blocked)
        blocked_dir = create_test_plan(
            tmp_path,
            "blocked_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(blocked_dir, severity="blocking")

        service = make_service(tmp_path)
        result = service.check_all_complete()

        # Blocked plans have action_required='blocked', not 'execute' or 'needs_planning',
        # so check_all_complete treats them as not actively incomplete.
        assert result is True

    def test_check_all_complete_empty_directory(self, tmp_path):
        """check_all_complete returns True when no plans exist."""
        service = make_service(tmp_path)
        result = service.check_all_complete()

        assert result is True


class TestServiceInitialization:
    """Test RalphLoopService initialization."""

    def test_init_with_custom_epics_dir(self, tmp_path):
        """Service accepts custom epics_dir."""
        service = RalphLoopService(epics_dir=tmp_path)

        assert service.epics_dir == tmp_path

    @patch("subprocess.run")
    def test_init_without_epics_dir_finds_git_root(self, mock_run, tmp_path):
        """Service finds git root when no epics_dir provided."""
        mock_run.return_value = MagicMock(
            stdout=str(tmp_path) + "\n",
            returncode=0,
        )

        service = RalphLoopService()
        expected_dir = tmp_path / "docs" / "epics" / "live"

        assert service.epics_dir == expected_dir


class TestQuestionBlocking:
    """Test question-based plan blocking."""

    def test_blocking_question_blocks_plan(self, tmp_path):
        """A plan with a blocking question is marked as blocked."""
        plan_dir = create_test_plan(
            tmp_path,
            "test_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(plan_dir, severity="blocking")

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        assert plans[0].action_required == "blocked"
        assert plans[0].blocking_questions == 1

    def test_non_blocking_question_does_not_block(self, tmp_path):
        """A plan with only medium questions is not blocked."""
        plan_dir = create_test_plan(
            tmp_path,
            "test_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(plan_dir, severity="medium")

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert len(plans) == 1
        assert plans[0].action_required == "execute"  # Not blocked by medium question
        assert plans[0].blocking_questions == 0

    def test_multiple_blocking_questions(self, tmp_path):
        """Plan blocking count includes all blocking questions."""
        plan_dir = create_test_plan(
            tmp_path,
            "test_plan",
            has_mmd=True,
            task_statuses=[{"id": "T1", "status": "pending"}],
        )
        create_question_file(plan_dir, severity="blocking", question_id="Q-001")
        create_question_file(plan_dir, severity="blocking", question_id="Q-002")
        create_question_file(plan_dir, severity="blocking", question_id="Q-003")

        service = make_service(tmp_path)
        plans = service.discover_epics()

        assert plans[0].blocking_questions == 3
        assert plans[0].action_required == "blocked"
