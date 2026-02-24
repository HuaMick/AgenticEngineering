"""Tests for loop stop idempotency.

Tests to verify that calling 'agentic loop stop' on loops in terminal
states returns success (exit 0) and does not raise errors.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.fixture
def loops_dir(tmp_path):
    """Create a temporary sessions directory (unified store)."""
    loops_dir = tmp_path / ".agentic" / "sessions"
    loops_dir.mkdir(parents=True)
    return loops_dir


@pytest.fixture
def mock_loops_dir(loops_dir, monkeypatch):
    """Patch StateStore.get_dir to use temp directory."""
    from agenticcli.commands import loop

    monkeypatch.setattr(loop._store, "get_dir", lambda override=None: loops_dir)
    return loops_dir


@pytest.fixture
def sample_loop_data():
    """Return sample loop data for testing."""
    return {
        "session_id": "12345678-1234-1234-1234-123456789abc",
        "type": "loop",
        "pid": 12345,
        "prompt": "Test loop task",
        "prompt_source": "string",
        "max_iterations": 10,
        "completion_promise": None,
        "current_iteration": 5,
        "status": "running",
        "started_at": "2024-01-15T10:00:00",
        "ended_at": None,
        "background": True,
        "working_dir": "/home/user/project",
        "output_file": None,
        "command": "claude --print --max-turns 10 --prompt Test loop task",
        "iterations": [
            {
                "number": 1,
                "started_at": "2024-01-15T10:00:00",
                "ended_at": "2024-01-15T10:02:00",
                "status": "completed",
            }
        ],
    }


class TestLoopStopIdempotency:
    """Tests for loop stop idempotency."""

    def test_stop_completed_loop_returns_success(
        self, mock_loops_dir, sample_loop_data, capsys
    ):
        """Test stopping a completed loop returns exit 0."""
        from agenticcli.commands import loop

        sample_loop_data["status"] = "completed"
        sample_loop_data["ended_at"] = "2024-01-15T10:10:00"
        loop._store.save(sample_loop_data)

        args = SimpleNamespace(
            loop_id=sample_loop_data["session_id"][:8],
            force=False,
        )

        # Should not raise SystemExit
        loop.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already in terminal state" in captured.out

    def test_stop_stopped_loop_returns_success(
        self, mock_loops_dir, sample_loop_data, capsys
    ):
        """Test stopping a stopped loop returns exit 0."""
        from agenticcli.commands import loop

        sample_loop_data["status"] = "stopped"
        sample_loop_data["ended_at"] = "2024-01-15T10:10:00"
        loop._store.save(sample_loop_data)

        args = SimpleNamespace(
            loop_id=sample_loop_data["session_id"][:8],
            force=False,
        )

        # Should not raise SystemExit
        loop.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already in terminal state" in captured.out

    def test_stop_failed_loop_returns_success(
        self, mock_loops_dir, sample_loop_data, capsys
    ):
        """Test stopping a failed loop returns exit 0."""
        from agenticcli.commands import loop

        sample_loop_data["status"] = "failed"
        sample_loop_data["ended_at"] = "2024-01-15T10:10:00"
        loop._store.save(sample_loop_data)

        args = SimpleNamespace(
            loop_id=sample_loop_data["session_id"][:8],
            force=False,
        )

        # Should not raise SystemExit
        loop.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already in terminal state" in captured.out

    @patch("os.kill")
    def test_stop_process_lookup_error_returns_success(
        self, mock_kill, mock_loops_dir, sample_loop_data, capsys
    ):
        """Test that ProcessLookupError marks loop as completed and returns exit 0."""
        from agenticcli.commands import loop

        mock_kill.side_effect = ProcessLookupError()
        loop._store.save(sample_loop_data)

        args = SimpleNamespace(
            loop_id=sample_loop_data["session_id"][:8],
            force=False,
        )

        # Should not raise SystemExit
        loop.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already exited" in captured.out

        # Verify loop was marked as completed
        loops = loop._store.list_all()
        assert loops[0]["status"] == "completed"

    @patch("os.kill")
    @patch("agenticcli.console.is_json_output")
    def test_stop_json_output_includes_success(
        self, mock_json_output, mock_kill, mock_loops_dir, sample_loop_data, capsys
    ):
        """Test that JSON output includes success:true for terminal state loops."""
        from agenticcli.commands import loop

        mock_json_output.return_value = True
        sample_loop_data["status"] = "completed"
        loop._store.save(sample_loop_data)

        args = SimpleNamespace(
            loop_id=sample_loop_data["session_id"][:8],
            force=False,
        )

        loop.cmd_stop(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["status"] == "completed"

    @patch("os.kill")
    @patch("agenticcli.console.is_json_output")
    def test_stop_process_not_found_json_output_includes_success(
        self, mock_json_output, mock_kill, mock_loops_dir, sample_loop_data, capsys
    ):
        """Test that ProcessLookupError returns success:true in JSON."""
        from agenticcli.commands import loop

        mock_json_output.return_value = True
        mock_kill.side_effect = ProcessLookupError()
        loop._store.save(sample_loop_data)

        args = SimpleNamespace(
            loop_id=sample_loop_data["session_id"][:8],
            force=False,
        )

        loop.cmd_stop(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["success"] is True
        assert output["status"] == "completed"
        assert "Process not found" in output["message"]
