"""Tmux orchestration layout utilities.

Provides 3-pane layout for orchestration UI:
- Main pane (70%): interactive Claude orchestrator (auto-executed)
- Status pane (30% x 60%): live session dashboard
- Questions pane (30% x 40%): pending questions dashboard

The layout creation requires tmux 2.3+ for pane titles and handles both:
- New session creation: creates detached session with explicit dimensions (-x/-y)
  and absolute column/row splits (-l) for WSL2/tmux 3.4 compatibility
- In-place layout: splits current pane when already in tmux

All dashboard and orchestrator commands are executed immediately upon layout creation.
"""

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

from agenticcli.utils.tmux import get_current_session_name, is_in_tmux


@dataclass
class OrchestrationLayout:
    """Layout information for an orchestration tmux session.

    Attributes:
        session_name: Name of the tmux session.
        main_pane_id: Pane ID for the main orchestrator (e.g., "%0").
        status_pane_id: Pane ID for the session dashboard (e.g., "%1").
        questions_pane_id: Pane ID for the questions dashboard (e.g., "%2").
        created_new_session: True if a new session was created, False if reused existing.
    """
    session_name: str
    main_pane_id: str
    status_pane_id: str
    questions_pane_id: str
    created_new_session: bool


def tmux_available() -> bool:
    """Check if tmux is available on the system.

    Returns:
        True if tmux is available, False otherwise.
    """
    return shutil.which("tmux") is not None


def _shell_escape_cmd(cmd: list[str]) -> str:
    """Escape a command list for safe execution in tmux shell.

    Args:
        cmd: Command as a list of strings.

    Returns:
        Shell-escaped command string.
    """
    return " ".join(shlex.quote(arg) for arg in cmd)


