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
    elif args.langsmith_command == "friction":
        cmd_friction(args)
    elif args.langsmith_command == "sessions":
        cmd_sessions(args)
    else:
        print("Usage: agentic langsmith <runs|run|projects|stats|friction|sessions>", file=sys.stderr)
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


def cmd_friction(args):
    """Analyze traces for friction patterns with session-based filtering.

    Implements: agentic langsmith friction --project <name> [options]
    """
    from datetime import datetime

    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )
    from rich.panel import Panel
    from rich.table import Table

    # Get parameters
    project_name = getattr(args, "project", None)
    if not project_name:
        print_error("--project is required for friction command")
        sys.exit(1)

    sessions_count = getattr(args, "sessions", None)
    since_date = getattr(args, "since", None)
    limit = getattr(args, "limit", 100)
    lookback_days = getattr(args, "lookback_days", 7)
    min_affected = getattr(args, "min_affected", 2)
    recommend = getattr(args, "recommend", False)
    validate = getattr(args, "validate", True)

    try:
        from agenticlangsmith import FrictionAnalyzer, ResolutionRecommender

        service = _get_service()
        analyzer = FrictionAnalyzer(service)

        # If --sessions provided, we need to first get sessions then filter
        if sessions_count is not None:
            # Get runs and group by session to determine which sessions to include
            runs = service.list_runs(project_name=project_name, limit=limit * 2)

            # Group by session_id
            sessions: dict[str, list[dict]] = {}
            for run in runs:
                session_id = run.get("session_id") or "unknown"
                if session_id not in sessions:
                    sessions[session_id] = []
                sessions[session_id].append(run)

            # Sort sessions by most recent run start_time
            sorted_sessions = sorted(
                sessions.items(),
                key=lambda x: max(
                    (r.get("start_time") or "" for r in x[1]),
                    default=""
                ),
                reverse=True,
            )

            # Take the N most recent sessions
            selected_sessions = [s[0] for s in sorted_sessions[:sessions_count]]

            # Re-run analysis with filtered runs
            report = analyzer.analyze(
                project_name=project_name,
                limit=limit,
                lookback_days=lookback_days,
            )

            # Filter patterns to only those affecting selected sessions
            filtered_patterns = []
            for pattern in report.patterns:
                # Check if pattern evidence involves selected sessions
                affected_sessions = set()
                for evidence in pattern.evidence:
                    if isinstance(evidence, dict):
                        session_id = evidence.get("session_id")
                        if session_id and session_id in selected_sessions:
                            affected_sessions.add(session_id)

                if len(affected_sessions) >= min_affected:
                    filtered_patterns.append(pattern)

            report.patterns = filtered_patterns

        else:
            # Standard analysis
            report = analyzer.analyze(
                project_name=project_name,
                limit=limit,
                lookback_days=lookback_days,
            )

            # Apply min_affected filter
            if min_affected > 1:
                filtered_patterns = []
                for pattern in report.patterns:
                    # Count unique sessions in evidence
                    affected_sessions = set()
                    for evidence in pattern.evidence:
                        if isinstance(evidence, dict):
                            session_id = evidence.get("session_id")
                            if session_id:
                                affected_sessions.add(session_id)

                    if len(affected_sessions) >= min_affected or pattern.frequency >= min_affected:
                        filtered_patterns.append(pattern)

                report.patterns = filtered_patterns

        # Generate recommendations if requested
        resolution_plan = None
        if recommend:
            recommender = ResolutionRecommender()
            resolution_plan = recommender.recommend(report)

            # Add validation note if enabled
            if validate and resolution_plan:
                for rec in resolution_plan.recommendations:
                    rec.suggested_changes.append(
                        "(Validate against existing guidance before implementing)"
                    )

        # Output
        if is_json_output():
            result = report.to_dict()
            if resolution_plan:
                result["resolution_plan"] = resolution_plan.to_dict()
            print_json(result)
            return

        print_header(f"Friction Analysis: {project_name}")

        # Summary panel
        summary = f"""[bold]Analyzed Runs:[/bold] {report.analyzed_runs}
[bold]Timeframe:[/bold] {report.timeframe_days} days
[bold]Patterns Found:[/bold] {len(report.patterns)}
[bold]Min Sessions Filter:[/bold] {min_affected}"""

        console.print(Panel(summary, title="Analysis Summary", border_style="cyan"))

        if not report.patterns:
            console.print("\n[green]No friction patterns detected![/green]")
            return

        # Severity breakdown
        breakdown = report.severity_breakdown
        console.print("\n[bold magenta]Severity Breakdown[/bold magenta]")
        console.print(f"  [red]High:[/red] {breakdown.get('high', 0)}")
        console.print(f"  [yellow]Medium:[/yellow] {breakdown.get('medium', 0)}")
        console.print(f"  [dim]Low:[/dim] {breakdown.get('low', 0)}")

        # Patterns table
        console.print("\n[bold magenta]Detected Patterns[/bold magenta]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Pattern", style="cyan")
        table.add_column("Severity")
        table.add_column("Freq", justify="right")
        table.add_column("Description", max_width=50)

        for pattern in report.patterns:
            severity = pattern.severity.value
            if severity == "high":
                severity_str = "[red]HIGH[/red]"
            elif severity == "medium":
                severity_str = "[yellow]MEDIUM[/yellow]"
            else:
                severity_str = "[dim]LOW[/dim]"

            table.add_row(
                pattern.pattern_type.value,
                severity_str,
                str(pattern.frequency),
                _truncate(pattern.description, 48),
            )

        console.print(table)

        # Recommendations
        if resolution_plan and resolution_plan.recommendations:
            console.print("\n[bold magenta]Resolution Recommendations[/bold magenta]")
            for i, rec in enumerate(resolution_plan.recommendations, 1):
                console.print(f"\n[bold]{i}. {rec.pattern_type.value}[/bold] ({rec.resolution_type.value})")
                console.print(f"   [dim]{rec.description}[/dim]")
                if rec.target_locations:
                    console.print(f"   [blue]Targets:[/blue] {', '.join(rec.target_locations[:2])}")

            if resolution_plan.next_steps:
                console.print("\n[bold cyan]Next Steps:[/bold cyan]")
                for step in resolution_plan.next_steps:
                    console.print(f"  - {step}")

        console.print()

    except ImportError:
        print_error(
            "agenticlangsmith package not installed. "
            "Install it with: pip install -e modules/AgenticLangSmith"
        )
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to analyze friction: {e}")
        sys.exit(1)


