"""Planner loop CLI commands.

Commands for starting, stopping, and monitoring the orchestration planner loop.
The planner loop automates the planning workflow: discovers plans needing
orchestration MMDs, spawns specialized planners, runs review cycles,
and generates validated MMD files.
"""

import logging
import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

from agenticcli.utils.state_store import StateStore, is_process_running

logger = logging.getLogger(__name__)

_store = StateStore("planner_loops", id_key="id")


def handle(args, ctx=None):
    """Route planner subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext.
    """
    cmd = args.planner_command
    if cmd == "start":
        cmd_start(args, ctx)
    elif cmd == "stop":
        cmd_stop(args, ctx)
    elif cmd == "status":
        cmd_status(args, ctx)
    else:
        print("Usage: agentic session planner <start|stop|status>", file=sys.stderr)
        sys.exit(1)


def cmd_start(args, ctx=None):
    """Start the planner loop.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success

    max_iterations = getattr(args, "max_iterations", 10)
    background = getattr(args, "background", False)
    completion_promise = getattr(args, "completion_promise", None)
    project = getattr(args, "project", None)
    working_dir = getattr(args, "directory", None) or os.getcwd()

    loop_id = f"pl-{uuid.uuid4().hex[:12]}"

    state = {
        "id": loop_id,
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "pid": None,
        "max_iterations": max_iterations,
        "current_iteration": 0,
        "plans_processed": [],
        "plans_pending": [],
        "current_plan": None,
        "errors": [],
        "completion_promise": completion_promise,
        "directory": working_dir,
    }

    if background:
        # Re-invoke in foreground as a subprocess
        cmd = [sys.executable, "-m", "agenticcli.entry", "planner", "start"]
        cmd.extend(["--max-iterations", str(max_iterations)])
        if completion_promise:
            cmd.extend(["--completion-promise", completion_promise])
        if project:
            cmd.extend(["--project", project])
        if getattr(args, "dangerously_skip_permissions", False):
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--directory", working_dir])

        logs_dir = _store.get_dir() / loop_id
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
        _store.save(state)

        if is_json_output():
            print_json({
                "id": loop_id,
                "pid": process.pid,
                "status": "running",
                "background": True,
                "max_iterations": max_iterations,
            })
        else:
            print_success(f"Planner loop {loop_id} started in background (PID: {process.pid})")
            console.print(f"[dim]Max iterations: {max_iterations}[/dim]")
        return

    # Foreground execution
    state["pid"] = os.getpid()
    state["status"] = "running"
    _store.save(state)

    from agenticcli.workflows.planner_loop import PlannerLoopRunner, PlannerLoopWorkflow

    plans_dir = Path(working_dir) / "docs" / "plans" / "live"
    workflow = PlannerLoopWorkflow(plans_dir=plans_dir, working_dir=working_dir)
    runner = PlannerLoopRunner(workflow=workflow, project=project)

    try:
        success = runner.run(
            max_iterations=max_iterations,
            completion_promise=completion_promise,
        )
        state["status"] = "completed" if success else "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["plans_processed"] = runner.state["plans_processed"]
        state["errors"] = runner.state["errors"]
        state["current_iteration"] = runner.state["iteration"]
        _store.save(state)

        if is_json_output():
            print_json({
                "id": loop_id,
                "status": state["status"],
                "iterations": runner.state["iteration"],
                "plans_processed": runner.state["plans_processed"],
                "errors": runner.state["errors"],
            })
        else:
            if success:
                print_success(f"Planner loop {loop_id} completed")
                console.print(f"[dim]Plans processed: {len(runner.state['plans_processed'])}[/dim]")
            else:
                print_error(f"Planner loop {loop_id} finished with errors")
                for err in runner.state["errors"]:
                    console.print(f"[red]  {err.get('plan', 'N/A')}: {err.get('error', 'unknown')}[/red]")
    except Exception as e:
        state["status"] = "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["errors"].append({"plan": None, "error": str(e)})
        _store.save(state)
        print_error(f"Planner loop failed: {e}")
        sys.exit(1)


def cmd_stop(args, ctx=None):
    """Stop a running planner loop.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    planner_id = getattr(args, "planner_id", None)
    if not planner_id:
        print_error("Planner loop ID is required.")
        sys.exit(1)

    # Find by ID (support partial matching)
    states = _store.list_all()
    matching = [s for s in states if s.get("id", "").startswith(planner_id)]

    if not matching:
        print_error(f"Planner loop not found: {planner_id}")
        sys.exit(1)

    if len(matching) > 1:
        print_error(f"Multiple loops match '{planner_id}'. Provide a more specific ID.")
        sys.exit(1)

    state = matching[0]
    pid = state.get("pid")
    status = state.get("status")

    if status in ("completed", "stopped", "failed"):
        if is_json_output():
            print_json({"id": state["id"], "status": status, "message": f"Already {status}", "success": True})
        else:
            print_success(f"Planner loop {state['id']} is already {status}")
        return

    force = getattr(args, "force", False)
    try:
        if force:
            os.kill(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGTERM)

        state["status"] = "stopped"
        state["completed_at"] = datetime.now().isoformat()
        _store.save(state)

        if is_json_output():
            print_json({"id": state["id"], "pid": pid, "status": "stopped", "success": True})
        else:
            print_success(f"Planner loop {state['id']} stopped (PID: {pid})")

    except ProcessLookupError:
        state["status"] = "completed"
        state["completed_at"] = datetime.now().isoformat()
        _store.save(state)
        if is_json_output():
            print_json({"id": state["id"], "status": "completed", "message": "Process already exited", "success": True})
        else:
            print_success(f"Planner loop {state['id']} already exited")
    except PermissionError:
        print_error(f"Permission denied to stop process {pid}")
        sys.exit(1)


