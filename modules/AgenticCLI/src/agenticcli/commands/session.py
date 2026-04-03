"""Session management commands for Claude Code sessions.

Commands for spawning, listing, stopping, and monitoring Claude Code sessions.
"""

import atexit
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agenticcli.utils.context_file import get_context_dir, write_context_file
from agenticcli.utils.session_id import generate_session_id
from agenticcli.utils.session_id import tmux_session_name as _tmux_session_name_util
from agenticcli.utils.session_state import mark_failed
from agenticcli.utils.state_store import StateStore, is_process_running
from agenticcli.utils.subprocess_utils import get_clean_env

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



def _enable_pipe_pane_logging(tmux_session_name: str, session_id: str) -> None:
    """Enable tmux pipe-pane to capture all pane output to a log file.

    Must be called AFTER the tmux session is created but BEFORE the agent
    starts producing significant output. The log file is written to
    ~/.agentic/sessions/logs/{session_id}.pane.log.
    """
    logs_dir = _get_logs_dir()
    pane_log = logs_dir / f"{session_id}.pane.log"
    try:
        subprocess.run(
            ["tmux", "pipe-pane", "-t", tmux_session_name,
             f"cat >> {pane_log}"],
            capture_output=True, timeout=5,
        )
        logger.debug("Enabled pipe-pane logging: %s -> %s", tmux_session_name, pane_log)
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.debug("Failed to enable pipe-pane for %s: %s", tmux_session_name, e)


def _tmux_session_name(
    session_id: str,
    epic_folder: Optional[Path] = None,
    role: Optional[str] = None,
) -> str:
    """Generate a descriptive tmux session name.

    Delegates to agenticcli.utils.session_id.tmux_session_name for the
    canonical implementation. Kept as a thin wrapper so internal callers
    are not broken.
    """
    return _tmux_session_name_util(session_id, epic_folder=epic_folder, role=role)


# Track tmux sessions for atexit cleanup
_active_tmux_sessions: list[str] = []


def _cleanup_tmux_sessions():
    """Kill any orphaned tmux sessions on unexpected exit."""
    for session_name in _active_tmux_sessions:
        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass


atexit.register(_cleanup_tmux_sessions)


def _compile_spawn_context(
    prompt: str,
    role: str | None,
    epic_folder: Path | None,
    phase_id: str | None = None,
) -> str:
    """Compile full context for a spawned session into a markdown document.

    Combines the spawn prompt with pre-fetched bootstrap context (role process,
    inputs manifest, current task) so the agent doesn't need to manually run
    ``agentic -j epic status --epic <epic>``.

    Args:
        prompt: The base prompt (from _build_role_prompt or _build_ticket_prompt).
        role: Agent role identifier, if known.
        epic_folder: Optional epic folder path.
        phase_id: Optional phase identifier — when provided, adds a Phase
            Constraint section instructing the agent to only work on tickets
            in that phase.

    Returns:
        Compiled context as a markdown string.
    """
    sections = [prompt]

    # Add phase constraint when the agent is scoped to a specific phase
    if phase_id and epic_folder:
        sections.append(
            f"\n---\n## Phase Constraint\n\n"
            f"You are scoped to phase **{phase_id}** of this epic. "
            f"Only work on tickets belonging to this phase.\n\n"
            f"When querying for your current ticket, use:\n"
            f"```\nagentic -j epic ticket current --epic {epic_folder} --phase \"{phase_id}\"\n```\n\n"
            f"Do NOT start or complete tickets from other phases."
        )

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

        # Get current ticket from epic if available
        if epic_folder:
            try:
                from agenticguidance.services import MainFirstPlanResolver
                resolver = MainFirstPlanResolver()
                current_task = resolver.extract_current_task(epic_folder)
                if current_task:
                    sections.append("\n---\n## Current Ticket\n")
                    sections.append(f"- **ID**: {current_task.get('id', 'N/A')}")
                    sections.append(f"- **Name**: {current_task.get('name', 'N/A')}")
                    sections.append(f"- **Status**: {current_task.get('status', 'N/A')}")
                    if current_task.get("description"):
                        sections.append(f"- **Description**: {current_task['description']}")
            except Exception:
                pass  # Epic ticket lookup is best-effort

    except Exception as e:
        # If bootstrap fails, the agent can still bootstrap manually
        logger.debug("Failed to compile bootstrap context: %s", e)
        sections.append(
            f"\nNote: Auto-bootstrap failed ({e}). "
            f"Run manually: agentic -j epic status --epic <epic>"
        )

    return "\n".join(sections)




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
    return session_data


def _get_all_unified_sessions(type_filter: str | None = None):
    """Get all sessions from the unified sessions store, optionally filtered by type.

    All session types (sessions, loops, orchestrations) now reside in the
    single 'sessions' StateStore. Records with no 'type' field are treated as
    plain Claude Code sessions.

    Args:
        type_filter: Optional type to filter by. One of "session", "loop",
            "orchestration". If None, returns all types.

    Returns:
        List of session dicts.
    """
    if type_filter:
        if type_filter == "session":
            # Plain sessions have no 'type' key or type == "session"
            filter_fn = lambda r: r.get("type") in (None, "session")
        else:
            filter_fn = lambda r: r.get("type") == type_filter
        return _store.list_all(filter_fn=filter_fn)
    return _store.list_all()


