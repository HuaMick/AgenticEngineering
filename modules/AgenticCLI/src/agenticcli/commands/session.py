"""Session management commands for Claude Code sessions.

Commands for spawning, listing, stopping, and monitoring Claude Code sessions.
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from agenticcli.utils.state_store import StateStore, is_process_running

logger = logging.getLogger(__name__)

_store = StateStore("sessions", id_key="session_id")


def _get_logs_dir() -> Path:
    """Get the logs directory path for session output.

    Returns:
        Path to ~/.agentic/sessions/logs/
    """
    logs_dir = Path.home() / ".agentic" / "sessions" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _get_context_dir() -> Path:
    """Get the context directory for pre-compiled session context files.

    Returns:
        Path to ~/.agentic/sessions/context/
    """
    context_dir = Path.home() / ".agentic" / "sessions" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    return context_dir


def _compile_spawn_context(
    prompt: str,
    role: str | None,
    plan_folder: Path | None,
) -> str:
    """Compile full context for a spawned session into a markdown document.

    Combines the spawn prompt with pre-fetched bootstrap context (role process,
    inputs manifest, current task) so the agent doesn't need to manually run
    ``agentic -j context bootstrap``.

    Args:
        prompt: The base prompt (from _build_role_prompt or _build_task_prompt).
        role: Agent role identifier, if known.
        plan_folder: Optional plan folder path.

    Returns:
        Compiled context as a markdown string.
    """
    sections = [prompt]

    if not role:
        return "\n".join(sections)

    try:
        from agenticguidance.services import (
            get_role_process,
            get_role_inputs_manifest,
        )

        # Get role process/guidelines
        role_process = get_role_process(role)
        if role_process:
            sections.append("\n---\n## Role Process\n")
            if isinstance(role_process, dict):
                import yaml
                sections.append(yaml.dump(role_process, default_flow_style=False))
            else:
                sections.append(str(role_process))

        # Get essential inputs manifest
        inputs_manifest = get_role_inputs_manifest(role)
        if inputs_manifest and inputs_manifest.get("inputs"):
            sections.append("\n---\n## Essential Inputs\n")
            for inp in inputs_manifest["inputs"][:10]:
                name = inp.get("name", "unknown")
                location = inp.get("location", "")
                desc = inp.get("description", "")
                sections.append(f"- **{name}**: {desc}")
                if location:
                    sections.append(f"  Location: `{location}`")

        # Get current task from plan if available
        if plan_folder:
            try:
                from agenticguidance.services import MainFirstPlanResolver
                resolver = MainFirstPlanResolver()
                current_task = resolver.extract_current_task(plan_folder)
                if current_task:
                    sections.append("\n---\n## Current Task\n")
                    sections.append(f"- **ID**: {current_task.get('id', 'N/A')}")
                    sections.append(f"- **Name**: {current_task.get('name', 'N/A')}")
                    sections.append(f"- **Status**: {current_task.get('status', 'N/A')}")
                    if current_task.get("description"):
                        sections.append(f"- **Description**: {current_task['description']}")
            except Exception:
                pass  # Plan task lookup is best-effort

    except Exception as e:
        # If bootstrap fails, the agent can still bootstrap manually
        logger.debug("Failed to compile bootstrap context: %s", e)
        sections.append(
            f"\nNote: Auto-bootstrap failed ({e}). "
            f"Run manually: agentic -j context bootstrap --role {role}"
        )

    return "\n".join(sections)


def _capture_langsmith_trace(session_data: dict) -> bool:
    """Capture LangSmith trace for a completed background session.

    Reads the stdout log to extract the Claude Code session_id,
    finds the transcript path, and calls the stop hook to submit traces.
    This is needed because --print mode sessions don't fire Stop hooks.

    Args:
        session_data: Session data dict with stdout_log path.

    Returns:
        True if trace was captured, False otherwise.
    """
    if session_data.get("trace_captured"):
        return True

    stdout_log = session_data.get("stdout_log")
    if not stdout_log or not Path(stdout_log).exists():
        return False

    # Extract Claude Code session_id from JSON output in stdout log
    claude_session_id = None
    try:
        with open(stdout_log) as f:
            content = f.read().strip()
        if content:
            # The last line of --output-format json output is the result JSON
            for line in reversed(content.splitlines()):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        result = json.loads(line)
                        claude_session_id = result.get("session_id")
                        if claude_session_id:
                            break
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return False

    if not claude_session_id:
        return False

    # Find transcript path
    # Claude Code stores transcripts at ~/.claude/projects/<project-hash>/<session-id>.jsonl
    working_dir = session_data.get("working_dir", os.getcwd())
    # Convert working dir to Claude Code project hash format
    project_hash = working_dir.replace("/", "-")
    if project_hash.startswith("-"):
        project_hash = project_hash  # Keep leading dash
    transcript_dir = Path.home() / ".claude" / "projects" / project_hash
    transcript_path = transcript_dir / f"{claude_session_id}.jsonl"

    if not transcript_path.exists():
        # Try common project paths
        claude_projects = Path.home() / ".claude" / "projects"
        if claude_projects.exists():
            for proj_dir in claude_projects.iterdir():
                candidate = proj_dir / f"{claude_session_id}.jsonl"
                if candidate.exists():
                    transcript_path = candidate
                    break

    if not transcript_path.exists():
        return False

    # Call the stop hook with the session data
    hook_path = Path.home() / ".claude" / "hooks" / "stop_hook.sh"
    if not hook_path.exists():
        return False

    hook_input = json.dumps({
        "session_id": claude_session_id,
        "transcript_path": str(transcript_path),
        "hook_event_name": "Stop",
        "stop_hook_active": False,
    })

    try:
        subprocess.run(
            ["bash", str(hook_path)],
            input=hook_input,
            capture_output=True,
            text=True,
            timeout=120,
        )
        session_data["trace_captured"] = True
        session_data["claude_session_id"] = claude_session_id
        _store.save(session_data)
        return True
    except (subprocess.TimeoutExpired, OSError):
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
        if pid and not is_process_running(pid):
            session_data["status"] = "completed"
            session_data["ended_at"] = datetime.now().isoformat()
            _store.save(session_data)
            # Capture trace for background sessions
            if session_data.get("background"):
                _capture_langsmith_trace(session_data)
    return session_data


def _spawn_diagnostic_planner(stuck_session: dict) -> str | None:
    """Spawn a diagnostic planner for a stuck session.

    Creates a new background session that investigates why the original
    session became stuck and creates a remediation plan if needed.
    Only spawns once per stuck session.

    Args:
        stuck_session: Session data dict of the stuck session.

    Returns:
        New session ID if diagnostic was spawned, None otherwise.
    """
    if stuck_session.get("diagnostic_spawned", False):
        return None

    session_id = stuck_session["session_id"]
    prompt_excerpt = stuck_session.get("prompt", "")[:200]

    prompt = (
        f"Your role is DIAGNOSTIC PLANNER. A session has become stuck/unhealthy.\n\n"
        f"## Stuck Session Details\n"
        f"- Session ID: {session_id[:8]}\n"
        f"- Started: {stuck_session.get('started_at', 'unknown')}\n"
        f"- Status: {stuck_session.get('status', 'unknown')}\n"
        f"- PID: {stuck_session.get('pid', 'unknown')}\n"
        f"- Prompt excerpt: {prompt_excerpt}...\n\n"
        f"## Your Task\n"
        f"1. Investigate what went wrong (check logs at ~/.agentic/sessions/logs/{session_id}.*.log)\n"
        f"2. Determine if this is a one-off or systemic issue\n"
        f"3. If systemic, create a planning folder to address the root cause\n"
        f"4. If one-off, document findings and exit\n\n"
        f"Exit when investigation is complete."
    )

    # Build command for background spawn
    new_session_id = str(uuid.uuid4())
    cmd = ["claude", "--print", "--dangerously-skip-permissions", "--max-turns", "10", prompt]

    logs_dir = _get_logs_dir()
    stdout_log = open(logs_dir / f"{new_session_id}.stdout.log", "w")
    stderr_log = open(logs_dir / f"{new_session_id}.stderr.log", "w")

    try:
        process = subprocess.Popen(
            cmd,
            cwd=stuck_session.get("working_dir", "."),
            stdin=subprocess.DEVNULL,
            stdout=stdout_log,
            stderr=stderr_log,
            start_new_session=True,
        )
    except (FileNotFoundError, OSError):
        return None
    finally:
        stdout_log.close()
        stderr_log.close()

    # Save diagnostic session
    diag_session = {
        "session_id": new_session_id,
        "pid": process.pid,
        "prompt": prompt,
        "max_turns": 10,
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "ended_at": None,
        "background": True,
        "working_dir": stuck_session.get("working_dir", "."),
        "command": " ".join(cmd),
        "last_activity": datetime.now().isoformat(),
        "stdout_log": str(logs_dir / f"{new_session_id}.stdout.log"),
        "stderr_log": str(logs_dir / f"{new_session_id}.stderr.log"),
        "metadata": {"diagnostic_for": session_id},
    }
    _store.save(diag_session)

    # Mark original session
    sessions_dir = _store.get_dir()
    session_path = sessions_dir / f"{session_id}.json"
    if session_path.exists():
        data = json.loads(session_path.read_text())
        data["diagnostic_spawned"] = True
        data["diagnostic_session_id"] = new_session_id
        session_path.write_text(json.dumps(data, indent=2))

    return new_session_id


def _check_tmux_session(session_id: str) -> bool | None:
    """Check if a tmux session exists for the given session ID.

    Args:
        session_id: Session ID to check as tmux session name.

    Returns:
        True if tmux session exists, False if it doesn't,
        None if tmux is not installed or check timed out.
    """
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_id],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None


def _check_session_health(session: dict) -> dict:
    """Evaluate session health from multiple signals.

    Checks PID liveness, log file size, and log recency to determine
    whether a session is healthy, stale, or unhealthy.

    Args:
        session: Session data dict.

    Returns:
        Dict with keys: healthy (bool), signals (list[dict]),
        stale (bool), stale_minutes (int).
    """
    signals = []
    session_id = session.get("session_id", "")
    pid = session.get("pid")
    status = session.get("status", "")

    # Signal 1: PID alive check
    pid_alive = is_process_running(pid) if pid else False
    signals.append({
        "name": "pid_alive",
        "ok": pid_alive,
        "detail": f"PID {pid} {'alive' if pid_alive else 'dead'}",
    })

    # Signal 2: Log file size check
    logs_dir = _get_logs_dir()
    stdout_path = logs_dir / f"{session_id}.stdout.log"
    stderr_path = logs_dir / f"{session_id}.stderr.log"
    stdout_bytes = stdout_path.stat().st_size if stdout_path.exists() else 0
    stderr_bytes = stderr_path.stat().st_size if stderr_path.exists() else 0
    total_bytes = stdout_bytes + stderr_bytes
    has_output = total_bytes > 0
    signals.append({
        "name": "has_output",
        "ok": has_output,
        "detail": f"Log size: {total_bytes} bytes (stdout={stdout_bytes}, stderr={stderr_bytes})",
    })

    # Signal 3: Log file recency (mtime)
    log_mtime = None
    for p in [stdout_path, stderr_path]:
        if p.exists():
            mtime = p.stat().st_mtime
            if log_mtime is None or mtime > log_mtime:
                log_mtime = mtime

    if log_mtime:
        minutes_since_write = (time.time() - log_mtime) / 60
    else:
        # Fall back to started_at
        started_at = session.get("started_at", "")
        if started_at:
            try:
                dt = datetime.fromisoformat(started_at)
                minutes_since_write = (datetime.now() - dt).total_seconds() / 60
            except ValueError:
                minutes_since_write = 999
        else:
            minutes_since_write = 999

    stale_threshold = 10  # minutes
    is_stale = status == "running" and minutes_since_write > stale_threshold
    signals.append({
        "name": "recent_activity",
        "ok": not is_stale,
        "detail": f"Last activity: {int(minutes_since_write)}m ago",
    })

    # Signal 4: tmux session existence (only for background sessions)
    if session.get("background") and status == "running":
        tmux_exists = _check_tmux_session(session_id)
        if tmux_exists is not None:
            signals.append({
                "name": "tmux_session",
                "ok": tmux_exists,
                "detail": f"tmux session {'exists' if tmux_exists else 'missing'}",
            })

    # Overall health
    healthy = pid_alive and (has_output or status != "running")
    stale = is_stale

    return {
        "healthy": healthy,
        "signals": signals,
        "stale": stale,
        "stale_minutes": int(minutes_since_write),
    }


def cmd_dashboard(args, ctx=None):
    """Display a live auto-refreshing dashboard of active sessions.

    Shows a Rich.Live table that updates every N seconds with:
    - Session ID (8-char), Status, Health, Age, Role/Description

    Args:
        args: Parsed command arguments with refresh interval.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console
    from rich.live import Live
    from rich.table import Table

    refresh_seconds = getattr(args, "refresh", 5)

    def build_table() -> Table:
        """Build the sessions dashboard table."""
        table = Table(show_header=True, header_style="bold cyan", title="Active Sessions")
        table.add_column("ID", style="yellow", width=10)
        table.add_column("Status", width=12)
        table.add_column("Health", width=8)
        table.add_column("Age", style="dim", width=10)
        table.add_column("Description", style="dim", no_wrap=False)

        sessions = _store.list_all()

        # Update status for all running sessions
        for session in sessions:
            _update_session_status(session)

        # Filter to running/starting only
        active_sessions = [s for s in sessions if s.get("status") in ("running", "starting")]

        # Compute health for active sessions
        health_data = {}
        for session in active_sessions:
            health_data[session["session_id"]] = _check_session_health(session)

        status_colors = {
            "running": "green",
            "starting": "yellow",
        }

        if not active_sessions:
            table.add_row("[dim]No active sessions[/dim]", "", "", "", "")
            return table

        for session in sorted(active_sessions, key=lambda s: s.get("started_at", ""), reverse=True):
            session_id = session.get("session_id", "")[:8]
            status = session.get("status", "unknown")
            status_color = status_colors.get(status, "white")
            age = _format_relative_time(session.get("started_at", ""))
            prompt = session.get("prompt", "")

            # Clean up prompt for display
            prompt = prompt.replace("\n", " ").replace("\r", "")
            if len(prompt) > 50:
                prompt = prompt[:50] + "..."

            # Health column
            health = health_data.get(session.get("session_id", ""))
            if health:
                if health["stale"]:
                    health_display = f"[yellow]STALE[/yellow]"
                    status_display = f"[yellow]stale {health['stale_minutes']}m[/yellow]"
                elif health["healthy"]:
                    health_display = "[green]OK[/green]"
                    status_display = f"[{status_color}]{status}[/{status_color}]"
                else:
                    health_display = "[red]FAIL[/red]"
                    status_display = f"[{status_color}]{status}[/{status_color}]"
            else:
                health_display = "[dim]-[/dim]"
                status_display = f"[{status_color}]{status}[/{status_color}]"

            table.add_row(
                session_id,
                status_display,
                health_display,
                age,
                prompt,
            )

        return table

    try:
        with Live(build_table(), console=console, refresh_per_second=1/refresh_seconds) as live:
            while True:
                time.sleep(refresh_seconds)
                live.update(build_table())
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped[/dim]")


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
    elif args.session_command == "health":
        cmd_health(args, ctx)
    elif args.session_command == "logs":
        cmd_logs(args, ctx)
    elif args.session_command == "dashboard":
        cmd_dashboard(args, ctx)
    else:
        print("Usage: agentic session <spawn|list|stop|status|health|logs|dashboard>", file=sys.stderr)
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
1. Check if a plan already exists: agentic -j plan list
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
        f"Initialize your context by running: agentic -j context bootstrap --role {role}",
    ]

    if plan_folder:
        plan_name = plan_folder.name
        parts.append(f"Your active plan is: {plan_name}")
        parts.append(f"Plan path: {plan_folder}")
        parts.append(f"List tasks with: agentic -j plan task list --plan {plan_name}")
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
    from agenticcli.console import console, get_status, is_json_output, print_error, print_json, print_success, print_warning
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

    # Warn if plan has pending questions (informational only)
    if plan_folder:
        from agenticcli.commands.plan import has_pending_questions
        if has_pending_questions(plan_folder):
            print_warning(f"Plan {plan_folder.name} has pending questions. Check: agentic question list --plan {plan_folder.name}")

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

    # Compile full context (prompt + bootstrap data) into a temp file
    # This avoids OS argument length limits and removes the need for
    # agents to manually run `agentic -j context bootstrap`
    compiled_context = _compile_spawn_context(prompt, role, plan_folder)
    context_dir = _get_context_dir()
    context_file = context_dir / f"{session_id}.md"
    context_file.write_text(compiled_context)

    short_prompt = (
        f"Your full instructions and context have been pre-compiled into a file. "
        f"IMPORTANT: Read the file at {context_file} FIRST before doing anything else. "
        f"It contains your role, task details, and bootstrap context."
    )

    # Build claude command
    # Always skip permissions for spawned sessions — they run autonomously
    cmd = ["claude", "--print", "--dangerously-skip-permissions"]
    if max_turns:
        cmd.extend(["--max-turns", str(max_turns)])
    # Use JSON output for background sessions to capture Claude Code session_id
    # This enables post-completion LangSmith trace capture
    if background:
        cmd.extend(["--output-format", "json"])
    cmd.append(short_prompt)

    # Estimate token usage from the compiled context (what the agent will process)
    prompt_tokens = estimate_tokens(compiled_context)
    usage_percent = context_usage_percent(prompt_tokens)
    usage_color = get_usage_color(usage_percent)

    # Create session record
    session_data = {
        "session_id": session_id,
        "pid": None,
        "prompt": prompt,
        "compiled_context": str(context_file),
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
        # --- Web Terminal Server Integration ---
        # If AGENTIC_TERMINAL_URL is set, create terminal via the web server
        # so the agent runs in a browser-visible PTY
        terminal_url = os.environ.get("AGENTIC_TERMINAL_URL")
        if terminal_url:
            import urllib.request
            import urllib.error

            api_url = f"{terminal_url.rstrip('/')}/api/terminals"
            payload = json.dumps({
                "name": session_id[:12],
                "cmd": " ".join(cmd),
                "cwd": working_dir,
                "role": getattr(args, "role", None),
            }).encode()

            try:
                req = urllib.request.Request(
                    api_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    result = json.loads(resp.read().decode())

                session_data["status"] = "running"
                session_data["terminal_url"] = terminal_url
                session_data["terminal_name"] = session_id[:12]
                _store.save(session_data)

                if is_json_output():
                    print_json({
                        "session_id": session_id,
                        "status": "running",
                        "terminal_url": terminal_url,
                        "terminal_name": session_id[:12],
                        "web_terminal": True,
                        "estimated_tokens": prompt_tokens,
                        "context_usage_percent": usage_percent,
                    })
                else:
                    print_success(
                        f"Session {session_id[:8]} created in web terminal at {terminal_url}"
                    )
                    console.print(
                        f"[dim]Context usage: [{usage_color}]{usage_percent:.1f}%"
                        f"[/{usage_color}] (~{prompt_tokens:,} tokens)[/dim]"
                    )
                return

            except (urllib.error.URLError, OSError) as e:
                # Server unreachable — fall through to local spawn
                logger.warning(
                    "Web terminal server at %s unreachable (%s), falling back to local spawn",
                    terminal_url, e,
                )
                if not is_json_output():
                    print_warning(
                        f"Web terminal server unreachable ({e}), falling back to local spawn"
                    )

        if background:
            # Background mode: use Popen and return immediately
            # Open log files for stdout and stderr
            logs_dir = _get_logs_dir()
            stdout_log = open(logs_dir / f"{session_id}.stdout.log", "w")
            stderr_log = open(logs_dir / f"{session_id}.stderr.log", "w")

            try:
                process = subprocess.Popen(
                    cmd,
                    cwd=working_dir,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_log,
                    stderr=stderr_log,
                    start_new_session=True,
                )
            finally:
                # Close file handles in parent process; child inherits the FDs
                stdout_log.close()
                stderr_log.close()

            session_data["pid"] = process.pid
            session_data["status"] = "running"
            session_data["last_activity"] = session_data["started_at"]
            session_data["stdout_log"] = str(logs_dir / f"{session_id}.stdout.log")
            session_data["stderr_log"] = str(logs_dir / f"{session_id}.stderr.log")
            _store.save(session_data)

            # Auto-start ntfy question watch-daemon for this plan
            if plan_folder:
                try:
                    from agenticcli.commands.question import _ensure_watch_daemon
                    started, reason = _ensure_watch_daemon(plan_folder)
                    if started:
                        logger.info("Auto-started question watch-daemon for %s", plan_folder.name)
                except Exception as e:
                    logger.debug("Failed to auto-start watch-daemon: %s", e)

            # Check for immediate spawn failure
            time.sleep(1)
            if not is_process_running(process.pid):
                session_data["status"] = "failed"
                session_data["ended_at"] = datetime.now().isoformat()
                session_data["error"] = "Process died immediately after spawn"
                _store.save(session_data)
                if is_json_output():
                    print_json({
                        "session_id": session_id,
                        "pid": process.pid,
                        "status": "failed",
                        "error": "Process died immediately after spawn",
                    })
                else:
                    print_error(f"Session {session_id[:8]} failed immediately after spawn (PID: {process.pid})")
                return

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
            _store.save(session_data)

            # Auto-start ntfy question watch-daemon for this plan
            if plan_folder:
                try:
                    from agenticcli.commands.question import _ensure_watch_daemon
                    started, reason = _ensure_watch_daemon(plan_folder)
                    if started:
                        logger.info("Auto-started question watch-daemon for %s", plan_folder.name)
                except Exception as e:
                    logger.debug("Failed to auto-start watch-daemon: %s", e)

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
            _store.save(session_data)

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
        _store.save(session_data)
        print_error("Claude CLI not found. Make sure 'claude' is installed and in PATH.")
        sys.exit(1)
    except Exception as e:
        session_data["status"] = "failed"
        session_data["ended_at"] = datetime.now().isoformat()
        session_data["error"] = str(e)
        _store.save(session_data)
        print_error(f"Failed to spawn session: {e}")
        sys.exit(1)


def _format_relative_time(iso_str: str) -> str:
    """Convert an ISO timestamp to a human-readable relative time string.

    Args:
        iso_str: ISO format timestamp string.

    Returns:
        Relative time string like "just now", "2m ago", "1h ago", "3d ago", or "Feb 01".
    """
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        delta = datetime.now() - dt
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return "just now"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m ago"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600}h ago"
        elif total_seconds < 604800:
            return f"{total_seconds // 86400}d ago"
        else:
            return dt.strftime("%b %d")
    except (ValueError, TypeError):
        return iso_str


def cmd_list(args, ctx=None):
    """List Claude Code sessions.

    By default shows only running/starting sessions. Use --all to show all.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_header, print_json

    all_sessions = _store.list_all()

    # Update status for running sessions
    for session in all_sessions:
        _update_session_status(session)

    total_count = len(all_sessions)

    # Default: show only active (running/starting). --all shows everything.
    show_all = getattr(args, "show_all", False)
    if show_all:
        sessions = all_sessions
    else:
        sessions = [s for s in all_sessions if s.get("status") in ("running", "starting")]

    # Compute health for running sessions
    health_data = {}
    for session in sessions:
        if session.get("status") in ("running", "starting"):
            health_data[session["session_id"]] = _check_session_health(session)

    if is_json_output():
        # Enrich running sessions with health data in JSON output
        enriched = []
        for s in sessions:
            s_copy = dict(s)
            if s["session_id"] in health_data:
                s_copy["health"] = health_data[s["session_id"]]
            enriched.append(s_copy)
        print_json({
            "sessions": enriched,
            "count": len(sessions),
            "total": total_count,
            "filtered": not show_all,
        })
        return

    print_header("Claude Code Sessions")

    if not sessions:
        if show_all:
            console.print("[dim]No sessions found[/dim]")
        else:
            console.print("[dim]No active sessions[/dim]")
            if total_count > 0:
                console.print(f"[dim]{total_count} session(s) total — use --all to see all[/dim]")
        return

    # Display as table
    from rich.table import Table

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="yellow", width=10)
    table.add_column("Status", width=10)
    table.add_column("Health", width=8)
    table.add_column("Age", style="dim", width=10)
    table.add_column("PID", style="white", width=7)
    table.add_column("Description", style="dim", no_wrap=False)

    status_colors = {
        "running": "green",
        "completed": "blue",
        "failed": "red",
        "starting": "yellow",
        "stopped": "yellow",
    }

    stale_count = 0

    for session in sorted(all_sessions if show_all else sessions, key=lambda s: s.get("started_at", ""), reverse=True):
        if not show_all and session.get("status") not in ("running", "starting"):
            continue
        session_id = session.get("session_id", "")[:8]
        pid = str(session.get("pid", "N/A"))
        status = session.get("status", "unknown")
        status_color = status_colors.get(status, "white")
        age = _format_relative_time(session.get("started_at", ""))
        prompt = session.get("prompt", "")
        # Clean up prompt for display: replace newlines, truncate to 60 chars
        prompt = prompt.replace("\n", " ").replace("\r", "")
        if len(prompt) > 60:
            prompt = prompt[:60] + "..."

        # Health column
        health = health_data.get(session.get("session_id", ""))
        if health:
            if health["stale"]:
                health_display = f"[yellow]STALE[/yellow]"
                status_display = f"[yellow]running (stale {health['stale_minutes']}m)[/yellow]"
                stale_count += 1
            elif health["healthy"]:
                health_display = "[green]OK[/green]"
                status_display = f"[{status_color}]{status}[/{status_color}]"
            else:
                health_display = "[red]FAIL[/red]"
                status_display = f"[{status_color}]{status}[/{status_color}]"
        else:
            health_display = "[dim]-[/dim]"
            status_display = f"[{status_color}]{status}[/{status_color}]"

        table.add_row(
            session_id,
            status_display,
            health_display,
            age,
            pid,
            prompt,
        )

    console.print(table)

    if stale_count > 0:
        console.print(f"\n[yellow]Warning: {stale_count} session(s) appear stale. Use 'agentic session health <id>' for details.[/yellow]")

    # Status summary
    from collections import Counter
    status_counts = Counter(s.get("status", "unknown") for s in all_sessions)
    summary_parts = []
    for s in ("running", "starting", "completed", "stopped", "failed"):
        count = status_counts.get(s, 0)
        if count > 0:
            color = status_colors.get(s, "white")
            summary_parts.append(f"[{color}]{count} {s}[/{color}]")

    if show_all:
        console.print(f"\n[dim]{', '.join(summary_parts)}[/dim]")
    else:
        console.print(f"\n[dim]Showing {len(sessions)} active of {total_count} total (use --all to see all)[/dim]")
        if summary_parts:
            console.print(f"[dim]{', '.join(summary_parts)}[/dim]")


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
    sessions = _store.list_all()
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
        _store.save(session)

        # Capture trace before reporting success
        if session.get("background"):
            _capture_langsmith_trace(session)

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
        _store.save(session)
        # Capture trace for background sessions
        if session.get("background"):
            _capture_langsmith_trace(session)
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
    sessions = _store.list_all()
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

    # Show health warnings for background running sessions
    if session.get("background") and status == "running":
        health = _check_session_health(session)
        unhealthy_signals = [s for s in health["signals"] if not s["ok"]]
        if unhealthy_signals:
            console.print("\n[bold yellow]Health Warnings:[/bold yellow]")
            for sig in unhealthy_signals:
                console.print(f"  [yellow]! {sig['name']}: {sig['detail']}[/yellow]")


def cmd_health(args, ctx=None):
    """Check health/vitality of a session.

    Evaluates PID liveness, log file output, and activity recency
    to determine overall session health.

    Args:
        args: Parsed command arguments with session_id.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_json

    session_id_prefix = getattr(args, "session_id", "")
    json_output = is_json_output() or getattr(args, "json_output", False)

    sessions_dir = _store.get_dir()
    matches = [f for f in sessions_dir.glob("*.json")
               if f.stem.startswith(session_id_prefix)]

    if not matches:
        print_error(f"No session found matching '{session_id_prefix}'")
        return

    if len(matches) > 1:
        print_error(f"Ambiguous ID '{session_id_prefix}' matches {len(matches)} sessions")
        return

    session = json.loads(matches[0].read_text())
    _update_session_status(session)

    health = _check_session_health(session)

    if json_output:
        result = {"session_id": session["session_id"], **health}
        # Auto-spawn diagnostic for JSON output too
        if health["stale"] or not health["healthy"]:
            if not session.get("diagnostic_spawned", False):
                new_id = _spawn_diagnostic_planner(session)
                if new_id:
                    result["diagnostic_spawned"] = new_id
            else:
                result["diagnostic_session_id"] = session.get("diagnostic_session_id")
        print(json.dumps(result, indent=2))
        return

    # Rich display
    console.print(f"\n[bold]Session Health: {session['session_id'][:8]}[/bold]")
    console.print(f"Status: {session.get('status', 'unknown')}")
    console.print(f"PID: {session.get('pid', 'N/A')}")
    console.print()

    for sig in health["signals"]:
        icon = "[green]OK[/green]" if sig["ok"] else "[red]FAIL[/red]"
        console.print(f"  {icon}  {sig['name']}: {sig['detail']}")

    console.print()
    if health["healthy"] and not health["stale"]:
        console.print("[green bold]Verdict: HEALTHY[/green bold]")
    elif health["stale"]:
        console.print(f"[yellow bold]Verdict: STALE ({health['stale_minutes']}m since last activity)[/yellow bold]")
    else:
        console.print("[red bold]Verdict: UNHEALTHY[/red bold]")

    # Auto-spawn diagnostic planner for unhealthy/stale sessions
    if health["stale"] or not health["healthy"]:
        if not session.get("diagnostic_spawned", False):
            new_id = _spawn_diagnostic_planner(session)
            if new_id:
                if json_output:
                    pass  # Already returned above
                else:
                    console.print(f"\n[cyan]Auto-spawned diagnostic session: {new_id[:8]}[/cyan]")
        else:
            diag_id = session.get("diagnostic_session_id", "unknown")[:8]
            if not json_output:
                console.print(f"\n[dim]Diagnostic already spawned: {diag_id}[/dim]")


def cmd_logs(args, ctx=None):
    """View logs for a session.

    Shows the last N lines of stdout or stderr log output for a session.
    Supports following the log with --follow.

    Args:
        args: Parsed command arguments with session_id.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, print_error

    session_id_prefix = getattr(args, "session_id", "")
    show_stderr = getattr(args, "stderr", False)
    num_lines = getattr(args, "lines", 50)
    follow = getattr(args, "follow", False)

    sessions_dir = _store.get_dir()
    matches = [f for f in sessions_dir.glob("*.json")
               if f.stem.startswith(session_id_prefix)]

    if not matches:
        print_error(f"No session found matching '{session_id_prefix}'")
        return

    if len(matches) > 1:
        print_error(f"Ambiguous ID '{session_id_prefix}' matches {len(matches)} sessions")
        return

    session = json.loads(matches[0].read_text())
    logs_dir = _get_logs_dir()
    suffix = "stderr" if show_stderr else "stdout"
    log_path = logs_dir / f"{session['session_id']}.{suffix}.log"

    if not log_path.exists():
        console.print(f"[yellow]No {suffix} log file found for session {session['session_id'][:8]}[/yellow]")
        return

    file_size = log_path.stat().st_size
    if file_size == 0:
        console.print(f"[yellow]{suffix} log is empty (0 bytes) for session {session['session_id'][:8]}[/yellow]")
        return

    if follow:
        try:
            subprocess.run(["tail", "-f", str(log_path)], check=False)
        except KeyboardInterrupt:
            pass
        return

    # Read last N lines
    lines = log_path.read_text().splitlines()
    display_lines = lines[-num_lines:] if len(lines) > num_lines else lines
    if len(lines) > num_lines:
        console.print(f"[dim]... showing last {num_lines} of {len(lines)} lines ...[/dim]")
    for line in display_lines:
        console.print(line)
