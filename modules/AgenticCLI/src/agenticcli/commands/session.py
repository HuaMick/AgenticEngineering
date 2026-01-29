"""Session management commands for Claude Code sessions.

Commands for spawning, listing, stopping, and monitoring Claude Code sessions.
"""

import json
import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


def _get_sessions_dir() -> Path:
    """Get the sessions directory path.

    Returns:
        Path to ~/.agentic/sessions/
    """
    sessions_dir = Path.home() / ".agentic" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


def _get_logs_dir() -> Path:
    """Get the logs directory path for session output.

    Returns:
        Path to ~/.agentic/sessions/logs/
    """
    logs_dir = Path.home() / ".agentic" / "sessions" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _load_session(session_id: str) -> dict | None:
    """Load a session from disk.

    Args:
        session_id: The session UUID.

    Returns:
        Session data dict or None if not found.
    """
    session_file = _get_sessions_dir() / f"{session_id}.json"
    if not session_file.exists():
        return None
    with open(session_file) as f:
        return json.load(f)


def _save_session(session_data: dict) -> None:
    """Save a session to disk.

    Args:
        session_data: Session data dict with session_id key.
    """
    session_file = _get_sessions_dir() / f"{session_data['session_id']}.json"
    with open(session_file, "w") as f:
        json.dump(session_data, f, indent=2)


def _list_all_sessions() -> list[dict]:
    """List all sessions from disk.

    Returns:
        List of session data dicts.
    """
    sessions = []
    sessions_dir = _get_sessions_dir()
    for session_file in sessions_dir.glob("*.json"):
        try:
            with open(session_file) as f:
                sessions.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return sessions


def _is_process_running(pid: int) -> bool:
    """Check if a process is still running.

    Args:
        pid: Process ID to check.

    Returns:
        True if process is running, False otherwise.
    """
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _update_session_status(session_data: dict) -> dict:
    """Update session status based on process state.

    Args:
        session_data: Session data dict.

    Returns:
        Updated session data dict.
    """
    if session_data.get("status") == "running":
        pid = session_data.get("pid")
        if pid and not _is_process_running(pid):
            session_data["status"] = "completed"
            session_data["ended_at"] = datetime.now().isoformat()
            _save_session(session_data)
    return session_data


def handle(args, ctx=None):
    """Route session subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.session_command == "spawn":
        cmd_spawn(args, ctx)
    elif args.session_command == "list":
        cmd_list(args, ctx)
    elif args.session_command == "stop":
        cmd_stop(args, ctx)
    elif args.session_command == "status":
        cmd_status(args, ctx)
    else:
        print("Usage: agentic session <spawn|list|stop|status>", file=sys.stderr)
        sys.exit(1)


def cmd_spawn(args, ctx=None):
    """Spawn a new Claude Code session.

    Args:
        args: Parsed command arguments with prompt, max_turns, background.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success

    prompt = getattr(args, "prompt", None)
    if not prompt:
        print_error("Prompt is required. Use --prompt or -p to specify.")
        sys.exit(1)

    max_turns = getattr(args, "max_turns", None)
    background = getattr(args, "background", False)
    working_dir = getattr(args, "directory", None) or os.getcwd()

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Build claude command
    cmd = ["claude", "--print"]
    if max_turns:
        cmd.extend(["--max-turns", str(max_turns)])
    cmd.append(prompt)

    # Create session record
    session_data = {
        "session_id": session_id,
        "pid": None,
        "prompt": prompt,
        "max_turns": max_turns,
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "ended_at": None,
        "background": background,
        "working_dir": working_dir,
        "command": " ".join(cmd),
    }

    try:
        if background:
            # Background mode: use Popen and return immediately
            # Open log files for stdout and stderr
            logs_dir = _get_logs_dir()
            stdout_log = open(logs_dir / f"{session_id}.stdout.log", "w")
            stderr_log = open(logs_dir / f"{session_id}.stderr.log", "w")

            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdin=subprocess.DEVNULL,
                stdout=stdout_log,
                stderr=stderr_log,
                start_new_session=True,
            )
            session_data["pid"] = process.pid
            session_data["status"] = "running"
            session_data["stdout_log"] = str(logs_dir / f"{session_id}.stdout.log")
            session_data["stderr_log"] = str(logs_dir / f"{session_id}.stderr.log")
            _save_session(session_data)

            if is_json_output():
                print_json({
                    "session_id": session_id,
                    "pid": process.pid,
                    "status": "running",
                    "background": True,
                })
            else:
                print_success(f"Session {session_id} started in background (PID: {process.pid})")
        else:
            # Foreground mode: use run and wait for completion
            session_data["pid"] = os.getpid()  # Current process for tracking
            session_data["status"] = "running"
            _save_session(session_data)

            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
            )

            session_data["status"] = "completed" if result.returncode == 0 else "failed"
            session_data["ended_at"] = datetime.now().isoformat()
            session_data["exit_code"] = result.returncode
            _save_session(session_data)

            if is_json_output():
                print_json({
                    "session_id": session_id,
                    "status": session_data["status"],
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                })
            else:
                if result.returncode == 0:
                    print_success(f"Session {session_id} completed")
                    if result.stdout:
                        console.print(result.stdout)
                else:
                    print_error(f"Session {session_id} failed with exit code {result.returncode}")
                    if result.stderr:
                        console.print(f"[red]{result.stderr}[/red]")

    except FileNotFoundError:
        session_data["status"] = "failed"
        session_data["ended_at"] = datetime.now().isoformat()
        session_data["error"] = "Claude CLI not found. Make sure 'claude' is installed and in PATH."
        _save_session(session_data)
        print_error("Claude CLI not found. Make sure 'claude' is installed and in PATH.")
        sys.exit(1)
    except Exception as e:
        session_data["status"] = "failed"
        session_data["ended_at"] = datetime.now().isoformat()
        session_data["error"] = str(e)
        _save_session(session_data)
        print_error(f"Failed to spawn session: {e}")
        sys.exit(1)


