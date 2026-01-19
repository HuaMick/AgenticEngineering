"""LangSmith integration commands.

Handles LangSmith trace querying and project management.
"""

import sys
from typing import Any, Optional


def handle(args, ctx=None):
    """Route langsmith subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.langsmith_command == "runs":
        cmd_runs(args)
    elif args.langsmith_command == "run":
        cmd_run(args)
    elif args.langsmith_command == "projects":
        cmd_projects(args)
    elif args.langsmith_command == "stats":
        cmd_stats(args)
    else:
        print("Usage: agentic langsmith <runs|run|projects|stats>", file=sys.stderr)
        sys.exit(1)


def _get_service():
    """Get LangSmithService instance with proper error handling.

    Returns:
        LangSmithService instance.

    Raises:
        SystemExit: If service cannot be initialized (missing API key).
    """
    from agenticcli.console import print_error

    try:
        from agenticlangsmith import LangSmithService

        return LangSmithService()
    except ImportError:
        print_error(
            "agenticlangsmith package not installed. "
            "Install it with: pip install -e modules/AgenticLangSmith"
        )
        sys.exit(1)
    except Exception as e:
        # LangSmithConfigError for missing API key
        print_error(str(e))
        sys.exit(1)


def _truncate(text: Optional[str], max_length: int = 500) -> str:
    """Truncate text to max length with ellipsis.

    Args:
        text: Text to truncate.
        max_length: Maximum length before truncation.

    Returns:
        Truncated string or empty string if None.
    """
    if text is None:
        return ""
    text_str = str(text)
    if len(text_str) <= max_length:
        return text_str
    return text_str[: max_length - 3] + "..."


def cmd_runs(args):
    """List recent runs with filtering options.

    Implements: agentic langsmith runs [--project] [--limit] [--type] [--error]
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_header,
        print_json,
    )
    from rich.table import Table

    service = _get_service()

    # Get filter options
    project_name = getattr(args, "project", None)
    limit = getattr(args, "limit", 20)
    run_type = getattr(args, "type", None)
    error_only = getattr(args, "error", False)

    try:
        runs = service.list_runs(
            project_name=project_name,
            limit=limit,
            run_type=run_type,
            error_only=error_only,
        )
    except Exception as e:
        from agenticcli.console import print_error

        print_error(f"Failed to list runs: {e}")
        sys.exit(1)

    if is_json_output():
        print_json({"runs": runs, "count": len(runs)})
        return

    print_header("LangSmith Runs")

    if not runs:
        console.print("[dim]No runs found[/dim]")
        return

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", max_width=12)
    table.add_column("Name", max_width=30)
    table.add_column("Type", style="blue")
    table.add_column("Latency", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Status")

    for run in runs:
        # Format ID (truncate UUID)
        run_id = run["id"][:8] + "..."

        # Format name (truncate if needed)
        name = _truncate(run["name"], 28)

        # Format latency
        latency = run.get("latency")
        latency_str = f"{latency * 1000:.0f}ms" if latency else "-"

        # Format tokens
        tokens = run.get("total_tokens")
        tokens_str = str(tokens) if tokens else "-"

        # Format status
        status = run.get("status", "unknown")
        if status == "success":
            status_str = "[green]success[/green]"
        elif status == "error":
            status_str = "[red]error[/red]"
        elif status == "running":
            status_str = "[yellow]running[/yellow]"
        else:
            status_str = f"[dim]{status}[/dim]"

        table.add_row(
            run_id,
            name,
            run.get("run_type", "-"),
            latency_str,
            tokens_str,
            status_str,
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(runs)} runs[/dim]")


def cmd_run(args):
    """Show detailed info for a single run.

    Implements: agentic langsmith run <run-id> [--url]
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )
    from rich.panel import Panel

    service = _get_service()

    run_id = args.run_id
    show_url = getattr(args, "url", False)

    try:
        run = service.get_run(run_id)
    except Exception as e:
        print_error(f"Failed to get run: {e}")
        sys.exit(1)

    # Get feedback if available
    feedback = []
    try:
        feedback = service.get_run_feedback(run_id)
    except Exception:
        pass  # Feedback is optional

    # Get URL if requested
    run_url = None
    if show_url:
        try:
            run_url = service.get_run_url(run_id)
        except Exception:
            pass

    if is_json_output():
        result = {
            "run": run,
            "feedback": feedback,
        }
        if run_url:
            result["url"] = run_url
        print_json(result)
        return

    print_header(f"Run: {run['name']}")

    # Basic info
    console.print(f"\n[bold]ID:[/bold] [cyan]{run['id']}[/cyan]")
    console.print(f"[bold]Type:[/bold] [blue]{run.get('run_type', '-')}[/blue]")

    # Status with color
    status = run.get("status", "unknown")
    if status == "success":
        console.print("[bold]Status:[/bold] [green]success[/green]")
    elif status == "error":
        console.print("[bold]Status:[/bold] [red]error[/red]")
        if run.get("error"):
            console.print(f"[red]Error:[/red] {_truncate(run['error'], 200)}")
    else:
        console.print(f"[bold]Status:[/bold] {status}")

    # Timing
    console.print(f"\n[bold magenta]Timing[/bold magenta]")
    console.print(f"  [dim]Start:[/dim] {run.get('start_time', '-')}")
    console.print(f"  [dim]End:[/dim] {run.get('end_time', '-')}")
    latency = run.get("latency")
    if latency:
        console.print(f"  [dim]Latency:[/dim] {latency * 1000:.0f}ms")

    # Tokens
    if run.get("total_tokens"):
        console.print(f"\n[bold magenta]Tokens[/bold magenta]")
        console.print(f"  [dim]Total:[/dim] {run['total_tokens']}")
        if run.get("prompt_tokens"):
            console.print(f"  [dim]Prompt:[/dim] {run['prompt_tokens']}")
        if run.get("completion_tokens"):
            console.print(f"  [dim]Completion:[/dim] {run['completion_tokens']}")

    # Inputs/Outputs (truncated)
    if run.get("inputs"):
        inputs_str = _truncate(str(run["inputs"]), 500)
        console.print(Panel(inputs_str, title="Inputs", border_style="blue"))

    if run.get("outputs"):
        outputs_str = _truncate(str(run["outputs"]), 500)
        console.print(Panel(outputs_str, title="Outputs", border_style="green"))

    # Parent/Session info
    if run.get("parent_run_id"):
        console.print(f"\n[bold]Parent Run:[/bold] [dim]{run['parent_run_id']}[/dim]")
    if run.get("session_id"):
        console.print(f"[bold]Session:[/bold] [dim]{run['session_id']}[/dim]")

    # Tags
    if run.get("tags"):
        tags_str = ", ".join(run["tags"])
        console.print(f"\n[bold]Tags:[/bold] [dim]{tags_str}[/dim]")

    # Feedback
    if feedback:
        console.print(f"\n[bold magenta]Feedback ({len(feedback)} items)[/bold magenta]")
        for fb in feedback:
            score = fb.get("score", "-")
            key = fb.get("key", "unknown")
            console.print(f"  [{key}] score={score}")
            if fb.get("comment"):
                console.print(f"    [dim]{_truncate(fb['comment'], 100)}[/dim]")

    # URL
    if run_url:
        console.print(f"\n[bold]URL:[/bold] [link={run_url}]{run_url}[/link]")

    console.print()


def cmd_projects(args):
    """List all projects in the workspace.

    Implements: agentic langsmith projects [--detail]
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_header,
        print_json,
    )
    from rich.table import Table

    service = _get_service()

    show_detail = getattr(args, "detail", False)

    try:
        projects = service.list_projects()
    except Exception as e:
        from agenticcli.console import print_error

        print_error(f"Failed to list projects: {e}")
        sys.exit(1)

    if is_json_output():
        print_json({"projects": projects, "count": len(projects)})
        return

    print_header("LangSmith Projects")

    if not projects:
        console.print("[dim]No projects found[/dim]")
        return

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("ID", max_width=20)
    table.add_column("Run Count", justify="right")
    if show_detail:
        table.add_column("Created")
        table.add_column("Description", max_width=30)

    for project in projects:
        # Format ID (truncate UUID)
        project_id = project["id"][:8] + "..." if len(project["id"]) > 11 else project["id"]

        # Format run count
        run_count = project.get("run_count")
        run_count_str = str(run_count) if run_count is not None else "-"

        if show_detail:
            created = project.get("created_at", "-")
            if created and created != "-":
                # Show just date portion
                created = created.split("T")[0]
            desc = _truncate(project.get("description") or "", 28)
            table.add_row(project["name"], project_id, run_count_str, created, desc)
        else:
            table.add_row(project["name"], project_id, run_count_str)

    console.print(table)
    console.print(f"\n[dim]Found {len(projects)} projects[/dim]")


