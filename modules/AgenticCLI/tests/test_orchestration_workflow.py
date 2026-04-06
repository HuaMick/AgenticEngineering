"""Tests for the orchestration workflow and PlanningRunner."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-PLN-053", "US-GDN-097", "US-GDN-098", "US-PLN-068", "US-PLN-069", "US-PLN-077")


# ---------------------------------------------------------------------------
# PlanningRunner tests
# ---------------------------------------------------------------------------


@pytest.mark.story("US-PLN-046", "US-PLN-053", "US-PLN-058", "US-PLN-067")
class TestPlanningRunner:
    """Test PlanningRunner class."""

    def test_run_single_plan_success(self, tmp_path, monkeypatch):
        """run() succeeds for single plan with all phases passing."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        # Create mock workflow with epics_dir that exists
        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = []

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = True
            mock_planner_runner.state = {
                "iteration": 1,
                "plans_processed": ["test_plan"],
                "errors": [],
            }
            MockRunner.return_value = mock_planner_runner

            runner = PlanningRunner(workflow=workflow, plan_folder="test_plan")
            result = runner.run(max_iterations=10)

            assert result is True
            assert "test_plan" in runner.state["plans_processed"]
            assert len(runner.state["plans_failed"]) == 0

    def test_run_discovery_mode(self, tmp_path, monkeypatch):
        """run() discovers and processes multiple plans when no --epic flag."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = ["plan_a", "plan_b"]

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = True
            mock_planner_runner.state = {"iteration": 1, "plans_processed": [], "errors": []}
            MockRunner.return_value = mock_planner_runner

            runner = PlanningRunner(workflow=workflow, plan_folder=None)
            result = runner.run()

            assert result is True
            assert len(runner.state["plans_processed"]) == 2

    def test_no_plans_returns_true(self, tmp_path, monkeypatch):
        """run() returns True immediately when no plans need orchestration."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = []

        runner = PlanningRunner(workflow=workflow, plan_folder=None)
        result = runner.run()

        assert result is True

    def test_health_check_failure_returns_false(self, tmp_path):
        """run() returns False when health check fails."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.run_health_check.side_effect = RuntimeError("Health check failed")

        runner = PlanningRunner(workflow=workflow)
        result = runner.run()

        assert result is False
        assert len(runner.state["errors"]) > 0

    def test_planner_runner_failure_tracked(self, tmp_path):
        """Plans that fail planning are added to plans_failed."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = ["bad_plan"]

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.return_value = False
            mock_planner_runner.state = {
                "iteration": 1,
                "plans_processed": [],
                "errors": [{"error": "Planning failed"}],
            }
            MockRunner.return_value = mock_planner_runner

            runner = PlanningRunner(workflow=workflow, plan_folder=None)
            result = runner.run()

            assert result is False
            assert "bad_plan" in runner.state["plans_failed"]

    def test_exception_in_planner_runner_tracked(self, tmp_path):
        """Exceptions raised by PlannerLoopRunner are caught and tracked."""
        from agenticcli.workflows.orchestration import PlanningRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir
        workflow.run_health_check.return_value = None
        workflow.discover_plans_needing_orchestration.return_value = ["crash_plan"]

        with patch("agenticcli.workflows.orchestration.PlannerLoopRunner") as MockRunner:
            mock_planner_runner = MagicMock()
            mock_planner_runner.run.side_effect = RuntimeError("Unexpected crash")
            mock_planner_runner.state = {"errors": []}
            MockRunner.return_value = mock_planner_runner

            runner = PlanningRunner(workflow=workflow, plan_folder=None)
            result = runner.run()

            assert result is False
            assert "crash_plan" in runner.state["plans_failed"]
            assert any("Unexpected crash" in str(e) for e in runner.state["errors"])


# ── TT_004: Test _run_phase passes --tmux flag ────────────────────────


