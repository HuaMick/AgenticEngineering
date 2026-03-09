"""Tests for auto-retry on quick exit (260308FX P3_003).

Covers:
- Session diagnostics module (error pattern detection)
- ExecutionRunner auto-retry on quick exit
- Exponential backoff timing
- Max retry limit enforcement
"""

import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── Tests: session_diagnostics module ────────────────────────────────────


class TestDiagnoseSessionLog:
    """Verify session log parsing detects known error patterns."""

    def test_detects_nested_session_error(self, tmp_path):
        """Should detect 'cannot be launched inside another' pattern."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            SuggestedAction,
            diagnose_session_log,
        )

        log = tmp_path / "test.stdout.log"
        log.write_text("Error: Claude Code cannot be launched inside another Claude Code session.")

        diagnosis = diagnose_session_log(log)
        assert diagnosis.error_type == ErrorType.NESTED_SESSION
        assert diagnosis.retryable is True
        assert diagnosis.suggested_action == SuggestedAction.RETRY_CLEAN_ENV

    def test_detects_max_turns_exceeded(self, tmp_path):
        """Should detect 'Maximum number of turns' pattern."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            diagnose_session_log,
        )

        log = tmp_path / "test.stdout.log"
        log.write_text("Maximum number of turns (5) reached. Exiting.")

        diagnosis = diagnose_session_log(log)
        assert diagnosis.error_type == ErrorType.MAX_TURNS_EXCEEDED
        assert diagnosis.retryable is False

    def test_detects_permission_denied(self, tmp_path):
        """Should detect 'permission denied' pattern."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            diagnose_session_log,
        )

        log = tmp_path / "test.stderr.log"
        log.write_text("Error: permission denied accessing /var/protected")

        diagnosis = diagnose_session_log("/dev/null", stderr_path=log)
        assert diagnosis.error_type == ErrorType.PERMISSION_DENIED
        assert diagnosis.retryable is False

    def test_detects_api_key_missing(self, tmp_path):
        """Should detect API key patterns."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            diagnose_session_log,
        )

        log = tmp_path / "test.stdout.log"
        log.write_text("Please set ANTHROPIC_API_KEY environment variable")

        diagnosis = diagnose_session_log(log)
        assert diagnosis.error_type == ErrorType.API_KEY_MISSING

    def test_detects_rate_limit(self, tmp_path):
        """Should detect rate limit patterns."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            diagnose_session_log,
        )

        log = tmp_path / "test.stderr.log"
        log.write_text("HTTP 429: rate limit exceeded. Try again later.")

        diagnosis = diagnose_session_log("/dev/null", stderr_path=log)
        assert diagnosis.error_type == ErrorType.RATE_LIMIT
        assert diagnosis.retryable is True

    def test_empty_logs_return_unknown_retryable(self, tmp_path):
        """Empty logs should return unknown but retryable (likely env issue)."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            diagnose_session_log,
        )

        log = tmp_path / "test.stdout.log"
        log.write_text("")

        diagnosis = diagnose_session_log(log)
        assert diagnosis.error_type == ErrorType.UNKNOWN
        assert diagnosis.retryable is True

    def test_missing_log_file_returns_unknown(self):
        """Non-existent log file should not crash."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            diagnose_session_log,
        )

        diagnosis = diagnose_session_log("/nonexistent/path.log")
        assert diagnosis.error_type == ErrorType.UNKNOWN

    def test_unrecognized_error_returns_unknown(self, tmp_path):
        """Unrecognized error text should return unknown, not retryable."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            diagnose_session_log,
        )

        log = tmp_path / "test.stdout.log"
        log.write_text("Something completely unexpected happened in the flux capacitor")

        diagnosis = diagnose_session_log(log)
        assert diagnosis.error_type == ErrorType.UNKNOWN
        assert diagnosis.retryable is False

    def test_reads_stderr_for_patterns(self, tmp_path):
        """Should check stderr log as well as stdout."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            diagnose_session_log,
        )

        stdout_log = tmp_path / "test.stdout.log"
        stdout_log.write_text("Agent output looks fine")
        stderr_log = tmp_path / "test.stderr.log"
        stderr_log.write_text("Error: cannot be launched inside another Claude Code session")

        diagnosis = diagnose_session_log(stdout_log, stderr_path=stderr_log)
        assert diagnosis.error_type == ErrorType.NESTED_SESSION


class TestDiagnoseSessionState:
    """Verify session state dict diagnosis."""

    def test_extracts_log_paths_from_state(self, tmp_path):
        """Should use stdout_log and stderr_log from state dict."""
        from agenticcli.utils.session_diagnostics import diagnose_session_state

        log = tmp_path / "test.stdout.log"
        log.write_text("rate limit hit")

        state = {
            "session_id": "test-123",
            "stdout_log": str(log),
            "stderr_log": None,
        }

        diagnosis = diagnose_session_state(state)
        assert diagnosis is not None
        assert diagnosis.retryable is True

    def test_returns_none_without_logs(self):
        """Should return None when no log paths are in state."""
        from agenticcli.utils.session_diagnostics import diagnose_session_state

        state = {"session_id": "test-456"}
        assert diagnose_session_state(state) is None


# ── Tests: ExecutionRunner auto-retry ────────────────────────────────────


class TestExecutionRunnerAutoRetry:
    """Verify _run_phase auto-retries on quick exit."""

    def _make_runner(self, tmp_path):
        """Create an ExecutionRunner for testing."""
        from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

        epics_dir = tmp_path / "docs" / "epics" / "live"
        epics_dir.mkdir(parents=True)

        workflow = MagicMock(spec=OrchestrationWorkflow)
        workflow.working_dir = str(tmp_path)
        workflow.epics_dir = epics_dir

        runner = ExecutionRunner(workflow=workflow, plan_folder="test_plan")
        return runner, workflow

    def _mock_spawn_success(self, session_id="abc-123"):
        """Return a MagicMock that simulates a successful spawn."""
        return MagicMock(
            returncode=0,
            stdout=json.dumps({"session_id": session_id, "tmux_session": "agentic-test"}),
            stderr="",
        )

    def test_no_retry_on_success(self, tmp_path):
        """Successful sessions should not trigger retry."""
        runner, workflow = self._make_runner(tmp_path)
        workflow.wait_for_session.return_value = "completed"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._mock_spawn_success()
            result = runner._run_phase("test", "Build", "build-python", {})

        assert result is True
        assert mock_run.call_count == 1  # No retry

    def test_no_retry_on_normal_failure(self, tmp_path):
        """Slow failures (not quick exit) should not trigger retry."""
        runner, workflow = self._make_runner(tmp_path)
        workflow.wait_for_session.return_value = "failed"

        with patch("subprocess.run") as mock_run, \
             patch("time.monotonic") as mock_time:
            mock_run.return_value = self._mock_spawn_success()
            # Simulate 120 seconds elapsed (well past quick exit threshold)
            mock_time.side_effect = [0.0, 120.0]
            result = runner._run_phase("test", "Build", "build-python", {})

        assert result is False
        assert mock_run.call_count == 1  # No retry

    def test_retry_on_quick_exit(self, tmp_path):
        """Quick exits should trigger retry."""
        runner, workflow = self._make_runner(tmp_path)

        call_count = [0]

        def wait_side_effect(session_id, timeout=1800):
            call_count[0] += 1
            if call_count[0] == 1:
                return "failed"  # First attempt fails
            return "completed"  # Retry succeeds

        workflow.wait_for_session.side_effect = wait_side_effect

        spawn_results = [
            self._mock_spawn_success("session-1"),
            self._mock_spawn_success("session-2"),
        ]

        with patch("subprocess.run") as mock_run, \
             patch("time.monotonic") as mock_time, \
             patch("time.sleep") as mock_sleep, \
             patch.object(runner, "_diagnose_quick_exit", return_value=None):
            mock_run.side_effect = spawn_results
            # First attempt: quick exit (5 seconds)
            # Second attempt: normal completion (120 seconds)
            mock_time.side_effect = [0.0, 5.0, 0.0, 120.0]
            result = runner._run_phase("test", "Build", "build-python", {})

        assert result is True
        assert mock_run.call_count == 2  # Original + 1 retry
        mock_sleep.assert_called_once_with(5)  # First backoff

    def test_max_retries_enforced(self, tmp_path):
        """Should stop retrying after MAX_SPAWN_RETRIES attempts."""
        from agenticcli.workflows.orchestration import MAX_SPAWN_RETRIES

        runner, workflow = self._make_runner(tmp_path)
        workflow.wait_for_session.return_value = "failed"

        with patch("subprocess.run") as mock_run, \
             patch("time.monotonic") as mock_time, \
             patch("time.sleep"), \
             patch.object(runner, "_diagnose_quick_exit", return_value=None):
            mock_run.return_value = self._mock_spawn_success()
            # All attempts are quick exits (5 seconds each)
            mock_time.side_effect = [0.0, 5.0] * (1 + MAX_SPAWN_RETRIES)
            result = runner._run_phase("test", "Build", "build-python", {})

        assert result is False
        assert mock_run.call_count == 1 + MAX_SPAWN_RETRIES

    def test_non_retryable_diagnosis_stops_retry(self, tmp_path):
        """Non-retryable diagnosis should stop retry loop immediately."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            SessionDiagnosis,
            SuggestedAction,
        )

        runner, workflow = self._make_runner(tmp_path)
        workflow.wait_for_session.return_value = "failed"

        non_retryable_diagnosis = SessionDiagnosis(
            error_type=ErrorType.PERMISSION_DENIED,
            suggested_action=SuggestedAction.CHECK_PERMISSIONS,
            detail="Permission denied",
            retryable=False,
        )

        with patch("subprocess.run") as mock_run, \
             patch("time.monotonic") as mock_time, \
             patch.object(runner, "_diagnose_quick_exit", return_value=non_retryable_diagnosis):
            mock_run.return_value = self._mock_spawn_success()
            mock_time.side_effect = [0.0, 5.0]  # Quick exit
            result = runner._run_phase("test", "Build", "build-python", {})

        assert result is False
        assert mock_run.call_count == 1  # No retry for non-retryable

    def test_exponential_backoff_timing(self, tmp_path):
        """Retry backoff should follow RETRY_BACKOFF_SECONDS pattern."""
        from agenticcli.workflows.orchestration import RETRY_BACKOFF_SECONDS

        runner, workflow = self._make_runner(tmp_path)
        workflow.wait_for_session.return_value = "failed"

        with patch("subprocess.run") as mock_run, \
             patch("time.monotonic") as mock_time, \
             patch("time.sleep") as mock_sleep, \
             patch.object(runner, "_diagnose_quick_exit", return_value=None):
            mock_run.return_value = self._mock_spawn_success()
            # All quick exits
            mock_time.side_effect = [0.0, 5.0, 0.0, 5.0, 0.0, 5.0]
            runner._run_phase("test", "Build", "build-python", {})

        # Check backoff values match RETRY_BACKOFF_SECONDS
        sleep_calls = [c[0][0] for c in mock_sleep.call_args_list]
        assert sleep_calls == RETRY_BACKOFF_SECONDS[:len(sleep_calls)]


class TestSpawnRetryConstants:
    """Verify retry configuration constants exist and are reasonable."""

    def test_max_spawn_retries_exists(self):
        from agenticcli.workflows.orchestration import MAX_SPAWN_RETRIES

        assert isinstance(MAX_SPAWN_RETRIES, int)
        assert MAX_SPAWN_RETRIES >= 1
        assert MAX_SPAWN_RETRIES <= 5

    def test_retry_backoff_seconds_exists(self):
        from agenticcli.workflows.orchestration import RETRY_BACKOFF_SECONDS

        assert isinstance(RETRY_BACKOFF_SECONDS, list)
        assert len(RETRY_BACKOFF_SECONDS) >= 1
        # Should be monotonically increasing (exponential)
        for i in range(1, len(RETRY_BACKOFF_SECONDS)):
            assert RETRY_BACKOFF_SECONDS[i] > RETRY_BACKOFF_SECONDS[i - 1]
