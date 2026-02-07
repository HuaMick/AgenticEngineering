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


def _resolve_plan_folder(plan_name: str) -> Path | None:
    """Resolve a plan folder name to its full path.

    Searches docs/plans/live/ for the matching plan folder.

    Args:
        plan_name: Plan folder name (e.g., '260207TA_cli_task_spawn').

    Returns:
        Path to plan folder, or None if not found.
    """
    # Try common plan locations
    search_dirs = [
        Path.cwd() / "docs" / "plans" / "live",
        Path.cwd() / "docs" / "plans" / "completed",
    ]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        candidate = search_dir / plan_name
        if candidate.exists() and candidate.is_dir():
            return candidate

    return None


_DOGFOOD_STRATEGY = """
Dogfood Strategy — Self-Healing Gaps:
If you encounter a gap in the system (missing service, broken workflow, missing CLI command),
do NOT work around it silently. Instead:
1. Check if a plan already exists: agentic plan list -j
2. If a relevant plan exists, add a task to it or start working on the gap task.
3. If no plan exists, create one: agentic plan init <descriptive-name>
4. Then spawn a subagent to implement the fix:
   agentic session spawn --role build-python --plan <plan_folder> -b
5. Continue your original work once the gap is resolved.
This ensures gaps are tracked and fixed systematically rather than patched ad-hoc.
""".strip()


def _build_role_prompt(role: str, plan_folder: Path | None) -> str:
    """Build a prompt for spawning an agent by role.

    Constructs a prompt that tells the agent its role and provides plan context.

    Args:
        role: Agent role identifier (e.g., 'build-python').
        plan_folder: Optional path to plan folder for additional context.

    Returns:
        Constructed prompt string.
    """
    parts = [
        f"You are being spawned as a {role} agent.",
        f"Initialize your context by running: agentic context bootstrap --role {role} -j",
    ]

    if plan_folder:
        plan_name = plan_folder.name
        parts.append(f"Your active plan is: {plan_name}")
        parts.append(f"Plan path: {plan_folder}")
        parts.append(f"List tasks with: agentic plan task list --plan {plan_name} -j")
        parts.append("Start by loading your bootstrap context, then work through the plan tasks.")

    parts.append("")
    parts.append(_DOGFOOD_STRATEGY)

    return "\n".join(parts)


def _build_task_prompt(task_id: str, plan_folder: Path) -> str | None:
    """Build a prompt for spawning an agent for a specific task.

    Loads task details from the plan and constructs a focused prompt.

    Args:
        task_id: Task identifier (e.g., 'CLI_001').
        plan_folder: Path to plan folder containing plan_build.yml.

    Returns:
        Constructed prompt string, or None if task not found.
    """
    from agenticguidance.services.task import TaskService

    service = TaskService(plan_folder)
    task = service.get_task(task_id)

    if not task:
        return None

    plan_name = plan_folder.name
    parts = [
        f"You are being spawned to work on task {task.id}: {task.name}",
        f"Plan: {plan_name}",
        "",
        f"Description: {task.description}",
    ]

    if task.guidance:
        parts.append(f"\nGuidance:\n{task.guidance}")

    if task.target_files:
        parts.append(f"\nTarget files: {', '.join(task.target_files)}")

    if task.inputs:
        parts.append(f"\nReference inputs: {', '.join(task.inputs)}")

    parts.append(f"\nWhen done, mark the task complete: agentic plan task complete {task_id} --plan {plan_name}")

    parts.append("")
    parts.append(_DOGFOOD_STRATEGY)

    return "\n".join(parts)


