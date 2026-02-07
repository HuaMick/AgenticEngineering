"""Tmux notification display utilities.

Provides functions for displaying question notifications in tmux panes,
including pane management and status bar messages.
"""

import subprocess
from pathlib import Path
from typing import Optional

from agenticcli.utils.tmux import (
    is_in_tmux,
    get_or_create_notification_pane,
    send_to_pane,
    get_pane_by_title,
)
from agenticcli.utils.question_formatter import (
    format_question_notification,
)


def notify_questions_in_tmux(plan_folder: Path, questions: list[dict]) -> bool:
    """Display question notifications in a tmux notification pane.

    Checks if running in tmux, creates or updates the notification pane
    with formatted question list, and displays a status bar message.

    Args:
        plan_folder: Path to the plan folder (for context, not currently used)
        questions: List of pending question dictionaries

    Returns:
        True if notification was successfully displayed in tmux,
        False if not in tmux or operation failed.

    Example:
        >>> from pathlib import Path
        >>> plan_folder = Path("/path/to/plan")
        >>> questions = [{"question_id": "Q001", "severity": "high", ...}]
        >>> if not notify_questions_in_tmux(plan_folder, questions):
        ...     # Fallback to stderr notification
        ...     print("Questions pending - check stderr", file=sys.stderr)
    """
    # Check if in tmux session
    if not is_in_tmux():
        return False

    try:
        # Get or create the notification pane
        pane_id = get_or_create_notification_pane(pane_name="questions")

        # Format the questions
        formatted_content = format_question_notification(questions)

        # Send formatted content to the pane
        send_to_pane(pane_id, formatted_content, clear=True)

        # Display status bar message
        question_count = len(questions)
        if question_count > 0:
            message = f"{question_count} pending question{'s' if question_count != 1 else ''} - check pane"
            display_tmux_message(message)

        return True

    except (RuntimeError, subprocess.CalledProcessError) as e:
        # Tmux operations failed - return False for graceful degradation
        # Could log this if logging is available
        return False


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


def clear_notification_pane() -> bool:
    """Clear the notification pane and show 'No pending questions' message.

    Finds the questions notification pane and displays a message indicating
    all questions have been answered.

    Returns:
        True if pane was found and cleared, False otherwise.

    Example:
        >>> clear_notification_pane()
        True
    """
    if not is_in_tmux():
        return False

    try:
        # Find the questions pane
        pane_id = get_pane_by_title("questions")
        if not pane_id:
            return False

        # Create a "no questions" message
        from agenticcli.utils.question_formatter import format_question_notification
        no_questions_content = format_question_notification([])

        # Send to pane
        send_to_pane(pane_id, no_questions_content, clear=True)

        # Display status message
        display_tmux_message("All questions answered")

        return True

    except (RuntimeError, subprocess.CalledProcessError):
        return False
