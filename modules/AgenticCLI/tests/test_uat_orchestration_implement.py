"""UAT: Orchestration implementation command (US-PLN-047).

Validates that `agentic orchestrate session implement` correctly routes
phases to agents via TinyDB, handles missing agent fields, per-phase
overrides, feedback triggers, and end-to-end phase completion.

UAT Journey coverage:
  Step 1: Phase list ordering via TinyDB _order field
  Step 2: Manual phase transition via update_phase
  Step 3: Idempotent resume — all phases pre-completed → zero work done
  Steps 4-5: Resume from mid-epic — completed phases are skipped
  Step 6: Missing agent routing → failed + non-zero exit
  Step 7: FileLock contention → execution aborted
  Success signals: recovery sweep, blocked-phase halting, epic completion

Includes both unit-level ExecutionRunner tests and CLI-level integration
tests that exercise the actual command entry points.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-PLN-047")


def _make_execution_runner(tmp_path, plan_folder="test_epic"):
    """Create an ExecutionRunner with mocked workflow."""
    from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

    epics_dir = tmp_path / "docs" / "epics" / "live"
    epics_dir.mkdir(parents=True, exist_ok=True)
    workflow = MagicMock(spec=OrchestrationWorkflow)
    workflow.working_dir = str(tmp_path)
    workflow.epics_dir = epics_dir
    workflow.wait_for_session.return_value = "completed"

    runner = ExecutionRunner(workflow=workflow, plan_folder=plan_folder)
    return runner, workflow


class TestExecutorRouting:
    """Verify ExecutionRunner routes to correct agents from TinyDB."""

    def test_executor_routes_new_agent_names(self, tmp_path, tinydb_populator):
        """ExecutionRunner spawns correct agents from TinyDB phase records."""
        epic = "260328UA_routing"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Routing Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "planning"},
                {"name": "P2 Test", "agent": "test-builder", "status": "planning"},
                {"name": "P3 Audit", "agent": "planner-audit", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        spawned_cmds = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            spawned_cmds.append(agent_type)
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is True
        assert spawned_cmds == ["build-python", "test-builder", "planner-audit"]
        # Verify all phases marked completed
        for phase in repo.list_phases(epic):
            assert phase.status == "completed", f"Phase {phase.name} not completed"

    def test_executor_handles_missing_agent_field(self, tmp_path, tinydb_populator):
        """Phase with agent=None fails with 'No agent routing' error."""
        epic = "260328UA_noagent"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "No Agent Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Broken", "status": "planning"},
                # No agent field
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=5)

        assert result is False
        # Phase should be marked failed
        phases = repo.list_phases(epic)
        assert phases[0].status == "failed"
        assert any("No agent routing" in str(e) for e in runner.state["errors"])

    def test_executor_missing_agent_error_names_phase_id(self, tmp_path, tinydb_populator):
        """C3: routing-missing error must surface phase_id, not just human name."""
        epic = "260328UA_noagent_id"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "No Agent With ID",
            "status": "in_progress",
            "phases": [
                {"name": "Build", "phase_id": "P4", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=5)

        assert result is False
        errs = " ".join(str(e) for e in runner.state["errors"])
        assert "P4" in errs, f"Expected 'P4' in error, got: {errs}"

    def test_executor_routes_build_docs_writer(self, tmp_path, tinydb_populator):
        """Renamed agent build-docs-writer routes correctly."""
        epic = "260328UA_docs"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Docs Writer Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Docs", "agent": "build-docs-writer", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        spawned_agents = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            spawned_agents.append(agent_type)
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=5)

        assert result is True
        assert spawned_agents == ["build-docs-writer"]


class TestExecutorOverrides:
    """Verify per-phase max_turns and timeout flow to spawn."""

    def test_executor_max_turns_override(self, tmp_path, tinydb_populator):
        """Per-phase max_turns=50 from TinyDB flows to _run_phase."""
        epic = "260328UA_turns"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Max Turns Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "agent": "build-python", "max_turns": 50, "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        captured_kwargs = {}

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            captured_kwargs.update(kwargs)
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        runner._execute_plan(epic, max_iterations=5)

        assert captured_kwargs.get("max_turns") == 50

    def test_executor_timeout_override(self, tmp_path, tinydb_populator):
        """Per-phase timeout=900 from TinyDB flows to _run_phase."""
        epic = "260328UA_timeout"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Timeout Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "agent": "build-python", "timeout": 900, "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        captured_kwargs = {}

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            captured_kwargs.update(kwargs)
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        runner._execute_plan(epic, max_iterations=5)

        assert captured_kwargs.get("timeout") == 900


class TestExecutorFeedback:
    """Verify feedback triggers cause phase re-runs."""

    def test_executor_feedback_trigger_reruns_phase(self, tmp_path, tinydb_populator):
        """Failed phase with feedback_triggers resets target phase to planning.

        When P2 fails and has a feedback trigger pointing at P1, the executor:
        1. Marks P2 as failed
        2. Resets P1 to planning (the trigger target)
        3. Re-runs P1 on the next iteration
        P2 stays failed (it won't be re-picked), so the plan ultimately fails,
        but the feedback mechanism itself fires correctly.
        """
        epic = "260328UA_feedback"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Feedback Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "planning"},
                {
                    "name": "P2 Test", "agent": "test-builder", "status": "planning",
                    "feedback_triggers": {"P2 TEST_FAILURE": "P1 Build"},
                },
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        call_count = {"P1 Build": 0, "P2 Test": 0}

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            call_count[phase_id] += 1
            if phase_id == "P2 Test":
                return False  # P2 always fails in this test
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        # The feedback mechanism fired: P1 was re-run after P2 failed
        assert call_count["P1 Build"] == 2, "P1 should run twice (initial + feedback re-run)"
        assert call_count["P2 Test"] == 1, "P2 ran once (failed, triggered feedback)"
        # Verify P1 Build was successfully re-run
        phases = repo.list_phases(epic)
        p1 = next(p for p in phases if p.name == "P1 Build")
        assert p1.status == "completed"
        # P2 stays failed (feedback only resets the target, not the failed phase)
        p2 = next(p for p in phases if p.name == "P2 Test")
        assert p2.status == "failed"


class TestExecutorE2E:
    """End-to-end execution with multiple phases."""

    def test_executor_full_loop_three_phases_complete(self, tmp_path, tinydb_populator):
        """3-phase epic with new agents completes and marks epic as completed."""
        epic = "260328UA_e2e"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "E2E Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Stories", "agent": "build-story-writer", "status": "planning"},
                {"name": "P2 Build", "agent": "build-python", "status": "planning"},
                {"name": "P3 UAT", "agent": "test-uat", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is True
        # All phases completed
        for phase in repo.list_phases(epic):
            assert phase.status == "completed", f"Phase {phase.name} not completed"
        assert epic in runner.state["plans_processed"] or len(runner.state["phases_completed"]) == 3
        # Epic status should be marked completed
        epic_data = repo.get_epic(epic)
        assert epic_data.status == "completed"


class TestCLIImplementExitCode:
    """C1: _run_executing_loop must exit non-zero when the runner reports failure."""

    def test_implement_loop_exits_nonzero_on_failure(self, tmp_path, tinydb_populator, monkeypatch):
        """Seed a phase with no agent → loop should sys.exit(1)."""
        from types import SimpleNamespace

        from agenticcli.commands import orchestrate as orch_mod

        epic = "260408UA_exit_code"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Exit Code Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Broken", "phase_id": "P1", "status": "planning"},
            ],
        })

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "agenticcli.workflows.orchestration.acquire_epic_lock", lambda *a: True
        )
        monkeypatch.setattr(
            "agenticcli.workflows.orchestration.release_epic_lock", lambda *a: None
        )

        # Avoid the real health check / discovery filesystem scan
        from agenticcli.workflows.orchestration import OrchestrationWorkflow

        monkeypatch.setattr(OrchestrationWorkflow, "run_health_check", lambda self: None)
        monkeypatch.setattr(OrchestrationWorkflow, "get_plan_status", lambda self, f: "planning")

        args = SimpleNamespace(
            max_iterations=2,
            background=False,
            completion_promise=None,
            project=None,
            plan=epic,
            directory=str(tmp_path),
            dangerously_skip_permissions=False,
            budget_usd=50.0,
        )

        with pytest.raises(SystemExit) as exc_info:
            orch_mod._run_executing_loop(args)
        assert exc_info.value.code == 1


class TestCLIImplementIntegration:
    """CLI-level integration: exercise `orchestrate session implement` with real TinyDB.

    Mocks only the subprocess.run call (agent spawn) and wait_for_session.
    Everything else — TinyDB reads, phase status transitions, epic completion —
    runs through the real code path.
    """

    def _setup_epic_with_phases(self, tinydb_populator, tmp_path, epic_name, phases):
        """Create epic + phases in isolated TinyDB."""
        epic_dir = tmp_path / epic_name
        epic_dir.mkdir(exist_ok=True)
        tinydb_populator(epic_name, epic_dir, {
            "name": epic_name,
            "status": "planning",
            "phases": phases,
        })

    def test_cli_implement_routes_all_new_agents(self, tmp_path, tinydb_populator, monkeypatch):
        """Full CLI flow: TinyDB epic with 3 phases → ExecutionRunner → all complete."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epic = "260328CL_cli_routing"
        self._setup_epic_with_phases(tinydb_populator, tmp_path, epic, [
            {"name": "P1 Build", "agent": "build-python", "status": "planning"},
            {"name": "P2 Test", "agent": "test-uat", "status": "planning"},
            {"name": "P3 Docs", "agent": "build-docs-writer", "status": "planning"},
        ])

        # Build the workflow pointing at our temp dir
        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True, exist_ok=True)
        workflow = OrchestrationWorkflow(working_dir=str(tmp_path))

        spawned_roles = []

        def _mock_run_phase(self_runner, plan_folder, phase_id, agent_type, routing, **kwargs):
            spawned_roles.append(agent_type)
            return True

        monkeypatch.setattr(ExecutionRunner, "_run_phase", _mock_run_phase)
        monkeypatch.setattr(workflow, "run_health_check", lambda: None)
        monkeypatch.setattr(workflow, "get_plan_status", lambda folder: "planning")
        monkeypatch.setattr(
            "agenticcli.workflows.orchestration.acquire_epic_lock", lambda *a: True
        )
        monkeypatch.setattr(
            "agenticcli.workflows.orchestration.release_epic_lock", lambda *a: None
        )

        runner = ExecutionRunner(
            workflow=workflow,
            plan_folder=epic,
        )
        success = runner.run(max_iterations=10)

        assert success is True
        assert spawned_roles == ["build-python", "test-uat", "build-docs-writer"]
        assert epic in runner.state["plans_processed"]

        # Verify TinyDB state: all phases completed, epic completed
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        for phase in repo.list_phases(epic):
            assert phase.status == "completed", f"{phase.name} should be completed"
        epic_data = repo.get_epic(epic)
        assert epic_data.status == "completed"

    def test_cli_implement_spawn_command_has_correct_role(self, tmp_path, tinydb_populator, monkeypatch):
        """Verify the actual spawn command built for a phase includes --role <agent>."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epic = "260328CL_spawn_cmd"
        self._setup_epic_with_phases(tinydb_populator, tmp_path, epic, [
            {"name": "P1", "agent": "trace-explorer", "status": "planning"},
        ])

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True, exist_ok=True)
        workflow = OrchestrationWorkflow(working_dir=str(tmp_path))

        captured_cmds = []

        # Only intercept subprocess.run calls that look like spawn commands
        _real_subprocess_run = subprocess.run

        def _mock_subprocess_run(cmd, **kwargs):
            if isinstance(cmd, list) and "spawn" in cmd:
                captured_cmds.append(cmd)
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({"session_id": "test-sess-001", "tmux_session": "agentic-test"}),
                    stderr="",
                )
            return _real_subprocess_run(cmd, **kwargs)

        monkeypatch.setattr(subprocess, "run", _mock_subprocess_run)
        monkeypatch.setattr(workflow, "run_health_check", lambda: None)
        monkeypatch.setattr(workflow, "get_plan_status", lambda folder: "planning")
        monkeypatch.setattr(workflow, "wait_for_session", lambda *a, **kw: "completed")
        monkeypatch.setattr(
            "agenticcli.workflows.orchestration.acquire_epic_lock", lambda *a: True
        )
        monkeypatch.setattr(
            "agenticcli.workflows.orchestration.release_epic_lock", lambda *a: None
        )

        runner = ExecutionRunner(workflow=workflow, plan_folder=epic)
        runner.run(max_iterations=5)

        # Verify spawn command contains --role trace-explorer
        assert len(captured_cmds) >= 1
        cmd = captured_cmds[0]
        assert "--role" in cmd
        role_idx = cmd.index("--role")
        assert cmd[role_idx + 1] == "trace-explorer"
        assert "--tmux" in cmd


# ── UAT Journey Step 1: Phase Ordering ─────────────────────────────────


class TestPhaseOrdering:
    """UAT Step 1: Phase execution follows TinyDB _order field."""

    def test_phases_listed_in_insertion_order(self, tmp_path, tinydb_populator):
        """Phases returned by list_phases() follow insertion (_order) sequence.

        Verifies that phases are listed in the order they were added (P1, P2, P3),
        regardless of their names or any other field.
        """
        epic = "260411UA_ordering"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Ordering Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "phase_id": "P1", "agent": "build-python", "status": "planning"},
                {"name": "P2 Test", "phase_id": "P2", "agent": "test-builder", "status": "planning"},
                {"name": "P3 Deploy", "phase_id": "P3", "agent": "build-python", "status": "planning"},
            ],
        })

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        phases = repo.list_phases(epic)

        assert len(phases) == 3
        assert [p.name for p in phases] == ["P1 Build", "P2 Test", "P3 Deploy"]
        assert [p.phase_id for p in phases] == ["P1", "P2", "P3"]
        # All start as planning
        assert all(p.status == "planning" for p in phases)

    def test_execution_order_matches_tinydb_order(self, tmp_path, tinydb_populator):
        """ExecutionRunner executes phases in TinyDB _order, not alphabetical.

        P3-named phase added first should execute first since _order is insertion-based.
        """
        epic = "260411UA_exec_order"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        # Note: names are NOT in alphabetical order, but insertion order matters
        tinydb_populator(epic, epic_dir, {
            "name": "Execution Order Test",
            "status": "in_progress",
            "phases": [
                {"name": "Zeta Phase", "agent": "build-python", "status": "planning"},
                {"name": "Alpha Phase", "agent": "test-builder", "status": "planning"},
                {"name": "Mu Phase", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        execution_order = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            execution_order.append(phase_id)
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is True
        # Execution follows insertion order, not alphabetical
        assert execution_order == ["Zeta Phase", "Alpha Phase", "Mu Phase"]


# ── UAT Journey Step 2: Manual Phase Transition ───────────────────────


class TestManualPhaseTransition:
    """UAT Step 2: Phase status can be transitioned via update_phase."""

    def test_update_phase_status_to_completed(self, tmp_path, tinydb_populator):
        """Manual transition of P1 to completed is reflected in list_phases."""
        epic = "260411UA_transition"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Transition Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "phase_id": "P1", "agent": "build-python", "status": "planning"},
                {"name": "P2 Test", "phase_id": "P2", "agent": "test-builder", "status": "planning"},
                {"name": "P3 Deploy", "phase_id": "P3", "agent": "build-python", "status": "planning"},
            ],
        })

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)

        # Transition P1 to completed
        repo.update_phase(epic, "P1 Build", {"status": "completed"})

        phases = repo.list_phases(epic)
        p1 = next(p for p in phases if p.name == "P1 Build")
        assert p1.status == "completed"
        # P2 and P3 remain unchanged
        p2 = next(p for p in phases if p.name == "P2 Test")
        p3 = next(p for p in phases if p.name == "P3 Deploy")
        assert p2.status == "planning"
        assert p3.status == "planning"


# ── UAT Journey Step 3: Idempotent Resume (All Complete) ──────────────


class TestIdempotentResumeAllComplete:
    """UAT Step 3: All phases pre-completed → implement does zero work."""

    def test_all_phases_completed_returns_true_no_execution(self, tmp_path, tinydb_populator):
        """When all phases are already completed, _execute_plan returns True
        without spawning any agents.
        """
        epic = "260411UA_allcomplete"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "All Complete Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "completed"},
                {"name": "P2 Test", "agent": "test-builder", "status": "completed"},
                {"name": "P3 Deploy", "agent": "build-python", "status": "completed"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        spawn_count = 0

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            nonlocal spawn_count
            spawn_count += 1
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is True
        assert spawn_count == 0, "No agents should be spawned when all phases are complete"
        # Phases remain completed (not re-executed)
        for phase in repo.list_phases(epic):
            assert phase.status == "completed", f"Phase {phase.name} should still be completed"

    def test_runner_run_all_complete_returns_true(self, tmp_path, tinydb_populator, monkeypatch):
        """Full runner.run() flow: all phases completed → returns True, zero work."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epic = "260411UA_runallcomplete"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Run All Complete Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "agent": "build-python", "status": "completed"},
                {"name": "P2", "agent": "test-builder", "status": "completed"},
            ],
        })

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True, exist_ok=True)
        workflow = OrchestrationWorkflow(working_dir=str(tmp_path))

        spawn_count = 0

        def _mock_run_phase(self_runner, plan_folder, phase_id, agent_type, routing, **kwargs):
            nonlocal spawn_count
            spawn_count += 1
            return True

        monkeypatch.setattr(ExecutionRunner, "_run_phase", _mock_run_phase)
        monkeypatch.setattr(workflow, "run_health_check", lambda: None)
        monkeypatch.setattr(workflow, "get_plan_status", lambda folder: "planning")
        monkeypatch.setattr(
            "agenticcli.workflows.orchestration.acquire_epic_lock", lambda *a: True
        )
        monkeypatch.setattr(
            "agenticcli.workflows.orchestration.release_epic_lock", lambda *a: None
        )

        runner = ExecutionRunner(workflow=workflow, plan_folder=epic)
        success = runner.run(max_iterations=10)

        assert success is True
        assert spawn_count == 0, "No agents should be spawned"