def cmd_list(args, ctx=None):
    """List all Claude Code sessions.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_header, print_json

    sessions = _list_all_sessions()

    # Update status for running sessions
    for session in sessions:
        _update_session_status(session)

    # Filter by active if requested
    active_only = getattr(args, "active", False)
    if active_only:
        sessions = [s for s in sessions if s.get("status") == "running"]

    if is_json_output():
        print_json({
            "sessions": sessions,
            "count": len(sessions),
        })
        return

    print_header("Claude Code Sessions")

    if not sessions:
        console.print("[dim]No sessions found[/dim]")
        return

    # Display as table
    from rich.table import Table

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Session ID", style="yellow", width=12)
    table.add_column("PID", style="white", width=8)
    table.add_column("Status", style="green", width=12)
    table.add_column("Started", style="dim", width=20)
    table.add_column("Prompt", style="dim", max_width=40)

    status_colors = {
        "running": "green",
        "completed": "blue",
        "failed": "red",
        "starting": "yellow",
    }

    for session in sorted(sessions, key=lambda s: s.get("started_at", ""), reverse=True):
        session_id = session.get("session_id", "")[:8]  # Truncate UUID
        pid = str(session.get("pid", "N/A"))
        status = session.get("status", "unknown")
        status_color = status_colors.get(status, "white")
        started_at = session.get("started_at", "")[:19]  # Truncate ISO timestamp
        prompt = session.get("prompt", "")[:40]  # Truncate prompt
        if len(session.get("prompt", "")) > 40:
            prompt += "..."

        table.add_row(
            session_id,
            pid,
            f"[{status_color}]{status}[/{status_color}]",
            started_at,
            prompt,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(sessions)} session(s)[/dim]")


def cmd_stop(args, ctx=None):
    """Stop a running Claude Code session.

    Args:
        args: Parsed command arguments with session_id.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    session_id = getattr(args, "session_id", None)
    if not session_id:
        print_error("Session ID is required.")
        sys.exit(1)

    # Find session by ID (support partial matching)
    sessions = _list_all_sessions()
    matching = [s for s in sessions if s.get("session_id", "").startswith(session_id)]

    if not matching:
        print_error(f"Session not found: {session_id}")
        sys.exit(1)

    if len(matching) > 1:
        print_error(f"Multiple sessions match '{session_id}'. Please provide a more specific ID.")
        sys.exit(1)

    session = matching[0]
    pid = session.get("pid")
    status = session.get("status")

    if status != "running":
        if is_json_output():
            print_json({"error": f"Session is not running (status: {status})", "success": False})
        else:
            print_error(f"Session is not running (status: {status})")
        sys.exit(1)

    # Try to stop the process
    force = getattr(args, "force", False)

    try:
        if force:
            os.kill(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGTERM)

        session["status"] = "stopped"
        session["ended_at"] = datetime.now().isoformat()
        _save_session(session)

        if is_json_output():
            print_json({
                "session_id": session["session_id"],
                "pid": pid,
                "status": "stopped",
                "success": True,
            })
        else:
            print_success(f"Session {session['session_id'][:8]} stopped (PID: {pid})")

    except ProcessLookupError:
        session["status"] = "completed"
        session["ended_at"] = datetime.now().isoformat()
        _save_session(session)
        if is_json_output():
            print_json({"error": "Process not found (may have already exited)", "success": False})
        else:
            print_error("Process not found (may have already exited)")
        sys.exit(1)
    except PermissionError:
        print_error(f"Permission denied to stop process {pid}")
        sys.exit(1)


