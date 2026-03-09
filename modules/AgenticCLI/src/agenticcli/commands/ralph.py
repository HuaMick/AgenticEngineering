"""Ralph Loop CLI commands.

This module provides CLI commands for the Ralph Loop - a self-directing epic
orchestration system that automatically discovers epics, prioritizes tasks,
and executes them in dependency order.

Commands:
    start: Start Ralph loop to process all live epics
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
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

# Import from AgenticGuidance
from agenticguidance.services.ralph import EpicAction, EpicInfo, RalphLoopService
from agenticguidance.services.question import QuestionQueue
from agenticcli.utils.session_id import generate_session_id
from agenticcli.utils.session_state import mark_failed
from agenticcli.utils.state_store import StateStore

# StateStore for tracking Ralph-spawned sessions alongside regular sessions
# so they appear in `agentic session list` and get structured diagnostics (P6_002).
_session_store = StateStore("sessions", id_key="session_id")

app = typer.Typer(
    name="ralph",
    help="Ralph Loop - self-directing epic orchestration"
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


def _update_ralph_session_store(loop_id: str, final_status: str) -> None:
    """Update the StateStore session record for a Ralph loop.

    Finds the session record by ralph_loop_id and marks it with the final
    status and end timestamp.  Best-effort — failures are logged but do
    not interrupt the caller.

    Args:
        loop_id: The Ralph loop_id used to locate the session record.
        final_status: Final session status (e.g., 'stopped', 'completed', 'failed').
    """
    try:
        records = _session_store.list_all(
            filter_fn=lambda r: r.get("ralph_loop_id") == loop_id
        )
        for record in records:
            record["status"] = final_status
            record["ended_at"] = datetime.now().isoformat()
            _session_store.save(record)
    except Exception:
        pass  # Best-effort; don't mask the caller's operation


@app.command()
def start(
    prompt_file: str = typer.Option(None, "--prompt-file", "-p", help="Custom prompt file"),
    max_iterations: int = typer.Option(20, "--max-iterations", "-n", help="Max iterations"),
    background: bool = typer.Option(False, "--background", "-b", help="Run in background"),
):
    """Start Ralph loop to process all live epics.

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
        console.print("\nUse 'agentic session orchestrate ralph stop' to stop it first.")
        raise typer.Exit(1)

    # Determine prompt file first (needed for both SDK and tmux paths)
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

    # SDK-first path: use run_agent_sync for background loops (no tmux needed).
    # Foreground mode always uses tmux so the user can attach and watch interactively.
    from agenticcli.utils.sdk_runner import SDK_AVAILABLE as _RALPH_SDK_AVAILABLE
    if _RALPH_SDK_AVAILABLE and background:
        # Load prompt content using Python file I/O (not shell substitution)
        if prompt_path and prompt_path.exists():
            prompt_content = prompt_path.read_text()
        else:
            prompt_content = (
                "Run: agentic session orchestrate ralph next -j and execute the returned action"
            )

        from agenticcli.utils.sdk_runner import run_agent_sync as _ralph_sdk_run
        from agenticcli.utils.transport import SDK_DIRECT as _RALPH_TRANSPORT
        try:
            from claude_agent_sdk import ClaudeAgentOptions as _RalphOptions
            from agenticcli.utils.subprocess_utils import get_clean_env
            sdk_options = _RalphOptions(permission_mode="bypassPermissions", env=get_clean_env())
        except ImportError:
            sdk_options = None

        state.transport = _RALPH_TRANSPORT
        service._save_state(state)

        # Create StateStore session record so Ralph SDK sessions appear in
        # `agentic session list` and get structured failure tracking (P6_002).
        ralph_session_id = generate_session_id()
        session_data = {
            "session_id": ralph_session_id,
            "type": "ralph",
            "pid": None,
            "prompt": prompt_content[:500],
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "background": True,
            "working_dir": str(Path.cwd()),
            "transport": _RALPH_TRANSPORT,
            "ralph_loop_id": state.loop_id,
            "max_iterations": max_iterations,
        }
        _session_store.save(session_data)

        console.print("[green]Ralph loop started (SDK)[/green]")
        console.print(f"[cyan]Loop ID:[/cyan] {state.loop_id}")
        console.print(f"[cyan]Max iterations:[/cyan] {max_iterations}")
        console.print("\n[dim]Running in background via SDK...[/dim]")
        console.print(f"  [cyan]Status:[/cyan] agentic session orchestrate ralph status")
        console.print(f"  [cyan]Stop:[/cyan] agentic session orchestrate ralph stop")

        # Run agent synchronously (blocks until loop completes or fails)
        sdk_result = _ralph_sdk_run(prompt_content, sdk_options, timeout_seconds=3600)
        final_status = "completed" if sdk_result.status == "completed" else "failed"
        service.stop_loop(final_status)

        # Update StateStore session record with completion info (P6_002)
        session_data["status"] = final_status
        session_data["ended_at"] = datetime.now().isoformat()
        if final_status == "failed":
            mark_failed(
                session_data,
                error_code="sdk_failure",
                error_type="unknown",
                detail=getattr(sdk_result, "result", "Ralph SDK run failed"),
                retryable=False,
            )
        _session_store.save(session_data)
        return

    # tmux path: required for foreground (interactive) mode and SDK-unavailable fallback
    if not shutil.which("tmux"):
        console.print("[red]Error:[/red] tmux not found")
        console.print("Ralph loop requires tmux. Install with: apt install tmux")
        service.stop_loop("failed")
        raise typer.Exit(1)

    # Check claude is available (tmux path only)
    if not shutil.which("claude"):
        console.print("[red]Error:[/red] claude CLI not found")
        console.print("Ralph loop requires Claude Code CLI.")
        service.stop_loop("failed")
        raise typer.Exit(1)

    # Create tmux session name
    session_name = f"ralph-{state.loop_id[:8]}"

    # Build claude command for tmux session
    # Use --dangerously-skip-permissions for non-interactive execution
    if prompt_path and prompt_path.exists():
        # Pass prompt content via stdin-safe method to avoid shell injection
        claude_cmd = f'claude --dangerously-skip-permissions -p "$(cat {prompt_path})"'
    else:
        # Inline minimal prompt
        claude_cmd = 'claude --dangerously-skip-permissions -p "Run: agentic session orchestrate ralph next -j and execute the returned action"'

    # Spawn tmux session
    # Must unset CLAUDECODE vars inside the tmux session because the tmux
    # server inherits its env from the parent (Claude Code) process.
    # Passing env= to subprocess.run only cleans the tmux client env,
    # not the server env that new sessions inherit from.
    wrapped_cmd = f"unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT; {claude_cmd}"

    result = subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_name,
         "bash", "-c", wrapped_cmd],
        capture_output=True,
        text=True,
    )

    # Create StateStore session record for tmux-spawned Ralph session so it
    # appears in `agentic session list` and gets structured diagnostics (P6_002).
    ralph_session_id = generate_session_id()
    session_data = {
        "session_id": ralph_session_id,
        "type": "ralph",
        "pid": None,
        "prompt": claude_cmd[:500],
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "ended_at": None,
        "background": background,
        "working_dir": str(Path.cwd()),
        "transport": "tmux",
        "tmux_session": session_name,
        "ralph_loop_id": state.loop_id,
        "max_iterations": max_iterations,
    }
    _session_store.save(session_data)

    if result.returncode != 0:
        console.print("[red]Error:[/red] Failed to create tmux session")
        console.print(f"[dim]{result.stderr}[/dim]")
        # Update StateStore with failure info (P6_002)
        mark_failed(
            session_data,
            error_code="tmux_spawn_failed",
            error_type="unknown",
            detail=f"tmux new-session failed: {result.stderr[:300]}",
            retryable=True,
        )
        _session_store.save(session_data)
        service.stop_loop("failed")
        raise typer.Exit(1)

    # Verify session started and is still running
    time.sleep(0.5)  # Brief delay to allow session to initialize or crash
    verify_result = subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        capture_output=True
    )
    if verify_result.returncode != 0:
        console.print("[red]Error:[/red] tmux session exited immediately")
        console.print("[dim]This usually means the claude command failed to start.[/dim]")
        console.print("[dim]Check that 'claude' CLI is properly installed and configured.[/dim]")
        # Update StateStore with failure info (P6_002)
        mark_failed(
            session_data,
            error_code="tmux_exit_immediate",
            error_type="unknown",
            detail="tmux session exited immediately after creation — likely claude startup failure",
            retryable=True,
            suggested_action="retry_clean_env",
        )
        _session_store.save(session_data)
        service.stop_loop("failed")
        raise typer.Exit(1)

    # Update state with tmux session
    state.tmux_session = session_name
    service._save_state(state)

    # Mark session as running now that tmux is verified alive
    session_data["status"] = "running"
    _session_store.save(session_data)

    console.print("[green]Ralph loop started[/green]")
    console.print(f"[cyan]Loop ID:[/cyan] {state.loop_id}")
    console.print(f"[cyan]Session:[/cyan] {session_name}")
    console.print(f"[cyan]Max iterations:[/cyan] {max_iterations}")

    if background:
        console.print("\n[dim]Running in background. Use these commands:[/dim]")
        console.print(f"  [cyan]Attach:[/cyan] tmux attach -t {session_name}")
        console.print(f"  [cyan]Status:[/cyan] agentic session orchestrate ralph status")
        console.print(f"  [cyan]Stop:[/cyan] agentic session orchestrate ralph stop")
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

    # Update StateStore session record for the Ralph session (P6_002)
    _update_ralph_session_store(state.loop_id, "stopped")

    console.print("[green]Ralph loop stopped[/green]")


