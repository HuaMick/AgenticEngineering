"""Tests for session management CLI commands.

Tests for spawning, listing, stopping, and monitoring Claude Code sessions.
Uses mock subprocess calls for deterministic testing.
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


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

    monkeypatch.setattr(session, "_get_sessions_dir", lambda: sessions_dir)
    return sessions_dir


@pytest.fixture
def sample_session_data():
    """Return sample session data for testing."""
    return {
        "session_id": "12345678-1234-1234-1234-123456789abc",
        "pid": 12345,
        "prompt": "Fix the bug in main.py",
        "max_turns": 10,
        "status": "running",
        "started_at": "2024-01-15T10:00:00",
        "ended_at": None,
        "background": True,
        "working_dir": "/home/user/project",
        "command": "claude --print --max-turns 10 --prompt 'Fix the bug'",
    }


class TestSessionHelperFunctions:
    """Tests for session module helper functions."""

    def test_get_sessions_dir_creates_directory(self, tmp_path, monkeypatch):
        """Test that _get_sessions_dir creates the directory if it doesn't exist."""
        from agenticcli.commands import session

        new_home = tmp_path / "home"
        new_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: new_home)

        result = session._get_sessions_dir()

        assert result.exists()
        assert result == new_home / ".agentic" / "sessions"

    def test_save_and_load_session(self, mock_sessions_dir, sample_session_data):
        """Test saving and loading a session."""
        from agenticcli.commands import session

        session._save_session(sample_session_data)
        loaded = session._load_session(sample_session_data["session_id"])

        assert loaded is not None
        assert loaded["session_id"] == sample_session_data["session_id"]
        assert loaded["prompt"] == sample_session_data["prompt"]

    def test_load_nonexistent_session(self, mock_sessions_dir):
        """Test loading a session that doesn't exist."""
        from agenticcli.commands import session

        result = session._load_session("nonexistent-id")

        assert result is None

    def test_list_all_sessions(self, mock_sessions_dir, sample_session_data):
        """Test listing all sessions."""
        from agenticcli.commands import session

        # Create multiple sessions
        session._save_session(sample_session_data)

        second_session = sample_session_data.copy()
        second_session["session_id"] = "87654321-4321-4321-4321-cba987654321"
        second_session["prompt"] = "Another task"
        session._save_session(second_session)

        result = session._list_all_sessions()

        assert len(result) == 2
        session_ids = [s["session_id"] for s in result]
        assert sample_session_data["session_id"] in session_ids
        assert second_session["session_id"] in session_ids

    def test_list_all_sessions_skips_invalid_files(self, mock_sessions_dir):
        """Test that list_all_sessions skips invalid JSON files."""
        from agenticcli.commands import session

        # Create an invalid JSON file
        invalid_file = mock_sessions_dir / "invalid.json"
        invalid_file.write_text("not valid json {{{")

        result = session._list_all_sessions()

        assert result == []

    def test_is_process_running_for_current_process(self):
        """Test is_process_running for the current process."""
        from agenticcli.commands import session

        # Current process should be running
        assert session._is_process_running(os.getpid()) is True

    def test_is_process_running_for_nonexistent_process(self):
        """Test is_process_running for a nonexistent process."""
        from agenticcli.commands import session

        # Very high PID unlikely to exist
        assert session._is_process_running(99999999) is False

    def test_update_session_status_marks_completed(self, mock_sessions_dir, sample_session_data):
        """Test that update_session_status marks dead processes as completed."""
        from agenticcli.commands import session

        # Use a nonexistent PID
        sample_session_data["pid"] = 99999999
        sample_session_data["status"] = "running"
        session._save_session(sample_session_data)

        result = session._update_session_status(sample_session_data)

        assert result["status"] == "completed"
        assert result["ended_at"] is not None


