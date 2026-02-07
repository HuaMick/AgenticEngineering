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
        assert "Test task" in cmd

        # Verify session was saved
        sessions = session._list_all_sessions()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "running"
        assert sessions[0]["pid"] == 12345

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
        sessions = session._list_all_sessions()
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

        # Should succeed without raising SystemExit
        session.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already in terminal state" in captured.out

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

        # Should succeed without raising SystemExit
        session.cmd_stop(args)

        captured = capsys.readouterr()
        assert "already exited" in captured.out


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


class TestResolvePlanFolder:
    """Tests for _resolve_plan_folder helper."""

    def test_resolve_existing_plan(self, tmp_path, monkeypatch):
        """Test resolving an existing plan folder in docs/plans/live/."""
        from agenticcli.commands import session

        live_dir = tmp_path / "docs" / "plans" / "live"
        plan_dir = live_dir / "260207TA_cli_task_spawn"
        plan_dir.mkdir(parents=True)

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        result = session._resolve_plan_folder("260207TA_cli_task_spawn")
        assert result == plan_dir

    def test_resolve_completed_plan(self, tmp_path, monkeypatch):
        """Test resolving a plan in docs/plans/completed/."""
        from agenticcli.commands import session

        completed_dir = tmp_path / "docs" / "plans" / "completed"
        plan_dir = completed_dir / "260203TS_task_service"
        plan_dir.mkdir(parents=True)

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

        result = session._resolve_plan_folder("260203TS_task_service")
        assert result == plan_dir

    def test_resolve_nonexistent_plan(self, tmp_path, monkeypatch):
        """Test resolving a plan that doesn't exist."""
        from agenticcli.commands import session

        (tmp_path / "docs" / "plans" / "live").mkdir(parents=True)
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
        assert "agentic context bootstrap" in prompt

    def test_role_prompt_with_plan(self, tmp_path):
        """Test building a role prompt with plan context."""
        from agenticcli.commands import session

        plan_folder = tmp_path / "260207TA_cli_task_spawn"
        plan_folder.mkdir()

        prompt = session._build_role_prompt("build-python", plan_folder)
        assert "build-python" in prompt
        assert "260207TA_cli_task_spawn" in prompt
        assert "agentic plan task list" in prompt


class TestBuildTaskPrompt:
    """Tests for _build_task_prompt helper."""

    def test_task_prompt_with_valid_task(self, tmp_path):
        """Test building a task prompt from a valid plan file."""
        from agenticcli.commands import session

        plan_folder = tmp_path / "260207TA_test"
        plan_folder.mkdir()

        # Create a plan_build.yml with a task
        plan_file = plan_folder / "plan_build.yml"
        plan_file.write_text("""
phases:
  - name: "Test Phase"
    tasks:
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
        assert "agentic plan task complete" in prompt

    def test_task_prompt_with_invalid_task(self, tmp_path):
        """Test building a task prompt for a nonexistent task."""
        from agenticcli.commands import session

        plan_folder = tmp_path / "260207TA_test"
        plan_folder.mkdir()

        plan_file = plan_folder / "plan_build.yml"
        plan_file.write_text("""
phases:
  - name: "Test Phase"
    tasks:
      - id: "CLI_001"
        name: "Existing task"
        status: "pending"
        description: "A task that exists."
""")

        prompt = session._build_task_prompt("NONEXISTENT", plan_folder)
        assert prompt is None


class TestSpawnWithRoleAndPlan:
    """Tests for spawn with --role and --plan flags."""

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_with_role(self, mock_popen, mock_sessions_dir, tmp_path, monkeypatch, capsys):
        """Test spawn with --role constructs prompt and spawns agent."""
        from agenticcli.commands import session

        # Set up plan folder
        live_dir = tmp_path / "docs" / "plans" / "live"
        plan_dir = live_dir / "260207TA_test"
        plan_dir.mkdir(parents=True)
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

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

        # Verify Popen was called with a prompt containing the role
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        # The last element should be the prompt
        prompt_text = cmd[-1]
        assert "build-python" in prompt_text

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_with_task(self, mock_popen, mock_sessions_dir, tmp_path, monkeypatch, capsys):
        """Test spawn with --task loads task context and spawns agent."""
        from agenticcli.commands import session

        # Set up plan folder with task
        live_dir = tmp_path / "docs" / "plans" / "live"
        plan_dir = live_dir / "260207TA_test"
        plan_dir.mkdir(parents=True)

        plan_file = plan_dir / "plan_build.yml"
        plan_file.write_text("""
phases:
  - name: "Build Phase"
    tasks:
      - id: "CLI_001"
        name: "Add feature"
        status: "pending"
        description: "Add a new feature."
        target_files:
          - src/main.py
""")

        monkeypatch.setattr(Path, "cwd", lambda: tmp_path)

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

        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        prompt_text = cmd[-1]
        assert "CLI_001" in prompt_text
        assert "Add feature" in prompt_text

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

        (tmp_path / "docs" / "plans" / "live").mkdir(parents=True)
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
        assert "Plan folder not found" in captured.err

    def test_spawn_invalid_task_id(self, mock_sessions_dir, tmp_path, monkeypatch, capsys):
        """Test that spawn with invalid task ID fails gracefully."""
        from agenticcli.commands import session

        live_dir = tmp_path / "docs" / "plans" / "live"
        plan_dir = live_dir / "260207TA_test"
        plan_dir.mkdir(parents=True)

        plan_file = plan_dir / "plan_build.yml"
        plan_file.write_text("""
phases:
  - name: "Build Phase"
    tasks:
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
        assert "Task not found" in captured.err

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

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_spawn_prompt_still_works_standalone(self, mock_popen, mock_sessions_dir, capsys):
        """Test that --prompt still works without --role or --task."""
        from agenticcli.commands import session

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
        assert "Hello world" in cmd
