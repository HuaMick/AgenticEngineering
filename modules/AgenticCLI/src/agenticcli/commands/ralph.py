"""Ralph Loop CLI commands.

This module provides CLI commands for the Ralph Loop - a self-directing plan
orchestration system that automatically discovers plans, prioritizes tasks,
and executes them in dependency order.

Commands:
    start: Start Ralph loop to process all live plans
    stop: Stop the running Ralph loop
    status: Show Ralph loop status and progress
    next: Get the next recommended action (used by agent)
    history: Show iteration history
"""

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

# Import from AgenticGuidance
from agenticguidance.services.ralph import PlanAction, RalphLoopService

app = typer.Typer(
    name="ralph",
    help="Ralph Loop - self-directing plan orchestration"
)

console = Console()


def handle(args, ctx=None):
    """Handle ralph commands from argparse.

    This function bridges argparse to the Typer-based commands.

    Args:
        args: Parsed command-line arguments from argparse
        ctx: Optional CLI context (not used for ralph commands)
    """
    # Map ralph_command to the appropriate function
    if args.ralph_command == "start":
        start(
            prompt_file=args.prompt_file,
            max_iterations=args.max_iterations,
            background=args.background,
        )
    elif args.ralph_command == "stop":
        stop(force=args.force)
    elif args.ralph_command == "status":
        status(json_output=args.json)
    elif args.ralph_command == "next":
        next_action(json_output=args.json)
    elif args.ralph_command == "history":
        history(limit=args.limit, json_output=args.json)
    else:
        console.print("[red]Error:[/red] Unknown ralph subcommand")
        console.print("Available commands: start, stop, status, next, history")
        sys.exit(1)


def get_default_ralph_prompt() -> Path:
    """Get path to default Ralph prompt.

    Looks in order:
    1. ./docs/prompts/ralph.txt (project-local, relative to git root)
    2. ~/.agentic/prompts/ralph.txt (user config)
    3. Returns None if not found (will use inline prompt)

    Returns:
        Path to prompt file, or None if not found.
    """
    # Check project-local first (relative to git root)
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True
        )
        git_root = Path(result.stdout.strip())
        local_prompt = git_root / "docs" / "prompts" / "ralph.txt"
        if local_prompt.exists():
            return local_prompt
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not in a git repo or git not available, try relative path
        local_prompt = Path("docs/prompts/ralph.txt")
        if local_prompt.exists():
            return local_prompt

    # Check user config
    user_prompt = Path.home() / ".agentic" / "prompts" / "ralph.txt"
    if user_prompt.exists():
        return user_prompt

    return None


