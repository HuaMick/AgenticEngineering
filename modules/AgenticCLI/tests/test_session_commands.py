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
    monkeypatch.setattr(session, "_get_context_dir", lambda: context_dir)

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

    monkeypatch.setattr(session, "_get_context_dir", lambda: context_dir)
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

    def test_is_process_running_for_current_process(self):
        """Test is_process_running for the current process."""
        from agenticcli.commands import session

        # Current process should be running
        assert session.is_process_running(os.getpid()) is True

    def test_is_process_running_for_nonexistent_process(self):
        """Test is_process_running for a nonexistent process."""
        from agenticcli.commands import session

        # Very high PID unlikely to exist
        assert session.is_process_running(99999999) is False

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
        assert "--print" in cmd
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


class TestResolvePlanFolder:
    """Tests for _resolve_plan_folder helper."""

    def test_resolve_existing_plan(self, tmp_path, monkeypatch):
        """Test resolving an existing epic folder in docs/epics/live/."""
        from agenticcli.commands import session

        live_dir = tmp_path / "docs" / "epics" / "live"
        plan_dir = live_dir / "260207TA_cli_task_spawn"
        plan_dir.mkdir(parents=True)

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        result = session._resolve_plan_folder("260207TA_cli_task_spawn")
        assert result == plan_dir

    def test_resolve_completed_plan(self, tmp_path, monkeypatch):
        """Test resolving an epic in docs/epics/completed/."""
        from agenticcli.commands import session

        completed_dir = tmp_path / "docs" / "epics" / "completed"
        plan_dir = completed_dir / "260203TS_task_service"
        plan_dir.mkdir(parents=True)

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        result = session._resolve_plan_folder("260203TS_task_service")
        assert result == plan_dir

    def test_resolve_nonexistent_plan(self, tmp_path, monkeypatch):
        """Test resolving an epic folder that doesn't exist."""
        from agenticcli.commands import session

        (tmp_path / "docs" / "epics" / "live").mkdir(parents=True)
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        result = session._resolve_plan_folder("nonexistent_plan")
        assert result is None


class TestBuildRolePrompt:
    """Tests for _build_role_prompt helper."""

    def test_role_prompt_without_plan(self):
        """Test building a role prompt without plan context."""
        from agenticcli.commands import session

        prompt = session._build_role_prompt("build-python", None)
        assert "build-python" in prompt
        assert "context bootstrap" in prompt

    def test_role_prompt_with_plan(self, tmp_path):
        """Test building a role prompt with plan context."""
        from agenticcli.commands import session

        plan_folder = tmp_path / "260207TA_cli_task_spawn"
        plan_folder.mkdir()

        prompt = session._build_role_prompt("build-python", plan_folder)
        assert "build-python" in prompt
        assert "260207TA_cli_task_spawn" in prompt
        assert "epic ticket list" in prompt


