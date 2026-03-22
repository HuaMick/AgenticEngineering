"""Tests for session management CLI commands.

Tests for spawning, listing, stopping, and monitoring Claude Code sessions.
Uses mock subprocess calls for deterministic testing.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-SES-001", "US-SES-010", "US-SES-011")


@pytest.fixture
def sessions_dir(tmp_path):
    """Create a temporary sessions directory."""
    sessions_dir = tmp_path / ".agentic" / "sessions"
    sessions_dir.mkdir(parents=True)
    return sessions_dir


@pytest.fixture
def logs_dir(sessions_dir):
    """Create a temporary logs directory inside sessions dir."""
    ld = sessions_dir / "logs"
    ld.mkdir(parents=True)
    return ld


@pytest.fixture
def mock_sessions_dir(sessions_dir, monkeypatch):
    """Patch StateStore and _get_context_dir to use temp directories."""
    from agenticcli.commands import session
    from agenticcli.utils.state_store import StateStore

    def _patched_get_dir(self, override=None):
        if self._subdir == "sessions":
            return sessions_dir
        else:
            d = sessions_dir.parent / self._subdir
            d.mkdir(parents=True, exist_ok=True)
            return d

    # Patch the StateStore class method to use temp directory for ALL stores
    monkeypatch.setattr(StateStore, "get_dir", _patched_get_dir)

    # Also remove any instance-level get_dir attribute that may have been left
    # behind by a previous test's monkeypatch restore (monkeypatch sets the
    # original bound method as an instance attribute, which shadows the class patch)
    if "get_dir" in session._store.__dict__:
        del session._store.__dict__["get_dir"]

    context_dir = sessions_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(session, "get_context_dir", lambda: context_dir)

    # Disable SDK path so subprocess-based tests exercise the subprocess code path.
    # SDK-specific tests should re-enable this explicitly.
    import agenticcli.utils.sdk_runner as _sdk_mod
    monkeypatch.setattr(_sdk_mod, "SDK_AVAILABLE", False)
    return sessions_dir


@pytest.fixture
def mock_logs_dir(logs_dir, monkeypatch):
    """Patch _get_logs_dir to use temp directory."""
    from agenticcli.commands import session

    monkeypatch.setattr(session, "_get_logs_dir", lambda: logs_dir)
    return logs_dir


@pytest.fixture
def context_dir(sessions_dir):
    """Create a temporary context directory inside sessions dir."""
    cd = sessions_dir / "context"
    cd.mkdir(parents=True)
    return cd


@pytest.fixture
def mock_context_dir(context_dir, monkeypatch):
    """Patch _get_context_dir to use temp directory."""
    from agenticcli.commands import session

    monkeypatch.setattr(session, "get_context_dir", lambda: context_dir)
    return context_dir


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


@pytest.mark.story("US-SES-001")
class TestSessionHelperFunctions:
    """Tests for session module helper functions."""

    def test_get_sessions_dir_creates_directory(self, tmp_path, monkeypatch):
        """Test that StateStore.get_dir creates the directory if it doesn't exist."""
        from agenticcli.commands import session

        new_home = tmp_path / "home"
        new_home.mkdir()
        monkeypatch.setattr(Path, "home", lambda: new_home)

        result = session._store.get_dir()

        assert result.exists()
        assert result == new_home / ".agentic" / "sessions"

    def test_save_and_load_session(self, mock_sessions_dir, sample_session_data):
        """Test saving and loading a session."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        loaded = session._store.load(sample_session_data["session_id"])

        assert loaded is not None
        assert loaded["session_id"] == sample_session_data["session_id"]
        assert loaded["prompt"] == sample_session_data["prompt"]

    def test_load_nonexistent_session(self, mock_sessions_dir):
        """Test loading a session that doesn't exist."""
        from agenticcli.commands import session

        result = session._store.load("nonexistent-id")

        assert result is None

    def test_list_all_sessions(self, mock_sessions_dir, sample_session_data):
        """Test listing all sessions."""
        from agenticcli.commands import session

        # Create multiple sessions
        session._store.save(sample_session_data)

        second_session = sample_session_data.copy()
        second_session["session_id"] = "87654321-4321-4321-4321-cba987654321"
        second_session["prompt"] = "Another task"
        session._store.save(second_session)

        result = session._store.list_all()

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

        result = session._store.list_all()

        assert result == []

    @pytest.mark.story("US-SES-008")
    def test_is_process_running_for_current_process(self):
        """Test is_process_running for the current process."""
        from agenticcli.commands import session

        # Current process should be running
        assert session.is_process_running(os.getpid()) is True

    @pytest.mark.story("US-SES-008")
    def test_is_process_running_for_nonexistent_process(self):
        """Test is_process_running for a nonexistent process."""
        from agenticcli.commands import session

        # Very high PID unlikely to exist
        assert session.is_process_running(99999999) is False

    @pytest.mark.story("US-SES-008", "US-SES-009")
    def test_update_session_status_marks_completed(self, mock_sessions_dir, sample_session_data):
        """Test that update_session_status marks dead processes as completed."""
        from agenticcli.commands import session

        # Use a nonexistent PID
        sample_session_data["pid"] = 99999999
        sample_session_data["status"] = "running"
        session._store.save(sample_session_data)

        result = session._update_session_status(sample_session_data)

        assert result["status"] == "completed"
        assert result["ended_at"] is not None