@app.command()
def status(
    json_output: bool = typer.Option(False, "-j", "--json", help="Output as JSON"),
):
    """Show Ralph loop status and progress.

    Displays:
    - Loop status (running/stopped/completed)
    - Current iteration number
    - Epics progress (discovered/executable/blocked)
    - Time elapsed
    - Tmux session info

    Args:
        json_output: Output structured data as JSON instead of formatted text
    """
    service = RalphLoopService()
    state = service.get_state()

    # Also get current epic status
    plans = service.discover_epics()
    queue = service.get_priority_queue()

    # Count by action type
    execute_count = sum(1 for a in queue if a.action == "execute")
    plan_count = sum(1 for a in queue if a.action == "plan")
    blocked_count = sum(1 for a in queue if a.action == "blocked")
    complete_count = sum(1 for p in plans if p.action_required == "completed")

    # Aggregate pending questions across all plans
    question_counts = {"blocking": 0, "high": 0, "medium": 0, "low": 0}
    questions_available = True
    try:
        for plan_info in plans:
            qq = QuestionQueue(plan_info.path)
            for q in qq.list_pending_questions():
                if q.severity in question_counts:
                    question_counts[q.severity] += 1
    except Exception:
        questions_available = False

    total_pending_questions = sum(question_counts.values())

    # Get rich completion status
    completion = service.get_completion_status()

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
            "epics": {
                "total": len(plans),
                "ready_to_execute": execute_count,
                "needs_epic_planning": plan_count,
                "blocked": blocked_count,
                "completed": complete_count,
            },
            "questions": {
                **question_counts,
                "total_pending": total_pending_questions,
            } if questions_available else None,
            "completion": completion,
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

        console.print("\n[bold cyan]Epic Status[/bold cyan]")
        console.print("─" * 40)
        console.print(f"[green]Ready to execute:[/green] {execute_count}")
        console.print(f"[yellow]Needs epic planning:[/yellow] {plan_count}")
        console.print(f"[red]Blocked:[/red] {blocked_count}")
        console.print(f"[cyan]Completed:[/cyan] {complete_count}")
        console.print(f"[dim]Total:[/dim] {len(plans)}")

        console.print("\n[bold cyan]Pending Questions[/bold cyan]")
        console.print("─" * 40)
        if not questions_available:
            console.print("[dim]Questions: unavailable[/dim]")
        else:
            console.print(f"[red]Blocking:[/red] {question_counts['blocking']}")
            console.print(f"[yellow]High:[/yellow] {question_counts['high']}")
            console.print(f"[cyan]Medium:[/cyan] {question_counts['medium']}")
            console.print(f"[dim]Low:[/dim] {question_counts['low']}")
            console.print(f"[dim]Total pending:[/dim] {total_pending_questions}")

        if completion["all_complete"]:
            console.print("\n[bold green]All epics complete![/bold green]")
        elif completion["can_emit_promise"]:
            console.print(
                "\n[bold green]Can emit completion promise[/bold green]"
                f" [dim]({completion['blocked_by_deps']} dep-blocked epics OK)[/dim]"
            )


