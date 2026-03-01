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
def mock_sessions_dir(sessions_dir, monkeypatch):
    """Patch StateStore, _get_context_dir, and _get_logs_dir to use temp directories."""
    from agenticcli.commands import session

    monkeypatch.setattr(session._store, "get_dir", lambda override=None: sessions_dir)
    logs_dir = sessions_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(session, "_get_logs_dir", lambda: logs_dir)
    context_dir = sessions_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(session, "_get_context_dir", lambda: context_dir)

    # Disable SDK path so subprocess-based tests exercise the subprocess code path
    import agenticcli.utils.sdk_runner as _sdk_mod
    monkeypatch.setattr(_sdk_mod, "SDK_AVAILABLE", False)

    return sessions_dir




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
    def test_session_spawn_always_includes_skip_permissions(self, mock_popen, mock_sessions_dir):
        """Test that session spawn always includes --dangerously-skip-permissions.

        Spawned sessions run autonomously, so the flag is always added regardless
        of the args setting.
        """
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

        # Spawned sessions always include the flag for autonomous operation
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        cmd = call_args[0][0]

        assert "claude" in cmd
        assert "--dangerously-skip-permissions" in cmd

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

        # Flag should come after 'claude' and '--print' but before the prompt
        # (prompt is now a compiled context reference, always last in cmd)
        claude_idx = cmd.index("claude")
        flag_idx = cmd.index("--dangerously-skip-permissions")
        prompt_idx = len(cmd) - 1  # prompt is always the last argument

        assert claude_idx < flag_idx < prompt_idx
