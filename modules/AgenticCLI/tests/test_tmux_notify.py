"""Tests for tmux notification display utilities.

Tests notify_question_window() and display_tmux_message() behaviour
under various tmux presence and subprocess outcomes.
"""

import subprocess
from unittest.mock import patch

import pytest

from agenticcli.utils import tmux_notify


class TestNotifyQuestionWindowNotInTmux:
    """Tests for when TMUX env var is not set."""

    def test_notify_question_window_not_in_tmux(self, monkeypatch):
        """Returns False and makes no subprocess calls when not in tmux."""
        monkeypatch.delenv("TMUX", raising=False)

        with patch("subprocess.run") as mock_run:
            result = tmux_notify.notify_question_window(question_count=1)

        assert result is False
        mock_run.assert_not_called()


class TestNotifyQuestionWindowInTmux:
    """Tests for when TMUX env var is set."""

    def test_notify_question_window_in_tmux_success(self, monkeypatch):
        """Returns True when in tmux and subprocess.run succeeds."""
        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")

        with patch("subprocess.run") as mock_run:
            result = tmux_notify.notify_question_window(question_count=1)

        assert result is True
        # At minimum the display-message call should have been made
        assert mock_run.call_count >= 1

    def test_notify_question_window_in_tmux_failure(self, monkeypatch):
        """Returns False (graceful degradation) when subprocess.run raises CalledProcessError."""
        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "tmux"),
        ):
            result = tmux_notify.notify_question_window(question_count=1)

        assert result is False

    def test_message_text_single_question(self, monkeypatch):
        """Single question uses singular message text."""
        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")

        calls = []

        def capture_run(*args, **kwargs):
            calls.append(args[0] if args else kwargs.get("args", []))

        with patch("subprocess.run", side_effect=capture_run):
            tmux_notify.notify_question_window(question_count=1)

        # First call should be the display-message command
        display_call = calls[0]
        assert "display-message" in display_call
        message = display_call[-1]
        assert "New question pending" in message

    def test_message_text_multiple_questions(self, monkeypatch):
        """Multiple questions uses plural message text with count."""
        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")

        calls = []

        def capture_run(*args, **kwargs):
            calls.append(args[0] if args else kwargs.get("args", []))

        with patch("subprocess.run", side_effect=capture_run):
            tmux_notify.notify_question_window(question_count=5)

        display_call = calls[0]
        message = display_call[-1]
        assert "5 questions pending" in message


class TestDisplayTmuxMessage:
    """Tests for display_tmux_message()."""

    def test_display_not_in_tmux(self, monkeypatch):
        """Does nothing when not in tmux."""
        monkeypatch.delenv("TMUX", raising=False)

        with patch("subprocess.run") as mock_run:
            tmux_notify.display_tmux_message("hello")

        mock_run.assert_not_called()

    def test_display_in_tmux_calls_subprocess(self, monkeypatch):
        """Calls tmux display-message with correct arguments."""
        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")

        with patch("subprocess.run") as mock_run:
            tmux_notify.display_tmux_message("test message", duration_ms=3000)

        mock_run.assert_called_once_with(
            ["tmux", "display-message", "-d", "3000", "test message"],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_display_handles_file_not_found(self, monkeypatch):
        """Silently handles FileNotFoundError when tmux binary missing."""
        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")

        with patch("subprocess.run", side_effect=FileNotFoundError):
            # Should not raise
            tmux_notify.display_tmux_message("hello")

    def test_display_handles_called_process_error(self, monkeypatch):
        """Silently handles CalledProcessError."""
        monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,12345,0")

        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "tmux")):
            # Should not raise
            tmux_notify.display_tmux_message("hello")


class TestDeprecatedFunctionsRemoved:
    """Tests that old ntfy-based functions no longer exist."""

    def test_deprecated_functions_removed(self):
        """Old notification functions should not be exposed by tmux_notify module."""
        assert not hasattr(tmux_notify, "notify_questions_in_tmux")
        assert not hasattr(tmux_notify, "clear_notification_pane")
        assert not hasattr(tmux_notify, "send_ntfy")
        assert not hasattr(tmux_notify, "NtfyReplyPoller")
