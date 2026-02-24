"""Tmux notification display utilities.

Provides functions for alerting users about pending questions via tmux
status bar messages. Uses a dedicated tmux window approach rather than
split panes.
"""

import subprocess

from agenticcli.utils.tmux import is_in_tmux


def display_tmux_message(message: str, duration_ms: int = 5000) -> None:
    """Display a message in the tmux status bar.

    Shows a temporary message in the tmux status bar for the specified duration.
    This is a best-effort operation - failures are silently ignored.

    Args:
        message: Message text to display
        duration_ms: Display duration in milliseconds (default: 5000 = 5 seconds)

    Example:
        >>> display_tmux_message("3 pending questions - check pane", duration_ms=3000)
    """
    if not is_in_tmux():
        return

    try:
        subprocess.run(
            ["tmux", "display-message", "-d", str(duration_ms), message],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Best effort - silently ignore failures
        pass


def notify_question_window(question_count: int = 0) -> bool:
    """Alert the user that questions are pending via tmux status bar.

    Sends a tmux display-message and optionally highlights the 'questions'
    window in the status bar. This replaces the old split-pane notification
    approach.

    Args:
        question_count: Number of pending questions (for the message text).

    Returns:
        True if notification was sent, False if not in tmux or failed.
    """
    if not is_in_tmux():
        return False

    if question_count > 1:
        message = f"{question_count} questions pending - switch to [questions] window"
    else:
        message = "New question pending - switch to [questions] window"

    try:
        subprocess.run(
            ["tmux", "display-message", "-d", "5000", message],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        # If the primary notification fails, report failure to caller.
        return False

    # Best-effort: highlight the questions window via monitor-activity.
    # Failures here are silently ignored; the primary notification already succeeded.
    try:
        subprocess.run(
            ["tmux", "set-option", "-t", "questions", "monitor-activity", "on"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        pass

    return True