@pytest.mark.story("US-PLN-049", "US-PLN-059", "US-PLN-060", "US-PLN-065")
class TestRunPhaseTmux:
    """TT_004: Tests that ExecutionRunner._run_phase() includes --tmux."""

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

    def test_run_phase_includes_tmux_flag(self, tmp_path):
        """Verify the command list includes '--tmux'."""
        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"session_id": "abc-123", "tmux_session": "agentic-test"}),
                stderr="",
            )
            result = runner._run_phase("test_plan", "phase1", "build-python", {})

        assert result is True
        # Verify the command
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "--tmux" in cmd
        assert "--no-sdk" not in cmd  # Removed: sdk-tmux handles process isolation
        assert "-b" in cmd
        assert "--role" in cmd
        assert "build-python" in cmd

    def test_run_phase_no_manual_env_stripping(self, tmp_path):
        """Verify _run_phase does NOT pass env= to subprocess.run."""
        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"session_id": "abc-123"}),
                stderr="",
            )
            runner._run_phase("test_plan", "phase1", "test-builder", {})

        # subprocess.run should NOT have env= parameter (env isolation is in tmux)
        call_kwargs = mock_run.call_args[1]
        assert "env" not in call_kwargs, f"env= should not be passed, got: {call_kwargs}"

    def test_run_phase_parses_tmux_session_from_output(self, tmp_path):
        """Verify tmux_session is parsed from spawn output JSON."""
        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "session_id": "abc-123",
                    "tmux_session": "agentic-test-build",
                    "transport": "tmux",
                }),
                stderr="",
            )
            result = runner._run_phase("test_plan", "phase1", "build-python", {})

        assert result is True
        # The tmux_session should be parsed and logged (we verify no crash on parsing)
        workflow.wait_for_session.assert_called_once_with("abc-123", timeout=3600)

    def test_run_phase_works_without_tmux_in_output(self, tmp_path):
        """Verify normal flow when spawn output has no tmux_session (subprocess fallback)."""
        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            # Output without tmux_session (subprocess fallback case)
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "session_id": "def-456",
                    "pid": 12345,
                    "status": "running",
                }),
                stderr="",
            )
            result = runner._run_phase("test_plan", "phase1", "build-python", {})

        assert result is True
        workflow.wait_for_session.assert_called_once_with("def-456", timeout=3600)


# ── TT_007: Test full spawn chain with CLAUDECODE env isolation ──────