@pytest.mark.story("US-SES-001")
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

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_background_success(self, mock_popen, mock_is_running, mock_sessions_dir, capsys):
        """Test successful background spawn."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        mock_is_running.return_value = True

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
        assert "-p" in cmd
        assert "--max-turns" in cmd
        assert "5" in cmd
        # Prompt is now a short reference to a context file
        assert "pre-compiled" in cmd[-1]

        # Verify session was saved with original prompt
        sessions = session._store.list_all()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "running"
        assert sessions[0]["prompt"] == "Test task"
        assert sessions[0]["pid"] == 12345
        assert sessions[0].get("last_activity") is not None

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_foreground_success(self, mock_popen, mock_sessions_dir, capsys):
        """Test successful foreground spawn."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("Task completed successfully", "")
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=False,
            directory=None,
        )

        session.cmd_spawn(args)

        # Verify Popen was called
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert "claude" in cmd

        # Verify session was saved with completed status
        sessions = session._store.list_all()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "completed"

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_foreground_failure(self, mock_popen, mock_sessions_dir, capsys):
        """Test foreground spawn with failure."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = ("", "Command failed")
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Failing task",
            max_turns=None,
            background=False,
            directory=None,
        )

        session.cmd_spawn(args)

        sessions = session._store.list_all()
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

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    @patch("agenticcli.console.is_json_output")
    def test_spawn_json_output(self, mock_json_output, mock_popen, mock_is_running, mock_sessions_dir, capsys):
        """Test spawn with JSON output."""
        from agenticcli.commands import session

        mock_json_output.return_value = True
        mock_is_running.return_value = True
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


@pytest.mark.story("US-SES-002")
class TestSessionListCommand:
    """Tests for the session list command."""

    def test_list_empty(self, mock_sessions_dir, capsys):
        """Test listing when no sessions exist."""
        from agenticcli.commands import session

        args = SimpleNamespace(show_all=False)

        session.cmd_list(args)

        captured = capsys.readouterr()
        assert "No active sessions" in captured.out

    def test_list_empty_with_all(self, mock_sessions_dir, capsys):
        """Test listing with --all when no sessions exist."""
        from agenticcli.commands import session

        args = SimpleNamespace(show_all=True)

        session.cmd_list(args)

        captured = capsys.readouterr()
        assert "No sessions found" in captured.out

    def test_list_default_shows_running_only(self, mock_sessions_dir, sample_session_data, capsys):
        """Test that default (show_all=False) shows only running sessions."""
        from agenticcli.commands import session

        # Save running session
        session._store.save(sample_session_data)

        # Save completed session
        completed = sample_session_data.copy()
        completed["session_id"] = "completed-session-id-1234-123456789abc"
        completed["status"] = "completed"
        session._store.save(completed)

        args = SimpleNamespace(show_all=False)

        # Mock is_process_running to return True for the running session
        with patch.object(session, "is_process_running", return_value=True):
            session.cmd_list(args)

        captured = capsys.readouterr()
        assert sample_session_data["session_id"][:8] in captured.out
        # Completed session should not appear in default view
        assert "complete" not in captured.out.split("Sessions")[1].split("Showing")[0].lower() or "completed" not in captured.out.split("ID")[1].split("Showing")[0]

    def test_list_all_shows_everything(self, mock_sessions_dir, sample_session_data, capsys):
        """Test that --all shows all sessions including completed."""
        from agenticcli.commands import session

        # Save running session
        session._store.save(sample_session_data)

        # Save completed session
        completed = sample_session_data.copy()
        completed["session_id"] = "completed-session-id-1234-123456789abc"
        completed["status"] = "completed"
        session._store.save(completed)

        args = SimpleNamespace(show_all=True)

        with patch.object(session, "is_process_running", return_value=True):
            session.cmd_list(args)

        captured = capsys.readouterr()
        assert sample_session_data["session_id"][:8] in captured.out
        assert "complete" in captured.out.lower()

    def test_list_no_active_shows_hint(self, mock_sessions_dir, sample_session_data, capsys):
        """Test that when no active sessions exist, a hint about --all is shown."""
        from agenticcli.commands import session

        # Only save completed sessions
        completed = sample_session_data.copy()
        completed["status"] = "completed"
        session._store.save(completed)

        args = SimpleNamespace(show_all=False)

        session.cmd_list(args)

        captured = capsys.readouterr()
        assert "No active sessions" in captured.out
        assert "--all" in captured.out

    @patch("agenticcli.console.is_json_output")
    def test_list_json_output_default(self, mock_json_output, mock_sessions_dir, sample_session_data, capsys):
        """Test list JSON output with default filtering."""
        from agenticcli.commands import session

        mock_json_output.return_value = True
        session._store.save(sample_session_data)

        # Mock is_process_running to return True
        with patch.object(session, "is_process_running", return_value=True):
            args = SimpleNamespace(show_all=False)
            session.cmd_list(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "sessions" in output
        assert output["count"] == 1
        assert output["filtered"] is True
        assert output["total"] == 1

    @patch("agenticcli.console.is_json_output")
    def test_list_json_output_all(self, mock_json_output, mock_sessions_dir, sample_session_data, capsys):
        """Test list JSON output with --all flag."""
        from agenticcli.commands import session

        mock_json_output.return_value = True

        # Save running session
        session._store.save(sample_session_data)

        # Save completed session
        completed = sample_session_data.copy()
        completed["session_id"] = "completed-session-id-1234-123456789abc"
        completed["status"] = "completed"
        session._store.save(completed)

        with patch.object(session, "is_process_running", return_value=True):
            args = SimpleNamespace(show_all=True)
            session.cmd_list(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["count"] == 2
        assert output["total"] == 2
        assert output["filtered"] is False

    def test_list_shows_transport_column(self, mock_sessions_dir, sample_session_data, capsys):
        """Test that Transport column header and SDK+Tmux label appear when sessions have transport."""
        from agenticcli.commands import session

        sample_session_data["transport"] = "sdk-tmux"
        session._store.save(sample_session_data)

        with patch.object(session, "is_process_running", return_value=True):
            args = SimpleNamespace(show_all=False)
            session.cmd_list(args)

        captured = capsys.readouterr()
        assert "Transport" in captured.out
        assert "SDK+Tmux" in captured.out

    def test_list_transport_labels(self, mock_sessions_dir, sample_session_data, capsys):
        """Test all transport label mappings: sdk-tmux->SDK+Tmux, tmux->Tmux, subprocess->Proc, sdk->SDK."""
        from agenticcli.commands import session

        label_map = {
            "sdk-tmux": "SDK+Tmux",
            "tmux": "Tmux",
            "subprocess": "Proc",
            "sdk": "SDK",
        }

        base_id = "aaaaaaaa-0000-0000-0000-"
        for idx, (transport_value, _) in enumerate(label_map.items()):
            data = sample_session_data.copy()
            data["session_id"] = f"{base_id}{str(idx).zfill(12)}"
            data["transport"] = transport_value
            # Mark as completed so all appear under --all without process checks
            data["status"] = "completed"
            session._store.save(data)

        args = SimpleNamespace(show_all=True)
        session.cmd_list(args)

        captured = capsys.readouterr()
        for transport_value, expected_label in label_map.items():
            assert expected_label in captured.out, (
                f"Expected label '{expected_label}' for transport '{transport_value}' "
                f"not found in output:\n{captured.out}"
            )

    def test_list_no_transport_column_when_empty(self, mock_sessions_dir, sample_session_data, capsys):
        """Test that Transport column is absent when no sessions have a transport field."""
        from agenticcli.commands import session

        # Ensure no transport field in session data
        data = sample_session_data.copy()
        data.pop("transport", None)
        session._store.save(data)

        with patch.object(session, "is_process_running", return_value=True):
            args = SimpleNamespace(show_all=False)
            session.cmd_list(args)

        captured = capsys.readouterr()
        assert "Transport" not in captured.out

    @patch("agenticcli.console.is_json_output")
    def test_list_json_includes_transport(self, mock_json_output, mock_sessions_dir, sample_session_data, capsys):
        """Test that JSON list output includes the transport field."""
        from agenticcli.commands import session

        mock_json_output.return_value = True
        sample_session_data["transport"] = "sdk-tmux"
        session._store.save(sample_session_data)

        with patch.object(session, "is_process_running", return_value=True):
            args = SimpleNamespace(show_all=False)
            session.cmd_list(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["count"] == 1
        sessions_list = output["sessions"]
        assert len(sessions_list) == 1
        assert sessions_list[0].get("transport") == "sdk-tmux"


@pytest.mark.story("US-SES-003")
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
        session._store.save(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        # Should succeed without raising SystemExit
        session.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already in terminal state" in captured.out

    @patch("os.kill")
    def test_stop_running_session(self, mock_kill, mock_sessions_dir, sample_session_data, capsys):
        """Test stopping a running session."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        session.cmd_stop(args)

        # Verify kill was called with SIGTERM
        import signal

        mock_kill.assert_called_once_with(sample_session_data["pid"], signal.SIGTERM)

        # Verify session status was updated
        sessions = session._store.list_all()
        assert sessions[0]["status"] == "stopped"

    @patch("os.kill")
    def test_stop_with_force(self, mock_kill, mock_sessions_dir, sample_session_data, capsys):
        """Test stopping a session with force flag."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)

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
        session._store.save(sample_session_data)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        # Should succeed without raising SystemExit
        session.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already exited" in captured.out


@pytest.mark.story("US-SES-001")
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

        args = SimpleNamespace(session_command="list", show_all=False)

        session.handle(args)

        captured = capsys.readouterr()
        assert "No active sessions" in captured.out

    def test_handle_routes_to_stop(self, mock_sessions_dir):
        """Test that handle routes stop command correctly."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_command="stop", session_id=None)

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