def cmd_spawn(args, ctx=None):
    """Spawn a new Claude Code session.

    Args:
        args: Parsed command arguments with prompt, max_turns, background.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, get_status, is_json_output, print_error, print_json, print_success
    from agenticcli.utils.tokens import (
        context_usage_percent,
        estimate_tokens,
        get_usage_color,
    )

    prompt = getattr(args, "prompt", None)
    role = getattr(args, "role", None)
    task_id = getattr(args, "task", None)
    plan_name = getattr(args, "plan", None)

    # Resolve plan folder if provided
    plan_folder = None
    if plan_name:
        plan_folder = _resolve_plan_folder(plan_name)
        if not plan_folder:
            print_error(f"Plan folder not found: {plan_name}")
            sys.exit(1)

    # Validate: --task requires --plan
    if task_id and not plan_folder:
        print_error("--task requires --plan to be set.")
        sys.exit(1)

    # Build prompt from role or task if --prompt not provided
    if not prompt:
        if role:
            prompt = _build_role_prompt(role, plan_folder)
        elif task_id:
            prompt = _build_task_prompt(task_id, plan_folder)
            if not prompt:
                print_error(f"Task not found: {task_id} in plan {plan_name}")
                sys.exit(1)
        else:
            print_error("Prompt is required. Use --prompt, --role, or --task to specify.")
            sys.exit(1)

    max_turns = getattr(args, "max_turns", None)
    background = getattr(args, "background", False)
    working_dir = getattr(args, "directory", None) or os.getcwd()

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Build claude command
    cmd = ["claude", "--print"]
    if getattr(args, "dangerously_skip_permissions", False):
        cmd.append("--dangerously-skip-permissions")
    if max_turns:
        cmd.extend(["--max-turns", str(max_turns)])
    cmd.append(prompt)

    # Estimate token usage from prompt
    prompt_tokens = estimate_tokens(prompt)
    usage_percent = context_usage_percent(prompt_tokens)
    usage_color = get_usage_color(usage_percent)

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
        "estimated_tokens": prompt_tokens,
        "context_usage_percent": usage_percent,
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
                    "estimated_tokens": prompt_tokens,
                    "context_usage_percent": usage_percent,
                })
            else:
                print_success(f"Session {session_id} started in background (PID: {process.pid})")
                console.print(f"[dim]Context usage: [{usage_color}]{usage_percent:.1f}%[/{usage_color}] (~{prompt_tokens:,} tokens)[/dim]")
        else:
            # Foreground mode: use Popen for streaming output
            session_data["pid"] = os.getpid()  # Current process for tracking
            session_data["status"] = "running"
            _save_session(session_data)

            # Display context metrics before starting
            if not is_json_output():
                console.print(f"[dim]Context usage: [{usage_color}]{usage_percent:.1f}%[/{usage_color}] (~{prompt_tokens:,} tokens)[/dim]")

            # Use Popen for streaming output with status indicator
            status_message = f"Running Claude session {session_id[:8]}..."

            with get_status(status_message):
                process = subprocess.Popen(
                    cmd,
                    cwd=working_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                # Capture output
                stdout, stderr = process.communicate()
                returncode = process.returncode

            session_data["status"] = "completed" if returncode == 0 else "failed"
            session_data["ended_at"] = datetime.now().isoformat()
            session_data["exit_code"] = returncode
            _save_session(session_data)

            if is_json_output():
                print_json({
                    "session_id": session_id,
                    "status": session_data["status"],
                    "exit_code": returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "estimated_tokens": prompt_tokens,
                    "context_usage_percent": usage_percent,
                })
            else:
                if returncode == 0:
                    print_success(f"Session {session_id} completed")
                    if stdout:
                        console.print(stdout)
                else:
                    print_error(f"Session {session_id} failed with exit code {returncode}")
                    if stderr:
                        console.print(f"[red]{stderr}[/red]")

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

    # If already in terminal state, just return success
    if status in ["completed", "stopped", "failed"]:
        if is_json_output():
            print_json({
                "session_id": session["session_id"],
                "status": status,
                "message": f"Session is already in terminal state: {status}",
                "success": True
            })
        else:
            print_success(f"Session {session['session_id'][:8]} is already in terminal state: {status}")
        return

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
        # Process not found, mark as completed if it was running
        session["status"] = "completed"
        session["ended_at"] = datetime.now().isoformat()
        _save_session(session)
        if is_json_output():
            print_json({
                "session_id": session["session_id"],
                "status": "completed",
                "message": "Process not found (may have already exited)",
                "success": True
            })
        else:
            print_success(f"Session {session['session_id'][:8]} already exited (process not found)")
        return
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