@app.command()
def start(
    prompt_file: str = typer.Option(None, "--prompt-file", "-p", help="Custom prompt file"),
    max_iterations: int = typer.Option(20, "--max-iterations", "-n", help="Max iterations"),
    background: bool = typer.Option(False, "--background", "-b", help="Run in background"),
):
    """Start Ralph loop to process all live plans.

    If no prompt_file specified, uses default orchestration prompt.

    Process:
    1. Check no other Ralph loop running
    2. Initialize state in ~/.agentic/ralph/
    3. Spawn tmux session with Claude
    4. In foreground mode, attach to session
    5. In background mode, return immediately

    Args:
        prompt_file: Path to custom prompt file for agent sessions
        max_iterations: Maximum number of iterations to run
        background: Run the loop in the background
    """
    service = RalphLoopService()

    # Check for existing loop
    existing = service.get_state()
    if existing and existing.status == "running":
        console.print("[red]Error:[/red] Ralph loop already running")
        console.print(f"[dim]Loop ID: {existing.loop_id}[/dim]")
        console.print(f"[dim]Iteration: {existing.current_iteration}[/dim]")
        console.print("\nUse 'agentic ralph stop' to stop it first.")
        raise typer.Exit(1)

    # Check tmux is available
    if not shutil.which("tmux"):
        console.print("[red]Error:[/red] tmux not found")
        console.print("Ralph loop requires tmux. Install with: apt install tmux")
        raise typer.Exit(1)

    # Check claude is available
    if not shutil.which("claude"):
        console.print("[red]Error:[/red] claude CLI not found")
        console.print("Ralph loop requires Claude Code CLI.")
        raise typer.Exit(1)

    # Determine prompt file
    prompt_path = None
    if prompt_file:
        prompt_path = Path(prompt_file)
        if not prompt_path.exists():
            console.print(f"[red]Error:[/red] Prompt file not found: {prompt_file}")
            raise typer.Exit(1)
    else:
        prompt_path = get_default_ralph_prompt()
        if prompt_path is None:
            console.print("[yellow]Warning:[/yellow] No default prompt found")
            console.print("Using inline prompt. Create docs/prompts/ralph.txt for custom prompts.")

    # Initialize loop state
    state = service.start_loop(
        prompt_file=str(prompt_path) if prompt_path else None,
        max_iterations=max_iterations
    )

    # Create tmux session name
    session_name = f"ralph-{state.loop_id[:8]}"

    # Build claude command
    # Use --dangerously-skip-permissions for non-interactive execution in tmux
    # Use shell command substitution to load prompt file content
    if prompt_path:
        # Use cat to load file content, properly quoted for shell
        claude_cmd = f'claude --dangerously-skip-permissions -p "$(cat {prompt_path})"'
    else:
        # Inline minimal prompt
        claude_cmd = 'claude --dangerously-skip-permissions -p "Run: agentic ralph next -j and execute the returned action"'

    # Spawn tmux session
    result = subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name, claude_cmd],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        console.print(f"[red]Error:[/red] Failed to create tmux session")
        console.print(f"[dim]{result.stderr}[/dim]")
        service.stop_loop("failed")
        raise typer.Exit(1)

    # Verify session started and is still running
    time.sleep(0.5)  # Brief delay to allow session to initialize or crash
    verify_result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True
    )
    if verify_result.returncode != 0:
        console.print(f"[red]Error:[/red] tmux session exited immediately")
        console.print("[dim]This usually means the claude command failed to start.[/dim]")
        console.print("[dim]Check that 'claude' CLI is properly installed and configured.[/dim]")
        service.stop_loop("failed")
        raise typer.Exit(1)

    # Update state with tmux session
    state.tmux_session = session_name
    service._save_state(state)

    console.print(f"[green]Ralph loop started[/green]")
    console.print(f"[cyan]Loop ID:[/cyan] {state.loop_id}")
    console.print(f"[cyan]Session:[/cyan] {session_name}")
    console.print(f"[cyan]Max iterations:[/cyan] {max_iterations}")

    if background:
        console.print("\n[dim]Running in background. Use these commands:[/dim]")
        console.print(f"  [cyan]Attach:[/cyan] tmux attach -t {session_name}")
        console.print(f"  [cyan]Status:[/cyan] agentic ralph status")
        console.print(f"  [cyan]Stop:[/cyan] agentic ralph stop")
    else:
        console.print("\n[dim]Attaching to session (Ctrl+B, D to detach)...[/dim]")
        subprocess.run(["tmux", "attach", "-t", session_name])


@app.command()
def stop(
    force: bool = typer.Option(False, "--force", "-f", help="Force stop immediately"),
):
    """Stop the running Ralph loop.

    Gracefully stops by:
    1. Setting state to 'stopping'
    2. Sending SIGTERM to tmux session
    3. Waiting for clean exit (or SIGKILL if --force)

    Args:
        force: Force immediate stop without waiting for current iteration
    """
    service = RalphLoopService()
    state = service.get_state()

    if not state or state.status != "running":
        console.print("[yellow]No Ralph loop is running[/yellow]")
        raise typer.Exit(0)

    console.print("[cyan]Stopping Ralph loop...[/cyan]")
    console.print(f"[dim]Loop ID: {state.loop_id}[/dim]")

    # Kill tmux session
    if state.tmux_session:
        if force:
            # Force kill immediately
            subprocess.run(
                ["tmux", "kill-session", "-t", state.tmux_session],
                capture_output=True
            )
            console.print(f"[yellow]Killed session: {state.tmux_session}[/yellow]")
        else:
            # Send termination signal (graceful)
            subprocess.run(
                ["tmux", "send-keys", "-t", state.tmux_session, "C-c"],
                capture_output=True
            )
            # Wait briefly then kill
            time.sleep(2)
            subprocess.run(
                ["tmux", "kill-session", "-t", state.tmux_session],
                capture_output=True
            )
            console.print(f"[green]Stopped session: {state.tmux_session}[/green]")

    # Update state
    service.stop_loop("user_requested")
    console.print("[green]Ralph loop stopped[/green]")


