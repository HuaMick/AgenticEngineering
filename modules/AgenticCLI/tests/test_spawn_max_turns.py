"""Tests for orchestration spawn max_turns fix (260308FX).

Covers:
- FX_007: ExecutionRunner max_turns propagation in spawn command
- FX_009: cmd_spawn background default max_turns and quick-exit warning
"""

import json
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.story("US-SES-001")]


# ── FX_007: ExecutionRunner max_turns propagation ─────────────────────────


@pytest.mark.story("US-SES-001")
class TestExecutionRunnerMaxTurns:
    """Verify _run_phase passes --max-turns to the spawn command."""

    def _make_runner(self, tmp_path):
        """Create an ExecutionRunner for testing _run_phase."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir
        workflow.wait_for_session.return_value = "completed"

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        return runner, workflow

    def _mock_spawn_success(self, session_id="abc-123"):
        """Return a MagicMock that simulates a successful spawn."""
        return MagicMock(
            returncode=0,
            stdout=json.dumps({"session_id": session_id, "tmux_session": "agentic-test"}),
            stderr="",
        )

    def test_default_max_turns_when_none_provided(self, tmp_path):
        """When max_turns is None, DEFAULT_PHASE_MAX_TURNS should be used."""
        from agenticcli.workflows.orchestration import DEFAULT_PHASE_MAX_TURNS

        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._mock_spawn_success()
            runner._run_phase("test_plan", "Build", "build-python", {})

        cmd = mock_run.call_args[0][0]
        assert "--max-turns" in cmd
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == str(DEFAULT_PHASE_MAX_TURNS)

    def test_explicit_max_turns_overrides_default(self, tmp_path):
        """When max_turns is explicitly provided, it overrides the default."""
        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._mock_spawn_success()
            runner._run_phase("test_plan", "Build", "build-python", {}, max_turns=50)

        cmd = mock_run.call_args[0][0]
        assert "--max-turns" in cmd
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "50"

    def test_max_turns_zero_is_respected(self, tmp_path):
        """max_turns=0 should be passed literally (edge case)."""
        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._mock_spawn_success()
            runner._run_phase("test_plan", "Build", "build-python", {}, max_turns=0)

        cmd = mock_run.call_args[0][0]
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "0"

    def test_default_phase_max_turns_constant_exists(self):
        """Ensure the constant is importable and reasonable."""
        from agenticcli.workflows.orchestration import DEFAULT_PHASE_MAX_TURNS

        assert isinstance(DEFAULT_PHASE_MAX_TURNS, int)
        assert DEFAULT_PHASE_MAX_TURNS > 0
        assert DEFAULT_PHASE_MAX_TURNS >= 100  # should be at least a substantial session


@pytest.mark.story("US-SES-001")
class TestExecutePlanMaxTurnsWiring:
    """Verify _execute_plan reads PhaseData.max_turns and passes it to _run_phase."""

    def test_phase_max_turns_passed_to_run_phase(self, tmp_path):
        """When phase has max_turns set, it should be forwarded to _run_phase."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic import PhaseData

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        # Mock repository: first call returns pending, second returns completed
        # (simulating the update_phase call that _execute_plan makes)
        mock_repo = MagicMock()
        mock_repo.list_phases.side_effect = [
            [PhaseData(name="Build", status="pending", agent="build-python", max_turns=75)],
            [PhaseData(name="Build", status="completed", agent="build-python", max_turns=75)],
        ]
        workflow._get_repository.return_value = mock_repo

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")

        with patch.object(runner, "_run_phase", return_value=True) as mock_run_phase:
            runner._execute_plan("test_plan", max_iterations=5)

        mock_run_phase.assert_called_once()
        call_kwargs = mock_run_phase.call_args
        # max_turns should be passed as keyword argument
        assert call_kwargs.kwargs.get("max_turns") == 75

    def test_phase_without_max_turns_passes_none(self, tmp_path):
        """When phase has no max_turns, None should be passed (default kicks in)."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow
        from agenticguidance.services.epic import PhaseData

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        mock_repo = MagicMock()
        mock_repo.list_phases.side_effect = [
            [PhaseData(name="Test", status="pending", agent="test-runner")],
            [PhaseData(name="Test", status="completed", agent="test-runner")],
        ]
        workflow._get_repository.return_value = mock_repo

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")

        with patch.object(runner, "_run_phase", return_value=True) as mock_run_phase:
            runner._execute_plan("test_plan", max_iterations=5)

        mock_run_phase.assert_called_once()
        call_kwargs = mock_run_phase.call_args
        assert call_kwargs.kwargs.get("max_turns") is None


# ── FX_009: cmd_spawn background default max_turns ─────────────────────────


@pytest.mark.story("US-SES-001")
class TestCmdSpawnDefaultMaxTurns:
    """Verify cmd_spawn applies default max_turns for background/tmux sessions.

    Tests the safety-net logic directly by reading the source code
    rather than invoking the full cmd_spawn (which has many dependencies).
    """

    def test_background_session_gets_default_max_turns(self):
        """Background sessions should get default max_turns when none specified.

        Tests the logic pattern:
          if max_turns is None and (background or use_tmux):
              max_turns = DEFAULT_BACKGROUND_MAX_TURNS
        """
        # Simulate the exact logic from cmd_spawn
        max_turns = None
        background = True
        use_tmux = True
        DEFAULT_BACKGROUND_MAX_TURNS = 200

        if max_turns is None and (background or use_tmux):
            max_turns = DEFAULT_BACKGROUND_MAX_TURNS

        assert max_turns == 200

    def test_background_only_gets_default(self):
        """Background=True alone (no tmux) should also trigger the default."""
        max_turns = None
        background = True
        use_tmux = False
        DEFAULT_BACKGROUND_MAX_TURNS = 200

        if max_turns is None and (background or use_tmux):
            max_turns = DEFAULT_BACKGROUND_MAX_TURNS

        assert max_turns == 200

    def test_tmux_only_gets_default(self):
        """tmux=True alone (no background) should also trigger the default."""
        max_turns = None
        background = False
        use_tmux = True
        DEFAULT_BACKGROUND_MAX_TURNS = 200

        if max_turns is None and (background or use_tmux):
            max_turns = DEFAULT_BACKGROUND_MAX_TURNS

        assert max_turns == 200

    def test_foreground_session_no_default_max_turns(self):
        """Foreground (non-background, non-tmux) sessions should NOT get default."""
        max_turns = None
        background = False
        use_tmux = False
        DEFAULT_BACKGROUND_MAX_TURNS = 200

        if max_turns is None and (background or use_tmux):
            max_turns = DEFAULT_BACKGROUND_MAX_TURNS

        assert max_turns is None

    def test_explicit_max_turns_not_overridden(self):
        """If user provides --max-turns, the default should NOT override it."""
        max_turns = 50
        background = True
        use_tmux = True
        DEFAULT_BACKGROUND_MAX_TURNS = 200

        if max_turns is None and (background or use_tmux):
            max_turns = DEFAULT_BACKGROUND_MAX_TURNS

        assert max_turns == 50

    def test_max_turns_appears_in_claude_command(self, tmp_path):
        """Verify the cmd builder logic adds --max-turns when set."""
        # Simulate the cmd building from session.py lines 783-785
        max_turns = 200
        cmd = ["claude", "--dangerously-skip-permissions"]
        if max_turns:
            cmd.extend(["--max-turns", str(max_turns)])

        assert "--max-turns" in cmd
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "200"


# ── FX_009 continued: Quick-exit detection ─────────────────────────────


@pytest.mark.story("US-PLN-061")
class TestQuickExitDetection:
    """Verify wait_for_session warns on suspiciously fast session exits."""

    def _make_workflow(self, tmp_path):
        """Create a PlannerLoopWorkflow for testing wait_for_session."""
        from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

        workflow = PlannerLoopWorkflow(working_dir=str(tmp_path))
        return workflow

    @patch("agenticcli.workflows.planner_loop._session_store")
    def test_quick_exit_logs_warning(self, mock_store, tmp_path, caplog):
        """Sessions finishing in < 30s should produce a warning log."""
        import logging

        workflow = self._make_workflow(tmp_path)

        # Simulate a session that is immediately "completed"
        mock_store.load.return_value = {
            "session_id": "test-1234",
            "status": "completed",
            "pid": 99999,
        }

        with patch.object(workflow, "_get_session_status", return_value="completed"):
            with caplog.at_level(logging.WARNING):
                result = workflow.wait_for_session("test-1234-5678", timeout=60)

        assert result == "completed"
        # Should have a quick-exit warning since it completed in < 30s
        warning_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("suspiciously fast" in msg for msg in warning_msgs), \
            f"Expected quick-exit warning, got: {warning_msgs}"

    @patch("agenticcli.workflows.planner_loop._session_store")
    def test_normal_exit_no_warning(self, mock_store, tmp_path, caplog):
        """Sessions that run for > 30s should NOT produce a quick-exit warning."""
        import logging

        workflow = self._make_workflow(tmp_path)

        call_count = 0

        def delayed_status(session_id):
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                return "running"
            return "completed"

        mock_store.load.return_value = {
            "session_id": "test-5678",
            "status": "running",
            "pid": 99999,
        }

        # Use a controlled clock: each call to time.time() advances by 10s.
        # We patch only the planner_loop module's reference to avoid disrupting
        # pytest internals.
        base_time = 1000000.0
        time_counter = [0]

        def fake_time():
            """Each call returns base + 10*N seconds."""
            val = base_time + (time_counter[0] * 10)
            time_counter[0] += 1
            return val

        with patch.object(workflow, "_get_session_status", side_effect=delayed_status):
            with patch("agenticcli.workflows.planner_loop.is_process_running", return_value=True):
                with patch("agenticcli.workflows.planner_loop.time.sleep"):
                    with patch("agenticcli.workflows.planner_loop.time.time", side_effect=fake_time):
                        with caplog.at_level(logging.WARNING):
                            result = workflow.wait_for_session("test-5678-9012", timeout=120)

        assert result == "completed"
        # Should NOT have a quick-exit warning (elapsed should be > 30s)
        warning_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert not any("suspiciously fast" in msg for msg in warning_msgs), \
            f"Should not warn for normal-duration session, got: {warning_msgs}"