@pytest.mark.story("US-SES-001")
class TestResolvePlanFolder:
    """Tests for _resolve_epic_folder helper."""

    def test_resolve_existing_plan(self, tmp_path, monkeypatch):
        """Test resolving an existing epic folder via TinyDB."""
        from agenticcli.commands import session

        live_dir = tmp_path / "docs" / "epics" / "live"
        plan_dir = live_dir / "260207TA_cli_task_spawn"
        plan_dir.mkdir(parents=True)

        # Mock find_epic_folder to return the expected path (TinyDB-based)
        monkeypatch.setattr(
            "agenticcli.commands.epic.find_epic_folder",
            lambda name: plan_dir,
        )

        result = session._resolve_epic_folder("260207TA_cli_task_spawn")
        assert result == plan_dir

    def test_resolve_completed_plan(self, tmp_path, monkeypatch):
        """Test resolving a completed epic folder via TinyDB."""
        from agenticcli.commands import session

        completed_dir = tmp_path / "docs" / "epics" / "completed"
        plan_dir = completed_dir / "260203TS_task_service"
        plan_dir.mkdir(parents=True)

        # Mock find_epic_folder to return the expected path (TinyDB-based)
        monkeypatch.setattr(
            "agenticcli.commands.epic.find_epic_folder",
            lambda name: plan_dir,
        )

        result = session._resolve_epic_folder("260203TS_task_service")
        assert result == plan_dir

    def test_resolve_nonexistent_plan(self, tmp_path, monkeypatch):
        """Test resolving an epic folder that doesn't exist."""
        from agenticcli.commands import session

        # find_epic_folder raises SystemExit for not-found (via sys.exit(1))
        import sys

        def raise_exit(name):
            raise SystemExit(1)

        monkeypatch.setattr(
            "agenticcli.commands.epic.find_epic_folder",
            raise_exit,
        )

        result = session._resolve_epic_folder("nonexistent_plan")
        assert result is None


@pytest.mark.story("US-SES-001")
class TestBuildRolePrompt:
    """Tests for _build_role_prompt helper."""

    def test_role_prompt_without_plan(self):
        """Test building a role prompt without plan context."""
        from agenticcli.commands import session

        prompt = session._build_role_prompt("build-python", None)
        assert "build-python" in prompt
        assert "epic list" in prompt

    def test_role_prompt_with_plan(self, tmp_path):
        """Test building a role prompt with plan context."""
        from agenticcli.commands import session

        plan_folder = tmp_path / "260207TA_cli_task_spawn"
        plan_folder.mkdir()

        prompt = session._build_role_prompt("build-python", plan_folder)
        assert "build-python" in prompt
        assert "260207TA_cli_task_spawn" in prompt
        assert "epic ticket list" in prompt


@pytest.mark.story("US-SES-001")
class TestBuildTaskPrompt:
    """Tests for _build_task_prompt helper."""

    def test_task_prompt_with_valid_task(self, tmp_path):
        """Test building a task prompt from TinyDB ticket data."""
        from agenticcli.commands import session
        from agenticguidance.services.epic_repository import EpicRepository

        plan_folder = tmp_path / "260207TA_test"
        plan_folder.mkdir()

        # Create .git so TicketService can find repo root at tmp_path
        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Populate TinyDB with the ticket (TicketService reads from TinyDB only)
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": "260207TA_test",
            "epic_folder": str(plan_folder),
            "name": "260207TA_test",
            "status": "active",
        })
        repo.add_phase("260207TA_test", {"name": "Test Phase"})
        repo.add_ticket("260207TA_test", "Test Phase", {
            "task_id": "CLI_001",
            "name": "Add --task argument",
            "status": "pending",
            "description": "Add the --task argument to session spawn.",
            "target_files": ["modules/AgenticCLI/src/agenticcli/commands/session.py"],
            "inputs": ["modules/AgenticCLI/src/agenticcli/commands/plan.py"],
            "guidance": "Follow existing patterns.",
        })
        repo.close()

        prompt = session._build_task_prompt("CLI_001", plan_folder)
        assert prompt is not None
        assert "CLI_001" in prompt
        assert "Add --task argument" in prompt
        assert "session.py" in prompt
        assert "agentic epic ticket complete" in prompt

    def test_task_prompt_with_invalid_task(self, tmp_path):
        """Test building a task prompt for a nonexistent task."""
        from agenticcli.commands import session

        plan_folder = tmp_path / "260207TA_test"
        plan_folder.mkdir()
        # No TinyDB entry - _build_task_prompt reads from TinyDB, returns None for unknown ticket

        prompt = session._build_task_prompt("NONEXISTENT", plan_folder)
        assert prompt is None