@pytest.mark.story("US-PLN-049", "US-PLN-059", "US-PLN-060", "US-PLN-065", "US-PLN-066")
class TestSpawnChainEnvIsolation:
    """TT_007: Tests the _run_phase -> cmd_spawn -> tmux -> wait_for_session chain.

    These tests verify that when running inside a Claude Code session
    (CLAUDECODE=1 in env), _run_phase correctly delegates to the tmux
    path which isolates the environment. The spawned agent should NOT
    inherit CLAUDECODE, preventing the nested-session guard error.
    """

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

    def test_run_phase_with_claudecode_set_uses_tmux_not_env(self, tmp_path, monkeypatch):
        """When CLAUDECODE=1 is set (running inside Claude Code),
        _run_phase uses --tmux flag and does NOT strip env manually.

        The tmux path handles env isolation via 'unset CLAUDECODE' in
        the wrapped command, not via subprocess env= parameter.
        """
        # Simulate running inside Claude Code
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "test")

        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "session_id": "chain-001",
                    "tmux_session": "agentic-chain-test",
                    "transport": "tmux",
                    "pid": 12345,
                }),
                stderr="",
            )
            result = runner._run_phase("test_plan", "phase1", "build-python", {})

        assert result is True

        # Verify tmux flags are in the command
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "--tmux" in cmd, "Must use --tmux for env isolation"
        assert "--no-sdk" not in cmd, "sdk-tmux handles process isolation now"

        # Verify NO env= parameter (env isolation happens inside tmux, not here)
        call_kwargs = call_args[1]
        assert "env" not in call_kwargs, (
            "env= must NOT be passed to subprocess.run; "
            "CLAUDECODE isolation happens in the tmux wrapped command"
        )

        # Verify session_id was correctly threaded to wait_for_session
        workflow.wait_for_session.assert_called_once_with("chain-001", timeout=3600)

    def test_run_phase_spawn_failure_returns_false(self, tmp_path, monkeypatch):
        """When spawn subprocess fails (e.g., tmux unavailable), _run_phase returns False."""
        monkeypatch.setenv("CLAUDECODE", "1")

        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="tmux: command not found",
            )
            result = runner._run_phase("test_plan", "phase1", "build-python", {})

        assert result is False
        # wait_for_session should NOT be called when spawn fails
        workflow.wait_for_session.assert_not_called()

    def test_run_phase_spawn_timeout_returns_false(self, tmp_path, monkeypatch):
        """When spawn subprocess times out (>60s), _run_phase returns False."""
        monkeypatch.setenv("CLAUDECODE", "1")

        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["agentic"], timeout=60)
            result = runner._run_phase("test_plan", "phase1", "build-python", {})

        assert result is False
        workflow.wait_for_session.assert_not_called()

    def test_run_phase_wait_failure_returns_false(self, tmp_path, monkeypatch):
        """When wait_for_session returns 'failed', _run_phase returns False."""
        monkeypatch.setenv("CLAUDECODE", "1")

        runner, workflow = self._make_runner(tmp_path)
        workflow.wait_for_session.return_value = "failed"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "session_id": "chain-002",
                    "tmux_session": "agentic-chain-fail",
                    "transport": "tmux",
                }),
                stderr="",
            )
            result = runner._run_phase("test_plan", "phase1", "build-python", {})

        assert result is False

    def test_run_phase_wait_timeout_returns_false(self, tmp_path, monkeypatch):
        """When wait_for_session returns None (timeout), _run_phase returns False."""
        monkeypatch.setenv("CLAUDECODE", "1")

        runner, workflow = self._make_runner(tmp_path)
        workflow.wait_for_session.return_value = None  # Timeout

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "session_id": "chain-003",
                    "tmux_session": "agentic-chain-timeout",
                    "transport": "tmux",
                }),
                stderr="",
            )
            result = runner._run_phase("test_plan", "phase1", "build-python", {})

        assert result is False

    def test_run_phase_invalid_json_output_returns_false(self, tmp_path, monkeypatch):
        """When spawn returns invalid JSON, _run_phase returns False."""
        monkeypatch.setenv("CLAUDECODE", "1")

        runner, workflow = self._make_runner(tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not valid json",
                stderr="",
            )
            result = runner._run_phase("test_plan", "phase1", "build-python", {})

        assert result is False
        workflow.wait_for_session.assert_not_called()

    def test_run_phase_dangerously_skip_permissions_flag(self, tmp_path, monkeypatch):
        """When dangerously_skip_permissions is set, flag is included in spawn command."""
        monkeypatch.setenv("CLAUDECODE", "1")

        runner, workflow = self._make_runner(tmp_path)
        runner.dangerously_skip_permissions = True

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({
                    "session_id": "chain-004",
                    "tmux_session": "agentic-chain-perms",
                    "transport": "tmux",
                }),
                stderr="",
            )
            runner._run_phase("test_plan", "phase1", "build-python", {})

        cmd = mock_run.call_args[0][0]
        assert "--dangerously-skip-permissions" in cmd


# ── TestSDKMetricsReading: SDK metrics reading via ExecutionRunner ───────────