def _update_unified_session_status(session_data: dict) -> dict:
    """Update session status based on process state, for any session type.

    All records now live in the unified sessions store, so a single save
    is always sufficient regardless of session type.

    Args:
        session_data: Session data dict.

    Returns:
        Updated session data dict.
    """
    return _update_session_status(session_data)


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
    stdout_log_path = session.get("stdout_log")
    stderr_log_path = session.get("stderr_log")
    
    if stdout_log_path and Path(stdout_log_path).exists():
        stdout_path = Path(stdout_log_path)
    else:
        logs_dir = _get_logs_dir()
        stdout_path = logs_dir / f"{session_id}.stdout.log"
        
    if stderr_log_path and Path(stderr_log_path).exists():
        stderr_path = Path(stderr_log_path)
    else:
        logs_dir = _get_logs_dir()
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

    # Higher stale threshold for orchestration loops (can take a long time per iteration)
    stale_threshold = 30 if session.get("type") == "orchestration" else 10
    is_stale = status == "running" and minutes_since_write > stale_threshold
    signals.append({
        "name": "recent_activity",
        "ok": not is_stale,
        "detail": f"Last activity: {int(minutes_since_write)}m ago",
    })

    # Signal 4: tmux session existence (only for background Claude sessions)
    is_claude_session = session.get("type", "session") == "session"
    if session.get("background") and status == "running" and is_claude_session:
        tmux_exists = _check_tmux_session(session_id)
        if tmux_exists is not None:
            signals.append({
                "name": "tmux_session",
                "ok": tmux_exists,
                "detail": f"tmux session {'exists' if tmux_exists else 'missing'}",
            })

    # Overall health
    # Orchestration and loop types might not produce output immediately due to buffering
    requires_output = is_claude_session and minutes_since_write >= 2
    healthy = pid_alive and (has_output or not requires_output or status != "running")
    stale = is_stale

    return {
        "healthy": healthy,
        "signals": signals,
        "stale": stale,
        "stale_minutes": int(minutes_since_write),
    }


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
    elif args.session_command == "healthcheck":
        cmd_healthcheck(args, ctx)
    elif args.session_command == "logs":
        cmd_logs(args, ctx)
    else:
        print("Usage: agentic orchestrate session <spawn|list|stop>", file=sys.stderr)
        sys.exit(1)


def _resolve_epic_folder(epic_name: str) -> Path | None:
    """Resolve an epic folder name to its full path via TinyDB.

    Uses the TinyDB-first ``find_epic_folder()`` helper from the epic module.

    Args:
        epic_name: Epic folder name (e.g., '260207TA_cli_task_spawn').

    Returns:
        Path to epic folder, or None if not found.
    """
    try:
        from agenticcli.commands.epic import find_epic_folder
        return find_epic_folder(epic_name)
    except (SystemExit, Exception):
        return None



_DOGFOOD_STRATEGY = """
Dogfood Strategy — Self-Healing Gaps:
If you encounter a gap in the system (missing service, broken workflow, missing CLI command),
do NOT work around it silently. Instead:
1. Check if an epic already exists: agentic epic list
2. If a relevant epic exists, add a ticket to it or start working on the gap ticket.
3. If no epic exists, create one: agentic epic list (to confirm it's truly missing)
4. Then spawn a subagent to implement the fix:
   agentic orchestrate session spawn --role build-python --epic <epic_folder> -b
5. Continue your original work once the gap is resolved.
This ensures gaps are tracked and fixed systematically rather than patched ad-hoc.
""".strip()


# Roles that participate in the planning phase — must NEVER implement code.
# Mirrors _PLANNING_PHASE_ROLES from planner_loop.py.
_PLANNING_PHASE_ROLES_SESSION = frozenset({
    "epic-creator",
    "planner-explore",
    "explore",
    "build-story-writer",
    "planner-build",
    "planner-test",
    "planner-audit",
    "planner-orchestration",
})