@pytest.mark.story("US-SES-001")
class TestSpawnWithRoleAndPlan:
    """Tests for spawn with --role and --plan flags."""

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_with_role(self, mock_popen, mock_is_running, mock_sessions_dir, tmp_path, monkeypatch, capsys):
        """Test spawn with --role constructs prompt and spawns agent."""
        from agenticcli.commands import session

        # Set up epic folder
        live_dir = tmp_path / "docs" / "epics" / "live"
        plan_dir = live_dir / "260207TA_test"
        plan_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
        # Mock find_epic_folder since filesystem fallback was removed
        monkeypatch.setattr("agenticcli.commands.epic.find_epic_folder", lambda name: plan_dir)

        mock_is_running.return_value = True
        mock_process = MagicMock()
        mock_process.pid = 99999
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt=None,
            role="build-python",
            task=None,
            plan="260207TA_test",
            max_turns=None,
            background=True,
            directory=None,
            dangerously_skip_permissions=False,
        )

        session.cmd_spawn(args)

        # Verify Popen was called with the claude command
        # (may also be called for git rev-parse during context compilation,
        #  and for auto-started question watch-daemon)
        assert mock_popen.call_count >= 1
        # Find the claude spawn call among all Popen calls
        claude_calls = [
            call[0][0] for call in mock_popen.call_args_list
            if call[0] and call[0][0] and call[0][0][0] == "claude"
        ]
        assert len(claude_calls) >= 1, "Expected at least one claude Popen call"
        cmd = claude_calls[0]
        assert cmd[0] == "claude"
        assert "pre-compiled" in cmd[-1]

        # Verify the context file contains the role
        sessions = session._store.list_all()
        assert len(sessions) == 1
        context_file = Path(sessions[0]["compiled_context"])
        assert context_file.exists()
        context_content = context_file.read_text()
        assert "build-python" in context_content

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_with_task(self, mock_popen, mock_is_running, mock_sessions_dir, tmp_path, monkeypatch, capsys):
        """Test spawn with --task loads task context from TinyDB and spawns agent."""
        from agenticcli.commands import session
        from agenticguidance.services.epic_repository import EpicRepository

        # Set up epic folder with task
        live_dir = tmp_path / "docs" / "epics" / "live"
        plan_dir = live_dir / "260207TA_test"
        plan_dir.mkdir(parents=True)

        # Create .git so TicketService can find repo root at tmp_path
        (tmp_path / ".git").mkdir(exist_ok=True)
        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Populate TinyDB (TicketService reads from TinyDB only)
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": "260207TA_test",
            "epic_folder": str(plan_dir),
            "name": "260207TA_test",
            "status": "active",
        })
        repo.add_phase("260207TA_test", {"name": "Build Phase"})
        repo.add_ticket("260207TA_test", "Build Phase", {
            "task_id": "CLI_001",
            "name": "Add feature",
            "status": "pending",
            "description": "Add a new feature.",
            "target_files": ["src/main.py"],
        })
        repo.close()

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        mock_is_running.return_value = True
        mock_process = MagicMock()
        mock_process.pid = 88888
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt=None,
            role=None,
            task="CLI_001",
            plan="260207TA_test",
            max_turns=None,
            background=True,
            directory=None,
            dangerously_skip_permissions=False,
        )

        session.cmd_spawn(args)

        # Popen may be called multiple times (claude spawn + question watch-daemon)
        assert mock_popen.call_count >= 1
        # Find the claude spawn call among all Popen calls
        claude_calls = [
            call[0][0] for call in mock_popen.call_args_list
            if call[0] and call[0][0] and call[0][0][0] == "claude"
        ]
        assert len(claude_calls) >= 1, "Expected at least one claude Popen call"
        cmd = claude_calls[0]
        assert "pre-compiled" in cmd[-1]

        # Verify the context file contains task details
        sessions = session._store.list_all()
        assert len(sessions) == 1
        context_file = Path(sessions[0]["compiled_context"])
        context_content = context_file.read_text()
        assert "CLI_001" in context_content
        assert "Add feature" in context_content

    def test_spawn_task_requires_epic(self, mock_sessions_dir, capsys):
        """Test that --task without --epic fails."""
        from agenticcli.commands import session

        args = SimpleNamespace(
            prompt=None,
            role=None,
            task="CLI_001",
            plan=None,
            max_turns=None,
            background=False,
            directory=None,
            dangerously_skip_permissions=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_spawn(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "--task requires --epic" in captured.err

    def test_spawn_invalid_plan(self, mock_sessions_dir, tmp_path, monkeypatch, capsys):
        """Test that spawn with nonexistent plan fails."""
        from agenticcli.commands import session

        (tmp_path / "docs" / "epics" / "live").mkdir(parents=True)
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        args = SimpleNamespace(
            prompt=None,
            role="build-python",
            task=None,
            plan="nonexistent_plan",
            max_turns=None,
            background=False,
            directory=None,
            dangerously_skip_permissions=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_spawn(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Epic folder not found" in captured.err

    def test_spawn_invalid_task_id(self, mock_sessions_dir, tmp_path, monkeypatch, capsys):
        """Test that spawn with invalid task ID fails gracefully."""
        from agenticcli.commands import session

        live_dir = tmp_path / "docs" / "epics" / "live"
        plan_dir = live_dir / "260207TA_test"
        plan_dir.mkdir(parents=True)

        # Mock find_epic_folder since filesystem fallback was removed
        monkeypatch.setattr("agenticcli.commands.epic.find_epic_folder", lambda name: plan_dir)
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        args = SimpleNamespace(
            prompt=None,
            role=None,
            task="NONEXISTENT",
            plan="260207TA_test",
            max_turns=None,
            background=False,
            directory=None,
            dangerously_skip_permissions=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_spawn(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Ticket not found" in captured.err

    def test_spawn_no_prompt_no_role_no_task(self, mock_sessions_dir, capsys):
        """Test that spawn without any prompt source fails."""
        from agenticcli.commands import session

        args = SimpleNamespace(
            prompt=None,
            role=None,
            task=None,
            plan=None,
            max_turns=None,
            background=False,
            directory=None,
            dangerously_skip_permissions=False,
        )

        with pytest.raises(SystemExit) as exc_info:
            session.cmd_spawn(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Prompt is required" in captured.err

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_prompt_still_works_standalone(self, mock_popen, mock_is_running, mock_sessions_dir, capsys):
        """Test that --prompt still works without --role or --task."""
        from agenticcli.commands import session

        mock_is_running.return_value = True
        mock_process = MagicMock()
        mock_process.pid = 77777
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Hello world",
            role=None,
            task=None,
            plan=None,
            max_turns=None,
            background=True,
            directory=None,
            dangerously_skip_permissions=False,
        )

        session.cmd_spawn(args)

        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        # Command now contains a short file reference, not the raw prompt
        assert "pre-compiled" in cmd[-1]

        # Verify the context file contains the original prompt
        sessions = session._store.list_all()
        assert len(sessions) == 1
        context_file = Path(sessions[0]["compiled_context"])
        assert "Hello world" in context_file.read_text()


@pytest.mark.story("US-SES-004")
class TestCheckSessionHealth:
    """Tests for _check_session_health helper function."""

    def test_healthy_session(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch):
        """Test health check for a healthy running session."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)

        # Create non-empty log files with recent mtime
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stderr_log = mock_logs_dir / f"{sample_session_data['session_id']}.stderr.log"
        stdout_log.write_text("Some output here")
        stderr_log.write_text("")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        health = session._check_session_health(sample_session_data)

        assert health["healthy"] is True
        assert health["stale"] is False

        # Check signals
        signal_names = [s["name"] for s in health["signals"]]
        assert "pid_alive" in signal_names
        assert "has_output" in signal_names
        assert "recent_activity" in signal_names

        pid_signal = next(s for s in health["signals"] if s["name"] == "pid_alive")
        assert pid_signal["ok"] is True

        output_signal = next(s for s in health["signals"] if s["name"] == "has_output")
        assert output_signal["ok"] is True

    def test_stale_session(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch):
        """Test health check for a stale session (log mtime > 10m)."""
        import time as time_mod
        from agenticcli.commands import session

        session._store.save(sample_session_data)

        # Create log files with old mtime (20 minutes ago)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("Old output")
        old_time = time_mod.time() - (20 * 60)  # 20 minutes ago
        os.utime(stdout_log, (old_time, old_time))

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        health = session._check_session_health(sample_session_data)

        assert health["stale"] is True
        assert health["stale_minutes"] >= 10

    @pytest.mark.story("US-SES-008")
    def test_dead_pid(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch):
        """Test health check for a session with dead PID."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)

        monkeypatch.setattr(session, "is_process_running", lambda pid: False)

        health = session._check_session_health(sample_session_data)

        assert health["healthy"] is False
        pid_signal = next(s for s in health["signals"] if s["name"] == "pid_alive")
        assert pid_signal["ok"] is False

    def test_empty_logs(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch):
        """Test health check for session with empty log files."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)

        # Create empty log files
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stderr_log = mock_logs_dir / f"{sample_session_data['session_id']}.stderr.log"
        stdout_log.write_text("")
        stderr_log.write_text("")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        health = session._check_session_health(sample_session_data)

        output_signal = next(s for s in health["signals"] if s["name"] == "has_output")
        assert output_signal["ok"] is False

    def test_missing_log_files(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch):
        """Test health check with no log files."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        health = session._check_session_health(sample_session_data)

        output_signal = next(s for s in health["signals"] if s["name"] == "has_output")
        assert output_signal["ok"] is False

    def test_completed_session_not_stale(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch):
        """Test that completed sessions are not marked as stale."""
        from agenticcli.commands import session

        sample_session_data["status"] = "completed"
        session._store.save(sample_session_data)
        monkeypatch.setattr(session, "is_process_running", lambda pid: False)

        health = session._check_session_health(sample_session_data)

        assert health["stale"] is False


@pytest.mark.story("US-SES-004")
class TestSessionHealthcheckCommand:
    """Tests for cmd_healthcheck command."""

    def test_healthcheck_healthy_session(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys):
        """Test healthcheck command displays HEALTHY verdict."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("Some output")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8])
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert "HEALTHY" in captured.out

    def test_healthcheck_stale_session_no_diagnose(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys):
        """Test healthcheck displays STALE verdict without spawning diagnostic when --diagnose is not set."""
        import time as time_mod
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("Old output")
        old_time = time_mod.time() - (20 * 60)
        os.utime(stdout_log, (old_time, old_time))

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8])
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert "STALE" in captured.out

    def test_healthcheck_unhealthy_session(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys):
        """Test healthcheck command displays UNHEALTHY verdict."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        monkeypatch.setattr(session, "is_process_running", lambda pid: False)

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8])
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert "UNHEALTHY" in captured.out

    @patch("agenticcli.console.is_json_output")
    def test_healthcheck_json_output(self, mock_json, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys):
        """Test healthcheck command with JSON output."""
        from agenticcli.commands import session

        mock_json.return_value = True
        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("output")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8], json_output=True)
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "session_id" in output
        assert "healthy" in output
        assert "signals" in output
        assert "stale" in output

    def test_healthcheck_partial_id(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys):
        """Test healthcheck command with partial ID matching."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("output")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:4])
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert "Session Health" in captured.out

    def test_healthcheck_no_match(self, mock_sessions_dir, mock_logs_dir, capsys):
        """Test healthcheck command with non-existent session."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_id="nonexistent")
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert "No session found" in captured.err


@pytest.mark.story("US-SES-004")
class TestSessionLogsCommand:
    """Tests for cmd_logs command."""

    def test_logs_shows_stdout(self, mock_sessions_dir, mock_logs_dir, sample_session_data, capsys):
        """Test logs command shows stdout content."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("line1\nline2\nline3\n")

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            stderr=False, lines=50, follow=False,
        )
        session.cmd_logs(args)

        captured = capsys.readouterr()
        assert "line1" in captured.out
        assert "line2" in captured.out
        assert "line3" in captured.out

    def test_logs_shows_stderr(self, mock_sessions_dir, mock_logs_dir, sample_session_data, capsys):
        """Test logs command with --stderr shows stderr content."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stderr_log = mock_logs_dir / f"{sample_session_data['session_id']}.stderr.log"
        stderr_log.write_text("error output\nmore errors\n")

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            stderr=True, lines=50, follow=False,
        )
        session.cmd_logs(args)

        captured = capsys.readouterr()
        assert "error output" in captured.out
        assert "more errors" in captured.out

    def test_logs_line_limit(self, mock_sessions_dir, mock_logs_dir, sample_session_data, capsys):
        """Test logs command respects line limit."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        lines_content = "\n".join(f"line{i}" for i in range(100))
        stdout_log.write_text(lines_content)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            stderr=False, lines=10, follow=False,
        )
        session.cmd_logs(args)

        captured = capsys.readouterr()
        assert "showing last 10 of 100 lines" in captured.out
        # Should show last 10 lines
        assert "line99" in captured.out
        assert "line90" in captured.out
        # Should NOT show early lines
        assert "line0\n" not in captured.out

    def test_logs_empty_file(self, mock_sessions_dir, mock_logs_dir, sample_session_data, capsys):
        """Test logs command with empty log file."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("")

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            stderr=False, lines=50, follow=False,
        )
        session.cmd_logs(args)

        captured = capsys.readouterr()
        assert "empty (0 bytes)" in captured.out

    def test_logs_missing_file(self, mock_sessions_dir, mock_logs_dir, sample_session_data, capsys):
        """Test logs command with missing log file."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        # Don't create any log files

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            stderr=False, lines=50, follow=False,
        )
        session.cmd_logs(args)

        captured = capsys.readouterr()
        assert "No stdout log file found" in captured.out

    def test_logs_no_session(self, mock_sessions_dir, mock_logs_dir, capsys):
        """Test logs command with non-existent session."""
        from agenticcli.commands import session

        args = SimpleNamespace(
            session_id="nonexistent",
            stderr=False, lines=50, follow=False,
        )
        session.cmd_logs(args)

        captured = capsys.readouterr()
        assert "No session found" in captured.err


@pytest.mark.story("US-SES-002")
class TestStaleWarningInList:
    """Tests for stale warning integration in session list."""

    def test_list_shows_stale_warning(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys):
        """Test that session list shows stale warning for stuck sessions."""
        import time as time_mod
        from agenticcli.commands import session

        session._store.save(sample_session_data)

        # Create log with old mtime
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("old output")
        old_time = time_mod.time() - (30 * 60)  # 30 minutes ago
        os.utime(stdout_log, (old_time, old_time))

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        args = SimpleNamespace(show_all=False)
        session.cmd_list(args)

        captured = capsys.readouterr()
        assert "STALE" in captured.out
        assert "appear stale" in captured.out

    def test_list_healthy_no_warning(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys):
        """Test that session list shows no stale warning for healthy sessions."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)

        # Create log with recent mtime (just created = fresh)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("fresh output")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        args = SimpleNamespace(show_all=False)
        session.cmd_list(args)

        captured = capsys.readouterr()
        assert "appear stale" not in captured.out

    @patch("agenticcli.console.is_json_output")
    def test_list_json_includes_health(self, mock_json, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys):
        """Test that JSON list output includes health data for running sessions."""
        from agenticcli.commands import session

        mock_json.return_value = True
        session._store.save(sample_session_data)

        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("output")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        args = SimpleNamespace(show_all=False)
        session.cmd_list(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert len(output["sessions"]) == 1
        assert "health" in output["sessions"][0]
        assert "healthy" in output["sessions"][0]["health"]

    def test_list_completed_no_health(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys):
        """Test that completed sessions don't get health checks."""
        from agenticcli.commands import session

        sample_session_data["status"] = "completed"
        session._store.save(sample_session_data)

        args = SimpleNamespace(show_all=True)
        session.cmd_list(args)

        captured = capsys.readouterr()
        # Completed sessions should show "-" in health column
        assert "-" in captured.out


@pytest.mark.story("US-SES-001")
class TestCheckTmuxSession:
    """Tests for _check_tmux_session helper."""

    def test_tmux_session_exists(self, monkeypatch):
        """Test _check_tmux_session returns True when tmux session exists."""
        from agenticcli.commands import session

        mock_result = MagicMock()
        mock_result.returncode = 0
        monkeypatch.setattr(session.subprocess, "run", lambda *args, **kwargs: mock_result)

        result = session._check_tmux_session("test-session")
        assert result is True

    def test_tmux_session_missing(self, monkeypatch):
        """Test _check_tmux_session returns False when tmux session doesn't exist."""
        from agenticcli.commands import session

        mock_result = MagicMock()
        mock_result.returncode = 1
        monkeypatch.setattr(session.subprocess, "run", lambda *args, **kwargs: mock_result)

        result = session._check_tmux_session("nonexistent")
        assert result is False

    def test_tmux_not_installed(self, monkeypatch):
        """Test _check_tmux_session returns None when tmux is not installed."""
        from agenticcli.commands import session

        def raise_fnf(*args, **kwargs):
            raise FileNotFoundError("tmux not found")

        monkeypatch.setattr(session.subprocess, "run", raise_fnf)

        result = session._check_tmux_session("test-session")
        assert result is None

    def test_tmux_timeout(self, monkeypatch):
        """Test _check_tmux_session returns None on timeout."""
        from agenticcli.commands import session

        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="tmux", timeout=5)

        monkeypatch.setattr(session.subprocess, "run", raise_timeout)

        result = session._check_tmux_session("test-session")
        assert result is None


