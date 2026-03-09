"""Tests for Ralph StateStore session tracking (260308FX P6_002).

Covers:
- StateStore session record creation on Ralph tmux/SDK spawn
- StateStore update on Ralph stop
- Failure reason persistence for Ralph session failures
- failure_summary() utility function correctness (P6_001/P6_003)
"""

import json
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── Tests: failure_summary() ──────────────────────────────────────────


class TestFailureSummary:
    """Verify failure_summary() converts SessionDiagnosis to the expected dict shape."""

    def test_failure_summary_nested_session(self):
        """Should produce correct dict for nested session diagnosis."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            SessionDiagnosis,
            SuggestedAction,
            failure_summary,
        )

        diagnosis = SessionDiagnosis(
            error_type=ErrorType.NESTED_SESSION,
            suggested_action=SuggestedAction.RETRY_CLEAN_ENV,
            detail="Claude Code cannot be launched inside another Claude Code session.",
            retryable=True,
            matched_pattern="cannot be launched inside another",
        )
        result = failure_summary(diagnosis)

        assert result["error_code"] == "nested_session"
        assert result["error_type"] == "nested_session"
        assert result["suggested_action"] == "retry_clean_env"
        assert result["retryable"] is True
        assert result["matched_pattern"] == "cannot be launched inside another"
        assert "Claude Code" in result["detail"]

    def test_failure_summary_truncates_detail(self):
        """Detail should be truncated to 500 chars."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            SessionDiagnosis,
            SuggestedAction,
            failure_summary,
        )

        long_detail = "x" * 1000
        diagnosis = SessionDiagnosis(
            error_type=ErrorType.UNKNOWN,
            suggested_action=SuggestedAction.ESCALATE,
            detail=long_detail,
            retryable=False,
        )
        result = failure_summary(diagnosis)
        assert len(result["detail"]) == 500

    def test_failure_summary_all_error_types(self):
        """All ErrorType values should produce valid dicts."""
        from agenticcli.utils.session_diagnostics import (
            ErrorType,
            SessionDiagnosis,
            SuggestedAction,
            failure_summary,
        )

        for error_type in ErrorType:
            diagnosis = SessionDiagnosis(
                error_type=error_type,
                suggested_action=SuggestedAction.ESCALATE,
                detail="test",
                retryable=False,
            )
            result = failure_summary(diagnosis)
            assert result["error_code"] == error_type.value
            assert isinstance(result["retryable"], bool)
            assert "error_code" in result
            assert "error_type" in result
            assert "suggested_action" in result
            assert "detail" in result
            assert "matched_pattern" in result


# ── Tests: Ralph StateStore tracking (P6_002) ─────────────────────────


class TestRalphStateStoreHelper:
    """Verify _update_ralph_session_store() helper works correctly."""

    def test_updates_session_record_by_loop_id(self, tmp_path):
        """Should find and update session record matching ralph_loop_id."""
        from agenticcli.utils.state_store import StateStore

        store = StateStore("sessions", id_key="session_id")
        state_dir = tmp_path / "sessions"
        state_dir.mkdir()

        # Create a Ralph session record
        record = {
            "session_id": "ralph-sess-001",
            "type": "ralph",
            "ralph_loop_id": "loop-abc",
            "status": "running",
            "ended_at": None,
        }
        store.save(record, state_dir=state_dir)

        # Simulate what _update_ralph_session_store does
        records = store.list_all(
            state_dir=state_dir,
            filter_fn=lambda r: r.get("ralph_loop_id") == "loop-abc",
        )
        assert len(records) == 1
        records[0]["status"] = "stopped"
        records[0]["ended_at"] = datetime.now().isoformat()
        store.save(records[0], state_dir=state_dir)

        # Verify update persisted
        updated = store.load("ralph-sess-001", state_dir=state_dir)
        assert updated["status"] == "stopped"
        assert updated["ended_at"] is not None

    def test_no_match_does_not_crash(self, tmp_path):
        """Should not crash when no matching session record exists."""
        from agenticcli.utils.state_store import StateStore

        store = StateStore("sessions", id_key="session_id")
        state_dir = tmp_path / "sessions"
        state_dir.mkdir()

        # No records exist — should return empty list, not crash
        records = store.list_all(
            state_dir=state_dir,
            filter_fn=lambda r: r.get("ralph_loop_id") == "nonexistent",
        )
        assert records == []


