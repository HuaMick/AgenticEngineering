"""End-to-end integration tests for stop command idempotency.

Tests that multiple consecutive stop calls on the same session/loop
return success without errors.
"""

import json
import subprocess
import time
from pathlib import Path

import pytest


@pytest.fixture
def sessions_dir(tmp_path):
    """Create a temporary sessions directory."""
    sessions_dir = tmp_path / ".agentic" / "sessions"
    sessions_dir.mkdir(parents=True)
    return sessions_dir


@pytest.fixture
def loops_dir(tmp_path):
    """Create a temporary loops directory."""
    loops_dir = tmp_path / ".agentic" / "loops"
    loops_dir.mkdir(parents=True)
    return loops_dir


class TestSessionStopIdempotencyE2E:
    """End-to-end tests for session stop idempotency."""

    def test_session_stop_twice_returns_success(self, sessions_dir, monkeypatch):
        """Test that calling session stop twice on same session returns success."""
        from agenticcli.commands import session

        # Mock the sessions directory
        monkeypatch.setattr(session._store, "get_dir", lambda override=None: sessions_dir)

        # Create a completed session
        session_data = {
            "session_id": "test-session-12345678",
            "pid": 99999,
            "prompt": "Test",
            "max_turns": 5,
            "status": "completed",
            "started_at": "2024-01-15T10:00:00",
            "ended_at": "2024-01-15T10:05:00",
            "background": False,
            "working_dir": "/tmp",
            "command": "claude --print Test",
        }
        session._store.save(session_data)

        # First stop call
        from types import SimpleNamespace

        args1 = SimpleNamespace(session_id="test-session", force=False)
        session.cmd_stop(args1)  # Should succeed

        # Second stop call
        args2 = SimpleNamespace(session_id="test-session", force=False)
        session.cmd_stop(args2)  # Should also succeed

        # Both calls should complete without raising SystemExit

    def test_session_stop_three_times_returns_success(
        self, sessions_dir, monkeypatch
    ):
        """Test that calling session stop three times returns success."""
        from agenticcli.commands import session

        monkeypatch.setattr(session._store, "get_dir", lambda override=None: sessions_dir)

        session_data = {
            "session_id": "test-session-87654321",
            "pid": 99998,
            "prompt": "Test",
            "max_turns": 5,
            "status": "stopped",
            "started_at": "2024-01-15T10:00:00",
            "ended_at": "2024-01-15T10:05:00",
            "background": False,
            "working_dir": "/tmp",
            "command": "claude --print Test",
        }
        session._store.save(session_data)

        from types import SimpleNamespace

        # Call stop multiple times
        for i in range(3):
            args = SimpleNamespace(session_id="test-session-87", force=False)
            session.cmd_stop(args)  # All should succeed

    def test_session_stop_failed_session_idempotent(
        self, sessions_dir, monkeypatch, capsys
    ):
        """Test that stopping a failed session multiple times is idempotent."""
        from agenticcli.commands import session

        monkeypatch.setattr(session._store, "get_dir", lambda override=None: sessions_dir)

        session_data = {
            "session_id": "failed-session-11111111",
            "pid": 99997,
            "prompt": "Test",
            "max_turns": 5,
            "status": "failed",
            "started_at": "2024-01-15T10:00:00",
            "ended_at": "2024-01-15T10:05:00",
            "background": False,
            "working_dir": "/tmp",
            "command": "claude --print Test",
            "exit_code": 1,
        }
        session._store.save(session_data)

        from types import SimpleNamespace

        # First stop
        args1 = SimpleNamespace(session_id="failed-session", force=False)
        session.cmd_stop(args1)
        captured1 = capsys.readouterr()
        assert "terminal state" in captured1.out

        # Second stop
        args2 = SimpleNamespace(session_id="failed-session", force=False)
        session.cmd_stop(args2)
        captured2 = capsys.readouterr()
        assert "terminal state" in captured2.out