@pytest.mark.story("US-SES-001")
class TestSessionHandleRoutingNewCommands:
    """Tests for handle routing of new commands."""

    def test_handle_routes_to_healthcheck(self, mock_sessions_dir, mock_logs_dir, capsys):
        """Test that handle routes healthcheck command correctly."""
        from agenticcli.commands import session

        args = SimpleNamespace(session_command="healthcheck", session_id="nonexistent")
        session.handle(args)

        captured = capsys.readouterr()
        assert "No session found" in captured.err

    def test_handle_routes_to_logs(self, mock_sessions_dir, mock_logs_dir, capsys):
        """Test that handle routes logs command correctly."""
        from agenticcli.commands import session

        args = SimpleNamespace(
            session_command="logs",
            session_id="nonexistent",
            stderr=False, lines=50, follow=False,
        )
        session.handle(args)

        captured = capsys.readouterr()
        assert "No session found" in captured.err


@pytest.mark.story("US-SES-001")
class TestLogFileDescriptorManagement:
    """Tests for log file descriptor management in background spawn (TSM_003)."""

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_file_handles_closed_after_popen(
        self, mock_popen, mock_is_running, mock_sessions_dir, mock_logs_dir, monkeypatch
    ):
        """Verify that stdout/stderr file handles are closed after Popen call."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 55555
        mock_popen.return_value = mock_process
        mock_is_running.return_value = True

        # Track open() calls and close() calls
        opened_files = []
        original_open = open

        def tracking_open(path, *a, **kw):
            f = original_open(path, *a, **kw)
            path_str = str(path)
            if ".stdout.log" in path_str or ".stderr.log" in path_str:
                original_close = f.close
                close_tracker = {"closed": False, "path": path_str}

                def tracked_close():
                    close_tracker["closed"] = True
                    return original_close()

                f.close = tracked_close
                opened_files.append(close_tracker)
            return f

        monkeypatch.setattr("builtins.open", tracking_open)

        args = SimpleNamespace(
            prompt="Test fd management",
            max_turns=None,
            background=True,
            directory=None,
            role=None,
            task=None,
            plan=None,
            dangerously_skip_permissions=False,
        )

        session.cmd_spawn(args)

        # Verify both log files were opened and closed
        assert len(opened_files) == 2, f"Expected 2 log files opened, got {len(opened_files)}"
        for tracker in opened_files:
            assert tracker["closed"], f"File handle not closed: {tracker['path']}"

    @patch("agenticcli.commands.session.time.sleep")
    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_immediate_spawn_failure_detected(
        self, mock_popen, mock_is_running, mock_sleep, mock_sessions_dir, mock_logs_dir, capsys
    ):
        """Verify that a process dying immediately after spawn is detected and marked as failed."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 66666
        mock_popen.return_value = mock_process
        # Process dies immediately
        mock_is_running.return_value = False

        args = SimpleNamespace(
            prompt="Doomed task",
            max_turns=None,
            background=True,
            directory=None,
            role=None,
            task=None,
            plan=None,
            dangerously_skip_permissions=False,
        )

        session.cmd_spawn(args)

        # Verify session was marked as failed
        sessions = session._store.list_all()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "failed"
        assert "died immediately" in sessions[0].get("error", "")

        captured = capsys.readouterr()
        assert "failed" in captured.err.lower()

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_last_activity_set_on_spawn(
        self, mock_popen, mock_is_running, mock_sessions_dir, mock_logs_dir
    ):
        """Verify that last_activity is set to started_at on background spawn."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 77777
        mock_popen.return_value = mock_process
        mock_is_running.return_value = True

        args = SimpleNamespace(
            prompt="Track activity",
            max_turns=None,
            background=True,
            directory=None,
            role=None,
            task=None,
            plan=None,
            dangerously_skip_permissions=False,
        )

        session.cmd_spawn(args)

        sessions = session._store.list_all()
        assert len(sessions) == 1
        s = sessions[0]
        assert s.get("last_activity") is not None
        assert s["last_activity"] == s["started_at"]

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_file_handles_closed_even_on_popen_failure(
        self, mock_popen, mock_sessions_dir, mock_logs_dir, monkeypatch, capsys
    ):
        """Verify file handles are closed even if Popen raises an exception."""
        from agenticcli.commands import session

        mock_popen.side_effect = FileNotFoundError("claude not found")

        closed_files = []
        original_open = open

        def tracking_open(path, *a, **kw):
            f = original_open(path, *a, **kw)
            path_str = str(path)
            if ".stdout.log" in path_str or ".stderr.log" in path_str:
                original_close = f.close

                def tracked_close():
                    closed_files.append(path_str)
                    return original_close()

                f.close = tracked_close
            return f

        monkeypatch.setattr("builtins.open", tracking_open)

        args = SimpleNamespace(
            prompt="Will fail",
            max_turns=None,
            background=True,
            directory=None,
            role=None,
            task=None,
            plan=None,
            dangerously_skip_permissions=False,
        )

        with pytest.raises(SystemExit):
            session.cmd_spawn(args)

        # Both files should be closed even though Popen failed
        assert len(closed_files) == 2


@pytest.mark.story("US-SES-001", "US-SES-004")
class TestTmuxHealthIntegration:
    """Tests for tmux signal in health check (TSM_007)."""

    def test_health_includes_tmux_signal_for_background_session(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch
    ):
        """Verify health check includes tmux signal for background running sessions."""
        from agenticcli.commands import session

        sample_session_data["background"] = True
        sample_session_data["status"] = "running"
        session._store.save(sample_session_data)

        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("output")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)
        monkeypatch.setattr(session, "_check_tmux_session", lambda sid: True)

        health = session._check_session_health(sample_session_data)

        signal_names = [s["name"] for s in health["signals"]]
        assert "tmux_session" in signal_names
        tmux_signal = next(s for s in health["signals"] if s["name"] == "tmux_session")
        assert tmux_signal["ok"] is True
        assert "exists" in tmux_signal["detail"]

    def test_health_tmux_missing_shows_fail_signal(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch
    ):
        """Verify health check shows FAIL tmux signal when tmux session is missing."""
        from agenticcli.commands import session

        sample_session_data["background"] = True
        sample_session_data["status"] = "running"
        session._store.save(sample_session_data)

        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("output")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)
        monkeypatch.setattr(session, "_check_tmux_session", lambda sid: False)

        health = session._check_session_health(sample_session_data)

        tmux_signal = next(s for s in health["signals"] if s["name"] == "tmux_session")
        assert tmux_signal["ok"] is False
        assert "missing" in tmux_signal["detail"]

    def test_health_no_tmux_signal_for_foreground_session(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch
    ):
        """Verify health check omits tmux signal for non-background sessions."""
        from agenticcli.commands import session

        sample_session_data["background"] = False
        sample_session_data["status"] = "running"
        session._store.save(sample_session_data)

        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("output")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        health = session._check_session_health(sample_session_data)

        signal_names = [s["name"] for s in health["signals"]]
        assert "tmux_session" not in signal_names

    def test_health_no_tmux_signal_when_tmux_unavailable(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch
    ):
        """Verify health check omits tmux signal when tmux returns None (not installed)."""
        from agenticcli.commands import session

        sample_session_data["background"] = True
        sample_session_data["status"] = "running"
        session._store.save(sample_session_data)

        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("output")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)
        monkeypatch.setattr(session, "_check_tmux_session", lambda sid: None)

        health = session._check_session_health(sample_session_data)

        signal_names = [s["name"] for s in health["signals"]]
        # tmux_session signal should NOT be included when tmux returns None
        assert "tmux_session" not in signal_names

    def test_health_no_tmux_signal_for_completed_session(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch
    ):
        """Verify health check omits tmux signal for completed background sessions."""
        from agenticcli.commands import session

        sample_session_data["background"] = True
        sample_session_data["status"] = "completed"
        session._store.save(sample_session_data)

        monkeypatch.setattr(session, "is_process_running", lambda pid: False)

        health = session._check_session_health(sample_session_data)

        signal_names = [s["name"] for s in health["signals"]]
        assert "tmux_session" not in signal_names


@pytest.mark.story("US-SES-001")
class TestTmuxFlagParsing:
    """TT_001: Tests for --tmux flag parsing and propagation in cmd_spawn."""

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_tmux_flag_defaults_false(
        self, mock_popen, mock_is_running, mock_sessions_dir, mock_logs_dir, capsys
    ):
        """Verify default behavior without --tmux doesn't trigger tmux path."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        mock_is_running.return_value = True

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
        )

        session.cmd_spawn(args)

        # Should use subprocess.Popen (not tmux)
        mock_popen.assert_called_once()
        sessions = session._store.list_all()
        assert len(sessions) == 1
        # No tmux-related fields
        assert sessions[0].get("transport") != "tmux"
        assert sessions[0].get("tmux_session") is None

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.run")
    @patch("agenticcli.commands.session.shutil.which")
    @patch("agenticcli.commands.session.time.sleep")
    def test_spawn_tmux_flag_propagated(
        self, mock_sleep, mock_which, mock_run, mock_is_running,
        mock_sessions_dir, mock_logs_dir, capsys, monkeypatch,
    ):
        """Verify --tmux=True reaches cmd_spawn and triggers tmux path."""
        from agenticcli.commands import session

        mock_which.return_value = "/usr/bin/tmux"
        mock_is_running.return_value = True

        # Mock subprocess.run for tmux new-session, has-session, list-panes
        def mock_run_fn(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "99999\n"
            result.stderr = ""
            return result

        mock_run.side_effect = mock_run_fn

        # Mock session_exists to return True (session started ok)
        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists", lambda name: True
        )

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
            tmux=True,
        )

        session.cmd_spawn(args)

        sessions = session._store.list_all()
        assert len(sessions) == 1
        assert sessions[0].get("tmux") is True

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.run")
    @patch("agenticcli.commands.session.shutil.which")
    @patch("agenticcli.commands.session.time.sleep")
    def test_spawn_tmux_flag_in_session_data(
        self, mock_sleep, mock_which, mock_run, mock_is_running,
        mock_sessions_dir, mock_logs_dir, capsys, monkeypatch,
    ):
        """Verify the tmux flag is recorded in the session state JSON."""
        from agenticcli.commands import session

        mock_which.return_value = "/usr/bin/tmux"
        mock_is_running.return_value = True

        def mock_run_fn(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "88888\n"
            result.stderr = ""
            return result

        mock_run.side_effect = mock_run_fn
        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists", lambda name: True
        )

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
            tmux=True,
        )

        session.cmd_spawn(args)

        sessions = session._store.list_all()
        assert len(sessions) == 1
        data = sessions[0]
        # The tmux flag should be set at the top of cmd_spawn
        assert data.get("tmux") is True
        # The session should have tmux transport and session name
        assert data.get("transport") == "tmux"
        assert data.get("tmux_session") is not None
        assert data["tmux_session"].startswith("agentic-spawn-")


