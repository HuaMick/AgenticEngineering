"""Ralph Loop CLI commands for loop execution.

Commands for starting, stopping, and monitoring Ralph Loops via CLI.
"""

import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from agenticcli.utils.state_store import StateStore, is_process_running

_store = StateStore("loops", id_key="loop_id")


def _update_loop_status(loop_data: dict) -> dict:
    """Update loop status based on process state.

    Args:
        loop_data: Loop data dict.

    Returns:
        Updated loop data dict.
    """
    if loop_data.get("status") == "running":
        pid = loop_data.get("pid")
        if pid and not is_process_running(pid):
            loop_data["status"] = "completed"
            loop_data["ended_at"] = datetime.now().isoformat()
            _store.save(loop_data)
    return loop_data


def _resolve_prompt(args) -> tuple[str, str]:
    """Resolve prompt from various sources.

    Args:
        args: Parsed command arguments.

    Returns:
        Tuple of (prompt_text, prompt_source).

    Raises:
        SystemExit: If prompt cannot be resolved.
    """
    from agenticcli.console import print_error

    # Direct prompt string
    prompt = getattr(args, "prompt", None)
    if prompt:
        return prompt, "string"

    # Prompt from file
    prompt_file = getattr(args, "prompt_file", None)
    if prompt_file:
        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            print_error(f"Prompt file not found: {prompt_file}")
            sys.exit(1)
        return prompt_path.read_text().strip(), f"file:{prompt_file}"

    # Prompt from entrypoint reference
    entrypoint = getattr(args, "entrypoint", None)
    if entrypoint:
        # Use the entrypoint module for consistent resolution
        from agenticcli.commands.entrypoint import _find_entrypoint

        # First, check if it's a direct path to a file
        if Path(entrypoint).exists():
            return Path(entrypoint).read_text().strip(), f"entrypoint:{entrypoint}"

        # Use entrypoint module's resolution logic
        filepath = _find_entrypoint(entrypoint)
        if filepath:
            return filepath.read_text().strip(), f"entrypoint:{entrypoint}"

        print_error(f"Entrypoint not found: {entrypoint}")
        print_error("Hint: Use 'agentic entrypoint list' to see available entrypoints.")
        sys.exit(1)

    print_error("Prompt is required. Use --prompt, --prompt-file, or --entrypoint.")
    sys.exit(1)