class TestBuildTaskPrompt:
    """Tests for _build_task_prompt helper."""

    def test_task_prompt_with_valid_task(self, tmp_path):
        """Test building a task prompt from a valid plan file."""
        from agenticcli.commands import session

        plan_folder = tmp_path / "260207TA_test"
        plan_folder.mkdir()

        # Create a ticket_build.yml with a task
        plan_file = plan_folder / "ticket_build.yml"
        plan_file.write_text("""
phases:
  - name: "Test Phase"
    tickets:
      - id: "CLI_001"
        name: "Add --task argument"
        status: "pending"
        description: "Add the --task argument to session spawn."
        target_files:
          - modules/AgenticCLI/src/agenticcli/commands/session.py
        inputs:
          - modules/AgenticCLI/src/agenticcli/commands/plan.py
        guidance: "Follow existing patterns."
""")

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

        plan_file = plan_folder / "ticket_build.yml"
        plan_file.write_text("""
phases:
  - name: "Test Phase"
    tickets:
      - id: "CLI_001"
        name: "Existing task"
        status: "pending"
        description: "A task that exists."
""")

        prompt = session._build_task_prompt("NONEXISTENT", plan_folder)
        assert prompt is None


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
        """Test spawn with --task loads task context and spawns agent."""
        from agenticcli.commands import session

        # Set up epic folder with task
        live_dir = tmp_path / "docs" / "epics" / "live"
        plan_dir = live_dir / "260207TA_test"
        plan_dir.mkdir(parents=True)

        plan_file = plan_dir / "ticket_build.yml"
        plan_file.write_text("""
phases:
  - name: "Build Phase"
    tickets:
      - id: "CLI_001"
        name: "Add feature"
        status: "pending"
        description: "Add a new feature."
        target_files:
          - src/main.py
""")

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

    def test_spawn_task_requires_plan(self, mock_sessions_dir, capsys):
        """Test that --task without --plan fails."""
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
        assert "--task requires --plan" in captured.err

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

        plan_file = plan_dir / "plan_build.yml"
        plan_file.write_text("""
phases:
  - name: "Build Phase"
    tickets:
      - id: "CLI_001"
        name: "Real task"
        status: "pending"
        description: "A real task."
""")

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

        spawn_called = []
        monkeypatch.setattr(session, "_spawn_diagnostic_planner", lambda s: spawn_called.append(1))

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8])
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert "STALE" in captured.out
        assert len(spawn_called) == 0  # No diagnostic spawn without --diagnose

    def test_healthcheck_stale_session_with_diagnose(self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys):
        """Test healthcheck spawns diagnostic when --diagnose is set for stale sessions."""
        import time as time_mod
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("Old output")
        old_time = time_mod.time() - (20 * 60)
        os.utime(stdout_log, (old_time, old_time))

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        spawned_ids = []

        def mock_spawn(s):
            new_id = "diag-1234-5678"
            spawned_ids.append(new_id)
            return new_id

        monkeypatch.setattr(session, "_spawn_diagnostic_planner", mock_spawn)

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8], diagnose=True)
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert "STALE" in captured.out
        assert len(spawned_ids) == 1

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


