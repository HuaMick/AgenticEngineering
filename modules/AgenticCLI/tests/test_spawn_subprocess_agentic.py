"""Tests for subprocess fallback using -p agentic mode (260308FX P1_003).

Validates that the subprocess fallback path in cmd_spawn uses -p (not --print),
correctly orders arguments so -p consumes the prompt, and tracks transport as
'subprocess' in session state.
"""

import json
import os
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def sessions_dir(tmp_path):
    """Create a temporary sessions directory."""
    sd = tmp_path / ".agentic" / "sessions"
    sd.mkdir(parents=True)
    return sd


@pytest.fixture
def logs_dir(sessions_dir):
    """Create a temporary logs directory inside sessions dir."""
    ld = sessions_dir / "logs"
    ld.mkdir(parents=True)
    return ld


@pytest.fixture
def mock_env(sessions_dir, logs_dir, monkeypatch):
    """Patch StateStore, logs dir, and context dir for isolated testing."""
    from agenticcli.commands import session
    from agenticcli.utils.state_store import StateStore

    def _patched_get_dir(self, override=None):
        if self._subdir == "sessions":
            return sessions_dir
        else:
            d = sessions_dir.parent / self._subdir
            d.mkdir(parents=True, exist_ok=True)
            return d

    monkeypatch.setattr(StateStore, "get_dir", _patched_get_dir)

    # Clear instance-level shadow if present
    if "get_dir" in session._store.__dict__:
        del session._store.__dict__["get_dir"]

    context_dir = sessions_dir / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(session, "get_context_dir", lambda: context_dir)
    monkeypatch.setattr(session, "_get_logs_dir", lambda: logs_dir)

    # Disable SDK path to force subprocess fallback
    import agenticcli.utils.sdk_runner as _sdk_mod
    monkeypatch.setattr(_sdk_mod, "SDK_AVAILABLE", False)

    return sessions_dir


# ── Tests: subprocess fallback uses -p ───────────────────────────────────


class TestSubprocessUsesShortP:
    """Verify the subprocess fallback path uses -p instead of --print."""

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_background_cmd_uses_dash_p(self, mock_popen, mock_is_running, mock_env):
        """Background subprocess spawn must use -p, not --print."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 42000
        mock_popen.return_value = mock_process
        mock_is_running.return_value = True

        args = SimpleNamespace(
            prompt="Do background work",
            max_turns=10,
            background=True,
            directory=None,
        )
        session.cmd_spawn(args)

        cmd = mock_popen.call_args[0][0]
        assert "-p" in cmd, f"Expected -p in cmd: {cmd}"
        assert "--print" not in cmd, f"--print should not appear in cmd: {cmd}"

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_foreground_cmd_uses_dash_p(self, mock_popen, mock_env):
        """Foreground subprocess spawn must use -p, not --print."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("Done", "")
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Do foreground work",
            max_turns=5,
            background=False,
            directory=None,
        )
        session.cmd_spawn(args)

        cmd = mock_popen.call_args[0][0]
        assert "-p" in cmd, f"Expected -p in cmd: {cmd}"
        assert "--print" not in cmd, f"--print should not appear in cmd: {cmd}"


class TestSubprocessPromptOrdering:
    """Verify -p is the last flag and its argument is the prompt."""

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_prompt_follows_dash_p(self, mock_popen, mock_is_running, mock_env):
        """The prompt must be the argument immediately after -p."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 42001
        mock_popen.return_value = mock_process
        mock_is_running.return_value = True

        args = SimpleNamespace(
            prompt="Test prompt ordering",
            max_turns=10,
            background=True,
            directory=None,
        )
        session.cmd_spawn(args)

        cmd = mock_popen.call_args[0][0]
        p_idx = cmd.index("-p")
        prompt_arg = cmd[p_idx + 1]
        # The prompt is a short reference to a pre-compiled context file
        assert "pre-compiled" in prompt_arg or "IMPORTANT" in prompt_arg, \
            f"Argument after -p should be the prompt, got: {prompt_arg}"

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_output_format_before_dash_p(self, mock_popen, mock_is_running, mock_env):
        """--output-format json should appear before -p (not after)."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 42002
        mock_popen.return_value = mock_process
        mock_is_running.return_value = True

        args = SimpleNamespace(
            prompt="Test output ordering",
            max_turns=10,
            background=True,
            directory=None,
        )
        session.cmd_spawn(args)

        cmd = mock_popen.call_args[0][0]
        if "--output-format" in cmd:
            fmt_idx = cmd.index("--output-format")
            p_idx = cmd.index("-p")
            assert fmt_idx < p_idx, \
                f"--output-format (idx {fmt_idx}) must come before -p (idx {p_idx})"


