# story: US-SET-014
"""Console output utilities using rich library.

Provides colored and formatted output for CLI commands.
"""

import json
from contextlib import contextmanager
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.status import Status
from rich.table import Table
from rich.tree import Tree

# Global console instance
console = Console()
error_console = Console(stderr=True)

# Global output format flag
_output_json = False
_debug_mode = False


def set_json_output(enabled: bool):
    """Enable or disable JSON output mode."""
    global _output_json
    _output_json = enabled


# Alias for Typer integration
set_json_mode = set_json_output


def is_json_output() -> bool:
    """Check if JSON output mode is enabled."""
    return _output_json


def set_debug_mode(enabled: bool):
    """Enable or disable debug mode.

    When enabled, debug messages are printed to console.
    """
    global _debug_mode
    _debug_mode = enabled


def is_debug_mode() -> bool:
    """Check if debug mode is enabled."""
    return _debug_mode


def print_debug(message: str):
    """Print a debug message (only when debug mode is enabled)."""
    if _debug_mode and not _output_json:
        console.print(f"[dim cyan]DEBUG: {message}[/dim cyan]")


def print_success(message: str):
    """Print a success message in green."""
    if _output_json:
        return
    console.print(f"[green]{message}[/green]")


def print_error(message: str):
    """Print an error message in red."""
    if _output_json:
        error_console.print(json.dumps({"error": message}))
    else:
        error_console.print(f"[red]Error:[/red] {message}")


def print_warning(message: str):
    """Print a warning message in yellow."""
    if _output_json:
        return
    console.print(f"[yellow]Warning:[/yellow] {message}")


def print_info(message: str):
    """Print an info message in blue."""
    if _output_json:
        return
    console.print(f"[blue]{message}[/blue]")


def print_header(title: str):
    """Print a header with underline."""
    if _output_json:
        return
    console.print(f"[bold cyan]{title}[/bold cyan]")
    console.print("[dim]" + "=" * len(title) + "[/dim]")


def print_json(data: Any):
    """Print data as formatted JSON."""
    # Use regular print to avoid rich's line wrapping
    print(json.dumps(data, indent=2, default=str))


def print_table(title: str, columns: list[str], rows: list[list[str]]):
    """Print a formatted table."""
    if _output_json:
        data = []
        for row in rows:
            data.append(dict(zip(columns, row)))
        console.print(json.dumps(data, indent=2))
        return

    table = Table(title=title, show_header=True, header_style="bold magenta")
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def print_key_value(key: str, value: Any, indent: int = 0):
    """Print a key-value pair."""
    if _output_json:
        return
    prefix = "  " * indent
    console.print(f"{prefix}[bold]{key}:[/bold] {value}")


def print_panel(content: str, title: str = None, style: str = "blue"):
    """Print content in a panel."""
    if _output_json:
        return
    console.print(Panel(content, title=title, border_style=style))


def print_tree(root_label: str, items: dict):
    """Print a tree structure."""
    if _output_json:
        console.print(json.dumps(items, indent=2))
        return

    tree = Tree(f"[bold]{root_label}[/bold]")
    _add_tree_items(tree, items)
    console.print(tree)


def _add_tree_items(tree: Tree, items: dict):
    """Recursively add items to a tree."""
    for key, value in items.items():
        if isinstance(value, dict):
            branch = tree.add(f"[bold]{key}[/bold]")
            _add_tree_items(branch, value)
        elif isinstance(value, list):
            branch = tree.add(f"[bold]{key}[/bold]")
            for item in value:
                if isinstance(item, dict):
                    _add_tree_items(branch, item)
                else:
                    branch.add(str(item))
        else:
            tree.add(f"[dim]{key}:[/dim] {value}")


def format_status(status: str) -> str:
    """Format a status string with appropriate color.

    Supports 6 lifecycle statuses: active, planning, in_progress, completed,
    deferred, blocked.  Legacy values (proposed, pending, approved) are mapped
    for backward compatibility.
    """
    _colors = {
        "seed": "[magenta]seed[/magenta]",
        "ready": "[cyan]ready[/cyan]",
        "planning": "[blue]planning[/blue]",
        "in_progress": "[yellow]in_progress[/yellow]",
        "completed": "[green]completed[/green]",
        "deferred": "[dim]deferred[/dim]",
        "blocked": "[red]blocked[/red]",
        # Backward compat for legacy values
        "proposed": "[dim]proposed[/dim]",
        "failed": "[red]failed[/red]",
    }
    # Legacy aliases — map to canonical status before lookup
    _legacy = {
        "active": "planning",
        "approved": "in_progress",
    }
    status_lower = status.lower()
    normalized = _legacy.get(status_lower, status_lower)
    return _colors.get(normalized, status)


def print_stability_banner(command: str):
    """Print a stability warning banner for non-stable commands.

    Suppressed in JSON output mode.

    Args:
        command: Command name to check stability for.
    """
    if _output_json:
        return

    from agenticcli.decorators import (
        StabilityLevel,
        get_command_stability,
        get_stability_banner_text,
        get_stability_color,
    )

    level = get_command_stability(command)
    if level == StabilityLevel.STABLE:
        return

    banner_text = get_stability_banner_text(level, command)
    if banner_text:
        color = get_stability_color(level)
        console.print(f"[{color}]{banner_text}[/{color}]")
        console.print()


def get_progress(**kwargs) -> Progress:
    """Return a configured Rich Progress instance for CLI operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        **kwargs,
    )


@contextmanager
def get_status(message: str):
    """Context manager for showing a status spinner."""
    if _output_json:
        yield None
        return
    with console.status(message) as status:
        yield status