# ── TT_002: Test tmux session creation in cmd_spawn ───────────────────


@pytest.mark.story("US-SES-001")
class TestTmuxSessionCreation:
    """TT_002: Tests for tmux session creation path when --tmux is set."""

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.run")
    @patch("agenticcli.commands.session.shutil.which")
    @patch("agenticcli.commands.session.time.sleep")
    def test_spawn_tmux_creates_session(
        self, mock_sleep, mock_which, mock_run, mock_is_running,
        mock_sessions_dir, mock_logs_dir, capsys, monkeypatch,
    ):
        """Mock tmux new-session and verify correct args and session data."""
        from agenticcli.commands import session

        mock_which.return_value = "/usr/bin/tmux"
        mock_is_running.return_value = True

        calls = []

        def mock_run_fn(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = "77777\n"
            result.stderr = ""
            return result

        mock_run.side_effect = mock_run_fn
        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists", lambda name: True
        )

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
            tmux=True,
        )

        session.cmd_spawn(args)

        # Find the tmux new-session call
        new_session_calls = [c for c in calls if isinstance(c, list) and "new-session" in c]
        assert len(new_session_calls) >= 1, f"Expected tmux new-session call, got: {calls}"

        new_session_cmd = new_session_calls[0]
        assert new_session_cmd[0] == "tmux"
        assert "-d" in new_session_cmd
        assert "-s" in new_session_cmd

        # Session name should follow convention: agentic-spawn-{id[:8]}
        idx = new_session_cmd.index("-s")
        tmux_name = new_session_cmd[idx + 1]
        assert tmux_name.startswith("agentic-spawn-")

        # Session data should be saved correctly
        sessions = session._store.list_all()
        assert len(sessions) == 1
        data = sessions[0]
        assert data["transport"] == "tmux"
        assert data["tmux_session"] == tmux_name
        assert data["status"] == "running"

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.run")
    @patch("agenticcli.commands.session.shutil.which")
    @patch("agenticcli.commands.session.time.sleep")
    def test_spawn_tmux_background_returns_immediately(
        self, mock_sleep, mock_which, mock_run, mock_is_running,
        mock_sessions_dir, mock_logs_dir, capsys, monkeypatch,
    ):
        """With -b flag, verify cmd_spawn returns without blocking (no tmux attach)."""
        from agenticcli.commands import session

        mock_which.return_value = "/usr/bin/tmux"
        mock_is_running.return_value = True

        calls = []

        def mock_run_fn(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = "66666\n"
            result.stderr = ""
            return result

        mock_run.side_effect = mock_run_fn
        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists", lambda name: True
        )

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
            tmux=True,
        )

        session.cmd_spawn(args)

        # tmux attach should NOT be called for background sessions
        attach_calls = [c for c in calls if isinstance(c, list) and "attach" in c]
        assert len(attach_calls) == 0, f"tmux attach should not be called in background mode, got: {attach_calls}"

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.run")
    @patch("agenticcli.commands.session.shutil.which")
    @patch("agenticcli.commands.session.time.sleep")
    def test_spawn_tmux_foreground_attaches(
        self, mock_sleep, mock_which, mock_run, mock_is_running,
        mock_sessions_dir, mock_logs_dir, capsys, monkeypatch,
    ):
        """Without -b flag, verify tmux attach is called."""
        from agenticcli.commands import session

        mock_which.return_value = "/usr/bin/tmux"
        mock_is_running.return_value = True

        calls = []

        def mock_run_fn(cmd, **kwargs):
            calls.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = "55555\n"
            result.stderr = ""
            return result

        mock_run.side_effect = mock_run_fn

        # First call to session_exists returns True (session started ok),
        # second call returns False (session ended after attach)
        exists_calls = []

        def mock_session_exists(name):
            exists_calls.append(name)
            if len(exists_calls) == 1:
                return True  # verify step
            return False  # after attach, session is done

        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists", mock_session_exists
        )

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=False,
            directory=None,
            tmux=True,
        )

        session.cmd_spawn(args)

        # tmux attach SHOULD be called for foreground sessions
        attach_calls = [c for c in calls if isinstance(c, list) and "attach" in c]
        assert len(attach_calls) >= 1, f"Expected tmux attach call, got: {calls}"

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.run")
    @patch("agenticcli.commands.session.shutil.which")
    @patch("agenticcli.commands.session.time.sleep")
    def test_spawn_tmux_verifies_session_started(
        self, mock_sleep, mock_which, mock_run, mock_is_running,
        mock_sessions_dir, mock_logs_dir, capsys, monkeypatch,
    ):
        """Verify the 0.5s delay + session_exists check after creation."""
        from agenticcli.commands import session

        mock_which.return_value = "/usr/bin/tmux"
        mock_is_running.return_value = True

        def mock_run_fn(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "44444\n"
            result.stderr = ""
            return result

        mock_run.side_effect = mock_run_fn
        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists", lambda name: True
        )

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
            tmux=True,
        )

        session.cmd_spawn(args)

        # time.sleep should be called with 0.5 for the verification delay
        mock_sleep.assert_any_call(0.5)

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    @patch("agenticcli.commands.session.subprocess.run")
    @patch("agenticcli.commands.session.shutil.which")
    @patch("agenticcli.commands.session.time.sleep")
    def test_spawn_tmux_immediate_exit_reports_failure(
        self, mock_sleep, mock_which, mock_run, mock_popen, mock_is_running,
        mock_sessions_dir, mock_logs_dir, capsys, monkeypatch,
    ):
        """Mock session_exists returning False to verify spawn falls back."""
        from agenticcli.commands import session

        mock_which.return_value = "/usr/bin/tmux"
        mock_is_running.return_value = True

        def mock_run_fn(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "33333\n"
            result.stderr = ""
            return result

        mock_run.side_effect = mock_run_fn

        # session_exists returns False => tmux session exited immediately
        monkeypatch.setattr(
            "agenticcli.utils.tmux.session_exists", lambda name: False
        )

        # Provide Popen mock for fallback path
        mock_process = MagicMock()
        mock_process.pid = 33333
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
            tmux=True,
        )

        session.cmd_spawn(args)

        # Session should fall back to subprocess
        sessions = session._store.list_all()
        assert len(sessions) == 1
        data = sessions[0]
        assert data.get("tmux_fallback") is True