class TestLoopStopIdempotencyE2E:
    """End-to-end tests for loop stop idempotency."""

    def test_loop_stop_twice_returns_success(self, loops_dir, monkeypatch):
        """Test that calling loop stop twice on same loop returns success."""
        from agenticcli.commands import loop

        monkeypatch.setattr(loop._store, "get_dir", lambda override=None: loops_dir)

        loop_data = {
            "loop_id": "test-loop-12345678",
            "pid": 99999,
            "prompt": "Test loop",
            "prompt_source": "string",
            "max_iterations": 10,
            "current_iteration": 10,
            "status": "completed",
            "started_at": "2024-01-15T10:00:00",
            "ended_at": "2024-01-15T10:30:00",
            "background": False,
            "working_dir": "/tmp",
            "command": "claude --print --max-turns 10 --prompt Test loop",
            "iterations": [],
        }
        loop._store.save(loop_data)

        from types import SimpleNamespace

        # First stop call
        args1 = SimpleNamespace(loop_id="test-loop", force=False)
        loop.cmd_stop(args1)  # Should succeed

        # Second stop call
        args2 = SimpleNamespace(loop_id="test-loop", force=False)
        loop.cmd_stop(args2)  # Should also succeed

    def test_loop_stop_multiple_times_json_output(
        self, loops_dir, monkeypatch, capsys
    ):
        """Test multiple stop calls with JSON output."""
        from agenticcli.commands import loop
        from unittest.mock import patch

        monkeypatch.setattr(loop._store, "get_dir", lambda override=None: loops_dir)

        loop_data = {
            "loop_id": "json-loop-87654321",
            "pid": 99998,
            "prompt": "Test loop",
            "prompt_source": "string",
            "max_iterations": 5,
            "current_iteration": 5,
            "status": "stopped",
            "started_at": "2024-01-15T10:00:00",
            "ended_at": "2024-01-15T10:15:00",
            "background": False,
            "working_dir": "/tmp",
            "command": "claude --print Test loop",
            "iterations": [],
        }
        loop._store.save(loop_data)

        from types import SimpleNamespace

        # Call stop twice with JSON output
        with patch("agenticcli.console.is_json_output", return_value=True):
            # First stop
            args1 = SimpleNamespace(loop_id="json-loop", force=False)
            loop.cmd_stop(args1)
            captured1 = capsys.readouterr()
            output1 = json.loads(captured1.out)
            assert output1["success"] is True

            # Second stop
            args2 = SimpleNamespace(loop_id="json-loop", force=False)
            loop.cmd_stop(args2)
            captured2 = capsys.readouterr()
            output2 = json.loads(captured2.out)
            assert output2["success"] is True


class TestCrossCommandIdempotency:
    """Tests for idempotency across different command scenarios."""

    def test_stop_after_natural_completion(self, sessions_dir, monkeypatch, capsys):
        """Test stopping a session that completed naturally is idempotent."""
        from agenticcli.commands import session

        monkeypatch.setattr(session._store, "get_dir", lambda override=None: sessions_dir)

        # Simulate a session that ran to completion
        session_data = {
            "session_id": "natural-complete-12345678",
            "pid": 99996,
            "prompt": "Test",
            "max_turns": 1,
            "status": "completed",
            "started_at": "2024-01-15T10:00:00",
            "ended_at": "2024-01-15T10:01:00",
            "background": False,
            "working_dir": "/tmp",
            "command": "claude --print Test",
            "exit_code": 0,
        }
        session._store.save(session_data)

        from types import SimpleNamespace

        # Try to stop it
        args = SimpleNamespace(session_id="natural-complete", force=False)
        session.cmd_stop(args)

        captured = capsys.readouterr()
        assert "terminal state" in captured.out

        # Try again
        session.cmd_stop(args)
        captured = capsys.readouterr()
        assert "terminal state" in captured.out

    def test_force_stop_on_completed_session(self, sessions_dir, monkeypatch):
        """Test that force stop on completed session is also idempotent."""
        from agenticcli.commands import session

        monkeypatch.setattr(session._store, "get_dir", lambda override=None: sessions_dir)

        session_data = {
            "session_id": "force-stop-12345678",
            "pid": 99995,
            "prompt": "Test",
            "max_turns": 5,
            "status": "completed",
            "started_at": "2024-01-15T10:00:00",
            "ended_at": "2024-01-15T10:05:00",
            "background": False,
            "working_dir": "/tmp",
            "command": "claude --print Test",
        }
        session._store.save(session_data)

        from types import SimpleNamespace

        # Force stop on completed session
        args = SimpleNamespace(session_id="force-stop", force=True)
        session.cmd_stop(args)  # Should succeed

        # Force stop again
        session.cmd_stop(args)  # Should also succeed