def _build_role_prompt(role: str, epic_folder: Path | None) -> str:
    """Build a prompt for spawning an agent by role.

    Constructs a prompt that tells the agent its role and provides epic context.
    For planning-phase roles, injects a PLANNING-ONLY constraint to prevent
    agents from implementing instead of planning.

    Args:
        role: Agent role identifier (e.g., 'build-python').
        epic_folder: Optional path to epic folder for additional context.

    Returns:
        Constructed prompt string.
    """
    parts = [
        f"You are being spawned as a {role} agent.",
    ]

    if epic_folder:
        epic_name = epic_folder.name
        parts.append(f"Initialize your context by running: agentic -j epic status --epic {epic_name}")
        parts.append(f"Your active epic is: {epic_name}")
        parts.append(f"Epic path: {epic_folder}")
        parts.append(f"List tickets with: agentic -j epic ticket list --epic {epic_name}")
    else:
        parts.append("Initialize your context by running: agentic epic list")

    if role in _PLANNING_PHASE_ROLES_SESSION:
        parts.append(
            "IMPORTANT: This is a PLANNING-ONLY session. You must NOT implement code, "
            "write tests, or modify source files. Your job is to create, update, or "
            "review tickets, phases, stories, and architecture documents ONLY. "
            "Read source files for context but do not edit them."
        )
        parts.append(
            "All work products are managed through the epic/ticket system. "
            "Use `agentic epic ticket list` to see current tickets. "
            "Use `agentic epic ticket update` to modify tickets. "
            "Never create files directly — use CLI commands."
        )
        parts.append("Start by loading your bootstrap context, then plan the epic tasks.")
    else:
        if epic_folder:
            parts.append("Start by loading your bootstrap context, then work through the epic tickets.")
        # Dogfood strategy only for execution agents, not planners
        parts.append("")
        parts.append(_DOGFOOD_STRATEGY)

    return "\n".join(parts)


def _build_ticket_prompt(ticket_id: str, epic_folder: Path) -> str | None:
    """Build a prompt for spawning an agent for a specific ticket.

    Loads ticket details from the epic and constructs a focused prompt.

    Args:
        ticket_id: Ticket identifier (e.g., 'CLI_001').
        epic_folder: Path to epic folder.

    Returns:
        Constructed prompt string, or None if ticket not found.
    """
    from agenticguidance.services.ticket import TicketService

    service = TicketService(epic_folder)
    ticket = service.get_ticket(ticket_id)

    if not ticket:
        return None

    epic_name = epic_folder.name
    parts = [
        f"You are being spawned to work on ticket {ticket.id}: {ticket.name}",
        f"Epic: {epic_name}",
        "",
        f"Description: {ticket.description}",
    ]

    if ticket.guidance:
        parts.append(f"\nGuidance:\n{ticket.guidance}")

    if ticket.target_files:
        parts.append(f"\nTarget files: {', '.join(ticket.target_files)}")

    if ticket.inputs:
        parts.append(f"\nReference inputs: {', '.join(ticket.inputs)}")

    parts.append(f"\nWhen done, mark the ticket complete: agentic epic ticket complete {ticket_id} --epic {epic_name}")

    parts.append("")
    parts.append(_DOGFOOD_STRATEGY)

    return "\n".join(parts)


# Backward compatibility alias
_build_task_prompt = _build_ticket_prompt


def _build_tmux_wrapper_cmd(claude_cmd_str: str, session_id: str, state_dir: Path) -> str:
    """Build a bash wrapper command that runs claude and writes completion state.

    The returned bash string:
    1. Unsets CLAUDECODE / CLAUDE_CODE_ENTRYPOINT (env isolation)
    2. Runs the claude command
    3. Captures $? as EXIT_CODE
    4. Uses python3 -c to atomically update the session state JSON file with
       status (completed/failed), exit_code, and ended_at.

    This eliminates the correctness bug where tmux-spawned sessions always show
    status="completed" because wait_for_session inferred status from PID death
    and had no exit code information.

    Args:
        claude_cmd_str: The fully-quoted claude command string to execute.
        session_id: Session UUID for state file lookup.
        state_dir: Directory containing session state JSON files
                   (typically ~/.agentic/sessions/).

    Returns:
        A bash command string suitable for ``bash -c <wrapper>``.
    """
    import shlex

    state_file = str(state_dir / f"{session_id}.json")
    safe_state_file = shlex.quote(state_file)
    safe_session_id = shlex.quote(session_id)

    # The python3 inline script loads the state file, updates fields, and
    # writes it back.  If the file is missing or corrupt, a minimal fresh
    # record is written so downstream consumers always have state.
    python_update_script = (
        "import json, sys, os\n"
        "from datetime import datetime\n"
        "sf = sys.argv[1]\n"
        "sid = sys.argv[2]\n"
        "ec = int(sys.argv[3])\n"
        "try:\n"
        "    with open(sf) as f:\n"
        "        data = json.load(f)\n"
        "except (FileNotFoundError, json.JSONDecodeError):\n"
        "    data = {'session_id': sid, 'status': 'running'}\n"
        "data['status'] = 'completed' if ec == 0 else 'failed'\n"
        "data['exit_code'] = ec\n"
        "data['ended_at'] = datetime.now().isoformat()\n"
        "if ec != 0:\n"
        "    data['error_code'] = 'tmux_exit_nonzero'\n"
        "    data['failure_reason'] = {\n"
        "        'error_code': 'tmux_exit_nonzero',\n"
        "        'error_type': 'unknown',\n"
        "        'suggested_action': 'escalate',\n"
        "        'detail': f'tmux session exited with code {ec}',\n"
        "        'retryable': True,\n"
        "        'matched_pattern': '',\n"
        "    }\n"
        "with open(sf, 'w') as f:\n"
        "    json.dump(data, f, indent=2)\n"
    )
    safe_python_script = shlex.quote(python_update_script)

    wrapper = (
        f"unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT; "
        f"{claude_cmd_str}; "
        f"EXIT_CODE=$?; "
        f"python3 -c {safe_python_script} {safe_state_file} {safe_session_id} $EXIT_CODE"
    )
    return wrapper