def cmd_status(args, ctx=None):
    """Show planner loop status.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json

    planner_id = getattr(args, "planner_id", None)

    if not planner_id:
        # List all planner loops
        states = _store.list_all()
        # Update status for running loops
        for s in states:
            if s.get("status") == "running":
                pid = s.get("pid")
                if pid and not is_process_running(pid):
                    s["status"] = "completed"
                    s["completed_at"] = datetime.now().isoformat()
                    _store.save(s)

        if is_json_output():
            print_json({"loops": states, "count": len(states)})
            return

        print_header("Planner Loops")
        if not states:
            console.print("[dim]No planner loops found[/dim]")
            return

        from rich.table import Table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("ID", style="yellow", width=18)
        table.add_column("Status", width=12)
        table.add_column("Iter", width=8)
        table.add_column("Processed", width=10)
        table.add_column("Errors", width=8)
        table.add_column("Started", style="dim", width=20)

        status_colors = {
            "running": "green", "completed": "blue",
            "failed": "red", "stopped": "yellow", "starting": "yellow",
        }

        for s in sorted(states, key=lambda x: x.get("started_at", ""), reverse=True):
            st = s.get("status", "unknown")
            color = status_colors.get(st, "white")
            table.add_row(
                s.get("id", "?"),
                f"[{color}]{st}[/{color}]",
                f"{s.get('current_iteration', 0)}/{s.get('max_iterations', '?')}",
                str(len(s.get("plans_processed", []))),
                str(len(s.get("errors", []))),
                str(s.get("started_at", ""))[:19],
            )
        console.print(table)
        return

    # Specific loop status
    states = _store.list_all()
    matching = [s for s in states if s.get("id", "").startswith(planner_id)]

    if not matching:
        print_error(f"Planner loop not found: {planner_id}")
        sys.exit(1)

    if len(matching) > 1:
        print_error(f"Multiple loops match '{planner_id}'.")
        sys.exit(1)

    state = matching[0]

    # Update status if running
    if state.get("status") == "running":
        pid = state.get("pid")
        if pid and not is_process_running(pid):
            state["status"] = "completed"
            state["completed_at"] = datetime.now().isoformat()
            _store.save(state)

    if is_json_output():
        print_json(state)
        return

    print_header(f"Planner Loop {state['id']}")

    status_colors = {
        "running": "green", "completed": "blue",
        "failed": "red", "stopped": "yellow", "starting": "yellow",
    }
    st = state.get("status", "unknown")
    color = status_colors.get(st, "white")

    console.print(f"[cyan]ID:[/cyan] {state.get('id')}")
    console.print(f"[cyan]Status:[/cyan] [{color}]{st}[/{color}]")
    console.print(f"[cyan]PID:[/cyan] {state.get('pid', 'N/A')}")
    console.print(f"[cyan]Iteration:[/cyan] {state.get('current_iteration', 0)}/{state.get('max_iterations', '?')}")
    console.print(f"[cyan]Started:[/cyan] {state.get('started_at', 'N/A')}")
    if state.get("completed_at"):
        console.print(f"[cyan]Completed:[/cyan] {state.get('completed_at')}")
    console.print(f"[cyan]Directory:[/cyan] {state.get('directory', 'N/A')}")

    processed = state.get("plans_processed", [])
    if processed:
        console.print(f"[cyan]Plans Processed:[/cyan] {', '.join(processed)}")

    current = state.get("current_plan")
    if current:
        console.print(f"[cyan]Current Plan:[/cyan] {current}")

    errors = state.get("errors", [])
    if errors:
        console.print(f"\n[red]Errors ({len(errors)}):[/red]")
        for err in errors:
            console.print(f"  [red]{err.get('plan', 'N/A')}: {err.get('error', 'unknown')}[/red]")