def _create_new_session_layout(
    session_name: str,
    claude_cmd: list[str],
    dashboard_refresh: int,
    question_refresh: int,
) -> OrchestrationLayout:
    """Create a new tmux session with 3-pane orchestration layout.

    Creates a new detached session with:
    - Main pane (70% width): runs the Claude command
    - Right-top pane (30% x 60% height): session dashboard
    - Right-bottom pane (30% x 40% height): questions dashboard

    Args:
        session_name: Name for the new tmux session.
        claude_cmd: Command to run in the main pane (e.g., ["claude", "--dangerously-skip-permissions"]).
        dashboard_refresh: Refresh interval in seconds for session dashboard.
        question_refresh: Refresh interval in seconds for questions dashboard.

    Returns:
        OrchestrationLayout with pane IDs and session info.

    Raises:
        RuntimeError: If tmux operations fail.
    """
    try:
        # Create new detached session with main pane
        # -d: detached, -s: session name, -n: window name
        # -x/-y: set explicit dimensions (required for split-window with percentages on detached sessions)
        result = subprocess.run(
            [
                "tmux", "new-session",
                "-d",
                "-s", session_name,
                "-n", "orchestrator",
                "-x", "200", "-y", "50",
                "-P", "-F", "#{pane_id}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        main_pane_id = result.stdout.strip()

        # Split vertically: create right pane (60 columns ~ 30% of 200)
        # -h: horizontal split (creates vertical division), -l: absolute columns
        # Note: -p percentage fails on detached sessions in tmux 3.4/WSL2
        result = subprocess.run(
            [
                "tmux", "split-window",
                "-t", f"{session_name}:orchestrator",
                "-h", "-l", "60",
                "-P", "-F", "#{pane_id}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        status_pane_id = result.stdout.strip()

        # Split the right pane horizontally: create bottom pane (20 rows ~ 40% of 50)
        # -v: vertical split (creates horizontal division), -l: absolute rows
        # Note: -p percentage fails on detached sessions in tmux 3.4/WSL2
        result = subprocess.run(
            [
                "tmux", "split-window",
                "-t", status_pane_id,
                "-v", "-l", "20",
                "-P", "-F", "#{pane_id}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        questions_pane_id = result.stdout.strip()

        # Set pane titles
        subprocess.run(
            ["tmux", "select-pane", "-t", main_pane_id, "-T", "orchestrator"],
            check=True,
        )
        subprocess.run(
            ["tmux", "select-pane", "-t", status_pane_id, "-T", "sessions"],
            check=True,
        )
        subprocess.run(
            ["tmux", "select-pane", "-t", questions_pane_id, "-T", "questions"],
            check=True,
        )

        # Start the session dashboard in the status pane
        dashboard_cmd = ["agentic", "session", "dashboard", "--refresh", str(dashboard_refresh)]
        subprocess.run(
            ["tmux", "send-keys", "-t", status_pane_id, _shell_escape_cmd(dashboard_cmd), "Enter"],
            check=True,
        )

        # Start the question dashboard in the questions pane
        question_cmd = ["agentic", "question", "dashboard", "--refresh", str(question_refresh)]
        subprocess.run(
            ["tmux", "send-keys", "-t", questions_pane_id, _shell_escape_cmd(question_cmd), "Enter"],
            check=True,
        )

        # Send the Claude command to the main pane and execute it immediately
        subprocess.run(
            ["tmux", "send-keys", "-t", main_pane_id, _shell_escape_cmd(claude_cmd), "Enter"],
            check=True,
        )

        # Select main pane for initial focus
        subprocess.run(
            ["tmux", "select-pane", "-t", main_pane_id],
            check=True,
        )

        return OrchestrationLayout(
            session_name=session_name,
            main_pane_id=main_pane_id,
            status_pane_id=status_pane_id,
            questions_pane_id=questions_pane_id,
            created_new_session=True,
        )

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"Failed to create tmux orchestration layout: {e}")


def _create_inplace_layout(
    claude_cmd: list[str],
    dashboard_refresh: int,
    question_refresh: int,
) -> OrchestrationLayout:
    """Create orchestration layout within the current tmux session.

    Splits the current pane to create the 3-pane layout.

    Args:
        claude_cmd: Command to run in the main pane (e.g., ["claude", "--dangerously-skip-permissions"]).
        dashboard_refresh: Refresh interval in seconds for session dashboard.
        question_refresh: Refresh interval in seconds for questions dashboard.

    Returns:
        OrchestrationLayout with pane IDs and session info.

    Raises:
        RuntimeError: If tmux operations fail or not in a tmux session.
    """
    if not is_in_tmux():
        raise RuntimeError("Not in a tmux session")

    session_name = get_current_session_name()
    if not session_name:
        raise RuntimeError("Could not determine current tmux session name")

    try:
        # Get the current pane ID (this will become the main pane)
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{pane_id}"],
            capture_output=True,
            text=True,
            check=True,
        )
        main_pane_id = result.stdout.strip()

        # Split vertically: create right pane (30% width)
        result = subprocess.run(
            [
                "tmux", "split-window",
                "-h", "-p", "30",
                "-P", "-F", "#{pane_id}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        status_pane_id = result.stdout.strip()

        # Split the right pane horizontally: create bottom pane (40% height)
        result = subprocess.run(
            [
                "tmux", "split-window",
                "-t", status_pane_id,
                "-v", "-p", "40",
                "-P", "-F", "#{pane_id}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        questions_pane_id = result.stdout.strip()

        # Set pane titles
        subprocess.run(
            ["tmux", "select-pane", "-t", main_pane_id, "-T", "orchestrator"],
            check=True,
        )
        subprocess.run(
            ["tmux", "select-pane", "-t", status_pane_id, "-T", "sessions"],
            check=True,
        )
        subprocess.run(
            ["tmux", "select-pane", "-t", questions_pane_id, "-T", "questions"],
            check=True,
        )

        # Start the session dashboard in the status pane
        dashboard_cmd = ["agentic", "session", "dashboard", "--refresh", str(dashboard_refresh)]
        subprocess.run(
            ["tmux", "send-keys", "-t", status_pane_id, _shell_escape_cmd(dashboard_cmd), "Enter"],
            check=True,
        )

        # Start the question dashboard in the questions pane
        question_cmd = ["agentic", "question", "dashboard", "--refresh", str(question_refresh)]
        subprocess.run(
            ["tmux", "send-keys", "-t", questions_pane_id, _shell_escape_cmd(question_cmd), "Enter"],
            check=True,
        )

        # Select main pane for initial focus
        subprocess.run(
            ["tmux", "select-pane", "-t", main_pane_id],
            check=True,
        )

        return OrchestrationLayout(
            session_name=session_name,
            main_pane_id=main_pane_id,
            status_pane_id=status_pane_id,
            questions_pane_id=questions_pane_id,
            created_new_session=False,
        )

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"Failed to create in-place tmux orchestration layout: {e}")


def create_orchestration_layout(
    claude_cmd: list[str],
    dashboard_refresh: int = 5,
    question_refresh: int = 10,
) -> OrchestrationLayout:
    """Create a 3-pane orchestration layout in tmux.

    If not already in a tmux session, creates a new detached session.
    If already in tmux, creates the layout in the current session.

    Args:
        claude_cmd: Command to run in the main pane (e.g., ["claude", "--dangerously-skip-permissions"]).
        dashboard_refresh: Refresh interval in seconds for session dashboard (default: 5).
        question_refresh: Refresh interval in seconds for questions dashboard (default: 10).

    Returns:
        OrchestrationLayout with pane IDs and session info.

    Raises:
        RuntimeError: If tmux is not available or operations fail.
    """
    if not tmux_available():
        raise RuntimeError("tmux is not available on this system")

    if is_in_tmux():
        return _create_inplace_layout(claude_cmd, dashboard_refresh, question_refresh)
    else:
        session_name = f"agentic-orch-{os.getpid()}"
        return _create_new_session_layout(session_name, claude_cmd, dashboard_refresh, question_refresh)


def attach_to_session(session_name: str) -> None:
    """Attach to a tmux session, replacing the current process.

    Uses os.execvp to replace the current process with tmux attach.
    This function does not return.

    Args:
        session_name: Name of the tmux session to attach to.

    Raises:
        RuntimeError: If tmux is not available.
    """
    if not tmux_available():
        raise RuntimeError("tmux is not available on this system")

    # Replace current process with tmux attach
    # This does not return
    os.execvp("tmux", ["tmux", "attach-session", "-t", session_name])
