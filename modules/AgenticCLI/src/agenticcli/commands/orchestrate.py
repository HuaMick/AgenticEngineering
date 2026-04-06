# story: US-PLN-046
"""Orchestrate command - run automated orchestration planning and execution for epics.

Provides `planning` and `executing` actions for the orchestration lifecycle.
Supports --dry-run mode for testable tmux layout verification.
"""

import json as json_mod
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from agenticcli.utils.session_id import generate_loop_id
from agenticcli.utils.state_store import StateStore


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


_store = StateStore("sessions", id_key="session_id")


def _run_planning_loop(args, ctx=None):
    """Run automated planning loop.

    Args:
        args: Parsed arguments with background, max_iterations, etc.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success

    max_iterations = getattr(args, "max_iterations", 10)
    background = getattr(args, "background", False)
    completion_promise = getattr(args, "completion_promise", None)
    project = getattr(args, "project", None)
    plan_folder = getattr(args, "plan", None)
    working_dir = getattr(args, "directory", None) or os.getcwd()
    prompt = getattr(args, "prompt", None)

    loop_id = os.environ.get("AGENTIC_ORCH_LOOP_ID")
    if not loop_id:
        loop_id = generate_loop_id("orch")

    state = {
        "session_id": loop_id,
        "type": "orchestration",
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
        # Re-invoke in foreground as a subprocess to detach from the terminal.
        # NOTE: The actual Claude agent invocations inside the loop use the SDK
        # (via PlannerLoopWorkflow._run_role_agent). This subprocess is just
        # the process-control wrapper that allows background detachment.
        cmd = [sys.executable, "-m", "agenticcli.entry", "orchestrate", "session", "plan"]
        cmd.extend(["--max-iterations", str(max_iterations)])
        if completion_promise:
            cmd.extend(["--completion-promise", completion_promise])
        if project:
            cmd.extend(["--project", project])
        if plan_folder:
            cmd.extend(["--plan", plan_folder])
        if prompt:
            cmd.extend(["--prompt", prompt])
        if getattr(args, "dangerously_skip_permissions", False):
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--directory", working_dir])

        logs_dir = _store.get_dir() / loop_id
        logs_dir.mkdir(parents=True, exist_ok=True)

        stdout_log = open(logs_dir / "stdout.log", "w")
        stderr_log = open(logs_dir / "stderr.log", "w")

        from agenticcli.utils.subprocess_utils import get_clean_env
        env = get_clean_env()
        env["AGENTIC_ORCH_LOOP_ID"] = loop_id

        # Record SDK transport metadata so consumers know agent calls use the SDK
        from agenticcli.utils.sdk_runner import SDK_AVAILABLE as _ORCH_SDK_AVAILABLE
        from agenticcli.utils.transport import determine_transport
        state["transport"] = determine_transport(sdk_available=_ORCH_SDK_AVAILABLE)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdin=subprocess.DEVNULL,
                stdout=stdout_log,
                stderr=stderr_log,
                start_new_session=True,
                env=env,
            )
        finally:
            stdout_log.close()
            stderr_log.close()

        state["pid"] = process.pid
        state["status"] = "running"
        _store.save(state)

        if is_json_output():
            print_json({
                "session_id": loop_id,
                "type": "orchestration",
                "pid": process.pid,
                "status": "running",
                "background": True,
                "max_iterations": max_iterations,
                "transport": state["transport"],
            })
        else:
            print_success(f"Orchestration loop {loop_id} started in background (PID: {process.pid})")
            console.print(f"[dim]Max iterations: {max_iterations}[/dim]")
            if state["transport"] in ("sdk", "sdk-tmux"):
                console.print("[dim]Agent invocations use Claude Agent SDK[/dim]")
        return

    # Foreground execution
    state["pid"] = os.getpid()
    state["status"] = "running"
    _store.save(state)

    from agenticcli.workflows.orchestration import PlanningRunner
    from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

    workflow = PlannerLoopWorkflow(working_dir=working_dir, prompt=prompt)
    budget_usd = getattr(args, "budget_usd", 50.0)
    runner = PlanningRunner(
        workflow=workflow, project=project, plan_folder=plan_folder,
        budget_usd=budget_usd,
    )

    try:
        success = runner.run(
            max_iterations=max_iterations,
            completion_promise=completion_promise,
        )
        state["status"] = "completed" if success else "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["plans_processed"] = runner.state["plans_processed"]
        state["plans_failed"] = runner.state.get("plans_failed", [])
        state["errors"] = runner.state["errors"]
        state["current_iteration"] = runner.state["iteration"]
        _store.save(state)

        if is_json_output():
            print_json({
                "session_id": loop_id,
                "type": "orchestration",
                "status": state["status"],
                "iterations": runner.state["iteration"],
                "plans_processed": runner.state["plans_processed"],
                "plans_failed": runner.state.get("plans_failed", []),
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
        _store.save(state)
        print_error(f"Orchestration loop failed: {e}")
        sys.exit(1)


def _run_dry_run(args, ctx=None):
    """Create tmux layout, verify pane count, print JSON, then exit.

    This enables automated testing of the tmux GUI path without needing
    a human to interact with Claude or dashboard processes.
    """
    from agenticcli.utils.tmux_layout import (
        cleanup_orchestration_sessions,
        create_orchestration_layout,
        tmux_available,
    )

    if not tmux_available():
        print(json_mod.dumps({"error": "tmux is not available"}), file=sys.stderr)
        sys.exit(1)

    # Clean up any orphaned sessions first
    cleanup_orchestration_sessions()

    session_name = f"agentic-orch-dryrun-{os.getpid()}"

    try:
        layout = create_orchestration_layout(
            claude_cmd_str="echo dry-run",
            skip_commands=True,
        )
        session_name = layout.session_name

        # Query actual pane count from tmux
        result = subprocess.run(
            ["tmux", "list-panes", "-t", session_name, "-F", "#{pane_id} #{pane_title}"],
            capture_output=True, text=True,
        )
        panes = []
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split(None, 1)
                panes.append({
                    "pane_id": parts[0],
                    "pane_title": parts[1] if len(parts) > 1 else "",
                })

        output = {
            "session_name": layout.session_name,
            "main_pane_id": layout.main_pane_id,
            "status_pane_id": layout.status_pane_id,
            "questions_pane_id": layout.questions_pane_id,
            "created_new_session": layout.created_new_session,
            "pane_count": len(panes),
            "panes": panes,
        }

        print(json_mod.dumps(output, indent=2))

        if len(panes) != 3:
            print(f"ERROR: Expected 3 panes, got {len(panes)}", file=sys.stderr)
            sys.exit(1)

    finally:
        # Always clean up the test session
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
        )

    sys.exit(0)


def _run_executing_loop(args, ctx=None):
    """Run automated execution loop.

    Args:
        args: Parsed arguments with background, max_iterations, etc.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success

    max_iterations = getattr(args, "max_iterations", 10)
    background = getattr(args, "background", False)
    completion_promise = getattr(args, "completion_promise", None)
    project = getattr(args, "project", None)
    plan_folder = getattr(args, "plan", None)
    working_dir = getattr(args, "directory", None) or os.getcwd()
    skip_perms = getattr(args, "dangerously_skip_permissions", False)

    loop_id = os.environ.get("AGENTIC_EXEC_LOOP_ID")
    if not loop_id:
        loop_id = generate_loop_id("exec")

    state = {
        "session_id": loop_id,
        "type": "execution",
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "pid": None,
        "max_iterations": max_iterations,
        "current_iteration": 0,
        "plans_processed": [],
        "plans_failed": [],
        "phases_completed": [],
        "phases_failed": [],
        "errors": [],
        "completion_promise": completion_promise,
        "directory": working_dir,
        "plan_folder": plan_folder,
    }

    if background:
        # Re-invoke in foreground as a subprocess to detach from the terminal.
        # NOTE: The actual Claude agent invocations inside the loop use the SDK
        # (via OrchestrationWorkflow). This subprocess is just the process-control
        # wrapper that allows background detachment.
        cmd = [sys.executable, "-m", "agenticcli.entry", "orchestrate", "session", "implement"]
        cmd.extend(["--max-iterations", str(max_iterations)])
        if completion_promise:
            cmd.extend(["--completion-promise", completion_promise])
        if project:
            cmd.extend(["--project", project])
        if plan_folder:
            cmd.extend(["--plan", plan_folder])
        if skip_perms:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--directory", working_dir])

        logs_dir = _store.get_dir() / loop_id
        logs_dir.mkdir(parents=True, exist_ok=True)

        stdout_log = open(logs_dir / "stdout.log", "w")
        stderr_log = open(logs_dir / "stderr.log", "w")

        from agenticcli.utils.subprocess_utils import get_clean_env
        env = get_clean_env()
        env["AGENTIC_EXEC_LOOP_ID"] = loop_id

        # Record SDK transport metadata so consumers know agent calls use the SDK
        from agenticcli.utils.sdk_runner import SDK_AVAILABLE as _EXEC_SDK_AVAILABLE
        from agenticcli.utils.transport import determine_transport
        state["transport"] = determine_transport(sdk_available=_EXEC_SDK_AVAILABLE)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdin=subprocess.DEVNULL,
                stdout=stdout_log,
                stderr=stderr_log,
                start_new_session=True,
                env=env,
            )
        finally:
            stdout_log.close()
            stderr_log.close()

        state["pid"] = process.pid
        state["status"] = "running"
        _store.save(state)

        if is_json_output():
            print_json({
                "session_id": loop_id,
                "type": "execution",
                "pid": process.pid,
                "status": "running",
                "background": True,
                "max_iterations": max_iterations,
                "transport": state["transport"],
            })
        else:
            print_success(f"Execution loop {loop_id} started in background (PID: {process.pid})")
            console.print(f"[dim]Max iterations: {max_iterations}[/dim]")
            if state["transport"] in ("sdk", "sdk-tmux"):
                console.print("[dim]Agent invocations use Claude Agent SDK[/dim]")
        return

    # Foreground execution
    state["pid"] = os.getpid()
    state["status"] = "running"
    _store.save(state)

    from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

    workflow = OrchestrationWorkflow(working_dir=working_dir)
    budget_usd = getattr(args, "budget_usd", 50.0)
    runner = ExecutionRunner(
        workflow=workflow,
        project=project,
        plan_folder=plan_folder,
        dangerously_skip_permissions=skip_perms,
        budget_usd=budget_usd,
    )

    try:
        success = runner.run(
            max_iterations=max_iterations,
            completion_promise=completion_promise,
        )
        state["status"] = "completed" if success else "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["plans_processed"] = runner.state["plans_processed"]
        state["plans_failed"] = runner.state.get("plans_failed", [])
        state["phases_completed"] = runner.state.get("phases_completed", [])
        state["phases_failed"] = runner.state.get("phases_failed", [])
        state["errors"] = runner.state["errors"]
        state["current_iteration"] = runner.state["iteration"]
        _store.save(state)

        if is_json_output():
            print_json({
                "session_id": loop_id,
                "type": "execution",
                "status": state["status"],
                "iterations": runner.state["iteration"],
                "plans_processed": runner.state["plans_processed"],
                "plans_failed": runner.state.get("plans_failed", []),
                "phases_completed": runner.state.get("phases_completed", []),
                "phases_failed": runner.state.get("phases_failed", []),
                "errors": runner.state["errors"],
            })
        else:
            if success:
                print_success(f"Execution loop {loop_id} completed")
                console.print(f"[dim]Plans processed: {len(runner.state['plans_processed'])}[/dim]")
                console.print(f"[dim]Phases completed: {len(runner.state.get('phases_completed', []))}[/dim]")
            else:
                print_error(f"Execution loop {loop_id} finished with errors")
                for err in runner.state["errors"]:
                    console.print(f"[red]  {err}[/red]")
    except Exception as e:
        state["status"] = "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["errors"].append(str(e))
        _store.save(state)
        print_error(f"Execution loop failed: {e}")
        sys.exit(1)


def cmd_orchestrate(args, ctx=None):
    """Run automated orchestration planning or execution for epics.

    Args:
        args: Parsed arguments with action, epic, background, max_iterations, etc.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import print_error

    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        _run_dry_run(args, ctx)
        return

    action = getattr(args, "action", None)
    if action == "planning":
        _run_planning_loop(args, ctx)
    elif action == "executing":
        _run_executing_loop(args, ctx)
    else:
        print_error(f"Unknown action '{action}'. Valid actions: planning, executing")
        sys.exit(1)
