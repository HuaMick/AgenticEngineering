"""Tmux session and pane utilities.

Provides helpers for detecting tmux, managing sessions, and controlling panes.
"""

import os
import subprocess
from typing import Optional


def is_in_tmux() -> bool:
    """Check if currently running inside a tmux session.

    Returns:
        True if running in tmux (TMUX environment variable is set), False otherwise.
    """
    return "TMUX" in os.environ


def get_current_session_name() -> Optional[str]:
    """Get the name of the current tmux session.

    First tries to parse the TMUX environment variable, then falls back
    to running `tmux display-message -p '#S'` if in a tmux session.

    Returns:
        Session name if in a tmux session, None otherwise.
    """
    if not is_in_tmux():
        return None

    # Try to use tmux command to get session name
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_session_info(session_name: Optional[str] = None) -> Optional[dict]:
    """Get detailed information about a tmux session.

    Args:
        session_name: Name of the session to query. If None, uses current session.

    Returns:
        Dictionary with session details (name, windows, panes, etc.) or None if
        session not found or tmux not available.
    """
    # If no session name provided, get current session
    if session_name is None:
        session_name = get_current_session_name()
        if session_name is None:
            return None

    try:
        # Get session info using tmux list-sessions
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            check=True,
        )
        sessions = result.stdout.strip().split("\n")
        if session_name not in sessions:
            return None

        # Get detailed info: windows and panes count
        windows_result = subprocess.run(
            ["tmux", "list-windows", "-t", session_name, "-F", "#{window_name}"],
            capture_output=True,
            text=True,
            check=True,
        )
        windows = windows_result.stdout.strip().split("\n") if windows_result.stdout.strip() else []

        panes_result = subprocess.run(
            ["tmux", "list-panes", "-t", session_name, "-a", "-F", "#{pane_id}"],
            capture_output=True,
            text=True,
            check=True,
        )
        panes = panes_result.stdout.strip().split("\n") if panes_result.stdout.strip() else []

        return {
            "name": session_name,
            "windows": windows,
            "window_count": len(windows),
            "panes": panes,
            "pane_count": len(panes),
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def session_exists(session_name: str) -> bool:
    """Check if a named tmux session exists.

    Args:
        session_name: Name of the session to check.

    Returns:
        True if session exists, False otherwise or if tmux not available.
    """
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
            check=False,  # Don't raise on non-zero exit
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def kill_session(session_name: str) -> bool:
    """Kill a named tmux session.

    Args:
        session_name: Name of the session to kill.

    Returns:
        True if session was killed, False otherwise or if tmux not available.
    """
    try:
        result = subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_pane_by_title(title: str) -> Optional[str]:
    """Find a pane by its title.

    Args:
        title: The pane title to search for.

    Returns:
        Pane ID (e.g., "%1") if found, None otherwise.
    """
    if not is_in_tmux():
        return None

    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id}:#{pane_title}"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.strip().split("\n"):
            if ":" in line:
                pane_id, pane_title = line.split(":", 1)
                if pane_title == title:
                    return pane_id
        return None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_or_create_notification_pane(pane_name: str = "questions") -> str:
    """Get or create a notification pane with the specified name.

    Checks if a pane with the given title exists. If not, creates a new
    split window and sets its title.

    Args:
        pane_name: Name/title for the notification pane.

    Returns:
        Pane ID of the existing or newly created pane.

    Raises:
        RuntimeError: If not in a tmux session or tmux operations fail.
    """
    if not is_in_tmux():
        raise RuntimeError("Not running in a tmux session")

    # Check if pane already exists
    existing_pane = get_pane_by_title(pane_name)
    if existing_pane:
        return existing_pane

    try:
        # Create a new split window (vertical split, 30% width on the right)
        result = subprocess.run(
            ["tmux", "split-window", "-h", "-p", "30", "-P", "-F", "#{pane_id}"],
            capture_output=True,
            text=True,
            check=True,
        )
        new_pane_id = result.stdout.strip()

        # Set the pane title
        subprocess.run(
            ["tmux", "select-pane", "-t", new_pane_id, "-T", pane_name],
            capture_output=True,
            text=True,
            check=True,
        )

        return new_pane_id
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"Failed to create notification pane: {e}")


def send_to_pane(pane_id: str, content: str, clear: bool = True) -> None:
    """Send content to a specific tmux pane.

    Args:
        pane_id: ID of the target pane (e.g., "%1").
        content: Text content to send to the pane.
        clear: If True, clear the pane before sending content.

    Raises:
        RuntimeError: If not in a tmux session or tmux operations fail.
    """
    if not is_in_tmux():
        raise RuntimeError("Not running in a tmux session")

    try:
        # Clear the pane if requested
        if clear:
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "C-l"],
                capture_output=True,
                text=True,
                check=True,
            )

        # Send the content line by line to avoid issues with special characters
        for line in content.split("\n"):
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "-l", line],
                capture_output=True,
                text=True,
                check=True,
            )
            # Send Enter after each line
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "Enter"],
                capture_output=True,
                text=True,
                check=True,
            )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"Failed to send content to pane: {e}")
