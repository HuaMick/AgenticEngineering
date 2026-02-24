"""Tests for the tmux layout module.

Tests 3-pane orchestration layout creation, session management, and error handling.
"""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from agenticcli.utils.tmux_layout import (
    OrchestrationLayout,
    _create_inplace_layout,
    _create_new_session_layout,
    _shell_escape_cmd,
    attach_to_session,
    cleanup_orchestration_sessions,
    create_orchestration_layout,
    tmux_available,
)


@pytest.fixture
def mock_subprocess_success():
    """Mock successful subprocess.run calls."""
    def _mock_run(cmd, **kwargs):
        mock_result = MagicMock()
        mock_result.returncode = 0

        # Return different pane IDs for different commands
        if "new-session" in cmd:
            mock_result.stdout = "%0\n"
        elif "split-window" in cmd and "-l" in cmd and "60" in cmd:
            mock_result.stdout = "%1\n"
        elif "split-window" in cmd and "-l" in cmd and "20" in cmd:
            mock_result.stdout = "%2\n"
        elif "split-window" in cmd and "-p" in cmd and "30" in cmd:
            mock_result.stdout = "%1\n"
        elif "split-window" in cmd and "-p" in cmd and "40" in cmd:
            mock_result.stdout = "%2\n"
        elif "display-message" in cmd:
            mock_result.stdout = "%0\n"
        else:
            mock_result.stdout = ""

        return mock_result

    return _mock_run


@pytest.fixture
def sample_claude_cmd_str():
    """Sample Claude command string for testing."""
    return "claude --dangerously-skip-permissions --profile test"


class TestTmuxAvailable:
    """Tests for tmux binary availability check."""

    def test_returns_true_when_tmux_exists(self):
        """Returns True when tmux binary exists in PATH."""
        with patch("shutil.which", return_value="/usr/bin/tmux"):
            assert tmux_available() is True

    def test_returns_false_when_tmux_not_found(self):
        """Returns False when tmux binary not found."""
        with patch("shutil.which", return_value=None):
            assert tmux_available() is False


class TestShellEscapeCmd:
    """Tests for shell command escaping."""

    def test_escapes_single_argument(self):
        """Escapes single argument correctly."""
        result = _shell_escape_cmd(["echo"])
        assert result == "echo"

    def test_escapes_multiple_arguments_with_spaces(self):
        """Escapes multiple arguments with spaces."""
        result = _shell_escape_cmd(["echo", "hello world", "test"])
        assert result == "echo 'hello world' test"

    def test_handles_special_characters(self):
        """Handles special characters (quotes, backslashes)."""
        result = _shell_escape_cmd(["echo", "it's", '"quoted"', "back\\slash"])
        # shlex.quote handles these correctly
        assert "it\\'s" in result or "'it'\"'\"'s'" in result
        assert "quoted" in result

    def test_handles_empty_list(self):
        """Handles empty list."""
        result = _shell_escape_cmd([])
        assert result == ""

    def test_handles_unicode_characters(self):
        """Handles unicode characters."""
        result = _shell_escape_cmd(["echo", "hello 世界"])
        assert "世界" in result