def cmd_status(args, ctx=None):
    """Get status of a Claude Code session.

    Args:
        args: Parsed command arguments with session_id.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json

    session_id = getattr(args, "session_id", None)
    if not session_id:
        print_error("Session ID is required.")
        sys.exit(1)

    # Find session by ID (support partial matching)
    sessions = _list_all_sessions()
    matching = [s for s in sessions if s.get("session_id", "").startswith(session_id)]

    if not matching:
        print_error(f"Session not found: {session_id}")
        sys.exit(1)

    if len(matching) > 1:
        print_error(f"Multiple sessions match '{session_id}'. Please provide a more specific ID.")
        sys.exit(1)

    session = _update_session_status(matching[0])

    if is_json_output():
        print_json(session)
        return

    print_header(f"Session {session['session_id'][:8]}")

    status_colors = {
        "running": "green",
        "completed": "blue",
        "failed": "red",
        "starting": "yellow",
        "stopped": "yellow",
    }
    status = session.get("status", "unknown")
    status_color = status_colors.get(status, "white")

    console.print(f"[cyan]Session ID:[/cyan] {session.get('session_id')}")
    console.print(f"[cyan]PID:[/cyan] {session.get('pid', 'N/A')}")
    console.print(f"[cyan]Status:[/cyan] [{status_color}]{status}[/{status_color}]")
    console.print(f"[cyan]Background:[/cyan] {session.get('background', False)}")
    console.print(f"[cyan]Working Dir:[/cyan] {session.get('working_dir', 'N/A')}")
    console.print(f"[cyan]Started:[/cyan] {session.get('started_at', 'N/A')}")

    if session.get("ended_at"):
        console.print(f"[cyan]Ended:[/cyan] {session.get('ended_at')}")

    if session.get("max_turns"):
        console.print(f"[cyan]Max Turns:[/cyan] {session.get('max_turns')}")

    console.print(f"[cyan]Prompt:[/cyan] {session.get('prompt', 'N/A')}")

    if session.get("error"):
        console.print(f"[red]Error:[/red] {session.get('error')}")

    if session.get("exit_code") is not None:
        console.print(f"[cyan]Exit Code:[/cyan] {session.get('exit_code')}")

    # Display log file paths if they exist
    stdout_log = session.get("stdout_log")
    stderr_log = session.get("stderr_log")

    if stdout_log:
        console.print(f"[cyan]Stdout Log:[/cyan] {stdout_log}")
    if stderr_log:
        console.print(f"[cyan]Stderr Log:[/cyan] {stderr_log}")

    # If --show-output is passed and log files exist, display their contents
    show_output = getattr(args, "show_output", False)
    if show_output:
        if stdout_log and Path(stdout_log).exists():
            console.print("\n[bold cyan]--- Stdout Log Contents ---[/bold cyan]")
            with open(stdout_log) as f:
                content = f.read()
                if content:
                    console.print(content)
                else:
                    console.print("[dim](empty)[/dim]")

        if stderr_log and Path(stderr_log).exists():
            console.print("\n[bold cyan]--- Stderr Log Contents ---[/bold cyan]")
            with open(stderr_log) as f:
                content = f.read()
                if content:
                    console.print(f"[red]{content}[/red]")
                else:
                    console.print("[dim](empty)[/dim]")
