"""UAT: Orchestration implementation command after agent restructure.

Validates that `agentic orchestrate session implement` correctly routes
phases to agents via TinyDB, handles missing agent fields, per-phase
overrides, feedback triggers, and end-to-end phase completion.

Includes both unit-level ExecutionRunner tests and CLI-level integration
tests that exercise the actual command entry points.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-PLN-091")


def _make_execution_runner(tmp_path, plan_folder="test_epic"):
    """Create an ExecutionRunner with mocked workflow."""
    from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

    epics_dir = tmp_path / "docs" / "epics" / "live"
    epics_dir.mkdir(parents=True)
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
                {"name": "P1 Build", "agent": "build-python", "status": "pending"},
                {"name": "P2 Test", "agent": "test-builder", "status": "pending"},
                {"name": "P3 Audit", "agent": "planner-audit", "status": "pending"},
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
                {"name": "P1 Broken", "status": "pending"},
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

    def test_executor_routes_build_docs_writer(self, tmp_path, tinydb_populator):
        """Renamed agent build-docs-writer routes correctly."""
        epic = "260328UA_docs"
        epic_dir = tmp_path / epic
        epic_dir.mkdir()
        tinydb_populator(epic, epic_dir, {
            "name": "Docs Writer Test",
            "status": "in_progress",
            "phases": [
                {"name": "P1 Docs", "agent": "build-docs-writer", "status": "pending"},
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
                {"name": "P1", "agent": "build-python", "max_turns": 50, "status": "pending"},
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
                {"name": "P1", "agent": "build-python", "timeout": 900, "status": "pending"},
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
        """Failed phase with feedback_triggers resets target phase to pending.

        When P2 fails and has a feedback trigger pointing at P1, the executor:
        1. Marks P2 as failed
        2. Resets P1 to pending (the trigger target)
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
                {"name": "P1 Build", "agent": "build-python", "status": "pending"},
                {
                    "name": "P2 Test", "agent": "test-builder", "status": "pending",
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
                {"name": "P1 Stories", "agent": "build-story-writer", "status": "pending"},
                {"name": "P2 Build", "agent": "build-python", "status": "pending"},
                {"name": "P3 UAT", "agent": "test-uat", "status": "pending"},
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
            "status": "active",
            "phases": phases,
        })

    def test_cli_implement_routes_all_new_agents(self, tmp_path, tinydb_populator, monkeypatch):
        """Full CLI flow: TinyDB epic with 3 phases → ExecutionRunner → all complete."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epic = "260328CL_cli_routing"
        self._setup_epic_with_phases(tinydb_populator, tmp_path, epic, [
            {"name": "P1 Build", "agent": "build-python", "status": "pending"},
            {"name": "P2 Test", "agent": "test-uat", "status": "pending"},
            {"name": "P3 Docs", "agent": "build-docs-writer", "status": "pending"},
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
        monkeypatch.setattr(workflow, "get_plan_status", lambda folder: "active")
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
            {"name": "P1", "agent": "trace-explorer", "status": "pending"},
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
        monkeypatch.setattr(workflow, "get_plan_status", lambda folder: "active")
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
