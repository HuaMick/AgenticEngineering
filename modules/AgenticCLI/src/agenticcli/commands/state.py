"""State management commands.

Commands for viewing and managing the process state registry.
"""

import sys
from datetime import datetime


def handle(args, ctx=None):
    """Route state subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.state_command == "list":
        cmd_list(args, ctx)
    elif args.state_command == "show":
        cmd_show(args, ctx)
    elif args.state_command == "clear":
        cmd_clear(args, ctx)
    elif args.state_command == "cleanup":
        cmd_cleanup(args, ctx)
    else:
        print("Usage: agentic state <list|show|clear|cleanup>", file=sys.stderr)
        sys.exit(1)


def cmd_list(args, ctx=None):
    """List all registered processes."""
    from agenticcli.console import console, is_json_output, print_header, print_info, print_json
    from agenticguidance.services import StateRegistry

    if ctx:
        registry = StateRegistry(ctx.config_dir / "state.json")
    else:
        registry = StateRegistry()

    # Auto-cleanup dead processes on list
    cleaned = registry.cleanup_dead_processes()

    if getattr(args, "active", False):
        entries = registry.list_active()
    else:
        entries = registry.list_all()

    if is_json_output():
        print_json({
            "processes": [e.to_dict() for e in entries],
            "count": len(entries),
            "cleaned": cleaned,
        })
        return

    print_header("State Registry")
    if cleaned > 0:
        print_info(f"Cleaned up {cleaned} stale process(es)")

    if not entries:
        console.print("[dim]No registered processes[/dim]")
        return

    # Display as table
    from rich.table import Table

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("PID", style="yellow", width=8)
    table.add_column("Name", style="white")
    table.add_column("State", style="green")
    table.add_column("Started", style="dim")
    table.add_column("Command", style="dim", max_width=40)

    state_colors = {
        "running": "green",
        "completed": "blue",
        "failed": "red",
        "stale": "yellow",
    }

    for entry in entries:
        started = datetime.fromtimestamp(entry.started_at).strftime("%H:%M:%S")
        state_color = state_colors.get(entry.state.value, "white")
        table.add_row(
            str(entry.pid),
            entry.name,
            f"[{state_color}]{entry.state.value}[/{state_color}]",
            started,
            entry.command[:40] + "..." if len(entry.command) > 40 else entry.command,
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(entries)} process(es)[/dim]")


def cmd_show(args, ctx=None):
    """Show details of a specific process."""
    from agenticcli.console import console, is_json_output, print_error, print_header, print_json
    from agenticguidance.services import StateRegistry

    if ctx:
        registry = StateRegistry(ctx.config_dir / "state.json")
    else:
        registry = StateRegistry()

    entry = registry.get(args.pid)

    if entry is None:
        print_error(f"Process not found: {args.pid}")
        sys.exit(1)

    if is_json_output():
        print_json(entry.to_dict())
        return

    print_header(f"Process {entry.pid}")

    state_colors = {
        "running": "green",
        "completed": "blue",
        "failed": "red",
        "stale": "yellow",
    }
    state_color = state_colors.get(entry.state.value, "white")

    console.print(f"[cyan]Name:[/cyan] {entry.name}")
    console.print(f"[cyan]PID:[/cyan] {entry.pid}")
    console.print(f"[cyan]State:[/cyan] [{state_color}]{entry.state.value}[/{state_color}]")
    console.print(f"[cyan]Command:[/cyan] {entry.command}")

    started = datetime.fromtimestamp(entry.started_at).strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"[cyan]Started:[/cyan] {started}")

    if entry.ended_at:
        ended = datetime.fromtimestamp(entry.ended_at).strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"[cyan]Ended:[/cyan] {ended}")
        duration = entry.ended_at - entry.started_at
        console.print(f"[cyan]Duration:[/cyan] {duration:.1f}s")

    if entry.metadata:
        console.print("[cyan]Metadata:[/cyan]")
        for key, value in entry.metadata.items():
            console.print(f"  {key}: {value}")


def cmd_clear(args, ctx=None):
    """Clear entries from the state registry."""
    from agenticcli.console import is_json_output, print_error, print_json, print_success
    from agenticguidance.services import StateRegistry

    if ctx:
        registry = StateRegistry(ctx.config_dir / "state.json")
    else:
        registry = StateRegistry()

    if getattr(args, "all", False):
        if not getattr(args, "force", False):
            print_error("Use --force to clear all entries (including running processes)")
            sys.exit(1)
        count = registry.clear_all()
        msg = f"Cleared all {count} entries"
    else:
        # Clear only completed/failed/stale
        count = registry.clear_completed()
        msg = f"Cleared {count} completed/failed/stale entries"

    if is_json_output():
        print_json({"cleared": count, "success": True})
    else:
        print_success(msg)


def cmd_cleanup(args, ctx=None):
    """Clean up stale processes (those no longer running)."""
    from agenticcli.console import is_json_output, print_json, print_success
    from agenticguidance.services import StateRegistry

    if ctx:
        registry = StateRegistry(ctx.config_dir / "state.json")
    else:
        registry = StateRegistry()

    cleaned = registry.cleanup_dead_processes()

    if is_json_output():
        print_json({"cleaned": cleaned})
    else:
        if cleaned > 0:
            print_success(f"Marked {cleaned} process(es) as stale")
        else:
            print_success("No stale processes found")