# ── TT_003: Test tmux fallback when tmux unavailable ──────────────────


@pytest.mark.story("US-SES-001")
class TestTmuxFallback:
    """TT_003: Tests for graceful degradation when tmux is not available."""

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    @patch("agenticcli.commands.session.shutil.which")
    def test_spawn_tmux_fallback_no_tmux(
        self, mock_which, mock_popen, mock_is_running,
        mock_sessions_dir, mock_logs_dir, capsys,
    ):
        """When tmux is not installed, fall through to subprocess.Popen path."""
        from agenticcli.commands import session

        mock_which.return_value = None  # tmux not available
        mock_is_running.return_value = True

        mock_process = MagicMock()
        mock_process.pid = 22222
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
            tmux=True,
        )

        session.cmd_spawn(args)

        # Should fall through to Popen subprocess path
        mock_popen.assert_called_once()
        sessions = session._store.list_all()
        assert len(sessions) == 1
        data = sessions[0]
        # Should NOT have tmux_session field
        assert data.get("tmux_session") is None
        assert data.get("transport") != "tmux"

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    @patch("agenticcli.commands.session.subprocess.run")
    @patch("agenticcli.commands.session.shutil.which")
    def test_spawn_tmux_fallback_creation_fails(
        self, mock_which, mock_run, mock_popen, mock_is_running,
        mock_sessions_dir, mock_logs_dir, capsys,
    ):
        """When tmux new-session returns non-zero, fall back to subprocess."""
        from agenticcli.commands import session

        mock_which.return_value = "/usr/bin/tmux"
        mock_is_running.return_value = True

        # tmux new-session fails
        def mock_run_fn(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 1  # failure
            result.stdout = ""
            result.stderr = "tmux: session creation failed"
            return result

        mock_run.side_effect = mock_run_fn

        mock_process = MagicMock()
        mock_process.pid = 11111
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=None,
            background=True,
            directory=None,
            tmux=True,
        )

        session.cmd_spawn(args)

        # Should fall back to subprocess.Popen
        mock_popen.assert_called_once()
        sessions = session._store.list_all()
        assert len(sessions) == 1
        data = sessions[0]
        assert data.get("tmux_fallback") is True

    def test_spawn_tmux_session_name_convention(self):
        """Verify session naming convention for various inputs."""
        from agenticcli.commands.session import _tmux_session_name

        # Without epic: agentic-spawn-{session_id[:8]}
        name = _tmux_session_name("abcd1234-5678-9abc-def0-123456789abc")
        assert name == "agentic-spawn-abcd1234"

        # With epic + role: agentic-{epic_short}-{role[:8]}-{session_id[:6]}
        epic = Path("/docs/epics/live/260306AG_tmux_orch")
        name = _tmux_session_name("abcd1234-5678", epic_folder=epic, role="build-python")
        assert name == "agentic-260306AG-build-py-abcd12"

        # With epic only (no role)
        name = _tmux_session_name("abcd1234-5678", epic_folder=epic)
        assert name == "agentic-260306AG-abcd1234"

        # Invalid chars replaced with hyphens
        epic_bad = Path("/docs/epics/live/260306AG_bad!chars")
        name = _tmux_session_name("abcd1234-5678", epic_folder=epic_bad, role="test")
        # '!' should be replaced with '-'
        assert "!" not in name
        assert all(c.isalnum() or c in ("_", "-") for c in name)