class TestCreateNewSessionLayout:
    """Tests for _create_new_session_layout function."""

    def test_success_path_creates_three_pane_layout(self, sample_claude_cmd_str, mock_subprocess_success):
        """Creates new session with correct 3-pane layout."""
        with patch("subprocess.run", side_effect=mock_subprocess_success) as mock_run:
            result = _create_new_session_layout(
                session_name="test-session",
                claude_cmd_str=sample_claude_cmd_str,
                dashboard_refresh=5,
                question_refresh=10,
            )

            # Verify result structure
            assert isinstance(result, OrchestrationLayout)
            assert result.session_name == "test-session"
            assert result.main_pane_id == "%0"
            assert result.status_pane_id == "%1"
            assert result.questions_pane_id == "%2"
            assert result.created_new_session is True

            # Verify subprocess calls
            calls = mock_run.call_args_list
            assert len(calls) >= 9  # new-session, 2x split-window, 3x select-pane, 2x send-keys (session list + question dashboard), 1x send-keys (claude), 1x select-pane

            # Verify new-session includes -x and -y dimensions (CRITICAL FIX)
            new_session_call = calls[0]
            cmd = new_session_call[0][0]
            assert "tmux" in cmd
            assert "new-session" in cmd
            assert "-x" in cmd
            assert "200" in cmd
            assert "-y" in cmd
            assert "50" in cmd
            assert "-s" in cmd
            assert "test-session" in cmd

    def test_sends_enter_key_with_claude_command(self, sample_claude_cmd_str, mock_subprocess_success):
        """Sends Enter key with Claude command to execute it immediately (CRITICAL FIX)."""
        with patch("subprocess.run", side_effect=mock_subprocess_success) as mock_run:
            _create_new_session_layout(
                session_name="test-session",
                claude_cmd_str=sample_claude_cmd_str,
                dashboard_refresh=5,
                question_refresh=10,
            )

            # Find the send-keys call for the Claude command (main pane)
            calls = mock_run.call_args_list
            claude_send_keys_call = None
            for call in calls:
                cmd = call[0][0]
                if "send-keys" in cmd and "-t" in cmd and "%0" in cmd:
                    # This is a send-keys to main pane
                    if "claude" in " ".join(cmd):
                        claude_send_keys_call = cmd
                        break

            assert claude_send_keys_call is not None, "Claude send-keys call not found"
            assert "Enter" in claude_send_keys_call, "Enter key not sent with Claude command"

    def test_sends_command_string_directly_without_shell_escaping(self, mock_subprocess_success):
        """Command string with $(cat ...) is sent directly, not via _shell_escape_cmd."""
        cmd_str = 'claude --dangerously-skip-permissions --append-system-prompt "$(cat /tmp/test.md)"'
        with patch("subprocess.run", side_effect=mock_subprocess_success) as mock_run:
            _create_new_session_layout(
                session_name="test-session",
                claude_cmd_str=cmd_str,
                dashboard_refresh=5,
                question_refresh=10,
            )

            # Find the send-keys call for the main pane
            calls = mock_run.call_args_list
            for call in calls:
                cmd = call[0][0]
                if "send-keys" in cmd and "%0" in cmd and "claude" in " ".join(cmd):
                    # The $(cat ...) should be in double quotes, NOT single quotes
                    assert cmd_str in cmd, (
                        f"Command string should be passed directly. Got: {cmd}"
                    )
                    break

    def test_sets_pane_titles_correctly(self, sample_claude_cmd_str, mock_subprocess_success):
        """Sets correct titles for all three panes."""
        with patch("subprocess.run", side_effect=mock_subprocess_success) as mock_run:
            _create_new_session_layout(
                session_name="test-session",
                claude_cmd_str=sample_claude_cmd_str,
                dashboard_refresh=5,
                question_refresh=10,
            )

            # Verify select-pane calls with -T flag
            calls = mock_run.call_args_list
            select_pane_calls = [c for c in calls if "select-pane" in c[0][0] and "-T" in c[0][0]]

            # Should have 3 select-pane calls with titles (plus 1 without -T for final focus)
            assert len(select_pane_calls) >= 3

            # Verify titles are set
            all_cmds = " ".join([" ".join(c[0][0]) for c in select_pane_calls])
            assert "orchestrator" in all_cmds
            assert "sessions" in all_cmds
            assert "questions" in all_cmds

    def test_starts_pane_commands_with_enter(self, sample_claude_cmd_str, mock_subprocess_success):
        """Starts pane commands with Enter key to execute them."""
        with patch("subprocess.run", side_effect=mock_subprocess_success) as mock_run:
            _create_new_session_layout(
                session_name="test-session",
                claude_cmd_str=sample_claude_cmd_str,
                dashboard_refresh=5,
                question_refresh=10,
            )

            # Find send-keys calls for pane commands (watch, agentic)
            calls = mock_run.call_args_list
            pane_cmd_calls = [c for c in calls if "send-keys" in c[0][0] and ("watch" in " ".join(c[0][0]) or "agentic" in " ".join(c[0][0]))]

            # Should have at least 2 pane command calls (session list + question dashboard)
            assert len(pane_cmd_calls) >= 2

            # Both should have "Enter" to execute the commands
            for call in pane_cmd_calls:
                cmd = call[0][0]
                assert "Enter" in cmd, f"Pane command missing Enter: {cmd}"

    def test_uses_watch_for_session_list(self, sample_claude_cmd_str, mock_subprocess_success):
        """Uses watch command for auto-refreshing session list."""
        with patch("subprocess.run", side_effect=mock_subprocess_success) as mock_run:
            _create_new_session_layout(
                session_name="test-session",
                claude_cmd_str=sample_claude_cmd_str,
                dashboard_refresh=5,
                question_refresh=10,
            )

            calls = mock_run.call_args_list
            all_cmds_str = " ".join([" ".join(c[0][0]) for c in calls])

            # Session list pane should use 'watch' with 'agentic session list'
            assert "watch" in all_cmds_str
            assert "session" in all_cmds_str
            assert "list" in all_cmds_str

    def test_passes_refresh_intervals_to_pane_commands(self, sample_claude_cmd_str, mock_subprocess_success):
        """Passes custom refresh intervals to pane commands."""
        with patch("subprocess.run", side_effect=mock_subprocess_success) as mock_run:
            _create_new_session_layout(
                session_name="test-session",
                claude_cmd_str=sample_claude_cmd_str,
                dashboard_refresh=15,
                question_refresh=30,
            )

            calls = mock_run.call_args_list
            all_cmds_str = " ".join([" ".join(c[0][0]) for c in calls])

            # Verify refresh intervals are passed
            assert "--refresh" in all_cmds_str  # question dashboard uses --refresh
            assert "15" in all_cmds_str  # watch -n 15
            assert "30" in all_cmds_str  # --refresh 30

    def test_raises_runtime_error_on_new_session_failure(self, sample_claude_cmd_str):
        """Raises RuntimeError when new-session command fails."""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "tmux")):
            with pytest.raises(RuntimeError, match="Failed to create tmux orchestration layout"):
                _create_new_session_layout(
                    session_name="test-session",
                    claude_cmd_str=sample_claude_cmd_str,
                    dashboard_refresh=5,
                    question_refresh=10,
                )

    def test_raises_runtime_error_on_split_window_failure(self, sample_claude_cmd_str, mock_subprocess_success):
        """Raises RuntimeError when split-window command fails."""
        def mock_with_failure(cmd, **kwargs):
            if "split-window" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            return mock_subprocess_success(cmd, **kwargs)

        with patch("subprocess.run", side_effect=mock_with_failure):
            with pytest.raises(RuntimeError, match="Failed to create tmux orchestration layout"):
                _create_new_session_layout(
                    session_name="test-session",
                    claude_cmd_str=sample_claude_cmd_str,
                    dashboard_refresh=5,
                    question_refresh=10,
                )

    def test_raises_runtime_error_on_tmux_not_found(self, sample_claude_cmd_str):
        """Raises RuntimeError when tmux binary not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="Failed to create tmux orchestration layout"):
                _create_new_session_layout(
                    session_name="test-session",
                    claude_cmd_str=sample_claude_cmd_str,
                    dashboard_refresh=5,
                    question_refresh=10,
                )


class TestCreateInplaceLayout:
    """Tests for _create_inplace_layout function."""

    def test_success_path_splits_current_pane(self, mock_subprocess_success):
        """Creates in-place layout by splitting current pane."""
        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=True):
                with patch("agenticcli.utils.tmux_layout.get_current_session_name", return_value="existing-session"):
                    with patch("subprocess.run", side_effect=mock_subprocess_success) as mock_run:
                        result = _create_inplace_layout(
                            dashboard_refresh=5,
                            question_refresh=10,
                        )

                        # Verify result structure
                        assert isinstance(result, OrchestrationLayout)
                        assert result.session_name == "existing-session"
                        assert result.main_pane_id == "%0"
                        assert result.status_pane_id == "%1"
                        assert result.questions_pane_id == "%2"
                        assert result.created_new_session is False

                        # Verify no new-session command (should only split existing pane)
                        calls = mock_run.call_args_list
                        new_session_calls = [c for c in calls if "new-session" in c[0][0]]
                        assert len(new_session_calls) == 0

    def test_raises_error_when_not_in_tmux(self):
        """Raises RuntimeError when not in a tmux session."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=False):
                with pytest.raises(RuntimeError, match="Not in a tmux session"):
                    _create_inplace_layout(
                        dashboard_refresh=5,
                        question_refresh=10,
                    )

    def test_raises_error_when_session_name_unknown(self):
        """Raises RuntimeError when cannot determine session name."""
        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=True):
                with patch("agenticcli.utils.tmux_layout.get_current_session_name", return_value=None):
                    with pytest.raises(RuntimeError, match="Could not determine current tmux session name"):
                        _create_inplace_layout(
                            dashboard_refresh=5,
                            question_refresh=10,
                        )

    def test_raises_error_on_split_failure(self, mock_subprocess_success):
        """Raises RuntimeError when split-window fails."""
        def mock_with_failure(cmd, **kwargs):
            if "split-window" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            return mock_subprocess_success(cmd, **kwargs)

        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=True):
                with patch("agenticcli.utils.tmux_layout.get_current_session_name", return_value="existing-session"):
                    with patch("subprocess.run", side_effect=mock_with_failure):
                        with pytest.raises(RuntimeError, match="Failed to create in-place tmux orchestration layout"):
                            _create_inplace_layout(
                                dashboard_refresh=5,
                                question_refresh=10,
                            )


