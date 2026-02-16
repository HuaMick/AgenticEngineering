"""Orchestrate command - launch interactive Claude session with agent profile context.

Replaces the current process with an interactive Claude Code session
pre-loaded with the orchestration agent's process file and bootstrap context.

By default, creates a 3-pane tmux layout with:
- Main pane: interactive Claude orchestrator (auto-started)
- Status pane: live session dashboard
- Questions pane: pending questions dashboard

Use --no-tmux flag to bypass tmux layout and launch plain Claude session.

Also supports --planning-loop mode for automated plan lifecycle execution.
"""

import json
import os
import shlex
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Map --mode values to agent profile directories and default roles
_MODE_CONFIG = {
    "planning": {
        "agent_dir": "orchestration-planning",
        "role": "orchestration-planning",
    },
    "executor": {
        "agent_dir": "orchestration-executor",
        "role": "orchestration-executor",
    },
    "friction": {
        "agent_dir": "orchestration-friction",
        "role": "orchestration-friction",
    },
    "loop": {
        "agent_dir": "orchestration-loop",
        "role": "orchestration-loop",
    },
}

VALID_MODES = list(_MODE_CONFIG.keys())

_AGENTS_BASE = Path(
    "modules/AgenticGuidance/agents/orchestration"
)


def _get_repo_root() -> Path:
    """Find the repository root via git rev-parse."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: walk up from this file
        p = Path(__file__).resolve()
        while p != p.parent:
            if (p / ".git").exists():
                return p
            p = p.parent
        return Path.cwd()


def _find_process_file(agent_dir: Path) -> Path | None:
    """Find the process file (process.yml or process.mmd) in an agent directory."""
    for ext in ("yml", "mmd", "yaml", "md"):
        candidate = agent_dir / f"process.{ext}"
        if candidate.exists():
            return candidate
    return None


def _build_bootstrap_context(role: str, plan_name: str | None) -> str:
    """Build markdown bootstrap context from existing services.

    Args:
        role: Role identifier for bootstrap context.
        plan_name: Optional plan folder name to scope context.

    Returns:
        Markdown-formatted bootstrap context string.
    """
    sections = []

    # Active plan info
    try:
        from agenticguidance.services import MainFirstPlanResolver
        resolver = MainFirstPlanResolver()
        plan_info = resolver.resolve_active_plan()

        if plan_info:
            sections.append(f"**Active Plan:** {plan_info.get('plan_folder_name', 'N/A')}")
            if plan_info.get("objective"):
                sections.append(f"**Objective:** {plan_info['objective']}")
            if plan_info.get("plan_folder"):
                sections.append(f"**Plan Path:** {plan_info['plan_folder']}")

            # Current task
            current_task = resolver.extract_current_task(plan_info["plan_folder"])
            if current_task:
                sections.append(f"\n### Current Task")
                sections.append(f"- **ID:** {current_task.get('id', 'N/A')}")
                sections.append(f"- **Name:** {current_task.get('name', 'N/A')}")
                sections.append(f"- **Status:** {current_task.get('status', 'N/A')}")
    except Exception:
        sections.append("*Could not resolve active plan.*")

    # Role guidance
    try:
        from agenticguidance.services import get_role_process
        role_process = get_role_process(role)
        if role_process:
            sections.append(f"\n### Role Guidance ({role})")
            if isinstance(role_process, dict):
                if role_process.get("description"):
                    sections.append(f"**Description:** {role_process['description']}")
    except Exception:
        pass

    # Plan-specific context
    if plan_name:
        sections.append(f"\n### Scoped Plan: {plan_name}")
        try:
            repo_root = _get_repo_root()
            plan_path = repo_root / "docs" / "plans" / "live" / plan_name
            if plan_path.exists():
                sections.append(f"**Path:** {plan_path}")
            else:
                sections.append(f"*Plan folder not found at {plan_path}*")
        except Exception:
            pass

    # CLI command reference
    sections.append("\n### CLI Commands")
    sections.append("- `agentic --json plan list` - List all live plans")
    sections.append("- `agentic --json plan status <folder>` - Plan status")
    sections.append("- `agentic --json plan task list --plan <folder>` - List tasks")
    sections.append("- `agentic --json plan task current --plan <folder>` - Current task")
    sections.append("- `agentic --json context bootstrap --role <role>` - Bootstrap context")
    sections.append("- `agentic --json stories find --project <project>` - Find stories")

    return "\n".join(sections)


def _get_orchestration_loops_dir() -> Path:
    """Get the orchestration loops state directory.

    Returns:
        Path to ~/.agentic/orchestration_loops/
    """
    loops_dir = Path.home() / ".agentic" / "orchestration_loops"
    loops_dir.mkdir(parents=True, exist_ok=True)
    return loops_dir


def _save_state(state: dict, state_dir: Optional[Path] = None) -> None:
    """Write orchestration loop state to JSON file.

    Args:
        state: State dict with 'id' key.
        state_dir: Override state directory (for testing).
    """
    d = state_dir or _get_orchestration_loops_dir()
    state_file = d / f"{state['id']}.json"
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def _run_planning_loop(args, ctx=None):
    """Run automated planning loop instead of interactive session.

    Args:
        args: Parsed arguments with planning_loop, background, max_iterations, etc.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success

    max_iterations = getattr(args, "max_iterations", 10)
    background = getattr(args, "background", False)
    completion_promise = getattr(args, "completion_promise", None)
    project = getattr(args, "project", None)
    plan_folder = getattr(args, "plan", None)
    working_dir = getattr(args, "directory", None) or os.getcwd()

    loop_id = f"orch-{uuid.uuid4().hex[:12]}"

    state = {
        "id": loop_id,
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "pid": None,
        "max_iterations": max_iterations,
        "current_iteration": 0,
        "plans_processed": [],
        "plans_failed": [],
        "current_plan": None,
        "errors": [],
        "completion_promise": completion_promise,
        "directory": working_dir,
        "plan_folder": plan_folder,
    }

    if background:
        # Re-invoke in foreground as a subprocess
        cmd = [sys.executable, "-m", "agenticcli.entry", "orchestrate"]
        cmd.extend(["--planning-loop"])
        cmd.extend(["--max-iterations", str(max_iterations)])
        if completion_promise:
            cmd.extend(["--completion-promise", completion_promise])
        if project:
            cmd.extend(["--project", project])
        if plan_folder:
            cmd.extend(["--plan", plan_folder])
        if getattr(args, "dangerously_skip_permissions", False):
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--directory", working_dir])

        logs_dir = _get_orchestration_loops_dir() / loop_id
        logs_dir.mkdir(parents=True, exist_ok=True)

        stdout_log = open(logs_dir / "stdout.log", "w")
        stderr_log = open(logs_dir / "stderr.log", "w")

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
            stdout_log.close()
            stderr_log.close()

        state["pid"] = process.pid
        state["status"] = "running"
        _save_state(state)

        if is_json_output():
            print_json({
                "id": loop_id,
                "pid": process.pid,
                "status": "running",
                "background": True,
                "max_iterations": max_iterations,
            })
        else:
            print_success(f"Orchestration loop {loop_id} started in background (PID: {process.pid})")
            console.print(f"[dim]Max iterations: {max_iterations}[/dim]")
        return

    # Foreground execution
    state["pid"] = os.getpid()
    state["status"] = "running"
    _save_state(state)

    from agenticcli.workflows.orchestration import OrchestrationRunner, OrchestrationWorkflow

    plans_dir = Path(working_dir) / "docs" / "plans" / "live"
    workflow = OrchestrationWorkflow(plans_dir=plans_dir, working_dir=working_dir)
    runner = OrchestrationRunner(
        workflow=workflow, project=project, plan_folder=plan_folder
    )

    try:
        success = runner.run(
            max_iterations=max_iterations,
            completion_promise=completion_promise,
        )
        state["status"] = "completed" if success else "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["plans_processed"] = runner.state["plans_processed"]
        state["plans_failed"] = runner.state["plans_failed"]
        state["errors"] = runner.state["errors"]
        state["current_iteration"] = runner.state["iteration"]
        _save_state(state)

        if is_json_output():
            print_json({
                "id": loop_id,
                "status": state["status"],
                "iterations": runner.state["iteration"],
                "plans_processed": runner.state["plans_processed"],
                "plans_failed": runner.state["plans_failed"],
                "errors": runner.state["errors"],
            })
        else:
            if success:
                print_success(f"Orchestration loop {loop_id} completed")
                console.print(f"[dim]Plans processed: {len(runner.state['plans_processed'])}[/dim]")
            else:
                print_error(f"Orchestration loop {loop_id} finished with errors")
                for err in runner.state["errors"]:
                    console.print(f"[red]  {err}[/red]")
    except Exception as e:
        state["status"] = "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["errors"].append(str(e))
        _save_state(state)
        print_error(f"Orchestration loop failed: {e}")
        sys.exit(1)


