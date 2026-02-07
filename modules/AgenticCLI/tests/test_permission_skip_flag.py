"""Tests for --dangerously-skip-permissions flag.

Tests to verify that the --dangerously-skip-permissions flag is properly
parsed and passed to Claude CLI for both session spawn and loop start commands.
"""

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
def loops_dir(tmp_path):
    """Create a temporary loops directory."""
    loops_dir = tmp_path / ".agentic" / "loops"
    loops_dir.mkdir(parents=True)
    return loops_dir


@pytest.fixture
def mock_sessions_dir(sessions_dir, monkeypatch):
    """Patch _get_sessions_dir to use temp directory."""
    from agenticcli.commands import session

    monkeypatch.setattr(session, "_get_sessions_dir", lambda: sessions_dir)
    logs_dir = sessions_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(session, "_get_logs_dir", lambda: logs_dir)
    return sessions_dir


@pytest.fixture
def mock_loops_dir(loops_dir, monkeypatch):
    """Patch _get_loops_dir to use temp directory."""
    from agenticcli.commands import loop

    monkeypatch.setattr(loop, "_get_loops_dir", lambda: loops_dir)
    return loops_dir


class TestSessionSpawnPermissionFlag:
    """Tests for --dangerously-skip-permissions flag in session spawn."""

    def test_session_spawn_accepts_flag(self, mock_sessions_dir):
        """Test that session spawn accepts the flag in arguments."""
        from agenticcli.commands import session

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=5,
            background=False,
            directory=None,
            dangerously_skip_permissions=True,
        )

        # Verify the flag is present in args
        assert hasattr(args, "dangerously_skip_permissions")
        assert args.dangerously_skip_permissions is True

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_session_spawn_passes_flag_to_claude(
        self, mock_popen, mock_sessions_dir
    ):
        """Test that session spawn passes flag to claude subprocess."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("Success", "")
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=5,
            background=False,
            directory=None,
            dangerously_skip_permissions=True,
        )

        session.cmd_spawn(args)

        # Verify Popen was called with the flag
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]

        assert "claude" in cmd
        assert "--dangerously-skip-permissions" in cmd

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_session_spawn_without_flag(self, mock_popen, mock_sessions_dir):
        """Test that session spawn does not pass flag when not set."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("Success", "")
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=5,
            background=False,
            directory=None,
            dangerously_skip_permissions=False,
        )

        session.cmd_spawn(args)

        # Verify Popen was called without the flag
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]

        assert "claude" in cmd
        assert "--dangerously-skip-permissions" not in cmd

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_session_spawn_background_with_flag(
        self, mock_popen, mock_sessions_dir
    ):
        """Test that background session spawn passes flag correctly."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=5,
            background=True,
            directory=None,
            dangerously_skip_permissions=True,
        )

        session.cmd_spawn(args)

        # Verify Popen was called with the flag
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]

        assert "claude" in cmd
        assert "--dangerously-skip-permissions" in cmd


class TestLoopStartPermissionFlag:
    """Tests for --dangerously-skip-permissions flag in loop start."""

    def test_loop_start_accepts_flag(self, mock_loops_dir):
        """Test that loop start accepts the flag in arguments."""
        from agenticcli.commands import loop

        args = SimpleNamespace(
            prompt="Test loop task",
            prompt_file=None,
            entrypoint=None,
            max_iterations=10,
            completion_promise=None,
            background=False,
            directory=None,
            output=None,
            dangerously_skip_permissions=True,
        )

        # Verify the flag is present in args
        assert hasattr(args, "dangerously_skip_permissions")
        assert args.dangerously_skip_permissions is True

    @patch("agenticcli.commands.loop.subprocess.run")
    def test_loop_start_passes_flag_to_claude(
        self, mock_run, mock_loops_dir
    ):
        """Test that loop start passes flag to claude subprocess."""
        from agenticcli.commands import loop

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        args = SimpleNamespace(
            prompt="Test loop task",
            prompt_file=None,
            entrypoint=None,
            max_iterations=10,
            completion_promise=None,
            background=False,
            directory=None,
            output=None,
            dangerously_skip_permissions=True,
        )

        loop.cmd_start(args)

        # Verify run was called with the flag
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]

        assert "claude" in cmd
        assert "--dangerously-skip-permissions" in cmd

    @patch("agenticcli.commands.loop.subprocess.run")
    def test_loop_start_without_flag(self, mock_run, mock_loops_dir):
        """Test that loop start does not pass flag when not set."""
        from agenticcli.commands import loop

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        args = SimpleNamespace(
            prompt="Test loop task",
            prompt_file=None,
            entrypoint=None,
            max_iterations=10,
            completion_promise=None,
            background=False,
            directory=None,
            output=None,
            dangerously_skip_permissions=False,
        )

        loop.cmd_start(args)

        # Verify run was called without the flag
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd = call_args[0][0]

        assert "claude" in cmd
        assert "--dangerously-skip-permissions" not in cmd

    @patch("agenticcli.commands.loop.subprocess.Popen")
    def test_loop_start_background_with_flag(
        self, mock_popen, mock_loops_dir
    ):
        """Test that background loop start passes flag correctly."""
        from agenticcli.commands import loop

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test loop task",
            prompt_file=None,
            entrypoint=None,
            max_iterations=10,
            completion_promise=None,
            background=True,
            directory=None,
            output=None,
            dangerously_skip_permissions=True,
        )

        loop.cmd_start(args)

        # Verify Popen was called with the flag
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]

        assert "claude" in cmd
        assert "--dangerously-skip-permissions" in cmd


class TestPermissionFlagIntegration:
    """Integration tests for permission flag across commands."""

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_flag_position_in_command(self, mock_popen, mock_sessions_dir):
        """Test that flag is positioned correctly in the command."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("Success", "")
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test task",
            max_turns=5,
            background=False,
            directory=None,
            dangerously_skip_permissions=True,
        )

        session.cmd_spawn(args)

        call_args = mock_popen.call_args
        cmd = call_args[0][0]

        # Flag should come after 'claude' and '--print' but before prompt
        claude_idx = cmd.index("claude")
        flag_idx = cmd.index("--dangerously-skip-permissions")
        prompt_idx = cmd.index("Test task")

        assert claude_idx < flag_idx < prompt_idx