class TestSessionSpawnCommand:
    """Tests for the session spawn command."""

    def test_spawn_requires_prompt(self, mock_sessions_dir, capsys):
        """Test that spawn requires a prompt."""
        from agenticcli.commands import session

        args = SimpleNamespace(prompt=None, max_turns=None, background=False, directory=None)

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_spawn(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Prompt is required" in captured.err

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_background_success(self, mock_popen, mock_sessions_dir, capsys):
        """Test successful background spawn."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=5,
            background=True,
            directory=None,
        )

        session.cmd_spawn(args)

        # Verify Popen was called correctly
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "claude" in cmd
        assert "--print" in cmd
        assert "--max-turns" in cmd
        assert "5" in cmd
        assert "--prompt" in cmd
        assert "Test task" in cmd

        # Verify session was saved
        sessions = session._list_all_sessions()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "running"
        assert sessions[0]["pid"] == 12345

    @patch("agenticcli.commands.session.subprocess.run")
    def test_spawn_foreground_success(self, mock_run, mock_sessions_dir, capsys):
        """Test successful foreground spawn."""
        from agenticcli.commands import session

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Task completed successfully",
            stderr="",
        )

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=False,
            directory=None,
        )

        session.cmd_spawn(args)

        # Verify run was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert "claude" in cmd

        # Verify session was saved with completed status
        sessions = session._list_all_sessions()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "completed"

    @patch("agenticcli.commands.session.subprocess.run")
    def test_spawn_foreground_failure(self, mock_run, mock_sessions_dir, capsys):
        """Test foreground spawn with failure."""
        from agenticcli.commands import session

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Command failed",
        )

        args = SimpleNamespace(
            prompt="Failing task",
            max_turns=None,
            background=False,
            directory=None,
        )

        session.cmd_spawn(args)

        sessions = session._list_all_sessions()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "failed"
        assert sessions[0]["exit_code"] == 1

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_claude_not_found(self, mock_popen, mock_sessions_dir, capsys):
        """Test spawn when claude CLI is not found."""
        from agenticcli.commands import session

        mock_popen.side_effect = FileNotFoundError()

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
        )

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_spawn(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Claude CLI not found" in captured.err

    @patch("agenticcli.commands.session.subprocess.Popen")
    @patch("agenticcli.console.is_json_output")
    def test_spawn_json_output(self, mock_json_output, mock_popen, mock_sessions_dir, capsys):
        """Test spawn with JSON output."""
        from agenticcli.commands import session

        mock_json_output.return_value = True
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
        )

        session.cmd_spawn(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["pid"] == 12345
        assert output["status"] == "running"
        assert output["background"] is True


class TestSessionListCommand:
    """Tests for the session list command."""

    def test_list_empty(self, mock_sessions_dir, capsys):
        """Test listing when no sessions exist."""
        from agenticcli.commands import session

        args = SimpleNamespace(active=False)

        session.cmd_list(args)

        captured = capsys.readouterr()
        assert "No sessions found" in captured.out

    def test_list_with_sessions(self, mock_sessions_dir, sample_session_data, capsys):
        """Test listing with existing sessions."""
        from agenticcli.commands import session

        session._save_session(sample_session_data)
        args = SimpleNamespace(active=False)

        session.cmd_list(args)

        captured = capsys.readouterr()
        assert "Claude Code Sessions" in captured.out
        assert sample_session_data["session_id"][:8] in captured.out

    def test_list_active_only(self, mock_sessions_dir, sample_session_data, capsys):
        """Test listing only active sessions."""
        from agenticcli.commands import session

        # Save running session
        session._save_session(sample_session_data)

        # Save completed session
        completed = sample_session_data.copy()
        completed["session_id"] = "completed-session-id"
        completed["status"] = "completed"
        session._save_session(completed)

        args = SimpleNamespace(active=True)

        # Mock is_process_running to return True for the running session
        with patch.object(session, "_is_process_running", return_value=True):
            session.cmd_list(args)

        captured = capsys.readouterr()
        assert sample_session_data["session_id"][:8] in captured.out
        # Completed session should not appear (after status update, non-running filtered)

    @patch("agenticcli.console.is_json_output")
    def test_list_json_output(self, mock_json_output, mock_sessions_dir, sample_session_data, capsys):
        """Test list with JSON output."""
        from agenticcli.commands import session

        mock_json_output.return_value = True
        session._save_session(sample_session_data)

        # Mock is_process_running to return True
        with patch.object(session, "_is_process_running", return_value=True):
            args = SimpleNamespace(active=False)
            session.cmd_list(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "sessions" in output
        assert output["count"] == 1


class TestSessionStopCommand:
    """Tests for the session stop command."""

    def test_stop_requires_session_id(self, mock_sessions_dir, capsys):
        """Test that stop requires a session ID."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_id=None, force=False)

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_stop(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Session ID is required" in captured.err

    def test_stop_session_not_found(self, mock_sessions_dir, capsys):
        """Test stopping a nonexistent session."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_id="nonexistent", force=False)

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_stop(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Session not found" in captured.err

    def test_stop_completed_session(self, mock_sessions_dir, sample_session_data, capsys):
        """Test stopping an already completed session."""
        from agenticcli.commands import session

        sample_session_data["status"] = "completed"
        session._save_session(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_stop(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not running" in captured.err

    @patch("os.kill")
    def test_stop_running_session(self, mock_kill, mock_sessions_dir, sample_session_data, capsys):
        """Test stopping a running session."""
        from agenticcli.commands import session

        session._save_session(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        session.cmd_stop(args)

        # Verify kill was called with SIGTERM
        import signal

        mock_kill.assert_called_once_with(sample_session_data["pid"], signal.SIGTERM)

        # Verify session status was updated
        sessions = session._list_all_sessions()
        assert sessions[0]["status"] == "stopped"

    @patch("os.kill")
    def test_stop_with_force(self, mock_kill, mock_sessions_dir, sample_session_data, capsys):
        """Test stopping a session with force flag."""
        from agenticcli.commands import session

        session._save_session(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=True,
        )

        session.cmd_stop(args)

        # Verify kill was called with SIGKILL
        import signal

        mock_kill.assert_called_once_with(sample_session_data["pid"], signal.SIGKILL)

    @patch("os.kill")
    def test_stop_process_already_exited(self, mock_kill, mock_sessions_dir, sample_session_data, capsys):
        """Test stopping when process has already exited."""
        from agenticcli.commands import session

        mock_kill.side_effect = ProcessLookupError()
        session._save_session(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_stop(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "already exited" in captured.err


class TestSessionStatusCommand:
    """Tests for the session status command."""

    def test_status_requires_session_id(self, mock_sessions_dir, capsys):
        """Test that status requires a session ID."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_id=None)

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_status(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Session ID is required" in captured.err

    def test_status_session_not_found(self, mock_sessions_dir, capsys):
        """Test status for a nonexistent session."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_id="nonexistent")

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_status(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Session not found" in captured.err

    def test_status_displays_session_info(self, mock_sessions_dir, sample_session_data, capsys):
        """Test that status displays session information."""
        from agenticcli.commands import session

        session._save_session(sample_session_data)

        # Mock is_process_running to return True
        with patch.object(session, "_is_process_running", return_value=True):
            args = SimpleNamespace(session_id=sample_session_data["session_id"][:8])
            session.cmd_status(args)

        captured = capsys.readouterr()
        assert "Session " in captured.out
        assert sample_session_data["session_id"][:8] in captured.out
        assert "running" in captured.out.lower()

    @patch("agenticcli.console.is_json_output")
    def test_status_json_output(self, mock_json_output, mock_sessions_dir, sample_session_data, capsys):
        """Test status with JSON output."""
        from agenticcli.commands import session

        mock_json_output.return_value = True
        session._save_session(sample_session_data)

        # Mock is_process_running to return True
        with patch.object(session, "_is_process_running", return_value=True):
            args = SimpleNamespace(session_id=sample_session_data["session_id"][:8])
            session.cmd_status(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["session_id"] == sample_session_data["session_id"]
        assert output["status"] == "running"

    def test_status_partial_id_matching(self, mock_sessions_dir, sample_session_data, capsys):
        """Test that status supports partial ID matching."""
        from agenticcli.commands import session

        session._save_session(sample_session_data)

        # Use only first 4 characters of session ID
        with patch.object(session, "_is_process_running", return_value=True):
            args = SimpleNamespace(session_id=sample_session_data["session_id"][:4])
            session.cmd_status(args)

        captured = capsys.readouterr()
        assert "Session " in captured.out


class TestSessionHandleRouting:
    """Tests for the session handle function routing."""

    def test_handle_routes_to_spawn(self, mock_sessions_dir):
        """Test that handle routes spawn command correctly."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_command="spawn", prompt=None)

        with pytest.raises(SystemExit):
            session.handle(args)

    def test_handle_routes_to_list(self, mock_sessions_dir, capsys):
        """Test that handle routes list command correctly."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_command="list", active=False)

        session.handle(args)

        captured = capsys.readouterr()
        assert "No sessions found" in captured.out

    def test_handle_routes_to_stop(self, mock_sessions_dir):
        """Test that handle routes stop command correctly."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_command="stop", session_id=None)

        with pytest.raises(SystemExit):
            session.handle(args)

    def test_handle_routes_to_status(self, mock_sessions_dir):
        """Test that handle routes status command correctly."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_command="status", session_id=None)

        with pytest.raises(SystemExit):
            session.handle(args)

    def test_handle_invalid_command(self, mock_sessions_dir, capsys):
        """Test that handle exits with error for invalid command."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_command="invalid")

        with pytest.raises(SystemExit) as exc_info:
            session.handle(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Usage:" in captured.err