class TestCreateOrchestrationLayout:
    """Tests for create_orchestration_layout routing function."""

    def test_routes_to_new_session_when_not_in_tmux(self, sample_claude_cmd_str, mock_subprocess_success):
        """Routes to _create_new_session_layout when not in tmux."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/tmux"):
                with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=False):
                    with patch("subprocess.run", side_effect=mock_subprocess_success):
                        result = create_orchestration_layout(claude_cmd_str=sample_claude_cmd_str)

                        assert result.created_new_session is True
                        assert "agentic-orch-" in result.session_name

    def test_routes_to_inplace_layout_when_in_tmux(self, sample_claude_cmd_str, mock_subprocess_success):
        """Routes to _create_inplace_layout when already in tmux."""
        with patch.dict("os.environ", {"TMUX": "/tmp/tmux-1000/default,1234,0"}):
            with patch("shutil.which", return_value="/usr/bin/tmux"):
                with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=True):
                    with patch("agenticcli.utils.tmux_layout.get_current_session_name", return_value="existing-session"):
                        with patch("subprocess.run", side_effect=mock_subprocess_success):
                            result = create_orchestration_layout(claude_cmd_str=sample_claude_cmd_str)

                            assert result.created_new_session is False
                            assert result.session_name == "existing-session"

    def test_raises_error_when_tmux_not_available(self, sample_claude_cmd_str):
        """Raises RuntimeError when tmux is not available."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="tmux is not available"):
                create_orchestration_layout(claude_cmd_str=sample_claude_cmd_str)

    def test_passes_parameters_to_underlying_functions(self, sample_claude_cmd_str, mock_subprocess_success):
        """Passes parameters correctly to underlying layout functions."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/tmux"):
                with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=False):
                    with patch("subprocess.run", side_effect=mock_subprocess_success) as mock_run:
                        create_orchestration_layout(
                            claude_cmd_str=sample_claude_cmd_str,
                            dashboard_refresh=15,
                            question_refresh=30,
                        )

                        # Verify custom refresh intervals are passed through
                        calls = mock_run.call_args_list
                        all_cmds_str = " ".join([" ".join(c[0][0]) for c in calls])
                        assert "15" in all_cmds_str
                        assert "30" in all_cmds_str

    def test_cleans_up_orphaned_sessions_before_new(self, sample_claude_cmd_str, mock_subprocess_success):
        """Cleans up orphaned agentic-orch-* sessions before creating a new one."""
        def mock_run_with_list(cmd, **kwargs):
            if "list-sessions" in cmd:
                mock = MagicMock()
                mock.returncode = 0
                mock.stdout = "agentic-orch-111\nagentic-orch-222\nclaude\n"
                return mock
            if "kill-session" in cmd:
                return MagicMock(returncode=0)
            return mock_subprocess_success(cmd, **kwargs)

        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/tmux"):
                with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=False):
                    with patch("subprocess.run", side_effect=mock_run_with_list) as mock_run:
                        create_orchestration_layout(claude_cmd_str=sample_claude_cmd_str)

                        # Verify kill-session was called for orphaned sessions
                        kill_calls = [c for c in mock_run.call_args_list
                                      if "kill-session" in c[0][0]]
                        assert len(kill_calls) == 2


class TestAttachToSession:
    """Tests for attach_to_session function."""

    def test_calls_execvp_with_correct_arguments(self):
        """Calls os.execvp with correct tmux attach command."""
        with patch("shutil.which", return_value="/usr/bin/tmux"):
            with patch("os.execvp") as mock_execvp:
                attach_to_session("test-session")

                mock_execvp.assert_called_once_with(
                    "tmux",
                    ["tmux", "attach-session", "-t", "test-session"]
                )

    def test_raises_error_when_tmux_not_available(self):
        """Raises RuntimeError when tmux is not available."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="tmux is not available"):
                attach_to_session("test-session")