@app.command("next")
def next_action(
    json_output: bool = typer.Option(False, "-j", "--json", help="Output as JSON"),
):
    """Get the next recommended action.

    Returns JSON with:
    - action: 'execute' | 'plan' | 'complete' | 'blocked'
    - plan: epic folder name (if action is execute/plan)
    - task: current task ID (if action is execute)
    - reason: explanation of why this action

    Examples:
      {"action": "execute", "plan": "260203QC", "task": "QC_001", "reason": "Ready"}
      {"action": "plan", "plan": "260203QG", "reason": "Needs orchestration MMD"}
      {"action": "complete", "reason": "All epics finished"}
      {"action": "blocked", "reason": "All remaining epics have unmet dependencies"}

    Args:
        json_output: Output structured data as JSON instead of formatted text
    """
    service = RalphLoopService()
    completion = service.get_completion_status()

    # Check if all epics are complete
    if completion["can_emit_promise"]:
        reason = "All epics finished"
        if completion["blocked_by_deps"] > 0:
            reason += f" ({completion['blocked_by_deps']} dep-blocked epics OK)"
        output = {
            "action": "complete",
            "plan": None,
            "task": None,
            "reason": reason,
            "completion": completion,
        }
    else:
        action = service.get_next_action()
        if action is None:
            # No executable actions — build detailed reason
            reasons = []
            if completion["blocked_by_deps"] > 0:
                reasons.append(f"{completion['blocked_by_deps']} epic(s) blocked by dependencies")
            if completion["blocked_by_questions"] > 0:
                reasons.append(f"{completion['blocked_by_questions']} epic(s) blocked by questions")
            reason = "No actionable epics - " + ", ".join(reasons) if reasons else "No actionable epics - all remaining epics are blocked"
            output = {
                "action": "blocked",
                "plan": None,
                "task": None,
                "reason": reason,
                "completion": completion,
            }
        else:
            output = action.to_dict()
            output["completion"] = completion

    # Add hint when blocked by questions
    if output.get("action") == "blocked" and completion["blocked_by_questions"] > 0:
        plan_name = output.get("plan") or ""
        plan_flag = f" --plan {plan_name}" if plan_name else ""
        output["hint"] = f"Run: agentic question list{plan_flag} to see questions"

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
        if output.get("hint"):
            console.print(f"[yellow]Hint:[/yellow] {output['hint']}")


@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n", help="Limit number of entries"),
    json_output: bool = typer.Option(False, "-j", "--json", help="Output as JSON"),
):
    """Show iteration history.

    Displays table with:
    - Iteration #
    - Action taken (execute:epic, plan:epic)
    - Result (success/failure/skipped)
    - Duration
    - Epics completed

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
            console.print("[dim]Start a Ralph loop with: agentic session orchestrate ralph start[/dim]")
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
        table.add_column("Epics Completed", width=20)

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