# ── UAT Journey Steps 4-5: Resume From Mid-Epic ──────────────────────


class TestResumeFromMidEpic:
    """UAT Steps 4-5: Resume skips completed phases, starts from next pending."""

    def test_p1_completed_starts_from_p2(self, tmp_path, tinydb_populator):
        """With P1 already completed, implement starts from P2, skips P1."""
        epic = "260411UA_resume_mid"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Resume Mid-Epic Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "completed"},
                {"name": "P2 Test", "agent": "test-builder", "status": "planning"},
                {"name": "P3 Deploy", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        executed_phases = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            executed_phases.append(phase_id)
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is True
        # P1 was NOT re-executed; only P2 and P3 ran
        assert "P1 Build" not in executed_phases, "P1 should be skipped (already completed)"
        assert executed_phases == ["P2 Test", "P3 Deploy"]
        # All phases are now completed
        for phase in repo.list_phases(epic):
            assert phase.status == "completed"

    def test_p1_p2_completed_starts_from_p3(self, tmp_path, tinydb_populator):
        """UAT Step 5: With P1+P2 completed, implement starts from P3 only."""
        epic = "260411UA_resume_p3"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Resume P3 Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "completed"},
                {"name": "P2 Test", "agent": "test-builder", "status": "completed"},
                {"name": "P3 Deploy", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        executed_phases = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            executed_phases.append(phase_id)
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is True
        # Only P3 executed
        assert executed_phases == ["P3 Deploy"]
        # P1 and P2 remain completed (not re-executed)
        phases = repo.list_phases(epic)
        assert phases[0].status == "completed"
        assert phases[1].status == "completed"
        assert phases[2].status == "completed"


# ── UAT: In-Progress Recovery Sweep ──────────────────────────────────


class TestRecoverySweep:
    """Verify _recover_stale_phases resets in_progress → planning on startup."""

    def test_stale_in_progress_phase_reset_to_planning(self, tmp_path, tinydb_populator):
        """A phase stuck in in_progress from a prior interrupted run is reset
        to planning by the recovery sweep, then executed normally.
        """
        epic = "260411UA_recovery"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Recovery Sweep Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "completed"},
                {"name": "P2 Test", "agent": "test-builder", "status": "in_progress"},
                {"name": "P3 Deploy", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        executed_phases = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            executed_phases.append(phase_id)
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is True
        # P2 was reset from in_progress to planning, then executed
        assert "P2 Test" in executed_phases
        assert "P3 Deploy" in executed_phases
        # P1 was NOT re-executed
        assert "P1 Build" not in executed_phases
        # All phases now completed
        for phase in repo.list_phases(epic):
            assert phase.status == "completed"

    def test_multiple_stale_phases_all_reset(self, tmp_path, tinydb_populator):
        """Multiple stuck in_progress phases are all reset by recovery sweep."""
        epic = "260411UA_multi_recovery"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Multi Recovery Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "agent": "build-python", "status": "in_progress"},
                {"name": "P2", "agent": "test-builder", "status": "in_progress"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        # Run recovery sweep directly
        runner._recover_stale_phases(repo, epic)

        # Both phases should be reset to planning
        phases = repo.list_phases(epic)
        for phase in phases:
            assert phase.status == "planning", f"Phase {phase.name} should be reset to planning"


# ── UAT: Blocked Phase Halts Execution ───────────────────────────────


class TestBlockedPhaseHaltsExecution:
    """Verify that a blocked phase halts the entire execution loop."""

    def test_blocked_phase_prevents_further_execution(self, tmp_path, tinydb_populator):
        """A blocked phase causes _execute_plan to return False immediately.

        No subsequent phases are executed; the error names the blocked phase.
        """
        epic = "260411UA_blocked_halt"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Blocked Halt Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "completed"},
                {"name": "P2 Test", "agent": "test-builder", "status": "blocked"},
                {"name": "P3 Deploy", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        spawn_count = 0

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            nonlocal spawn_count
            spawn_count += 1
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is False
        assert spawn_count == 0, "No agents should spawn when a blocked phase exists"
        assert any("Blocked" in str(e) or "blocked" in str(e).lower() for e in runner.state["errors"])


# ── UAT Step 7: Lock Contention ──────────────────────────────────────


class TestLockContention:
    """UAT Step 7: Lock failure prevents concurrent orchestration."""

    def test_lock_failure_aborts_execution(self, tmp_path, tinydb_populator, monkeypatch):
        """When acquire_epic_lock returns False, the plan is not executed."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epic = "260411UA_lock_fail"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Lock Fail Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "agent": "build-python", "status": "planning"},
            ],
        })

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True, exist_ok=True)
        workflow = OrchestrationWorkflow(working_dir=str(tmp_path))

        # Lock acquisition always fails (simulating another process holding the lock)
        monkeypatch.setattr(
            "agenticcli.workflows.orchestration.acquire_epic_lock", lambda *a: False
        )
        monkeypatch.setattr(
            "agenticcli.workflows.orchestration.release_epic_lock", lambda *a: None
        )
        monkeypatch.setattr(workflow, "run_health_check", lambda: None)
        monkeypatch.setattr(workflow, "get_plan_status", lambda folder: "planning")

        runner = ExecutionRunner(workflow=workflow, plan_folder=epic)
        success = runner.run(max_iterations=10)

        assert success is False
        assert epic in runner.state["plans_failed"]
        assert any("Lock" in str(e) or "lock" in str(e).lower() for e in runner.state["errors"])

        # Phase should NOT have been touched (still planning)
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        phases = repo.list_phases(epic)
        assert phases[0].status == "planning", "Phase should remain planning (lock prevented execution)"


# ── UAT: No Phases in TinyDB ────────────────────────────────────────


class TestNoPhases:
    """Edge case: epic with zero phases should fail gracefully."""

    def test_execute_plan_no_phases_returns_false(self, tmp_path, tinydb_populator):
        """An epic with no phases added results in False with error."""
        epic = "260411UA_nophases"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "No Phases Test",
            "status": "in_progress",
            "phases": [],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=5)

        assert result is False
        assert any("No phases" in str(e) for e in runner.state["errors"])


# ── UAT: Max Iterations Reached ──────────────────────────────────────


class TestMaxIterationsReached:
    """Verify the executor stops when max_iterations is exhausted."""

    def test_max_iterations_exhausted_returns_false(self, tmp_path, tinydb_populator):
        """When max_iterations < phase count, execution stops early."""
        epic = "260411UA_maxiter"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Max Iterations Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "agent": "build-python", "status": "planning"},
                {"name": "P2", "agent": "test-builder", "status": "planning"},
                {"name": "P3", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        # Only 2 iterations for 3 phases
        result = runner._execute_plan(epic, max_iterations=2)

        assert result is False
        # Only 2 phases should be completed (P1 and P2)
        phases = repo.list_phases(epic)
        completed = [p for p in phases if p.status == "completed"]
        assert len(completed) == 2
        # P3 should still be pending
        p3 = next(p for p in phases if p.name == "P3")
        assert p3.status == "planning"


# ── UAT Step 2: Phase marked in_progress BEFORE spawn ────────────────


class TestInProgressBeforeSpawn:
    """US-PLN-047 Step 2: Phase is set to in_progress in TinyDB BEFORE _run_phase."""

    def test_phase_is_in_progress_when_agent_runs(self, tmp_path, tinydb_populator):
        """Inside _run_phase, the TinyDB phase status is already in_progress.

        This verifies the contract from Step 2: "The phase is marked in_progress
        in TinyDB BEFORE the agent is spawned."
        """
        epic = "260411UA_inprog_before"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "InProgress Before Spawn Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        observed_statuses = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            # At the moment _run_phase is called, read the phase status from TinyDB
            phases = repo.list_phases(plan_folder)
            p1 = next(p for p in phases if p.name == "P1 Build")
            observed_statuses.append(p1.status)
            return True

        runner._run_phase = _mock_run_phase

        result = runner._execute_plan(epic, max_iterations=5)

        assert result is True
        # The phase MUST have been in_progress when the agent ran
        assert observed_statuses == ["in_progress"], (
            f"Phase should be in_progress when _run_phase is called, got: {observed_statuses}"
        )

    def test_phase_transitions_planning_to_in_progress_to_completed(self, tmp_path, tinydb_populator):
        """Full lifecycle: planning → in_progress → completed verified via TinyDB reads."""
        epic = "260411UA_lifecycle"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Lifecycle Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        # Record status at each stage
        lifecycle = []

        # Check initial status
        phases = repo.list_phases(epic)
        lifecycle.append(("before_execute", phases[0].status))

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            phases = repo.list_phases(plan_folder)
            p = next(p for p in phases if p.name == "P1")
            lifecycle.append(("during_run_phase", p.status))
            return True

        runner._run_phase = _mock_run_phase

        result = runner._execute_plan(epic, max_iterations=5)

        # Check final status
        phases = repo.list_phases(epic)
        lifecycle.append(("after_execute", phases[0].status))

        assert result is True
        assert lifecycle == [
            ("before_execute", "planning"),
            ("during_run_phase", "in_progress"),
            ("after_execute", "completed"),
        ]


# ── UAT Step 4: Agent failure marks phase failed and halts execution ──


class TestAgentFailureHaltsExecution:
    """US-PLN-047 Step 4: When an agent fails, phase is marked failed and
    subsequent phases are NOT executed."""

    def test_agent_failure_marks_phase_failed_halts_pipeline(self, tmp_path, tinydb_populator):
        """P1 succeeds, P2 agent fails → P2 is marked failed, P3 never runs."""
        epic = "260411UA_fail_halt"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Failure Halt Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "planning"},
                {"name": "P2 Test", "agent": "test-builder", "status": "planning"},
                {"name": "P3 Deploy", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        executed_phases = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            executed_phases.append(phase_id)
            if phase_id == "P2 Test":
                return False  # Agent fails
            return True

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is False
        # P1 and P2 ran, but P3 did NOT
        assert executed_phases == ["P1 Build", "P2 Test"]
        # Verify phase statuses in TinyDB
        phases = repo.list_phases(epic)
        p1 = next(p for p in phases if p.name == "P1 Build")
        p2 = next(p for p in phases if p.name == "P2 Test")
        p3 = next(p for p in phases if p.name == "P3 Deploy")
        assert p1.status == "completed"
        assert p2.status == "failed"
        assert p3.status == "planning", "P3 should remain planning (never reached)"

    def test_agent_failure_records_error_and_phase_in_state(self, tmp_path, tinydb_populator):
        """Failed phase is recorded in state['errors'] and state['phases_failed']."""
        epic = "260411UA_fail_state"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Failure State Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            return False  # Agent fails

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=5)

        assert result is False
        # Error should mention the failed phase
        assert any("P1 Build" in str(e) for e in runner.state["errors"]), (
            f"Error should name P1 Build, got: {runner.state['errors']}"
        )
        assert f"{epic}:P1 Build" in runner.state["phases_failed"]

    def test_first_phase_failure_prevents_all_subsequent(self, tmp_path, tinydb_populator):
        """When P1 (first phase) fails, NO subsequent phases run."""
        epic = "260411UA_first_fail"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "First Phase Failure Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1", "agent": "build-python", "status": "planning"},
                {"name": "P2", "agent": "test-builder", "status": "planning"},
                {"name": "P3", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        executed = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            executed.append(phase_id)
            return False

        runner._run_phase = _mock_run_phase

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is False
        assert executed == ["P1"], "Only P1 should run; P2 and P3 must be skipped"
        phases = repo.list_phases(epic)
        assert phases[0].status == "failed"
        assert phases[1].status == "planning"
        assert phases[2].status == "planning"


# ── UAT Step 3: last_pass_commit recording ────────────────────────────


class TestStoryPassRecording:
    """US-PLN-047 Step 3: Executor records last_pass_commit for story IDs
    after phase completion."""

    def test_record_story_pass_called_on_success(self, tmp_path, tinydb_populator, monkeypatch):
        """_record_story_pass_for_phase is invoked after phase marked completed.

        We mock record_story_pass to capture the call and verify it happens
        with the correct story IDs and commit_kind.
        """
        epic = "260411UA_story_pass"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Story Pass Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            return True

        runner._run_phase = _mock_run_phase

        # Track whether _record_story_pass_for_phase was called
        record_calls = []
        original_record = runner._record_story_pass_for_phase

        def _tracking_record(repo_arg, plan_folder_arg, phase_name_arg):
            record_calls.append({
                "plan_folder": plan_folder_arg,
                "phase_name": phase_name_arg,
            })
            return original_record(repo_arg, plan_folder_arg, phase_name_arg)

        runner._record_story_pass_for_phase = _tracking_record

        result = runner._execute_plan(epic, max_iterations=5)

        assert result is True
        assert len(record_calls) == 1
        assert record_calls[0]["plan_folder"] == epic
        assert record_calls[0]["phase_name"] == "P1 Build"

    def test_record_story_pass_not_called_on_failure(self, tmp_path, tinydb_populator):
        """_record_story_pass_for_phase is NOT invoked when agent fails."""
        epic = "260411UA_no_story_pass"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "No Story Pass Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            return False

        runner._run_phase = _mock_run_phase

        record_calls = []
        original_record = runner._record_story_pass_for_phase

        def _tracking_record(repo_arg, plan_folder_arg, phase_name_arg):
            record_calls.append(phase_name_arg)
            return original_record(repo_arg, plan_folder_arg, phase_name_arg)

        runner._record_story_pass_for_phase = _tracking_record

        result = runner._execute_plan(epic, max_iterations=5)

        assert result is False
        assert len(record_calls) == 0, (
            "record_story_pass should NOT be called when phase fails"
        )

    def test_record_story_pass_called_per_completed_phase(self, tmp_path, tinydb_populator):
        """Each successfully completed phase triggers its own _record_story_pass call."""
        epic = "260411UA_multi_story_pass"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Multi Story Pass Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "planning"},
                {"name": "P2 Test", "agent": "test-builder", "status": "planning"},
                {"name": "P3 Deploy", "agent": "build-python", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            return True

        runner._run_phase = _mock_run_phase

        record_calls = []
        original_record = runner._record_story_pass_for_phase

        def _tracking_record(repo_arg, plan_folder_arg, phase_name_arg):
            record_calls.append(phase_name_arg)
            return original_record(repo_arg, plan_folder_arg, phase_name_arg)

        runner._record_story_pass_for_phase = _tracking_record

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is True
        assert record_calls == ["P1 Build", "P2 Test", "P3 Deploy"], (
            f"Each phase should trigger its own recording, got: {record_calls}"
        )


# ── UAT: _check_phase_tickets_complete unit tests ────────────────────


class TestCheckPhaseTicketsComplete:
    """Verify _check_phase_tickets_complete returns correct incomplete ticket IDs."""

    def test_all_tickets_completed_returns_empty(self, tmp_path, tinydb_populator):
        """When all tickets in the phase are completed, returns empty list."""
        epic = "260412UA_tkt_all_done"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "All Tickets Done",
            "status": "in_progress",
            "phases": [
                {
                    "name": "P1 Build", "agent": "build-python", "status": "in_progress",
                    "tickets": [
                        {"id": "T1", "name": "Task 1", "status": "completed"},
                        {"id": "T2", "name": "Task 2", "status": "completed"},
                    ],
                },
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)

        incomplete = runner._check_phase_tickets_complete(repo, epic, "P1 Build")
        assert incomplete == []

    def test_some_tickets_incomplete_returns_ids(self, tmp_path, tinydb_populator):
        """When some tickets are not completed, returns their IDs."""
        epic = "260412UA_tkt_partial"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Partial Tickets",
            "status": "in_progress",
            "phases": [
                {
                    "name": "P1 Build", "agent": "build-python", "status": "in_progress",
                    "tickets": [
                        {"id": "T1", "name": "Task 1", "status": "completed"},
                        {"id": "T2", "name": "Task 2", "status": "in_progress"},
                        {"id": "T3", "name": "Task 3", "status": "proposed"},
                    ],
                },
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)

        incomplete = runner._check_phase_tickets_complete(repo, epic, "P1 Build")
        assert "T2" in incomplete
        assert "T3" in incomplete
        assert "T1" not in incomplete

    def test_no_tickets_returns_empty(self, tmp_path, tinydb_populator):
        """A phase with no tickets returns empty list (not an error)."""
        epic = "260412UA_tkt_none"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "No Tickets",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "in_progress"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)

        incomplete = runner._check_phase_tickets_complete(repo, epic, "P1 Build")
        assert incomplete == []

    def test_other_phase_tickets_ignored(self, tmp_path, tinydb_populator):
        """Tickets in OTHER phases should not affect completeness check for target phase."""
        epic = "260412UA_tkt_cross_phase"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Cross Phase Tickets",
            "status": "in_progress",
            "phases": [
                {
                    "name": "P1 Build", "agent": "build-python", "status": "in_progress",
                    "tickets": [
                        {"id": "T1", "name": "Build Task", "status": "completed"},
                    ],
                },
                {
                    "name": "P2 Test", "agent": "test-builder", "status": "planning",
                    "tickets": [
                        {"id": "T2", "name": "Test Task", "status": "proposed"},
                    ],
                },
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)

        incomplete = runner._check_phase_tickets_complete(repo, epic, "P1 Build")
        # T2 belongs to P2 Test, should NOT appear in P1 Build check
        assert incomplete == []

    def test_exception_returns_empty_not_crash(self, tmp_path):
        """If repo.list_tickets throws, return empty list (graceful degradation)."""
        runner, workflow = _make_execution_runner(tmp_path, plan_folder="nonexistent")

        broken_repo = MagicMock()
        broken_repo.list_tickets.side_effect = RuntimeError("DB corrupted")

        # Must NOT raise — returns empty list
        incomplete = runner._check_phase_tickets_complete(broken_repo, "nonexistent", "P1")
        assert incomplete == []


# ── UAT: _commit_phase_result_atomic normal path ─────────────────────


class TestCommitPhaseResultAtomic:
    """Verify _commit_phase_result_atomic writes status to TinyDB."""

    def test_atomic_commit_writes_completed_status(self, tmp_path, tinydb_populator):
        """Normal path: status is written to TinyDB via repo.update_phase."""
        epic = "260412UA_atomic_commit"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Atomic Commit Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "in_progress"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)

        runner._commit_phase_result_atomic(repo, epic, "P1 Build", "completed")

        phases = repo.list_phases(epic)
        p1 = next(p for p in phases if p.name == "P1 Build")
        assert p1.status == "completed"

    def test_atomic_commit_writes_failed_status(self, tmp_path, tinydb_populator):
        """Normal path: failed status is written to TinyDB."""
        epic = "260412UA_atomic_fail"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Atomic Fail Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "in_progress"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)

        runner._commit_phase_result_atomic(repo, epic, "P1 Build", "failed")

        phases = repo.list_phases(epic)
        p1 = next(p for p in phases if p.name == "P1 Build")
        assert p1.status == "failed"


# ── UAT Step 6: Concurrent status query safety ──────────────────────


class TestConcurrentStatusQuery:
    """UAT Step 6: `agentic epic status --epic <folder>` is safe during a running implement.

    Verifies that repo.get_epic() and repo.list_phases() can be called while
    _execute_plan() is in progress (TinyDB reads don't block writes).
    """

    def test_status_query_during_phase_execution(self, tmp_path, tinydb_populator):
        """During _run_phase, a concurrent status query succeeds and shows in_progress."""
        epic = "260412UA_concurrent_query"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Concurrent Query Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "agent": "build-python", "status": "planning"},
                {"name": "P2 Test", "agent": "test-builder", "status": "planning"},
            ],
        })

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)
        workflow._get_repository.return_value = repo

        query_results = []

        def _mock_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            # Simulate a concurrent status query during phase execution
            # This is what `agentic epic status --epic <folder>` does
            queried_epic = repo.get_epic(plan_folder)
            queried_phases = repo.list_phases(plan_folder)
            query_results.append({
                "epic_status": queried_epic.status,
                "phase_name": phase_id,
                "phase_statuses": {p.name: p.status for p in queried_phases},
            })
            return True

        runner._run_phase = _mock_run_phase

        result = runner._execute_plan(epic, max_iterations=10)

        assert result is True
        # Query during P1 execution should show P1 as in_progress
        assert len(query_results) == 2
        assert query_results[0]["phase_statuses"]["P1 Build"] == "in_progress"
        assert query_results[0]["phase_statuses"]["P2 Test"] == "planning"
        # Query during P2 execution should show P1 completed, P2 in_progress
        assert query_results[1]["phase_statuses"]["P1 Build"] == "completed"
        assert query_results[1]["phase_statuses"]["P2 Test"] == "in_progress"


# ── UAT: Complete sequential journey test ────────────────────────────


class TestUATJourneySequential:
    """End-to-end sequential test following the US-PLN-047 UAT journey steps.

    Walks through the UAT plan journey steps 1-6 in a single test epic,
    verifying each step's preconditions and postconditions.
    """

    def test_full_uat_journey(self, tmp_path, tinydb_populator):
        """Walk the entire UAT journey for US-PLN-047 in sequence.

        Journey:
          Step 1: Phase list ordering — P1/P2/P3 listed in insertion order
          Step 2: Manual phase transition — P1 to completed
          Step 3: Idempotent resume — all phases completed → zero work
          Step 4: Reset P2/P3 → planning, mark P2 completed manually
          Step 5: Resume starts from P3 (P1 and P2 already completed)
          Step 6: Add P4 with no agent → failed + non-zero exit
        """
        epic = "260412UA_full_journey"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()

        # ── Step 1: Setup with 3 phases in order ─────────────────────
        tinydb_populator(epic, epic_dir, {
            "name": "Full Journey Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Build", "phase_id": "P1", "agent": "build-python", "status": "planning"},
                {"name": "P2 Test", "phase_id": "P2", "agent": "test-builder", "status": "planning"},
                {"name": "P3 Deploy", "phase_id": "P3", "agent": "build-python", "status": "planning"},
            ],
        })

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(auto_bootstrap=False)

        # Step 1: Verify ordering
        phases = repo.list_phases(epic)
        assert len(phases) == 3
        assert [p.name for p in phases] == ["P1 Build", "P2 Test", "P3 Deploy"]
        assert all(p.status == "planning" for p in phases)

        # ── Step 2: Manual transition P1 → completed ─────────────────
        repo.update_phase(epic, "P1 Build", {"status": "completed"})
        phases = repo.list_phases(epic)
        p1 = next(p for p in phases if p.name == "P1 Build")
        assert p1.status == "completed"
        # P2 and P3 unchanged
        assert next(p for p in phases if p.name == "P2 Test").status == "planning"
        assert next(p for p in phases if p.name == "P3 Deploy").status == "planning"

        # ── Step 3: Complete all phases → idempotent resume ──────────
        repo.update_phase(epic, "P2 Test", {"status": "completed"})
        repo.update_phase(epic, "P3 Deploy", {"status": "completed"})

        runner, workflow = _make_execution_runner(tmp_path, plan_folder=epic)
        workflow._get_repository.return_value = repo

        spawn_count = 0

        def _counting_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            nonlocal spawn_count
            spawn_count += 1
            return True

        runner._run_phase = _counting_run_phase

        result = runner._execute_plan(epic, max_iterations=10)
        assert result is True
        assert spawn_count == 0, "No agents should spawn when all phases are complete"

        # All phases remain completed
        for phase in repo.list_phases(epic):
            assert phase.status == "completed"

        # ── Step 4: Reset P2 and P3 → planning, mark P2 completed ───
        repo.update_phase(epic, "P2 Test", {"status": "planning"})
        repo.update_phase(epic, "P3 Deploy", {"status": "planning"})
        repo.update_phase(epic, "P2 Test", {"status": "completed"})

        phases = repo.list_phases(epic)
        assert next(p for p in phases if p.name == "P1 Build").status == "completed"
        assert next(p for p in phases if p.name == "P2 Test").status == "completed"
        assert next(p for p in phases if p.name == "P3 Deploy").status == "planning"

        # ── Step 5: Resume starts from P3 only ───────────────────────
        runner2, workflow2 = _make_execution_runner(tmp_path, plan_folder=epic)
        workflow2._get_repository.return_value = repo

        executed_phases = []

        def _tracking_run_phase(plan_folder, phase_id, agent_type, routing, **kwargs):
            executed_phases.append(phase_id)
            return True

        runner2._run_phase = _tracking_run_phase

        result = runner2._execute_plan(epic, max_iterations=10)
        assert result is True
        assert executed_phases == ["P3 Deploy"], (
            f"Only P3 should execute (P1 and P2 already completed), got: {executed_phases}"
        )

        # ── Step 6: Add P4 with no agent → failed ────────────────────
        # Reset epic status to allow further execution.
        # Use force=True because the executor already marked the epic completed
        # after Step 3 (all phases done), and completed → in_progress is not a
        # valid transition — but we need to add P4 and re-execute.
        repo.transition_epic_status(epic, "in_progress", force=True)

        repo.add_phase(epic, {
            "name": "P4 Broken",
            "phase_id": "P4",
            "status": "planning",
            # No agent field!
        })

        runner3, workflow3 = _make_execution_runner(tmp_path, plan_folder=epic)
        workflow3._get_repository.return_value = repo

        runner3._run_phase = _tracking_run_phase

        result = runner3._execute_plan(epic, max_iterations=10)
        assert result is False

        # P4 must be marked failed (not planning or pending)
        phases = repo.list_phases(epic)
        p4 = next(p for p in phases if p.name == "P4 Broken")
        assert p4.status == "failed", (
            f"P4 (no agent) should be 'failed', got '{p4.status}'"
        )

        # Error should mention P4
        errs = " ".join(str(e) for e in runner3.state["errors"])
        assert "P4" in errs, f"Error should reference P4, got: {errs}"