def cmd_stats(args):
    """Show usage statistics for a project.

    Implements: agentic langsmith stats --project <name>
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )
    from rich.panel import Panel

    service = _get_service()

    project_name = getattr(args, "project", None)
    if not project_name:
        print_error("--project is required for stats command")
        sys.exit(1)

    try:
        stats = service.get_project_stats(project_name)
    except Exception as e:
        print_error(f"Failed to get project stats: {e}")
        sys.exit(1)

    if is_json_output():
        print_json(stats)
        return

    print_header(f"Stats: {project_name}")

    # Overview panel
    overview = f"""[bold]Total Runs:[/bold] {stats['total_runs']}
[bold]Error Count:[/bold] {stats['error_count']}
[bold]Error Rate:[/bold] {stats['error_rate']}%"""

    console.print(Panel(overview, title="Overview", border_style="cyan"))

    # Performance panel
    avg_latency = stats.get("avg_latency")
    latency_str = f"{avg_latency * 1000:.0f}ms" if avg_latency else "N/A"
    total_tokens = stats.get("total_tokens", 0)

    performance = f"""[bold]Average Latency:[/bold] {latency_str}
[bold]Total Tokens:[/bold] {total_tokens:,}"""

    console.print(Panel(performance, title="Performance", border_style="green"))

    # Run types breakdown
    run_types = stats.get("run_types", {})
    if run_types:
        console.print("\n[bold magenta]Run Types[/bold magenta]")
        for rt, count in sorted(run_types.items(), key=lambda x: -x[1]):
            pct = (count / stats["total_runs"] * 100) if stats["total_runs"] > 0 else 0
            console.print(f"  [blue]{rt}[/blue]: {count} ({pct:.1f}%)")

    console.print()