@pytest.mark.story("US-PLN-051", "US-PLN-059")
class TestSDKMetricsReading:
    """Tests for read_sdk_metrics() and its integration in ExecutionRunner."""

    def _make_runner(self, tmp_path):
        """Create an ExecutionRunner for testing."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)
        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir
        workflow.wait_for_session.return_value = "completed"

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        return runner, workflow

    def test_read_sdk_metrics_success(self, monkeypatch):
        """read_sdk_metrics() returns all fields when StateStore.load() provides a full dict."""
        from agenticcli.utils.session_state import read_sdk_metrics

        full_state = {
            "session_id": "abc-123",
            "cost_usd": 0.0421,
            "duration_ms": 12500,
            "num_turns": 17,
            "usage": {"input_tokens": 5000, "output_tokens": 1200},
            "sdk_session_id": "sdk-xyz",
            "transport": "sdk-tmux",
        }

        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.load.return_value = full_state
            MockStore.return_value = mock_instance

            result = read_sdk_metrics("abc-123")

        assert result["cost_usd"] == pytest.approx(0.0421)
        assert result["duration_ms"] == 12500
        assert result["num_turns"] == 17
        assert result["usage"] == {"input_tokens": 5000, "output_tokens": 1200}
        assert result["sdk_session_id"] == "sdk-xyz"
        assert result["transport"] == "sdk-tmux"
        mock_instance.load.assert_called_once_with("abc-123")

    def test_read_sdk_metrics_missing_session(self, monkeypatch):
        """read_sdk_metrics() returns safe defaults when StateStore.load() returns None."""
        from agenticcli.utils.session_state import read_sdk_metrics

        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.load.return_value = None
            MockStore.return_value = mock_instance

            result = read_sdk_metrics("nonexistent-session")

        assert result["cost_usd"] == 0.0
        assert result["duration_ms"] == 0
        assert result["num_turns"] == 0
        assert result["usage"] == {}
        assert result["sdk_session_id"] == ""
        assert result["transport"] == "unknown"

    def test_read_sdk_metrics_partial_fields(self, monkeypatch):
        """read_sdk_metrics() fills missing fields with defaults when state is partial."""
        from agenticcli.utils.session_state import read_sdk_metrics

        # Only cost_usd and transport are present; other fields are absent
        partial_state = {
            "session_id": "partial-001",
            "cost_usd": 0.005,
            "transport": "tmux",
        }

        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.load.return_value = partial_state
            MockStore.return_value = mock_instance

            result = read_sdk_metrics("partial-001")

        assert result["cost_usd"] == pytest.approx(0.005)
        assert result["transport"] == "tmux"
        # Missing fields default to zero/empty
        assert result["duration_ms"] == 0
        assert result["num_turns"] == 0
        assert result["usage"] == {}
        assert result["sdk_session_id"] == ""

    def test_cost_accumulation_across_phases(self, tmp_path, monkeypatch):
        """ExecutionRunner accumulates total_cost_usd across 3 completed phases."""
        runner, workflow = self._make_runner(tmp_path)

        # Each phase returns a different cost
        costs_per_phase = [0.01, 0.02, 0.03]
        call_count = 0

        def fake_read_sdk_metrics(session_id):
            nonlocal call_count
            cost = costs_per_phase[call_count % len(costs_per_phase)]
            call_count += 1
            return {
                "cost_usd": cost,
                "duration_ms": 1000,
                "num_turns": 5,
                "usage": {},
                "sdk_session_id": "",
                "transport": "sdk-tmux",
            }

        with patch("agenticcli.workflows.orchestration.read_sdk_metrics", side_effect=fake_read_sdk_metrics):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=json.dumps({
                        "session_id": "phase-session",
                        "tmux_session": "agentic-test",
                        "transport": "sdk-tmux",
                    }),
                    stderr="",
                )

                # Run 3 phases
                runner._run_phase("test_plan", "phase1", "build-python", {})
                runner._run_phase("test_plan", "phase2", "test-builder", {})
                runner._run_phase("test_plan", "phase3", "build-python", {})

        expected_total = 0.01 + 0.02 + 0.03
        assert runner.total_cost_usd == pytest.approx(expected_total)

    def test_metrics_backward_compat(self, monkeypatch):
        """Old state files that lack SDK fields still return safe defaults without errors."""
        from agenticcli.utils.session_state import read_sdk_metrics

        # Simulate a legacy session state file written before SDK metrics were added
        legacy_state = {
            "session_id": "legacy-999",
            "status": "completed",
            "started_at": "2025-01-01T10:00:00",
            "ended_at": "2025-01-01T10:05:00",
            "pid": 9999,
            # No cost_usd, duration_ms, num_turns, usage, sdk_session_id, transport
        }

        with patch("agenticcli.utils.state_store.StateStore") as MockStore:
            mock_instance = MagicMock()
            mock_instance.load.return_value = legacy_state
            MockStore.return_value = mock_instance

            # Must not raise
            result = read_sdk_metrics("legacy-999")

        assert result["cost_usd"] == 0.0
        assert result["duration_ms"] == 0
        assert result["num_turns"] == 0
        assert result["usage"] == {}
        assert result["sdk_session_id"] == ""
        assert result["transport"] == "unknown"