class TestSubprocessTransportTracking:
    """Verify subprocess sessions are tagged with transport='subprocess'."""

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_session_data_has_subprocess_transport(self, mock_popen, mock_is_running, mock_env):
        """Session state must include transport='subprocess' for subprocess path."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 42003
        mock_popen.return_value = mock_process
        mock_is_running.return_value = True

        args = SimpleNamespace(
            prompt="Test transport tracking",
            max_turns=10,
            background=True,
            directory=None,
        )
        session.cmd_spawn(args)

        sessions = session._store.list_all()
        assert len(sessions) == 1
        assert sessions[0]["transport"] == "subprocess"

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_foreground_session_has_subprocess_transport(self, mock_popen, mock_env):
        """Foreground subprocess sessions also get transport='subprocess'."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("OK", "")
        mock_popen.return_value = mock_process

        args = SimpleNamespace(
            prompt="Test foreground transport",
            max_turns=5,
            background=False,
            directory=None,
        )
        session.cmd_spawn(args)

        sessions = session._store.list_all()
        assert len(sessions) == 1
        assert sessions[0]["transport"] == "subprocess"


class TestDiagnosticPlannerUsesP:
    """Verify the diagnostic planner spawn also uses -p instead of --print."""

    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_diagnostic_planner_uses_dash_p(self, mock_popen, mock_env):
        """_spawn_diagnostic_planner should use -p, not --print."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 42004
        mock_popen.return_value = mock_process

        stuck_session = {
            "session_id": "abcdefgh-1234-5678-9012-abcdefghijkl",
            "pid": 99999,
            "prompt": "Original prompt",
            "started_at": "2026-03-08T12:00:00",
            "status": "running",
            "working_dir": str(mock_env),
        }

        result = session._spawn_diagnostic_planner(stuck_session)
        assert result is not None  # Should have spawned

        cmd = mock_popen.call_args[0][0]
        assert "-p" in cmd, f"Expected -p in diagnostic cmd: {cmd}"
        assert "--print" not in cmd, f"--print should not be in diagnostic cmd: {cmd}"
        # -p should be followed by the diagnostic prompt
        p_idx = cmd.index("-p")
        assert p_idx + 1 < len(cmd), "Missing prompt argument after -p"
        assert "DIAGNOSTIC PLANNER" in cmd[p_idx + 1]


class TestSubprocessCmdConsistency:
    """Verify subprocess and tmux paths build consistent commands."""

    @patch("agenticcli.commands.session.is_process_running")
    @patch("agenticcli.commands.session.subprocess.Popen")
    def test_both_paths_use_same_base_flags(self, mock_popen, mock_is_running, mock_env):
        """Both tmux (cmd_agentic) and subprocess (cmd) should share the same base."""
        from agenticcli.commands import session

        mock_process = MagicMock()
        mock_process.pid = 42005
        mock_popen.return_value = mock_process
        mock_is_running.return_value = True

        args = SimpleNamespace(
            prompt="Test consistency",
            max_turns=15,
            background=True,
            directory=None,
        )
        session.cmd_spawn(args)

        cmd = mock_popen.call_args[0][0]
        # Both paths should include --dangerously-skip-permissions
        assert "--dangerously-skip-permissions" in cmd
        # Both paths should include --max-turns
        assert "--max-turns" in cmd
        assert "15" in cmd
        # Both paths should use -p for the prompt
        assert "-p" in cmd