def cmd_sessions(args):
    """List recent sessions with run counts.

    Implements: agentic langsmith sessions --project <name> [options]
    """
    from datetime import datetime

    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )
    from rich.table import Table

    # Get parameters
    project_name = getattr(args, "project", None)
    if not project_name:
        print_error("--project is required for sessions command")
        sys.exit(1)

    limit = getattr(args, "limit", 10)
    since_date = getattr(args, "since", None)

    try:
        service = _get_service()

        # Fetch runs (get more than limit to ensure we have enough sessions)
        runs = service.list_runs(project_name=project_name, limit=500)

        # Filter by since date if provided
        if since_date:
            try:
                cutoff = datetime.fromisoformat(since_date)
                runs = [
                    r for r in runs
                    if r.get("start_time") and datetime.fromisoformat(r["start_time"]) >= cutoff
                ]
            except ValueError:
                print_error(f"Invalid date format: {since_date}. Use ISO format (e.g., 2026-01-01)")
                sys.exit(1)

        # Group by session_id
        sessions: dict[str, dict] = {}
        for run in runs:
            session_id = run.get("session_id") or "unknown"
            if session_id not in sessions:
                sessions[session_id] = {
                    "session_id": session_id,
                    "run_count": 0,
                    "error_count": 0,
                    "first_run": None,
                    "last_run": None,
                    "run_types": {},
                }

            session = sessions[session_id]
            session["run_count"] += 1

            if run.get("status") == "error":
                session["error_count"] += 1

            # Track run types
            run_type = run.get("run_type", "unknown")
            session["run_types"][run_type] = session["run_types"].get(run_type, 0) + 1

            # Track timing
            start_time = run.get("start_time")
            if start_time:
                if session["first_run"] is None or start_time < session["first_run"]:
                    session["first_run"] = start_time
                if session["last_run"] is None or start_time > session["last_run"]:
                    session["last_run"] = start_time

        # Sort by most recent and limit
        sorted_sessions = sorted(
            sessions.values(),
            key=lambda s: s["last_run"] or "",
            reverse=True,
        )[:limit]

        # Output
        if is_json_output():
            print_json({
                "project": project_name,
                "sessions": sorted_sessions,
                "count": len(sorted_sessions),
            })
            return

        print_header(f"Sessions: {project_name}")

        if not sorted_sessions:
            console.print("[dim]No sessions found[/dim]")
            return

        # Create table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Session ID", style="cyan", max_width=12)
        table.add_column("Runs", justify="right")
        table.add_column("Errors", justify="right")
        table.add_column("Start Time")
        table.add_column("Types", max_width=30)

        for session in sorted_sessions:
            # Format session ID (truncate)
            session_id = session["session_id"]
            if len(session_id) > 12:
                session_id = session_id[:8] + "..."

            # Format error count with color
            error_count = session["error_count"]
            if error_count > 0:
                error_str = f"[red]{error_count}[/red]"
            else:
                error_str = "[dim]0[/dim]"

            # Format start time
            first_run = session["first_run"]
            if first_run:
                # Show date and time
                try:
                    dt = datetime.fromisoformat(first_run)
                    start_str = dt.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    start_str = first_run[:16]
            else:
                start_str = "-"

            # Format run types
            types = session["run_types"]
            type_parts = []
            for rt, count in sorted(types.items(), key=lambda x: -x[1]):
                type_parts.append(f"{rt}:{count}")
            types_str = ", ".join(type_parts[:3])
            if len(type_parts) > 3:
                types_str += "..."

            table.add_row(
                session_id,
                str(session["run_count"]),
                error_str,
                start_str,
                types_str,
            )

        console.print(table)
        console.print(f"\n[dim]Showing {len(sorted_sessions)} sessions[/dim]")

    except Exception as e:
        print_error(f"Failed to list sessions: {e}")
        sys.exit(1)