def handle(args, ctx=None):
    """Route loop subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.loop_command == "start":
        cmd_start(args, ctx)
    elif args.loop_command == "stop":
        cmd_stop(args, ctx)
    elif args.loop_command == "status":
        cmd_status(args, ctx)
    elif args.loop_command == "history":
        cmd_history(args, ctx)
    else:
        print("Usage: agentic session loop <start|stop|status|history>", file=sys.stderr)
        sys.exit(1)


def cmd_start(args, ctx=None):
    """Start a new Ralph Loop.

    Args:
        args: Parsed command arguments with prompt options.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success

    # Resolve prompt from various sources
    prompt, prompt_source = _resolve_prompt(args)

    max_iterations = getattr(args, "max_iterations", 10)
    completion_promise = getattr(args, "completion_promise", None)
    background = getattr(args, "background", False)
    working_dir = getattr(args, "directory", None) or os.getcwd()
    output_file = getattr(args, "output", None)

    # Generate loop ID
    loop_id = str(uuid.uuid4())

    # Build claude command for loop execution
    cmd = ["claude", "--print"]
    if getattr(args, "dangerously_skip_permissions", False):
        cmd.append("--dangerously-skip-permissions")
    if max_iterations:
        cmd.extend(["--max-turns", str(max_iterations)])
    cmd.extend(["--prompt", prompt])

    # Create loop record
    loop_data = {
        "loop_id": loop_id,
        "pid": None,
        "prompt": prompt,
        "prompt_source": prompt_source,
        "max_iterations": max_iterations,
        "completion_promise": completion_promise,
        "current_iteration": 0,
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "ended_at": None,
        "background": background,
        "working_dir": working_dir,
        "output_file": output_file,
        "command": " ".join(cmd),
        "iterations": [],
    }

    try:
        if background:
            # Background mode: use Popen and return immediately
            stdout_target = subprocess.PIPE
            if output_file:
                stdout_target = open(output_file, "w")

            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdout=stdout_target,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            loop_data["pid"] = process.pid
            loop_data["status"] = "running"
            loop_data["current_iteration"] = 1
            loop_data["iterations"].append({
                "number": 1,
                "started_at": datetime.now().isoformat(),
                "ended_at": None,
                "status": "running",
            })
            _store.save(loop_data)

            if is_json_output():
                print_json({
                    "loop_id": loop_id,
                    "pid": process.pid,
                    "status": "running",
                    "background": True,
                    "max_iterations": max_iterations,
                    "completion_promise": completion_promise,
                })
            else:
                print_success(f"Loop {loop_id[:8]} started in background (PID: {process.pid})")
                console.print(f"[dim]Max iterations: {max_iterations}[/dim]")
                if completion_promise:
                    console.print(f"[dim]Completion promise: {completion_promise}[/dim]")
        else:
            # Foreground mode: use run and wait for completion
            loop_data["pid"] = os.getpid()
            loop_data["status"] = "running"
            loop_data["current_iteration"] = 1
            loop_data["iterations"].append({
                "number": 1,
                "started_at": datetime.now().isoformat(),
                "ended_at": None,
                "status": "running",
            })
            _store.save(loop_data)

            result = subprocess.run(
                cmd,
                cwd=working_dir,
                capture_output=True,
                text=True,
            )

            # Update iteration status
            loop_data["iterations"][0]["ended_at"] = datetime.now().isoformat()
            loop_data["iterations"][0]["status"] = "completed" if result.returncode == 0 else "failed"

            loop_data["status"] = "completed" if result.returncode == 0 else "failed"
            loop_data["ended_at"] = datetime.now().isoformat()
            loop_data["exit_code"] = result.returncode

            # Write output to file if specified
            if output_file and result.stdout:
                Path(output_file).write_text(result.stdout)

            _store.save(loop_data)

            if is_json_output():
                print_json({
                    "loop_id": loop_id,
                    "status": loop_data["status"],
                    "exit_code": result.returncode,
                    "iterations_completed": 1,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                })
            else:
                if result.returncode == 0:
                    print_success(f"Loop {loop_id[:8]} completed")
                    if result.stdout:
                        console.print(result.stdout)
                else:
                    print_error(f"Loop {loop_id[:8]} failed with exit code {result.returncode}")
                    if result.stderr:
                        console.print(f"[red]{result.stderr}[/red]")

    except FileNotFoundError:
        loop_data["status"] = "failed"
        loop_data["ended_at"] = datetime.now().isoformat()
        loop_data["error"] = "Claude CLI not found. Make sure 'claude' is installed and in PATH."
        _store.save(loop_data)
        print_error("Claude CLI not found. Make sure 'claude' is installed and in PATH.")
        sys.exit(1)
    except Exception as e:
        loop_data["status"] = "failed"
        loop_data["ended_at"] = datetime.now().isoformat()
        loop_data["error"] = str(e)
        _store.save(loop_data)
        print_error(f"Failed to start loop: {e}")
        sys.exit(1)