# ── TT_006: Test session stop kills tmux session ──────────────────────


@pytest.mark.story("US-SES-003", "US-GDN-087")
class TestSessionStopTmux:
    """TT_006: Tests that session stop properly kills tmux sessions."""

    @patch("os.kill")
    @patch("agenticcli.commands.session.subprocess.run")
    def test_stop_kills_tmux_session(
        self, mock_run, mock_kill, mock_sessions_dir, sample_session_data, capsys
    ):
        """Session data has tmux_session — verify tmux kill-session is called."""
        from agenticcli.commands import session

        sample_session_data["tmux_session"] = "agentic-spawn-12345678"
        sample_session_data["transport"] = "tmux"
        session._store.save(sample_session_data)

        mock_run.return_value = MagicMock(returncode=0)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        session.cmd_stop(args)

        # Verify tmux kill-session was called
        tmux_kill_calls = [
            c for c in mock_run.call_args_list
            if isinstance(c[0][0], list) and "kill-session" in c[0][0]
        ]
        assert len(tmux_kill_calls) >= 1, f"Expected tmux kill-session call, got: {mock_run.call_args_list}"
        kill_cmd = tmux_kill_calls[0][0][0]
        assert kill_cmd == ["tmux", "kill-session", "-t", "agentic-spawn-12345678"]

    @patch("os.kill")
    @patch("agenticcli.commands.session.subprocess.run")
    def test_stop_ignores_dead_tmux_session(
        self, mock_run, mock_kill, mock_sessions_dir, sample_session_data, capsys
    ):
        """tmux kill-session returns non-zero (already dead) — no error raised."""
        from agenticcli.commands import session

        sample_session_data["tmux_session"] = "agentic-spawn-deadbeef"
        sample_session_data["transport"] = "tmux"
        session._store.save(sample_session_data)

        # tmux kill-session "fails" because session is already dead
        mock_run.return_value = MagicMock(returncode=1, stderr="session not found")

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        # Should NOT raise an error
        session.cmd_stop(args)

        # Session should still be stopped
        sessions = session._store.list_all()
        assert sessions[0]["status"] == "stopped"

    @patch("os.kill")
    def test_stop_without_tmux_session_unchanged(
        self, mock_kill, mock_sessions_dir, sample_session_data, capsys, monkeypatch,
    ):
        """Session without tmux_session field — no tmux commands called."""
        from agenticcli.commands import session

        # Ensure no tmux_session field
        assert "tmux_session" not in sample_session_data
        session._store.save(sample_session_data)

        # Track all subprocess.run calls
        run_calls = []
        original_run = session.subprocess.run

        def tracking_run(cmd, **kwargs):
            run_calls.append(cmd)
            return MagicMock(returncode=0)

        monkeypatch.setattr(session.subprocess, "run", tracking_run)

        args = SimpleNamespace(
            session_id=sample_session_data["session_id"][:8],
            force=False,
        )

        session.cmd_stop(args)

        # No tmux commands should be called
        tmux_calls = [c for c in run_calls if isinstance(c, list) and c[0] == "tmux"]
        assert len(tmux_calls) == 0, f"No tmux commands expected, got: {tmux_calls}"