class TestDiagnosticAutoSpawn:
    """Tests for diagnostic auto-spawn in healthcheck (requires --diagnose)."""

    def test_spawns_diagnostic_for_stale_session_with_diagnose(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys
    ):
        """Test that cmd_healthcheck auto-spawns diagnostic for stale sessions when --diagnose is set."""
        import time as time_mod
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("Old output")
        old_time = time_mod.time() - (20 * 60)
        os.utime(stdout_log, (old_time, old_time))

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        spawned_ids = []

        def mock_spawn(s):
            new_id = "diag-1234-5678"
            spawned_ids.append(new_id)
            return new_id

        monkeypatch.setattr(session, "_spawn_diagnostic_planner", mock_spawn)

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8], diagnose=True)
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert "STALE" in captured.out
        assert len(spawned_ids) == 1
        assert "diag-123" in captured.out  # Truncated to 8 chars

    def test_no_diagnostic_without_diagnose_flag(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys
    ):
        """Test that diagnostic is NOT spawned without --diagnose even for stale sessions."""
        import time as time_mod
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("Old output")
        old_time = time_mod.time() - (20 * 60)
        os.utime(stdout_log, (old_time, old_time))

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        spawn_called = []
        monkeypatch.setattr(session, "_spawn_diagnostic_planner", lambda s: spawn_called.append(1))

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8])
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert "STALE" in captured.out
        assert len(spawn_called) == 0

    def test_diagnostic_spawns_only_once(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys
    ):
        """Test that diagnostic is not spawned if already spawned."""
        from agenticcli.commands import session

        # Mark session as already having a diagnostic spawned
        sample_session_data["diagnostic_spawned"] = True
        sample_session_data["diagnostic_session_id"] = "existing-diag-id-1234"
        session._store.save(sample_session_data)

        monkeypatch.setattr(session, "is_process_running", lambda pid: False)

        spawn_called = []
        monkeypatch.setattr(session, "_spawn_diagnostic_planner", lambda s: spawn_called.append(1))

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8], diagnose=True)
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert len(spawn_called) == 0
        assert "already spawned" in captured.out.lower()
        assert "existing" in captured.out

    def test_no_diagnostic_for_healthy_session(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys
    ):
        """Test that diagnostic is NOT spawned for healthy sessions even with --diagnose."""
        from agenticcli.commands import session

        session._store.save(sample_session_data)
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("Some output")

        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        spawn_called = []
        monkeypatch.setattr(session, "_spawn_diagnostic_planner", lambda s: spawn_called.append(1))

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8], diagnose=True)
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        assert "HEALTHY" in captured.out
        assert len(spawn_called) == 0

    @patch("agenticcli.console.is_json_output")
    def test_diagnostic_in_json_output(
        self, mock_json, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch, capsys
    ):
        """Test diagnostic spawn info appears in JSON healthcheck output when --diagnose is set."""
        from agenticcli.commands import session

        mock_json.return_value = True
        session._store.save(sample_session_data)

        monkeypatch.setattr(session, "is_process_running", lambda pid: False)
        monkeypatch.setattr(session, "_spawn_diagnostic_planner", lambda s: "new-diag-9999")

        args = SimpleNamespace(session_id=sample_session_data["session_id"][:8], json_output=True, diagnose=True)
        session.cmd_healthcheck(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output.get("diagnostic_spawned") == "new-diag-9999"


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


class TestCaptureLangSmithTrace:
    """Tests for _capture_langsmith_trace post-completion trace capture."""

    def test_captures_trace_from_json_output(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, tmp_path, monkeypatch
    ):
        """Verify trace is captured from --output-format json stdout log."""
        from agenticcli.commands import session

        claude_sid = "abc12345-1234-5678-9abc-def012345678"
        # Create stdout log with JSON output from claude --print --output-format json
        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text(json.dumps({
            "type": "result",
            "session_id": claude_sid,
            "result": "done",
        }))
        sample_session_data["stdout_log"] = str(stdout_log)
        sample_session_data["background"] = True
        sample_session_data["working_dir"] = str(tmp_path)

        # Create a fake transcript
        project_hash = str(tmp_path).replace("/", "-")
        transcript_dir = tmp_path / ".claude_projects" / project_hash
        transcript_dir.mkdir(parents=True)
        transcript_path = transcript_dir / f"{claude_sid}.jsonl"
        transcript_path.write_text('{"type":"test"}\n')

        # Mock Path.home() for transcript search and hook path
        hook_path = tmp_path / "hook.sh"
        hook_path.write_text("#!/bin/bash\nexit 0\n")
        hook_path.chmod(0o755)

        mock_hook_path = tmp_path / ".claude" / "hooks" / "stop_hook.sh"
        mock_hook_path.parent.mkdir(parents=True, exist_ok=True)
        mock_hook_path.write_text("#!/bin/bash\nexit 0\n")

        # Mock subprocess.run to verify the hook is called
        run_calls = []
        original_run = subprocess.run

        def mock_run(*args, **kwargs):
            if args and isinstance(args[0], list) and "stop_hook" in str(args[0]):
                run_calls.append((args, kwargs))
                return MagicMock(returncode=0)
            return original_run(*args, **kwargs)

        monkeypatch.setattr(subprocess, "run", mock_run)

        # Mock the transcript search to find our fake transcript
        claude_projects = tmp_path / ".claude" / "projects"
        proj_dir = claude_projects / project_hash
        proj_dir.mkdir(parents=True)
        fake_transcript = proj_dir / f"{claude_sid}.jsonl"
        fake_transcript.write_text('{"type":"test"}\n')

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = session._capture_langsmith_trace(sample_session_data)

        assert result is True
        assert len(run_calls) == 1
        # Verify the hook input contains session_id and transcript_path
        call_kwargs = run_calls[0][1]
        hook_input = json.loads(call_kwargs["input"])
        assert hook_input["session_id"] == claude_sid

    def test_skips_if_already_captured(
        self, mock_sessions_dir, sample_session_data
    ):
        """Verify trace capture is skipped if already done."""
        from agenticcli.commands import session

        sample_session_data["trace_captured"] = True
        result = session._capture_langsmith_trace(sample_session_data)
        assert result is True

    def test_returns_false_if_no_stdout_log(
        self, mock_sessions_dir, sample_session_data
    ):
        """Verify returns False if stdout_log is missing."""
        from agenticcli.commands import session

        sample_session_data["stdout_log"] = "/nonexistent/path.log"
        result = session._capture_langsmith_trace(sample_session_data)
        assert result is False

    def test_returns_false_if_no_session_id_in_output(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data
    ):
        """Verify returns False if Claude output has no session_id."""
        from agenticcli.commands import session

        stdout_log = mock_logs_dir / f"{sample_session_data['session_id']}.stdout.log"
        stdout_log.write_text("Just plain text output, no JSON")
        sample_session_data["stdout_log"] = str(stdout_log)

        result = session._capture_langsmith_trace(sample_session_data)
        assert result is False

    def test_update_status_triggers_trace_capture(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch
    ):
        """Verify _update_session_status calls trace capture for completed bg sessions."""
        from agenticcli.commands import session

        sample_session_data["status"] = "running"
        sample_session_data["background"] = True
        sample_session_data["pid"] = 99999
        session._store.save(sample_session_data)

        monkeypatch.setattr(session, "is_process_running", lambda pid: False)

        capture_calls = []
        monkeypatch.setattr(
            session, "_capture_langsmith_trace",
            lambda data: capture_calls.append(data) or False
        )

        session._update_session_status(sample_session_data)

        assert sample_session_data["status"] == "completed"
        assert len(capture_calls) == 1

    def test_update_status_skips_trace_for_foreground(
        self, mock_sessions_dir, mock_logs_dir, sample_session_data, monkeypatch
    ):
        """Verify _update_session_status does NOT call trace capture for foreground sessions."""
        from agenticcli.commands import session

        sample_session_data["status"] = "running"
        sample_session_data["background"] = False
        sample_session_data["pid"] = 99999
        session._store.save(sample_session_data)

        monkeypatch.setattr(session, "is_process_running", lambda pid: False)

        capture_calls = []
        monkeypatch.setattr(
            session, "_capture_langsmith_trace",
            lambda data: capture_calls.append(data) or False
        )

        session._update_session_status(sample_session_data)

        assert sample_session_data["status"] == "completed"
        assert len(capture_calls) == 0

    def test_spawn_adds_output_format_json_for_background(
        self, mock_sessions_dir, mock_logs_dir, monkeypatch
    ):
        """Verify spawn adds --output-format json flag for background sessions."""
        from agenticcli.commands import session

        captured_cmds = []

        def mock_popen(cmd, **kwargs):
            captured_cmds.append(cmd)
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            return mock_proc

        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr(session, "is_process_running", lambda pid: True)

        args = SimpleNamespace(
            prompt="test prompt",
            role=None,
            task=None,
            plan=None,
            max_turns=5,
            background=True,
            directory=None,
            dangerously_skip_permissions=False,
        )

        # Mock builtins.open for log files
        import builtins
        original_open = builtins.open

        def mock_open(path, *a, **kw):
            if "stdout.log" in str(path) or "stderr.log" in str(path):
                return MagicMock()
            return original_open(path, *a, **kw)

        monkeypatch.setattr(builtins, "open", mock_open)
        monkeypatch.setattr("agenticcli.console.is_json_output", lambda: False)

        session.cmd_spawn(args)

        assert len(captured_cmds) == 1
        cmd = captured_cmds[0]
        assert "--output-format" in cmd
        assert "json" in cmd


class TestEnsureWatchDaemon:
    """WD_004: Unit tests for _ensure_watch_daemon function.

    Tests the PID-file based daemon management approach where each plan's
    watcher daemon stores its PID in a pidfile under
    ~/.config/agenticguidance/watchers/<plan_name>.pid.
    """

    def test_starts_when_no_pidfile(self, tmp_path, monkeypatch):
        """Test daemon starts when no existing pidfile (no prior watcher)."""
        from agenticcli.commands import question

        plan_path = tmp_path / "260210WD_test_plan"
        plan_path.mkdir()

        # Redirect pidfile to tmp_path to avoid writing to real config
        piddir = tmp_path / "watchers"
        piddir.mkdir()
        monkeypatch.setattr(question, "_get_watcher_pidfile",
                            lambda pp: piddir / f"{pp.name}.pid")

        mock_process = MagicMock()
        mock_process.pid = 54321
        mock_popen = MagicMock(return_value=mock_process)
        monkeypatch.setattr("subprocess.Popen", mock_popen)

        started, reason = question._ensure_watch_daemon(plan_path)

        assert started is True
        assert reason == "started"
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "nohup" in cmd
        assert "python3" in cmd
        # Pidfile should be created with the child PID
        pidfile = piddir / f"{plan_path.name}.pid"
        assert pidfile.exists()
        assert pidfile.read_text().strip() == "54321"

    def test_starts_without_ntfy(self, tmp_path, monkeypatch):
        """Test daemon starts even when ntfy is not configured (ntfy gate removed)."""
        from agenticcli.commands import question

        plan_path = tmp_path / "260210WD_test_plan"
        plan_path.mkdir()

        monkeypatch.setattr(question, "_get_ntfy_config", lambda: None)

        piddir = tmp_path / "watchers"
        piddir.mkdir()
        monkeypatch.setattr(question, "_get_watcher_pidfile",
                            lambda pp: piddir / f"{pp.name}.pid")

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen = MagicMock(return_value=mock_process)
        monkeypatch.setattr("subprocess.Popen", mock_popen)

        started, reason = question._ensure_watch_daemon(plan_path)

        assert started is True
        assert reason == "started"
        mock_popen.assert_called_once()

    def test_skips_when_already_running(self, tmp_path, monkeypatch):
        """Test daemon is skipped when pidfile references a live process."""
        from agenticcli.commands import question

        plan_path = tmp_path / "260210WD_test_plan"
        plan_path.mkdir()

        piddir = tmp_path / "watchers"
        piddir.mkdir()
        monkeypatch.setattr(question, "_get_watcher_pidfile",
                            lambda pp: piddir / f"{pp.name}.pid")

        # Write pidfile with current (alive) PID
        alive_pid = os.getpid()
        pidfile = piddir / f"{plan_path.name}.pid"
        pidfile.write_text(str(alive_pid))

        mock_popen = MagicMock()
        monkeypatch.setattr("subprocess.Popen", mock_popen)

        started, reason = question._ensure_watch_daemon(plan_path)

        assert started is False
        assert reason == "already_running"
        mock_popen.assert_not_called()

    def test_cleans_stale_and_starts(self, tmp_path, monkeypatch):
        """Test daemon cleans stale pidfile and starts a new daemon."""
        from agenticcli.commands import question

        plan_path = tmp_path / "260210WD_test_plan"
        plan_path.mkdir()

        piddir = tmp_path / "watchers"
        piddir.mkdir()
        monkeypatch.setattr(question, "_get_watcher_pidfile",
                            lambda pp: piddir / f"{pp.name}.pid")

        # Write pidfile with a dead PID
        dead_pid = 99999999
        pidfile = piddir / f"{plan_path.name}.pid"
        pidfile.write_text(str(dead_pid))

        mock_process = MagicMock()
        mock_process.pid = 11111
        mock_popen = MagicMock(return_value=mock_process)
        monkeypatch.setattr("subprocess.Popen", mock_popen)

        started, reason = question._ensure_watch_daemon(plan_path)

        assert started is True
        assert reason == "started"
        mock_popen.assert_called_once()
        # Pidfile should now contain the new PID
        assert pidfile.read_text().strip() == "11111"

    def test_handles_errors_gracefully(self, tmp_path, monkeypatch):
        """Test daemon returns error tuple on exception without propagating."""
        from agenticcli.commands import question

        plan_path = tmp_path / "260210WD_test_plan"
        plan_path.mkdir()

        piddir = tmp_path / "watchers"
        piddir.mkdir()
        monkeypatch.setattr(question, "_get_watcher_pidfile",
                            lambda pp: piddir / f"{pp.name}.pid")

        mock_popen = MagicMock(side_effect=OSError("spawn failed"))
        monkeypatch.setattr("subprocess.Popen", mock_popen)

        started, reason = question._ensure_watch_daemon(plan_path)

        assert started is False
        assert reason == "error"


class TestSpawnAutoWatchDaemon:
    """WD_005: Integration tests for cmd_spawn auto-daemon behavior."""

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_with_plan_starts_watch_daemon(
        self, mock_popen, mock_is_running, mock_sessions_dir, mock_logs_dir, tmp_path, monkeypatch
    ):
        """Test that spawn with --plan calls _ensure_watch_daemon."""
        from agenticcli.commands import session

        # Set up epic folder
        live_dir = tmp_path / "docs" / "epics" / "live"
        plan_dir = live_dir / "260210WD_test"
        plan_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        mock_is_running.return_value = True
        mock_process = MagicMock()
        mock_process.pid = 33333
        mock_popen.return_value = mock_process

        # Track _ensure_watch_daemon calls
        daemon_calls = []

        def mock_ensure(plan_path):
            daemon_calls.append(plan_path)
            return (True, "started")

        monkeypatch.setattr("agenticcli.commands.question._ensure_watch_daemon", mock_ensure)

        args = SimpleNamespace(
            prompt="Test with plan",
            role=None,
            task=None,
            plan="260210WD_test",
            max_turns=None,
            background=True,
            directory=None,
            dangerously_skip_permissions=False,
        )

        session.cmd_spawn(args)

        assert len(daemon_calls) == 1
        assert daemon_calls[0] == plan_dir

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_without_plan_skips_watch_daemon(
        self, mock_popen, mock_is_running, mock_sessions_dir, mock_logs_dir, monkeypatch
    ):
        """Test that spawn without --plan does NOT call _ensure_watch_daemon."""
        from agenticcli.commands import session

        mock_is_running.return_value = True
        mock_process = MagicMock()
        mock_process.pid = 22222
        mock_popen.return_value = mock_process

        daemon_calls = []

        def mock_ensure(plan_path):
            daemon_calls.append(plan_path)
            return (True, "started")

        monkeypatch.setattr("agenticcli.commands.question._ensure_watch_daemon", mock_ensure)

        args = SimpleNamespace(
            prompt="Test without plan",
            role=None,
            task=None,
            plan=None,
            max_turns=None,
            background=True,
            directory=None,
            dangerously_skip_permissions=False,
        )

        session.cmd_spawn(args)

        assert len(daemon_calls) == 0

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_daemon_failure_does_not_block_spawn(
        self, mock_popen, mock_is_running, mock_sessions_dir, mock_logs_dir, tmp_path, monkeypatch
    ):
        """Test that _ensure_watch_daemon failure doesn't block cmd_spawn."""
        from agenticcli.commands import session

        # Set up epic folder
        live_dir = tmp_path / "docs" / "epics" / "live"
        plan_dir = live_dir / "260210WD_test"
        plan_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        mock_is_running.return_value = True
        mock_process = MagicMock()
        mock_process.pid = 44444
        mock_popen.return_value = mock_process

        # Make _ensure_watch_daemon raise an exception
        def mock_ensure_boom(plan_path):
            raise RuntimeError("daemon startup crashed")

        monkeypatch.setattr("agenticcli.commands.question._ensure_watch_daemon", mock_ensure_boom)

        args = SimpleNamespace(
            prompt="Test daemon failure",
            role=None,
            task=None,
            plan="260210WD_test",
            max_turns=None,
            background=True,
            directory=None,
            dangerously_skip_permissions=False,
        )

        # Should NOT raise - spawn should succeed despite daemon failure
        session.cmd_spawn(args)

        # Session should be saved as running
        sessions = session._store.list_all()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "running"
        assert sessions[0]["pid"] == 44444