def cmd_stop(args, ctx=None):
    """Stop a running Ralph Loop.

    Args:
        args: Parsed command arguments with loop_id.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    loop_id = getattr(args, "loop_id", None)
    if not loop_id:
        print_error("Loop ID is required.")
        sys.exit(1)

    # Find loop by ID (support partial matching)
    loops = _store.list_all()
    matching = [lp for lp in loops if lp.get("loop_id", "").startswith(loop_id)]

    if not matching:
        print_error(f"Loop not found: {loop_id}")
        sys.exit(1)

    if len(matching) > 1:
        print_error(f"Multiple loops match '{loop_id}'. Please provide a more specific ID.")
        sys.exit(1)

    loop = matching[0]
    pid = loop.get("pid")
    status = loop.get("status")

    # If already in terminal state, just return success
    if status in ["completed", "stopped", "failed"]:
        if is_json_output():
            print_json({
                "loop_id": loop["loop_id"],
                "status": status,
                "message": f"Loop is already in terminal state: {status}",
                "success": True
            })
        else:
            print_success(f"Loop {loop['loop_id'][:8]} is already in terminal state: {status}")
        return

    # Try to stop the process
    force = getattr(args, "force", False)

    try:
        if force:
            os.kill(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGTERM)

        loop["status"] = "stopped"
        loop["ended_at"] = datetime.now().isoformat()

        # Mark current iteration as stopped
        for iteration in loop.get("iterations", []):
            if iteration.get("status") == "running":
                iteration["status"] = "stopped"
                iteration["ended_at"] = datetime.now().isoformat()

        _store.save(loop)

        if is_json_output():
            print_json({
                "loop_id": loop["loop_id"],
                "pid": pid,
                "status": "stopped",
                "success": True,
            })
        else:
            print_success(f"Loop {loop['loop_id'][:8]} stopped (PID: {pid})")

    except ProcessLookupError:
        # Process not found, mark as completed if it was running
        loop["status"] = "completed"
        loop["ended_at"] = datetime.now().isoformat()
        _store.save(loop)
        if is_json_output():
            print_json({
                "loop_id": loop["loop_id"],
                "status": "completed",
                "message": "Process not found (may have already exited)",
                "success": True
            })
        else:
            print_success(f"Loop {loop['loop_id'][:8]} already exited (process not found)")
        return
    except PermissionError:
        print_error(f"Permission denied to stop process {pid}")
        sys.exit(1)


def cmd_status(args, ctx=None):
    """Get status of a Ralph Loop.

    Args:
        args: Parsed command arguments with loop_id.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json

    loop_id = getattr(args, "loop_id", None)
    if not loop_id:
        print_error("Loop ID is required.")
        sys.exit(1)

    # Find loop by ID (support partial matching)
    loops = _store.list_all()
    matching = [lp for lp in loops if lp.get("loop_id", "").startswith(loop_id)]

    if not matching:
        print_error(f"Loop not found: {loop_id}")
        sys.exit(1)

    if len(matching) > 1:
        print_error(f"Multiple loops match '{loop_id}'. Please provide a more specific ID.")
        sys.exit(1)

    loop = _update_loop_status(matching[0])

    if is_json_output():
        print_json(loop)
        return

    print_header(f"Loop {loop['loop_id'][:8]}")

    status_colors = {
        "running": "green",
        "completed": "blue",
        "failed": "red",
        "starting": "yellow",
        "stopped": "yellow",
    }
    status = loop.get("status", "unknown")
    status_color = status_colors.get(status, "white")

    console.print(f"[cyan]Loop ID:[/cyan] {loop.get('loop_id')}")
    console.print(f"[cyan]PID:[/cyan] {loop.get('pid', 'N/A')}")
    console.print(f"[cyan]Status:[/cyan] [{status_color}]{status}[/{status_color}]")
    console.print(f"[cyan]Background:[/cyan] {loop.get('background', False)}")
    console.print(f"[cyan]Working Dir:[/cyan] {loop.get('working_dir', 'N/A')}")
    console.print(f"[cyan]Started:[/cyan] {loop.get('started_at', 'N/A')}")

    if loop.get("ended_at"):
        console.print(f"[cyan]Ended:[/cyan] {loop.get('ended_at')}")

    console.print(f"[cyan]Max Iterations:[/cyan] {loop.get('max_iterations', 'N/A')}")
    console.print(f"[cyan]Current Iteration:[/cyan] {loop.get('current_iteration', 0)}")

    if loop.get("completion_promise"):
        console.print(f"[cyan]Completion Promise:[/cyan] {loop.get('completion_promise')}")

    console.print(f"[cyan]Prompt Source:[/cyan] {loop.get('prompt_source', 'N/A')}")

    # Show prompt preview
    prompt = loop.get("prompt", "")
    if len(prompt) > 100:
        console.print(f"[cyan]Prompt:[/cyan] {prompt[:100]}...")
    else:
        console.print(f"[cyan]Prompt:[/cyan] {prompt}")

    if loop.get("output_file"):
        console.print(f"[cyan]Output File:[/cyan] {loop.get('output_file')}")

    if loop.get("error"):
        console.print(f"[red]Error:[/red] {loop.get('error')}")

    # Show iteration history
    iterations = loop.get("iterations", [])
    if iterations:
        console.print("\n[cyan]Iterations:[/cyan]")
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        table.add_column("#", style="yellow", width=4)
        table.add_column("Status", style="green", width=12)
        table.add_column("Started", style="dim", width=20)
        table.add_column("Ended", style="dim", width=20)

        for iteration in iterations:
            iter_status = iteration.get("status", "unknown")
            iter_color = status_colors.get(iter_status, "white")
            table.add_row(
                str(iteration.get("number", "?")),
                f"[{iter_color}]{iter_status}[/{iter_color}]",
                iteration.get("started_at", "N/A")[:19],
                iteration.get("ended_at", "N/A")[:19] if iteration.get("ended_at") else "running",
            )

        console.print(table)