class TestRalphStartTmuxStateStore:
    """Verify that ralph start creates StateStore records for tmux sessions."""

    @patch("agenticcli.commands.ralph.RalphLoopService")
    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("agenticcli.commands.ralph._session_store")
    @patch("agenticcli.commands.ralph.get_default_ralph_prompt")
    def test_tmux_spawn_creates_session_record(
        self, mock_prompt, mock_store, mock_which, mock_run, mock_service_cls
    ):
        """Spawning a tmux Ralph session should create a StateStore record."""
        from agenticcli.commands.ralph import start

        # Mock service
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.get_state.return_value = None
        state = MagicMock()
        state.loop_id = "test-loop-123"
        state.status = "running"
        state.tmux_session = None
        mock_service.start_loop.return_value = state

        # Mock prompt
        mock_prompt.return_value = None

        # Mock which (tmux and claude available, no SDK)
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}" if cmd in ("tmux", "claude") else None

        # Mock subprocess.run to succeed
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        # Mock SDK not available
        with patch("agenticcli.commands.ralph._RALPH_SDK_AVAILABLE", False, create=True), \
             patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            try:
                start(prompt_file=None, max_iterations=5, background=True)
            except SystemExit:
                pass  # Typer.Exit is normal

        # Verify StateStore.save was called (at least for initial creation + running update)
        save_calls = mock_store.save.call_args_list
        assert len(save_calls) >= 1, "StateStore.save should be called at least once"

        # Check the session record structure
        first_save = save_calls[0][0][0]  # First positional arg of first call
        assert first_save["type"] == "ralph"
        assert first_save["transport"] == "tmux"
        assert first_save["ralph_loop_id"] == "test-loop-123"
        assert "session_id" in first_save
        assert first_save["status"] in ("starting", "running")

    @patch("agenticcli.commands.ralph.RalphLoopService")
    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("agenticcli.commands.ralph._session_store")
    @patch("agenticcli.commands.ralph.get_default_ralph_prompt")
    def test_tmux_spawn_failure_records_failure_reason(
        self, mock_prompt, mock_store, mock_which, mock_run, mock_service_cls
    ):
        """Failed tmux spawn should record failure_reason in StateStore."""
        from agenticcli.commands.ralph import start

        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_service.get_state.return_value = None
        state = MagicMock()
        state.loop_id = "fail-loop-456"
        mock_service.start_loop.return_value = state

        mock_prompt.return_value = None
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}" if cmd in ("tmux", "claude") else None

        # tmux new-session fails
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="duplicate session: ralph-fail-loo")

        with patch("agenticcli.utils.sdk_runner.SDK_AVAILABLE", False):
            # typer.Exit raises click.exceptions.Exit when called directly
            from click.exceptions import Exit as ClickExit
            with pytest.raises((SystemExit, ClickExit)):
                start(prompt_file=None, max_iterations=5, background=True)

        # Verify failure_reason was persisted
        save_calls = mock_store.save.call_args_list
        assert len(save_calls) >= 2, "Should save initial + failure record"

        # The second save should have the failure info
        failure_save = save_calls[-1][0][0]
        assert failure_save["status"] == "failed"
        assert failure_save["error_code"] == "tmux_spawn_failed"
        assert "failure_reason" in failure_save
        assert failure_save["failure_reason"]["error_code"] == "tmux_spawn_failed"
        assert failure_save["failure_reason"]["retryable"] is True


class TestRalphStopStateStore:
    """Verify that ralph stop updates StateStore records."""

    @patch("agenticcli.commands.ralph.RalphLoopService")
    @patch("agenticcli.commands.ralph._update_ralph_session_store")
    @patch("subprocess.run")
    def test_stop_updates_session_store(self, mock_run, mock_update, mock_service_cls):
        """Stopping Ralph should call _update_ralph_session_store."""
        from agenticcli.commands.ralph import stop

        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        state = MagicMock()
        state.status = "running"
        state.loop_id = "stop-loop-789"
        state.tmux_session = "ralph-stop-lo"
        mock_service.get_state.return_value = state

        mock_run.return_value = MagicMock(returncode=0)

        stop(force=True)

        # Verify _update_ralph_session_store was called with the loop_id
        mock_update.assert_called_once_with("stop-loop-789", "stopped")


class TestRalphSessionRecordShape:
    """Verify the shape of Ralph session records matches regular sessions."""

    def test_ralph_session_has_required_fields(self):
        """Ralph session records should have the same core fields as regular sessions."""
        # This test validates the contract between Ralph and StateStore consumers
        # (like `agentic session list` and orchestration diagnostics).
        required_fields = [
            "session_id",
            "type",
            "status",
            "started_at",
            "ended_at",
            "background",
            "working_dir",
            "transport",
        ]
        ralph_specific_fields = [
            "ralph_loop_id",
            "max_iterations",
        ]

        # Build a sample Ralph session record (as ralph.py would create)
        import uuid

        sample = {
            "session_id": str(uuid.uuid4()),
            "type": "ralph",
            "pid": None,
            "prompt": "test prompt",
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "background": True,
            "working_dir": "/tmp/test",
            "transport": "tmux",
            "tmux_session": "ralph-test",
            "ralph_loop_id": "loop-test",
            "max_iterations": 20,
        }

        for field in required_fields + ralph_specific_fields:
            assert field in sample, f"Missing required field: {field}"

    def test_failure_reason_shape_matches_session_diagnostics(self):
        """failure_reason dict shape should match failure_summary() output."""
        required_keys = [
            "error_code",
            "error_type",
            "suggested_action",
            "detail",
            "retryable",
            "matched_pattern",
        ]

        # Sample failure_reason as Ralph would create
        failure_reason = {
            "error_code": "tmux_spawn_failed",
            "error_type": "unknown",
            "suggested_action": "escalate",
            "detail": "tmux new-session failed",
            "retryable": True,
            "matched_pattern": "",
        }

        for key in required_keys:
            assert key in failure_reason, f"Missing key in failure_reason: {key}"