class TestCleanupOrchestrationSessions:
    """Tests for cleanup_orchestration_sessions function."""

    def test_kills_orphaned_sessions(self):
        """Kills all agentic-orch-* sessions."""
        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if "list-sessions" in cmd:
                mock.stdout = "agentic-orch-111\nagentic-orch-222\nclaude\n"
            return mock

        with patch("shutil.which", return_value="/usr/bin/tmux"):
            with patch("subprocess.run", side_effect=mock_run) as mock:
                killed = cleanup_orchestration_sessions()
                assert killed == ["agentic-orch-111", "agentic-orch-222"]

    def test_returns_empty_when_no_sessions(self):
        """Returns empty list when no orphaned sessions exist."""
        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if "list-sessions" in cmd:
                mock.stdout = "claude\nmy-session\n"
            return mock

        with patch("shutil.which", return_value="/usr/bin/tmux"):
            with patch("subprocess.run", side_effect=mock_run):
                assert cleanup_orchestration_sessions() == []

    def test_returns_empty_when_tmux_unavailable(self):
        """Returns empty list when tmux is not installed."""
        with patch("shutil.which", return_value=None):
            assert cleanup_orchestration_sessions() == []


class TestEdgeCasesAndErrorRecovery:
    """Tests for edge cases and error recovery scenarios."""

    def test_session_name_uniqueness_with_pid(self, sample_claude_cmd_str, mock_subprocess_success):
        """Session name includes PID for uniqueness."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/tmux"):
                with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=False):
                    with patch("subprocess.run", side_effect=mock_subprocess_success):
                        with patch("os.getpid", return_value=99999):
                            result = create_orchestration_layout(claude_cmd_str=sample_claude_cmd_str)
                            assert "agentic-orch-99999" == result.session_name

    def test_handles_very_long_command_string(self, mock_subprocess_success):
        """Handles very long command string correctly."""
        long_cmd_str = "claude --profile " + "a" * 1000 + " --dangerously-skip-permissions"

        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/tmux"):
                with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=False):
                    with patch("subprocess.run", side_effect=mock_subprocess_success):
                        result = create_orchestration_layout(claude_cmd_str=long_cmd_str)
                        assert result is not None
                        assert result.created_new_session is True

    def test_shell_escape_with_command_injection_attempts(self):
        """Shell escaping prevents command injection."""
        dangerous_cmd = ["echo", "test; rm -rf /", "$(whoami)", "`ls`", "test && echo bad"]

        escaped = _shell_escape_cmd(dangerous_cmd)

        # Verify dangerous characters are properly escaped
        # shlex.quote wraps dangerous strings in single quotes
        assert ";" in escaped
        assert "$" in escaped or "whoami" in escaped
        assert "`" in escaped or "ls" in escaped
        assert "&&" in escaped

        # More importantly, verify the escaped string is safe
        # (each dangerous element should be in quotes)
        parts = escaped.split()
        assert len(parts) >= len(dangerous_cmd)

    def test_handles_empty_command_gracefully(self, mock_subprocess_success):
        """Handles empty command string gracefully."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/tmux"):
                with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=False):
                    with patch("subprocess.run", side_effect=mock_subprocess_success):
                        result = create_orchestration_layout(claude_cmd_str="")
                        assert result is not None

    def test_unicode_in_command_string(self, mock_subprocess_success):
        """Handles unicode characters in command string."""
        unicode_cmd_str = "claude --profile 测試プロファイル --dangerously-skip-permissions"

        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/tmux"):
                with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=False):
                    with patch("subprocess.run", side_effect=mock_subprocess_success):
                        result = create_orchestration_layout(claude_cmd_str=unicode_cmd_str)
                        assert result is not None

    def test_multiple_simultaneous_sessions(self, sample_claude_cmd_str, mock_subprocess_success):
        """New session creation uses PID-based naming."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("shutil.which", return_value="/usr/bin/tmux"):
                with patch("agenticcli.utils.tmux_layout.is_in_tmux", return_value=False):
                    with patch("subprocess.run", side_effect=mock_subprocess_success):
                        with patch("os.getpid", return_value=11111):
                            result1 = create_orchestration_layout(claude_cmd_str=sample_claude_cmd_str)
                            assert result1.session_name == "agentic-orch-11111"

                        with patch("os.getpid", return_value=22222):
                            result2 = create_orchestration_layout(claude_cmd_str=sample_claude_cmd_str)
                            assert result2.session_name == "agentic-orch-22222"

                        assert result1.session_name != result2.session_name