def cmd_orchestrate(args, ctx=None):
    """Launch an interactive Claude Code session with orchestration context.

    Loads the agent process file for the given --mode and builds bootstrap
    context, then replaces the current process with an interactive Claude session.

    If --planning-loop flag is set, runs automated planning loop instead.

    If --no-tmux flag is NOT set and tmux is available, creates a 3-pane
    tmux layout with session dashboard and questions dashboard.

    Args:
        args: Parsed arguments with mode, prompt_file, role, plan, model, planning_loop,
              no_tmux, dashboard_refresh, question_refresh.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import print_error, print_warning

    # Check for --planning-loop flag
    planning_loop = getattr(args, "planning_loop", False)
    if planning_loop:
        _run_planning_loop(args, ctx)
        return

    mode = getattr(args, "mode", None)
    if not mode or mode not in _MODE_CONFIG:
        print_error(f"--mode is required. Valid modes: {', '.join(VALID_MODES)}")
        sys.exit(1)

    config = _MODE_CONFIG[mode]
    repo_root = _get_repo_root()

    # 1. Resolve process file: --prompt-file overrides, otherwise load from agent profile
    prompt_file = getattr(args, "prompt_file", None)
    if prompt_file:
        prompt_path = Path(prompt_file)
        if not prompt_path.is_absolute():
            prompt_path = repo_root / prompt_path
    else:
        agent_dir = repo_root / _AGENTS_BASE / config["agent_dir"]
        prompt_path = _find_process_file(agent_dir)
        if prompt_path is None:
            print_error(
                f"No process file found for mode '{mode}' in {agent_dir}"
            )
            sys.exit(1)

    if not prompt_path.exists():
        print_error(f"Process file not found: {prompt_path}")
        sys.exit(1)

    prompt_content = prompt_path.read_text()

    # 2. Build bootstrap context
    role = getattr(args, "role", None) or config["role"]
    plan_name = getattr(args, "plan", None)
    bootstrap_text = _build_bootstrap_context(role, plan_name)

    # 3. Combine into system prompt appendix
    system_prompt = (
        f"{prompt_content}\n\n---\n\n"
        f"## BOOTSTRAP CONTEXT (auto-injected)\n\n{bootstrap_text}"
    )

    # 4. Write system prompt to temp file (avoids tmux send-keys character limit)
    # Note: File is not deleted because this process will be replaced by os.execvp.
    # The file persists in /tmp/ and will be cleaned up by the system.
    prompt_tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.md', delete=False, prefix='agentic_prompt_'
    )
    prompt_tmp.write(system_prompt)
    prompt_tmp.close()

    # 5. Build base claude command args (without system prompt - added per-path below)
    base_cmd = ["claude", "--dangerously-skip-permissions"]
    model = getattr(args, "model", None)
    if model:
        base_cmd.extend(["--model", model])

    # 6. Check for tmux layout path (unless --no-tmux is set)
    no_tmux = getattr(args, "no_tmux", False)
    dashboard_refresh = getattr(args, "dashboard_refresh", 5)
    question_refresh = getattr(args, "question_refresh", 10)

    if not no_tmux:
        try:
            from agenticcli.utils.tmux_layout import (
                create_orchestration_layout,
                attach_to_session,
                tmux_available,
            )
            from agenticcli.utils.tmux import is_in_tmux

            if tmux_available():
                # Build shell command string for tmux send-keys.
                # Use double quotes around $(cat file) so bash expands the
                # substitution (single quotes from shlex.quote would block it).
                tmux_parts = ["claude", "--dangerously-skip-permissions"]
                if model:
                    tmux_parts.extend(["--model", shlex.quote(model)])
                tmux_parts.extend([
                    "--append-system-prompt",
                    f'"$(cat {shlex.quote(prompt_tmp.name)})"',
                ])
                tmux_cmd_str = " ".join(tmux_parts)

                # Create the 3-pane layout (cleans up orphaned sessions first)
                layout = create_orchestration_layout(
                    claude_cmd_str=tmux_cmd_str,
                    dashboard_refresh=dashboard_refresh,
                    question_refresh=question_refresh,
                )

                # If we created a new session, attach to it (this will exec and not return)
                if layout.created_new_session:
                    attach_to_session(layout.session_name)
                else:
                    # Already in tmux, layout is created, exec with full content
                    direct_cmd = base_cmd + ["--append-system-prompt", system_prompt]
                    os.execvp("claude", direct_cmd)
            else:
                # tmux not available, pass full content directly (no char limit)
                print_warning("tmux not available, launching without dashboard layout")
                direct_cmd = base_cmd + ["--append-system-prompt", system_prompt]
                os.execvp("claude", direct_cmd)

        except RuntimeError as e:
            # Graceful fallback if tmux layout creation fails
            print_warning(f"Failed to create tmux layout: {e}")
            print_warning("Falling back to plain Claude session")
            direct_cmd = base_cmd + ["--append-system-prompt", system_prompt]
            os.execvp("claude", direct_cmd)
    else:
        # --no-tmux flag set, pass full content directly (no char limit)
        direct_cmd = base_cmd + ["--append-system-prompt", system_prompt]
        os.execvp("claude", direct_cmd)