@app.command()
def status(
    json_output: bool = typer.Option(False, "-j", "--json", help="Output as JSON"),
):
    """Show Ralph loop status and progress.

    Displays:
    - Loop status (running/stopped/completed)
    - Current iteration number
    - Plans progress (discovered/executable/blocked)
    - Time elapsed
    - Tmux session info

    Args:
        json_output: Output structured data as JSON instead of formatted text
    """
    service = RalphLoopService()
    state = service.get_state()

    # Also get current plan status
    plans = service.discover_plans()
    queue = service.get_priority_queue()

    # Count by action type
    execute_count = sum(1 for a in queue if a.action == "execute")
    plan_count = sum(1 for a in queue if a.action == "plan")
    blocked_count = sum(1 for a in queue if a.action == "blocked")
    complete_count = sum(1 for p in plans if p.action_required == "completed")

    if json_output:
        output = {
            "loop": {
                "status": state.status if state else "not_running",
                "loop_id": state.loop_id if state else None,
                "current_iteration": state.current_iteration if state else 0,
                "max_iterations": state.max_iterations if state else 0,
                "tmux_session": state.tmux_session if state else None,
                "started_at": state.started_at if state else None,
            } if state else None,
            "plans": {
                "total": len(plans),
                "ready_to_execute": execute_count,
                "needs_planning": plan_count,
                "blocked": blocked_count,
                "completed": complete_count,
            },
            "all_complete": service.check_all_complete(),
        }
        print(json.dumps(output))
    else:
        # Human-readable output
        console.print("\n[bold cyan]Ralph Loop Status[/bold cyan]")
        console.print("─" * 40)

        if not state:
            console.print("[dim]No loop has been started[/dim]")
        else:
            # Status with color
            status_colors = {
                "running": "green",
                "completed": "cyan",
                "stopped": "yellow",
                "failed": "red"
            }
            color = status_colors.get(state.status, "white")
            console.print(f"[{color}]Status:[/{color}] {state.status}")
            console.print(f"[cyan]Loop ID:[/cyan] {state.loop_id}")
            console.print(f"[cyan]Iteration:[/cyan] {state.current_iteration} / {state.max_iterations}")

            if state.tmux_session:
                console.print(f"[cyan]Session:[/cyan] {state.tmux_session}")
                console.print(f"[dim]Attach: tmux attach -t {state.tmux_session}[/dim]")

            # Elapsed time
            elapsed = time.time() - state.started_at
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            console.print(f"[cyan]Elapsed:[/cyan] {minutes}m {seconds}s")

        console.print("\n[bold cyan]Plan Status[/bold cyan]")
        console.print("─" * 40)
        console.print(f"[green]Ready to execute:[/green] {execute_count}")
        console.print(f"[yellow]Needs planning:[/yellow] {plan_count}")
        console.print(f"[red]Blocked:[/red] {blocked_count}")
        console.print(f"[cyan]Completed:[/cyan] {complete_count}")
        console.print(f"[dim]Total:[/dim] {len(plans)}")

        if service.check_all_complete():
            console.print("\n[bold green]All plans complete![/bold green]")