def cmd_history(args, ctx=None):
    """List all Ralph Loop executions.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_header, print_json

    loops = _store.list_all()

    # Update status for running loops
    for loop in loops:
        _update_loop_status(loop)

    # Filter by active if requested
    active_only = getattr(args, "active", False)
    if active_only:
        loops = [lp for lp in loops if lp.get("status") == "running"]

    # Filter by status if requested
    status_filter = getattr(args, "status", None)
    if status_filter:
        loops = [lp for lp in loops if lp.get("status") == status_filter]

    # Limit results
    limit = getattr(args, "limit", 20)

    if is_json_output():
        print_json({
            "loops": loops[:limit],
            "count": len(loops),
            "showing": min(limit, len(loops)),
        })
        return

    print_header("Ralph Loop History")

    if not loops:
        console.print("[dim]No loops found[/dim]")
        return

    # Display as table
    from rich.table import Table

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Loop ID", style="yellow", width=12)
    table.add_column("PID", style="white", width=8)
    table.add_column("Status", style="green", width=12)
    table.add_column("Iter", style="cyan", width=6)
    table.add_column("Started", style="dim", width=20)
    table.add_column("Source", style="dim", width=15)

    status_colors = {
        "running": "green",
        "completed": "blue",
        "failed": "red",
        "starting": "yellow",
        "stopped": "yellow",
    }

    for loop in sorted(loops, key=lambda lp: lp.get("started_at", ""), reverse=True)[:limit]:
        loop_id = loop.get("loop_id", "")[:8]
        pid = str(loop.get("pid", "N/A"))
        status = loop.get("status", "unknown")
        status_color = status_colors.get(status, "white")
        started_at = loop.get("started_at", "")[:19]
        current_iter = loop.get("current_iteration", 0)
        max_iter = loop.get("max_iterations", "?")
        iter_display = f"{current_iter}/{max_iter}"

        # Simplify prompt source display
        source = loop.get("prompt_source", "")
        if source.startswith("file:"):
            source = "file"
        elif source.startswith("entrypoint:"):
            source = "entrypoint"
        else:
            source = source[:15]

        table.add_row(
            loop_id,
            pid,
            f"[{status_color}]{status}[/{status_color}]",
            iter_display,
            started_at,
            source,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(loops)} loop(s)[/dim]")
