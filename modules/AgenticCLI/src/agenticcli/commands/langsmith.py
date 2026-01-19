"""LangSmith trace querying commands.

Provides CLI commands for querying LangSmith traces, runs, and projects.
Uses the agenticlangsmith backend module.
"""

import sys
from datetime import datetime, timedelta


def handle(args, ctx=None):
    """Route langsmith subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    subcommand = getattr(args, "langsmith_command", None)
    if subcommand == "runs":
        cmd_runs(args)
    elif subcommand == "run":
        cmd_run(args)
    elif subcommand == "projects":
        cmd_projects(args)
    elif subcommand == "stats":
        cmd_stats(args)
    else:
        print("Usage: agentic langsmith <runs|run|projects|stats>", file=sys.stderr)
        print("       agentic ls <runs|run|projects|stats>", file=sys.stderr)
        sys.exit(1)


def _get_service():
    """Get LangSmithService instance, handling import errors gracefully."""
    try:
        from agenticlangsmith.service import LangSmithService

        return LangSmithService()
    except ImportError:
        from agenticcli.console import print_error

        print_error(
            "agenticlangsmith package not installed. "
            "Install it with: pip install agenticlangsmith"
        )
        sys.exit(1)
    except Exception as e:
        from agenticcli.console import print_error

        # Handle LangSmithConfigError or other init errors
        error_msg = str(e)
        if "LANGSMITH_API_KEY" in error_msg or "api_key" in error_msg.lower():
            print_error(
                "LANGSMITH_API_KEY environment variable not set. "
                "Set it with: export LANGSMITH_API_KEY=your_key"
            )
        else:
            print_error(f"Failed to initialize LangSmith service: {e}")
        sys.exit(1)


def cmd_runs(args):
    """List recent runs with filtering options."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )
    from rich.table import Table

    service = _get_service()

    project = getattr(args, "project", None)
    limit = getattr(args, "limit", 20)
    run_type = getattr(args, "type", None)
    error_only = getattr(args, "error", False)

    try:
        runs = service.list_runs(
            project_name=project,
            limit=limit,
            run_type=run_type,
            error_only=error_only,
        )
    except Exception as e:
        print_error(f"Failed to fetch runs: {e}")
        sys.exit(1)

    if is_json_output():
        print_json({"runs": runs})
        return

    print_header("LangSmith Runs")
    console.print()

    if not runs:
        console.print("[dim]No runs found[/dim]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=10)
    table.add_column("Name", width=30)
    table.add_column("Type", width=10)
    table.add_column("Latency", justify="right", width=10)
    table.add_column("Tokens", justify="right", width=10)
    table.add_column("Status", width=10)

    for run in runs:
        run_id = run.get("id", "")[:8]
        name = run.get("name", "")[:30]
        run_type_val = run.get("run_type", "")

        # Calculate latency in ms
        latency_ms = ""
        if run.get("end_time") and run.get("start_time"):
            try:
                start = datetime.fromisoformat(run["start_time"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(run["end_time"].replace("Z", "+00:00"))
                latency_ms = f"{int((end - start).total_seconds() * 1000)}ms"
            except (ValueError, TypeError):
                latency_ms = "-"

        # Get token count
        tokens = ""
        token_usage = run.get("total_tokens") or run.get("prompt_tokens", 0) + run.get("completion_tokens", 0)
        if token_usage:
            tokens = str(token_usage)

        # Determine status
        if run.get("error"):
            status = "[red]error[/red]"
        elif run.get("end_time"):
            status = "[green]success[/green]"
        else:
            status = "[yellow]running[/yellow]"

        table.add_row(run_id, name, run_type_val, latency_ms, tokens, status)

    console.print(table)
    console.print(f"\n[dim]Showing {len(runs)} runs[/dim]")


def cmd_run(args):
    """Show detailed info for a single run."""
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
        print_error(f"Failed to fetch run {run_id}: {e}")
        sys.exit(1)

    if not run:
        print_error(f"Run not found: {run_id}")
        sys.exit(1)

    if show_url:
        try:
            url = service.get_run_url(run_id)
            if is_json_output():
                print_json({"run_id": run_id, "url": url})
            else:
                console.print(url)
            return
        except Exception as e:
            print_error(f"Failed to generate URL: {e}")
            sys.exit(1)

    if is_json_output():
        print_json(run)
        return

    print_header(f"Run: {run.get('name', run_id)}")
    console.print()

    # Basic info panel
    info_lines = [
        f"[bold]ID:[/bold] {run.get('id', '')}",
        f"[bold]Type:[/bold] {run.get('run_type', '')}",
        f"[bold]Status:[/bold] {'[red]error[/red]' if run.get('error') else '[green]success[/green]'}",
    ]

    if run.get("start_time"):
        info_lines.append(f"[bold]Started:[/bold] {run['start_time']}")
    if run.get("end_time"):
        info_lines.append(f"[bold]Ended:[/bold] {run['end_time']}")

    # Token usage
    total_tokens = run.get("total_tokens") or 0
    if total_tokens:
        info_lines.append(f"[bold]Tokens:[/bold] {total_tokens}")

    console.print(Panel("\n".join(info_lines), title="Run Info", border_style="blue"))

    # Inputs (truncated)
    inputs = run.get("inputs", {})
    if inputs:
        inputs_str = str(inputs)[:500]
        if len(str(inputs)) > 500:
            inputs_str += "... [truncated]"
        console.print(Panel(inputs_str, title="Inputs", border_style="cyan"))

    # Outputs (truncated)
    outputs = run.get("outputs", {})
    if outputs:
        outputs_str = str(outputs)[:500]
        if len(str(outputs)) > 500:
            outputs_str += "... [truncated]"
        console.print(Panel(outputs_str, title="Outputs", border_style="green"))

    # Error if present
    if run.get("error"):
        console.print(Panel(str(run["error"]), title="Error", border_style="red"))

    # Child runs
    child_runs = run.get("child_runs", [])
    if child_runs:
        console.print(f"\n[bold]Child Runs:[/bold] {len(child_runs)}")
        for child in child_runs[:5]:
            console.print(f"  - {child.get('id', '')[:8]}: {child.get('name', '')}")
        if len(child_runs) > 5:
            console.print(f"  [dim]... and {len(child_runs) - 5} more[/dim]")

    # Feedback
    feedback = run.get("feedback", [])
    if feedback:
        console.print(f"\n[bold]Feedback:[/bold]")
        for fb in feedback:
            score = fb.get("score", "")
            comment = fb.get("comment", "")
            console.print(f"  - Score: {score}, Comment: {comment}")


def cmd_projects(args):
    """List all projects with run counts."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )
    from rich.table import Table

    service = _get_service()

    show_detail = getattr(args, "detail", False)

    try:
        projects = service.list_projects()
    except Exception as e:
        print_error(f"Failed to fetch projects: {e}")
        sys.exit(1)

    if is_json_output():
        print_json({"projects": projects})
        return

    print_header("LangSmith Projects")
    console.print()

    if not projects:
        console.print("[dim]No projects found[/dim]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", width=30)
    table.add_column("ID", width=36)
    table.add_column("Run Count", justify="right", width=12)
    table.add_column("Created", width=20)

    if show_detail:
        table.add_column("Description", width=30)

    for project in projects:
        row = [
            project.get("name", ""),
            project.get("id", ""),
            str(project.get("run_count", 0)),
            project.get("created_at", "")[:19] if project.get("created_at") else "",
        ]
        if show_detail:
            row.append(project.get("description", "")[:30])
        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]Total: {len(projects)} projects[/dim]")


def cmd_stats(args):
    """Show usage statistics for a project."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )
    from rich.panel import Panel

    service = _get_service()

    project = args.project
    since = getattr(args, "since", None)
    until = getattr(args, "until", None)

    if not project:
        print_error("--project is required for stats command")
        sys.exit(1)

    try:
        stats = service.get_project_stats(project)
    except Exception as e:
        print_error(f"Failed to fetch stats for {project}: {e}")
        sys.exit(1)

    if is_json_output():
        print_json(stats)
        return

    print_header(f"Stats: {project}")
    console.print()

    # Summary panel
    total_runs = stats.get("total_runs", 0)
    total_tokens = stats.get("total_tokens", 0)
    error_count = stats.get("error_count", 0)
    error_rate = (error_count / total_runs * 100) if total_runs > 0 else 0

    summary_lines = [
        f"[bold]Total Runs:[/bold] {total_runs:,}",
        f"[bold]Total Tokens:[/bold] {total_tokens:,}",
        f"[bold]Errors:[/bold] {error_count:,}",
        f"[bold]Error Rate:[/bold] {error_rate:.1f}%",
    ]
    console.print(Panel("\n".join(summary_lines), title="Summary", border_style="blue"))

    # Latency stats
    latency = stats.get("latency", {})
    if latency:
        latency_lines = [
            f"[bold]Average:[/bold] {latency.get('avg', 0):.0f}ms",
            f"[bold]P50:[/bold] {latency.get('p50', 0):.0f}ms",
            f"[bold]P95:[/bold] {latency.get('p95', 0):.0f}ms",
            f"[bold]P99:[/bold] {latency.get('p99', 0):.0f}ms",
        ]
        console.print(Panel("\n".join(latency_lines), title="Latency", border_style="cyan"))

    # Token usage breakdown
    token_breakdown = stats.get("token_breakdown", {})
    if token_breakdown:
        token_lines = [
            f"[bold]Prompt Tokens:[/bold] {token_breakdown.get('prompt', 0):,}",
            f"[bold]Completion Tokens:[/bold] {token_breakdown.get('completion', 0):,}",
        ]
        console.print(Panel("\n".join(token_lines), title="Token Usage", border_style="green"))

    # Run type distribution
    run_types = stats.get("run_types", {})
    if run_types:
        console.print("\n[bold]Run Types:[/bold]")
        for rt, count in run_types.items():
            pct = (count / total_runs * 100) if total_runs > 0 else 0
            console.print(f"  {rt}: {count:,} ({pct:.1f}%)")