def _build_sdk_tmux_cmd(
    session_id: str,
    role: str,
    context_file: "Path",
    working_dir: str,
    timeout: "int | None" = None,
) -> str:
    """Build command string for SDK pane runner in tmux.

    Unlike _build_tmux_wrapper_cmd, this does NOT wrap in a bash status callback
    because the pane runner writes its own state file.

    Args:
        session_id: Session UUID.
        role: Agent role identifier.
        context_file: Path to compiled context file.
        working_dir: Working directory for the agent.
        timeout: Optional timeout override (seconds).

    Returns:
        Command string for tmux new-session.
    """
    import shlex

    cmd_parts = [
        "unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT;",
        "python3", "-m", "agenticcli.utils.sdk_pane_runner",
        "--role", shlex.quote(role),
        "--session-id", shlex.quote(session_id),
        "--context-file", shlex.quote(str(context_file)),
        "--working-dir", shlex.quote(working_dir),
    ]
    if timeout is not None:
        cmd_parts.extend(["--timeout", str(timeout)])

    return " ".join(cmd_parts)


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

    # Resolve epic folder if provided
    epic_folder = None
    if plan_name:
        epic_folder = _resolve_epic_folder(plan_name)
        if not epic_folder:
            print_error(f"Epic folder not found: {plan_name}")
            sys.exit(1)

    # Validate: --task requires --epic
    if task_id and not epic_folder:
        print_error("--task requires --epic to be set.")
        sys.exit(1)

    # Build prompt from role or ticket if --prompt not provided
    if not prompt:
        if role:
            prompt = _build_role_prompt(role, epic_folder)
        elif task_id:
            prompt = _build_ticket_prompt(task_id, epic_folder)
            if not prompt:
                print_error(f"Ticket not found: {task_id} in epic {plan_name}")
                sys.exit(1)
        else:
            print_error("Prompt is required. Use --prompt, --role, or --task to specify.")
            sys.exit(1)

    max_turns = getattr(args, "max_turns", None)
    background = getattr(args, "background", False)
    use_tmux = getattr(args, "tmux", False)
    dry_run = getattr(args, "dry_run", False)
    phase_id = getattr(args, "phase", None)
    working_dir = getattr(args, "directory", None) or os.getcwd()

    # Safety net: apply a default max_turns for background/tmux sessions to
    # prevent agents from running indefinitely.  Foreground sessions are not
    # capped (the operator can Ctrl-C manually).
    DEFAULT_BACKGROUND_MAX_TURNS = 200
    if max_turns is None and (background or use_tmux):
        max_turns = DEFAULT_BACKGROUND_MAX_TURNS
        logger.info("No --max-turns specified for background/tmux session; defaulting to %d", max_turns)

    # ── Pre-flight health check ───────────────────────────────────────
    # Detect problematic environment state before committing to a spawn.
    from agenticcli.utils.subprocess_utils import get_clean_env
    env_warnings = []
    for var in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):
        if var in os.environ:
            env_warnings.append(var)
    if env_warnings:
        logger.warning(
            "Pre-flight: detected Claude Code env vars %s — spawned agent "
            "may fail with 'nested session' error unless env isolation works correctly",
            env_warnings,
        )
        if not is_json_output():
            print_warning(
                f"Detected Claude Code env vars: {env_warnings}. "
                f"Will strip before spawn to avoid nested-session errors."
            )

    # Determine which spawn path will be used
    from agenticcli.utils.sdk_runner import SDK_AVAILABLE
    from agenticcli.utils.transport import determine_transport, SDK_TMUX, TMUX, SUBPROCESS
    spawn_path = determine_transport(sdk_available=SDK_AVAILABLE, tmux_requested=use_tmux)

    logger.info("Pre-flight: spawn path = %s, background=%s, tmux=%s, max_turns=%s",
                spawn_path, background, use_tmux, max_turns)

    # Generate session ID
    session_id = generate_session_id()

    # Compile full context (prompt + bootstrap data) into a temp file
    # This avoids OS argument length limits and removes the need for
    # agents to manually run `agentic -j epic status --epic <epic>`
    compiled_context = _compile_spawn_context(prompt, role, epic_folder, phase_id=phase_id)
    context_file = write_context_file(session_id, compiled_context)

    short_prompt = (
        f"Your full instructions and context have been pre-compiled into a file. "
        f"IMPORTANT: Read the file at {context_file} FIRST before doing anything else. "
        f"It contains your role, task details, and bootstrap context."
    )

    # Build claude command base — both tmux and subprocess paths use -p
    # (print/pipe mode) which is multi-turn agentic with tool use.
    # The only difference is tmux provides a real PTY; subprocess does not.
    cmd_base = ["claude", "--dangerously-skip-permissions"]
    if max_turns:
        cmd_base.extend(["--max-turns", str(max_turns)])

    # Agentic command for tmux (has PTY, supports interactive tool use)
    cmd_agentic = list(cmd_base) + ["-p", short_prompt]

    # Agentic command for subprocess fallback (no PTY, but still multi-turn
    # with tool use via -p mode + --dangerously-skip-permissions).
    # NOTE: --output-format must come BEFORE -p since -p consumes the next
    # argument as the prompt text.
    cmd = list(cmd_base)
    if background:
        # Use JSON output for background sessions to capture Claude Code session_id
        cmd.extend(["--output-format", "json"])
    cmd.extend(["-p", short_prompt])

    # Estimate token usage from the compiled context (what the agent will process)
    prompt_tokens = estimate_tokens(compiled_context)
    usage_percent = context_usage_percent(prompt_tokens)
    usage_color = get_usage_color(usage_percent)

    # ── Dry-run exit: report diagnostics without spawning ─────────────
    if dry_run:
        # Clean up the context file since we're not spawning
        context_file.unlink(missing_ok=True)

        dry_run_info = {
            "dry_run": True,
            "spawn_path": spawn_path,
            "background": background,
            "tmux": use_tmux,
            "max_turns": max_turns,
            "estimated_tokens": prompt_tokens,
            "context_usage_percent": round(usage_percent, 1),
            "compiled_context_bytes": len(compiled_context),
            "env_warnings": env_warnings,
            "working_dir": working_dir,
            "role": role,
            "claude_available": shutil.which("claude") is not None,
            "tmux_available": shutil.which("tmux") is not None,
            "sdk_available": SDK_AVAILABLE,
        }
        if is_json_output():
            print_json(dry_run_info)
        else:
            console.print("[bold]Dry-run report:[/bold]")
            console.print(f"  Spawn path: [cyan]{spawn_path}[/cyan]")
            console.print(f"  Background: {background}")
            console.print(f"  Max turns: {max_turns}")
            console.print(f"  Context: [{usage_color}]{usage_percent:.1f}%[/{usage_color}] (~{prompt_tokens:,} tokens, {len(compiled_context):,} bytes)")
            console.print(f"  claude available: {shutil.which('claude') is not None}")
            console.print(f"  tmux available: {shutil.which('tmux') is not None}")
            console.print(f"  SDK available: {SDK_AVAILABLE}")
            if env_warnings:
                console.print(f"  [yellow]Env warnings: {env_warnings}[/yellow]")
            else:
                console.print(f"  Env: [green]clean[/green]")
        return

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
        "command": " ".join(cmd_agentic if use_tmux else cmd),
        "estimated_tokens": prompt_tokens,
        "context_usage_percent": usage_percent,
    }
    if use_tmux:
        session_data["tmux"] = True

    # ── Write session state BEFORE spawn to avoid race condition ───────
    # The pane runner and wait_for_session() poll this file. Writing it
    # before the tmux spawn ensures it exists on disk before the agent
    # starts, preventing negative durations and missing-state bugs.
    if role:
        session_data["role"] = role
    if epic_folder:
        session_data["epic_folder"] = str(epic_folder)
    _store.save(session_data)

    # ── SDK-in-tmux path: spawn SDK pane runner inside tmux ───────────
    if spawn_path == SDK_TMUX:
        tmux_session_name = _tmux_session_name(session_id, epic_folder, role)

        sdk_tmux_cmd = _build_sdk_tmux_cmd(
            session_id=session_id,
            role=role or "general",
            context_file=context_file,
            working_dir=working_dir,
            timeout=None,  # Let pane runner use role-based timeout from ROLE_TIMEOUT_SECONDS
        )

        try:
            tmux_result = subprocess.run(
                ["tmux", "new-session", "-d", "-s", tmux_session_name,
                 "bash", "-c", sdk_tmux_cmd],
                capture_output=True,
                text=True,
                cwd=working_dir,
            )

            if tmux_result.returncode != 0:
                logger.warning(
                    "sdk-tmux session creation failed (rc=%d): %s",
                    tmux_result.returncode, tmux_result.stderr,
                )
                if not is_json_output():
                    print_warning("sdk-tmux session creation failed, falling back to tmux")
                # Fall through to legacy tmux path
            else:
                # Verify session started
                time.sleep(0.5)
                from agenticcli.utils.tmux import session_exists as _tmux_session_exists

                if not _tmux_session_exists(tmux_session_name):
                    logger.error("sdk-tmux session %s exited immediately", tmux_session_name)
                    if not is_json_output():
                        print_warning("sdk-tmux session exited immediately, falling back to tmux")
                else:
                    # Success — only track for atexit cleanup in foreground mode.
                    # Background spawns must survive CLI exit.
                    if not background:
                        _active_tmux_sessions.append(tmux_session_name)

                    # Enable pipe-pane logging before agent produces output
                    _enable_pipe_pane_logging(tmux_session_name, session_id)

                    # Get PID
                    pid_result = subprocess.run(
                        ["tmux", "list-panes", "-t", tmux_session_name, "-F", "#{pane_pid}"],
                        capture_output=True, text=True,
                    )
                    tmux_pid = None
                    if pid_result.returncode == 0 and pid_result.stdout.strip():
                        try:
                            tmux_pid = int(pid_result.stdout.strip().split("\n")[0])
                        except ValueError:
                            pass

                    session_data["pid"] = tmux_pid
                    session_data["status"] = "running"
                    session_data["transport"] = "sdk-tmux"
                    session_data["tmux_session"] = tmux_session_name
                    session_data["last_activity"] = session_data["started_at"]
                    _store.save(session_data)

                    if background:
                        if is_json_output():
                            print_json({
                                "session_id": session_id,
                                "pid": tmux_pid,
                                "status": "running",
                                "background": True,
                                "transport": "sdk-tmux",
                                "tmux_session": tmux_session_name,
                                "estimated_tokens": prompt_tokens,
                                "context_usage_percent": round(usage_percent, 1),
                            })
                        else:
                            console.print(f"[dim]Context usage: [{usage_color}]{usage_percent:.1f}%[/{usage_color}] (~{prompt_tokens:,} tokens)[/dim]")
                            console.print(f"[green]Spawned SDK-in-tmux session {session_id[:8]}[/green]")
                            console.print(f"[dim]tmux attach -t {tmux_session_name}[/dim]")
                        return
                    else:
                        # Foreground: attach to tmux session
                        if not is_json_output():
                            console.print(f"[dim]Context usage: [{usage_color}]{usage_percent:.1f}%[/{usage_color}] (~{prompt_tokens:,} tokens)[/dim]")
                            console.print(f"[green]Attaching to SDK-in-tmux session {session_id[:8]}...[/green]")
                        subprocess.run(
                            ["tmux", "attach-session", "-t", tmux_session_name],
                            cwd=working_dir,
                        )
                        return
        except Exception as e:
            logger.warning("sdk-tmux path failed, falling back: %s", e)
            if not is_json_output():
                print_warning(f"sdk-tmux path failed ({e}), falling back")

    # ── Tmux path: spawn claude inside a tmux session ─────────────────
    if use_tmux:
        tmux_spawned = False

        if not shutil.which("tmux"):
            logger.warning("tmux not available, falling back to subprocess")
            if not is_json_output():
                print_warning("tmux not available, falling back to subprocess")
        else:
            # Generate descriptive tmux session name
            tmux_session_name = _tmux_session_name(session_id, epic_folder, role)

            # Build the claude command string for tmux, wrapped with a
            # completion callback that writes status/exit_code/ended_at back
            # to the session state file when claude exits.  This eliminates
            # the correctness bug where wait_for_session had to infer status
            # from PID death and always defaulted to "completed".
            import shlex
            claude_cmd_str = " ".join(shlex.quote(c) for c in cmd_agentic)
            wrapped_cmd = _build_tmux_wrapper_cmd(
                claude_cmd_str, session_id, _store.get_dir(),
            )

            try:
                # Create tmux session with command (session closes when command exits)
                tmux_result = subprocess.run(
                    ["tmux", "new-session", "-d", "-s", tmux_session_name,
                     "bash", "-c", wrapped_cmd],
                    capture_output=True,
                    text=True,
                    cwd=working_dir,
                )

                if tmux_result.returncode != 0:
                    logger.warning(
                        "tmux session creation failed (rc=%d): %s",
                        tmux_result.returncode, tmux_result.stderr,
                    )
                    if not is_json_output():
                        print_warning(f"tmux session creation failed, falling back to subprocess")
                    session_data["tmux_fallback"] = True
                else:
                    # Verify session started and is still running
                    time.sleep(0.5)
                    from agenticcli.utils.tmux import session_exists as _tmux_session_exists

                    if not _tmux_session_exists(tmux_session_name):
                        logger.error("tmux session %s exited immediately", tmux_session_name)
                        if not is_json_output():
                            print_warning("tmux session exited immediately, falling back to subprocess")
                        session_data["tmux_fallback"] = True
                    else:
                        # Tmux session is running successfully
                        tmux_spawned = True

                        # Track for atexit cleanup (foreground only — background
                        # sessions must survive CLI process exit).
                        if not background:
                            _active_tmux_sessions.append(tmux_session_name)

                        # Enable pipe-pane logging before agent produces output
                        _enable_pipe_pane_logging(tmux_session_name, session_id)

                        # Get PID of the process inside tmux for StateStore compatibility
                        pid_result = subprocess.run(
                            ["tmux", "list-panes", "-t", tmux_session_name, "-F", "#{pane_pid}"],
                            capture_output=True,
                            text=True,
                        )
                        tmux_pid = None
                        if pid_result.returncode == 0 and pid_result.stdout.strip():
                            try:
                                tmux_pid = int(pid_result.stdout.strip().split("\n")[0])
                            except ValueError:
                                pass

                        # Update session data
                        session_data["pid"] = tmux_pid
                        session_data["status"] = "running"
                        session_data["transport"] = "tmux"
                        session_data["tmux_session"] = tmux_session_name
                        session_data["last_activity"] = session_data["started_at"]
                        _store.save(session_data)

                        if background:
                            # Background: return immediately
                            if is_json_output():
                                print_json({
                                    "session_id": session_id,
                                    "pid": tmux_pid,
                                    "status": "running",
                                    "background": True,
                                    "transport": "tmux",
                                    "tmux_session": tmux_session_name,
                                    "estimated_tokens": prompt_tokens,
                                    "context_usage_percent": usage_percent,
                                })
                            else:
                                print_success(f"Session {session_id[:8]} started in tmux (session: {tmux_session_name})")
                                console.print(f"[dim]Context usage: [{usage_color}]{usage_percent:.1f}%[/{usage_color}] (~{prompt_tokens:,} tokens)[/dim]")
                                console.print(f"[dim]Attach: tmux attach -t {tmux_session_name}[/dim]")
                            return
                        else:
                            # Foreground: attach to tmux session and block until it ends
                            if not is_json_output():
                                console.print(f"[dim]Attaching to tmux session {tmux_session_name} (Ctrl+B, D to detach)...[/dim]")

                            attach_result = subprocess.run(
                                ["tmux", "attach", "-t", tmux_session_name],
                            )

                            # After attach returns, session is done (or user detached)
                            if _tmux_session_exists(tmux_session_name):
                                # User detached - session still running
                                if is_json_output():
                                    print_json({
                                        "session_id": session_id,
                                        "status": "running",
                                        "transport": "tmux",
                                        "tmux_session": tmux_session_name,
                                        "detached": True,
                                    })
                                else:
                                    print_success(f"Detached from session {session_id[:8]} (still running)")
                                    console.print(f"[dim]Re-attach: tmux attach -t {tmux_session_name}[/dim]")
                            else:
                                # Session ended
                                session_data["status"] = "completed" if attach_result.returncode == 0 else "failed"
                                session_data["ended_at"] = datetime.now().isoformat()
                                session_data["exit_code"] = attach_result.returncode
                                # Add structured failure info for tmux failures (P6_001/P6_003)
                                if attach_result.returncode != 0:
                                    mark_failed(
                                        session_data,
                                        error_code="tmux_exit_nonzero",
                                        error_type="unknown",
                                        detail=f"tmux session exited with code {attach_result.returncode}",
                                        retryable=True,
                                    )
                                _store.save(session_data)

                                # Remove from atexit tracking
                                if tmux_session_name in _active_tmux_sessions:
                                    _active_tmux_sessions.remove(tmux_session_name)

                                if is_json_output():
                                    print_json({
                                        "session_id": session_id,
                                        "status": session_data["status"],
                                        "exit_code": attach_result.returncode,
                                        "transport": "tmux",
                                        "tmux_session": tmux_session_name,
                                    })
                                else:
                                    if session_data["status"] == "completed":
                                        print_success(f"Session {session_id[:8]} completed")
                                    else:
                                        print_error(f"Session {session_id[:8]} failed (exit code {attach_result.returncode})")
                            return

            except Exception as e:
                logger.warning("tmux spawn failed, falling back to subprocess: %s", e)
                if not is_json_output():
                    print_warning(f"tmux spawn failed, falling back to subprocess")
                session_data["tmux_fallback"] = True

    # ── Subprocess path (fallback) ────────────────────────────────────
    # The -p flag passes the prompt as a CLI argument, so stdin is not
    # needed for prompt delivery.  Background sessions use DEVNULL;
    # foreground sessions inherit the parent's stdin (unused by Claude
    # in -p mode but harmless to leave open).
    session_data["transport"] = "subprocess"
    try:
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
                    env=get_clean_env(),
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

            # Check for immediate spawn failure
            time.sleep(1)
            if not is_process_running(process.pid):
                session_data["error"] = "Process died immediately after spawn"
                mark_failed(
                    session_data,
                    error_code="spawn_failure",
                    error_type="spawn_failure",
                    detail="Process died immediately after spawn",
                    retryable=True,
                )
                # Try to run diagnostics on log files if available
                try:
                    from agenticcli.utils.session_diagnostics import diagnose_session_log, failure_summary
                    diag = diagnose_session_log(
                        session_data.get("stdout_log", "/dev/null"),
                        session_data.get("stderr_log"),
                    )
                    summary = failure_summary(diag)
                    session_data["error_code"] = summary["error_code"]
                    session_data["failure_reason"] = summary
                except Exception:
                    pass  # Keep the generic failure_reason set above
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
                    "transport": "subprocess",
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
                    env=get_clean_env(),
                )

                # Capture output
                stdout, stderr = process.communicate()
                returncode = process.returncode

            session_data["status"] = "completed" if returncode == 0 else "failed"
            session_data["ended_at"] = datetime.now().isoformat()
            session_data["exit_code"] = returncode
            # Add structured failure diagnostics for non-zero exit (P6_001/P6_003)
            if returncode != 0 and stderr:
                mark_failed(
                    session_data,
                    error_code="process_exit_nonzero",
                    error_type="unknown",
                    detail=stderr,
                    retryable=False,
                )
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
        session_data["error"] = "Claude CLI not found. Make sure 'claude' is installed and in PATH."
        mark_failed(
            session_data,
            error_code="cli_not_found",
            error_type="cli_not_found",
            detail="Claude CLI not found. Make sure 'claude' is installed and in PATH.",
            retryable=False,
            suggested_action="check_permissions",
        )
        _store.save(session_data)
        print_error("Claude CLI not found. Make sure 'claude' is installed and in PATH.")
        sys.exit(1)
    except Exception as e:
        session_data["error"] = str(e)
        mark_failed(
            session_data,
            error_code="spawn_exception",
            error_type="unknown",
            detail=str(e),
            retryable=False,
        )
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
    """List Claude Code sessions, loops, and orchestrations.

    By default shows only running/starting sessions. Use --all to show all.
    Use --type to filter by session type (session, loop, orchestration).

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_header, print_json

    type_filter = getattr(args, "type", None)
    all_sessions = _get_all_unified_sessions(type_filter=type_filter)

    # Update status for running sessions
    for session in all_sessions:
        _update_unified_session_status(session)

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
            "type_filter": type_filter,
        })
        return

    print_header("Sessions")

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

    # Only show Tmux column if any session has a tmux_session
    display_sessions = sorted(all_sessions if show_all else sessions, key=lambda s: s.get("started_at", ""), reverse=True)
    has_tmux_sessions = any(s.get("tmux_session") for s in display_sessions)
    has_transport = any(s.get("transport") for s in display_sessions)

    _transport_labels = {
        "sdk-tmux": "SDK+Tmux",
        "tmux": "Tmux",
        "subprocess": "Proc",
        "sdk": "SDK",
    }

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="yellow", width=10)
    table.add_column("Type", style="cyan", width=13)
    table.add_column("Status", width=10)
    table.add_column("Health", width=8)
    table.add_column("Age", style="dim", width=10)
    table.add_column("PID", style="white", width=7)
    if has_tmux_sessions:
        table.add_column("Tmux", style="dim", width=20)
    if has_transport:
        table.add_column("Transport", style="cyan", width=10)
    table.add_column("Description", style="dim", no_wrap=False)

    status_colors = {
        "running": "green",
        "completed": "blue",
        "failed": "red",
        "starting": "yellow",
        "stopped": "yellow",
    }

    stale_count = 0

    for session in display_sessions:
        if not show_all and session.get("status") not in ("running", "starting"):
            continue
        session_id = session.get("session_id", "")[:8]
        pid = str(session.get("pid", "N/A"))
        status = session.get("status", "unknown")
        status_color = status_colors.get(status, "white")
        age = _format_relative_time(session.get("started_at", ""))
        session_type = session.get("type") or "session"
        prompt = session.get("prompt", "")
        # Clean up prompt for display: replace newlines, truncate to 60 chars
        prompt = prompt.replace("\n", " ").replace("\r", "")
        if len(prompt) > 60:
            prompt = prompt[:60] + "..."

        # Health column
        health = health_data.get(session.get("session_id", ""))
        if health:
            if health["stale"]:
                health_display = "[yellow]STALE[/yellow]"
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

        # Build row data
        row = [session_id, session_type, status_display, health_display, age, pid]

        if has_tmux_sessions:
            # Tmux column: show session name if tmux-spawned, "-" otherwise
            tmux_name = session.get("tmux_session", "")
            if tmux_name and session.get("status") in ("running", "starting"):
                row.append(f"[cyan]{tmux_name}[/cyan]")
            elif tmux_name:
                row.append(f"[dim]{tmux_name}[/dim]")
            else:
                row.append("[dim]-[/dim]")

        if has_transport:
            transport_raw = session.get("transport", "")
            transport_label = _transport_labels.get(transport_raw, transport_raw or "-")
            if transport_raw and session.get("status") in ("running", "starting"):
                row.append(f"[cyan]{transport_label}[/cyan]")
            elif transport_raw:
                row.append(f"[dim]{transport_label}[/dim]")
            else:
                row.append("[dim]-[/dim]")

        row.append(prompt)
        table.add_row(*row)

    console.print(table)

    if stale_count > 0:
        console.print(f"\n[yellow]Warning: {stale_count} session(s) appear stale. Use 'agentic orchestrate health <id>' for details.[/yellow]")

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

    # Kill associated tmux session if present
    tmux_session_name = session.get("tmux_session")
    if tmux_session_name:
        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", tmux_session_name],
                capture_output=True,
                timeout=5,
            )
            logger.info("Killed tmux session %s", tmux_session_name)
            # Remove from atexit tracking
            if tmux_session_name in _active_tmux_sessions:
                _active_tmux_sessions.remove(tmux_session_name)
        except Exception as e:
            # tmux session may already be dead — that's fine
            logger.debug("tmux kill-session %s failed (may already be dead): %s", tmux_session_name, e)

    try:
        if pid is None:
            raise ProcessLookupError("No PID recorded for session")
        if force:
            os.kill(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGTERM)

        session["status"] = "stopped"
        session["ended_at"] = datetime.now().isoformat()
        _store.save(session)

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


def cmd_healthcheck(args, ctx=None):
    """Check health/vitality of a session.

    Evaluates PID liveness, log file output, and activity recency
    to determine overall session health. Read-only operation.

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