@app.command("next")
def next_action(
    json_output: bool = typer.Option(False, "-j", "--json", help="Output as JSON"),
):
    """Get the next recommended action.

    Returns JSON with:
    - action: 'execute' | 'plan' | 'complete' | 'blocked'
    - plan: plan folder name (if action is execute/plan)
    - task: current task ID (if action is execute)
    - reason: explanation of why this action

    Examples:
      {"action": "execute", "plan": "260203QC", "task": "QC_001", "reason": "Ready"}
      {"action": "plan", "plan": "260203QG", "reason": "Needs orchestration MMD"}
      {"action": "complete", "reason": "All plans finished"}
      {"action": "blocked", "reason": "All remaining plans have unmet dependencies"}

    Args:
        json_output: Output structured data as JSON instead of formatted text
    """
    service = RalphLoopService()

    # Check if all plans are complete
    if service.check_all_complete():
        output = {
            "action": "complete",
            "plan": None,
            "task": None,
            "reason": "All plans finished"
        }
    else:
        action = service.get_next_action()
        if action is None:
            output = {
                "action": "blocked",
                "plan": None,
                "task": None,
                "reason": "No actionable plans - all remaining plans are blocked"
            }
        else:
            output = action.to_dict()

    if json_output:
        print(json.dumps(output))
    else:
        # Pretty print for humans
        action_colors = {
            "execute": "green",
            "plan": "yellow",
            "complete": "cyan",
            "blocked": "red"
        }
        color = action_colors.get(output["action"], "white")
        console.print(f"[bold {color}]Action:[/bold {color}] {output['action']}")
        if output.get("plan"):
            console.print(f"[cyan]Plan:[/cyan] {output['plan']}")
        if output.get("task"):
            console.print(f"[cyan]Task:[/cyan] {output['task']}")
        console.print(f"[dim]Reason:[/dim] {output['reason']}")


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n", help="Limit number of entries"),
    json_output: bool = typer.Option(False, "-j", "--json", help="Output as JSON"),
):
    """Show iteration history.

    Displays table with:
    - Iteration #
    - Action taken (execute:plan, plan:plan)
    - Result (success/failure/skipped)
    - Duration
    - Plans completed

    Args:
        limit: Maximum number of iteration records to display
        json_output: Output structured data as JSON instead of formatted text
    """
    service = RalphLoopService()
    state = service.get_state()

    if not state or not state.iterations:
        if json_output:
            print(json.dumps({"iterations": [], "total": 0}))
        else:
            console.print("[dim]No iteration history available[/dim]")
            console.print("[dim]Start a Ralph loop with: agentic ralph start[/dim]")
        raise typer.Exit(0)

    # Get iterations (most recent first, limited)
    iterations = list(reversed(state.iterations))[:limit]

    if json_output:
        output = {
            "iterations": [
                {
                    "number": it.number,
                    "started_at": it.started_at,
                    "ended_at": it.ended_at,
                    "action": it.action_taken,
                    "result": it.result,
                    "duration_seconds": (it.ended_at - it.started_at) if it.ended_at else None,
                    "plans_completed": it.plans_completed,
                }
                for it in iterations
            ],
            "total": len(state.iterations),
            "showing": len(iterations),
        }
        print(json.dumps(output))
    else:
        console.print(f"\n[bold cyan]Ralph Loop History[/bold cyan]")
        console.print(f"[dim]Loop ID: {state.loop_id} | Total iterations: {len(state.iterations)}[/dim]")
        console.print()

        # Create table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Action", width=30)
        table.add_column("Result", width=10)
        table.add_column("Duration", width=10)
        table.add_column("Plans Completed", width=20)

        for it in iterations:
            # Format result with color
            result_colors = {
                "success": "[green]success[/green]",
                "failure": "[red]failure[/red]",
                "skipped": "[yellow]skipped[/yellow]",
            }
            result = result_colors.get(it.result, it.result or "-")

            # Format duration
            if it.ended_at and it.started_at:
                duration = it.ended_at - it.started_at
                if duration >= 60:
                    duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"
                else:
                    duration_str = f"{duration:.1f}s"
            else:
                duration_str = "running..."

            # Format plans completed
            plans = ", ".join(it.plans_completed) if it.plans_completed else "-"
            if len(plans) > 18:
                plans = plans[:15] + "..."

            table.add_row(
                str(it.number),
                it.action_taken or "-",
                result,
                duration_str,
                plans
            )

        console.print(table)

        if len(state.iterations) > limit:
            console.print(f"\n[dim]Showing {limit} of {len(state.iterations)} iterations. Use --limit to see more.[/dim]")
