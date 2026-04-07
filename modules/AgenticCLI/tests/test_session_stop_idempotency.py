"""Tests for session stop idempotency.

Tests to verify that calling 'agentic session stop' on sessions in terminal
states returns success (exit 0) and does not raise errors.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.story("US-SES-001")


@pytest.fixture
def sessions_dir(tmp_path):
    """Create a temporary sessions directory."""
    sessions_dir = tmp_path / ".agentic" / "sessions"
    sessions_dir.mkdir(parents=True)
    return sessions_dir


@pytest.fixture
def mock_sessions_dir(sessions_dir, monkeypatch):
    """Patch _get_sessions_dir to use temp directory."""
    from agenticcli.commands import session

    monkeypatch.setattr(session._store, "get_dir", lambda override=None: sessions_dir)
    return sessions_dir


@pytest.fixture
def sample_session_data():
    """Return sample session data for testing."""
    return {
        "session_id": "12345678-1234-1234-1234-123456789abc",
        "pid": 12345,
        "prompt": "Test task",
        "max_turns": 10,
        "status": "running",
        "started_at": "2024-01-15T10:00:00",
        "ended_at": None,
        "background": True,
        "working_dir": "/home/user/project",
        "command": "claude --print --max-turns 10 Test task",
    }


class TestSessionStopIdempotency:
    """Tests for session stop idempotency."""

    def test_stop_completed_session_returns_success(
        self, mock_sessions_dir, sample_session_data, capsys
    ):
        """Test stopping a completed session returns exit 0."""
        from agenticcli.commands import session

        sample_session_data["status"] = "completed"
        sample_session_data["ended_at"] = "2024-01-15T10:05:00"
        session._store.save(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        # Should not raise SystemExit
        session.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already in terminal state" in captured.out

    def test_stop_stopped_session_returns_success(
        self, mock_sessions_dir, sample_session_data, capsys
    ):
        """Test stopping a stopped session returns exit 0."""
        from agenticcli.commands import session

        sample_session_data["status"] = "stopped"
        sample_session_data["ended_at"] = "2024-01-15T10:05:00"
        session._store.save(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        # Should not raise SystemExit
        session.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already in terminal state" in captured.out

    def test_stop_failed_session_returns_success(
        self, mock_sessions_dir, sample_session_data, capsys
    ):
        """Test stopping a failed session returns exit 0."""
        from agenticcli.commands import session

        sample_session_data["status"] = "failed"
        sample_session_data["ended_at"] = "2024-01-15T10:05:00"
        session._store.save(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        # Should not raise SystemExit
        session.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already in terminal state" in captured.out

    @patch("os.kill")
    def test_stop_process_lookup_error_returns_success(
        self, mock_kill, mock_sessions_dir, sample_session_data, capsys
    ):
        """Test that ProcessLookupError marks session as completed and returns exit 0."""
        from agenticcli.commands import session

        mock_kill.side_effect = ProcessLookupError()
        session._store.save(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        # Should not raise SystemExit
        session.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already exited" in captured.out

        # Verify session was marked as completed
        sessions = session._store.list_all()
        assert sessions[0]["status"] == "completed"

    @patch("os.kill")
    @patch("agenticcli.console.is_json_output")
    def test_stop_json_output_includes_success(
        self, mock_json_output, mock_kill, mock_sessions_dir, sample_session_data, capsys
    ):
        """Test that JSON output includes success:true for terminal state sessions."""
        from agenticcli.commands import session

        mock_json_output.return_value = True
        sample_session_data["status"] = "completed"
        session._store.save(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        session.cmd_stop(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["status"] == "completed"

    @patch("os.kill")
    @patch("agenticcli.console.is_json_output")
    def test_stop_process_not_found_json_output_includes_success(
        self, mock_json_output, mock_kill, mock_sessions_dir, sample_session_data, capsys
    ):
        """Test that ProcessLookupError returns success:true in JSON."""
        from agenticcli.commands import session

        mock_json_output.return_value = True
        mock_kill.side_effect = ProcessLookupError()
        session._store.save(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        session.cmd_stop(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["status"] == "completed"
        assert "Process not found" in output["message"]
