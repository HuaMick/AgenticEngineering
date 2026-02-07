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
    elif args.langsmith_command == "session-analyze":
        cmd_session_analyze(args)
    elif args.langsmith_command == "batch-search":
        cmd_batch_search(args)
    else:
        print("Usage: agentic langsmith <runs|run|projects|stats|friction|sessions|session-analyze|batch-search>", file=sys.stderr)
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
    """Show detailed info for a single run with enhanced features.

    Implements: agentic langsmith run <run-id> [options]
    """
    import yaml

    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )
    from rich.panel import Panel
    from rich.tree import Tree

    service = _get_service()

    run_id = args.run_id
    show_url = getattr(args, "url", False)
    show_tree = getattr(args, "tree", False)
    show_full = getattr(args, "full", False)
    output_format = getattr(args, "format", "table")
    show_timing = getattr(args, "timing", False)

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

    # Build hierarchy if requested
    hierarchy = None
    if show_tree:
        hierarchy = {"parent": None, "children": []}

        # Get parent run
        if run.get("parent_run_id"):
            try:
                parent = service.get_run(run["parent_run_id"])
                hierarchy["parent"] = {
                    "id": parent["id"],
                    "name": parent["name"],
                    "run_type": parent.get("run_type"),
                    "latency_ms": parent.get("latency") * 1000 if parent.get("latency") else None,
                }
            except Exception:
                pass

        # Get child runs (runs with this run as parent)
        try:
            all_runs = service.list_runs(limit=500)
            children = [r for r in all_runs if r.get("parent_run_id") == run_id]
            hierarchy["children"] = [
                {
                    "id": child["id"],
                    "name": child["name"],
                    "run_type": child.get("run_type"),
                    "latency_ms": child.get("latency") * 1000 if child.get("latency") else None,
                }
                for child in children
            ]
        except Exception:
            pass

    # Handle format options
    if output_format == "yaml":
        result = {
            "run": run,
            "feedback": feedback,
        }
        if run_url:
            result["url"] = run_url
        if hierarchy:
            result["hierarchy"] = hierarchy
        print(yaml.dump(result, default_flow_style=False, sort_keys=False))
        return

    if is_json_output() or output_format == "json":
        result = {
            "run": run,
            "feedback": feedback,
        }
        if run_url:
            result["url"] = run_url
        if hierarchy:
            result["hierarchy"] = hierarchy
        print_json(result)
        return

    # Default table output
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
            error_text = run["error"] if show_full else _truncate(run["error"], 200)
            console.print(f"[red]Error:[/red] {error_text}")
    else:
        console.print(f"[bold]Status:[/bold] {status}")

    # Timing
    console.print(f"\n[bold magenta]Timing[/bold magenta]")
    console.print(f"  [dim]Start:[/dim] {run.get('start_time', '-')}")
    console.print(f"  [dim]End:[/dim] {run.get('end_time', '-')}")
    latency = run.get("latency")
    if latency:
        console.print(f"  [dim]Latency:[/dim] {latency * 1000:.0f}ms")

        # Enhanced timing breakdown if requested
        if show_timing and run.get("start_time") and run.get("end_time"):
            from datetime import datetime
            try:
                start = datetime.fromisoformat(run["start_time"])
                end = datetime.fromisoformat(run["end_time"])
                total_ms = (end - start).total_seconds() * 1000
                execution_ms = latency * 1000
                overhead_ms = total_ms - execution_ms if total_ms > execution_ms else 0

                console.print(f"\n[bold magenta]Timing Breakdown[/bold magenta]")
                console.print(f"  [dim]Total:[/dim] {total_ms:.0f}ms")
                console.print(f"  [dim]Execution:[/dim] {execution_ms:.0f}ms")
                if overhead_ms > 0:
                    console.print(f"  [dim]Overhead:[/dim] {overhead_ms:.0f}ms")
            except ValueError:
                pass

    # Tokens
    if run.get("total_tokens"):
        console.print(f"\n[bold magenta]Tokens[/bold magenta]")
        console.print(f"  [dim]Total:[/dim] {run['total_tokens']}")
        if run.get("prompt_tokens"):
            console.print(f"  [dim]Prompt:[/dim] {run['prompt_tokens']}")
        if run.get("completion_tokens"):
            console.print(f"  [dim]Completion:[/dim] {run['completion_tokens']}")

    # Inputs/Outputs
    if run.get("inputs"):
        if show_full:
            inputs_str = str(run["inputs"])
        else:
            inputs_str = _truncate(str(run["inputs"]), 500)
        console.print(Panel(inputs_str, title="Inputs", border_style="blue"))

    if run.get("outputs"):
        if show_full:
            outputs_str = str(run["outputs"])
        else:
            outputs_str = _truncate(str(run["outputs"]), 500)
        console.print(Panel(outputs_str, title="Outputs", border_style="green"))

    # Hierarchy tree view
    if show_tree and hierarchy:
        console.print(f"\n[bold magenta]Run Hierarchy[/bold magenta]")
        tree = Tree(f"[cyan]{run['name']}[/cyan] ({run.get('run_type', 'unknown')})")

        if hierarchy["parent"]:
            parent = hierarchy["parent"]
            latency_str = f" ({parent['latency_ms']:.0f}ms)" if parent["latency_ms"] else ""
            tree.add(f"[dim]Parent: {parent['name']} [{parent['run_type']}]{latency_str}[/dim]")

        if hierarchy["children"]:
            children_branch = tree.add(f"[bold]Children ({len(hierarchy['children'])})[/bold]")
            for child in hierarchy["children"]:
                latency_str = f" ({child['latency_ms']:.0f}ms)" if child["latency_ms"] else ""
                children_branch.add(f"{child['name']} [{child['run_type']}]{latency_str}")

        console.print(tree)

    # Parent/Session info (if not showing tree)
    if not show_tree:
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
    export_format = getattr(args, "export", None)
    group_by = getattr(args, "group_by", "severity")

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

        # Group patterns if requested
        grouped_patterns = {}
        if group_by == "severity":
            for pattern in report.patterns:
                sev = pattern.severity.value
                if sev not in grouped_patterns:
                    grouped_patterns[sev] = []
                grouped_patterns[sev].append(pattern)
        elif group_by == "type":
            for pattern in report.patterns:
                ptype = pattern.pattern_type.value
                if ptype not in grouped_patterns:
                    grouped_patterns[ptype] = []
                grouped_patterns[ptype].append(pattern)
        elif group_by == "session":
            for pattern in report.patterns:
                # Extract unique sessions from evidence
                sessions = set()
                for evidence in pattern.evidence:
                    if isinstance(evidence, dict):
                        session_id = evidence.get("session_id")
                        if session_id:
                            sessions.add(session_id)
                for session in sessions:
                    if session not in grouped_patterns:
                        grouped_patterns[session] = []
                    grouped_patterns[session].append(pattern)
        else:
            grouped_patterns["all"] = report.patterns

        # Handle export formats
        if export_format == "markdown":
            import yaml
            output = []
            output.append(f"# Friction Analysis Report\n")
            output.append(f"**Project**: {project_name}")
            output.append(f"**Analyzed Runs**: {report.analyzed_runs}")
            output.append(f"**Timeframe**: {report.timeframe_days} days")
            output.append(f"**Patterns Found**: {len(report.patterns)}\n")

            # Severity breakdown
            breakdown = report.severity_breakdown
            output.append("## Severity Breakdown\n")
            output.append(f"- High: {breakdown.get('high', 0)}")
            output.append(f"- Medium: {breakdown.get('medium', 0)}")
            output.append(f"- Low: {breakdown.get('low', 0)}\n")

            # Patterns by group
            for group_name, patterns in sorted(grouped_patterns.items()):
                output.append(f"## {group_by.capitalize()}: {group_name}\n")
                for pattern in patterns:
                    output.append(f"### {pattern.pattern_type.value} (Frequency: {pattern.frequency})\n")
                    output.append(f"**Severity**: {pattern.severity.value}")
                    output.append(f"**Description**: {pattern.description}\n")

                    # Evidence
                    if pattern.evidence:
                        output.append("**Evidence**:")
                        for i, evidence in enumerate(pattern.evidence[:5], 1):
                            if isinstance(evidence, dict):
                                run_id = evidence.get("run_id", "unknown")
                                output.append(f"- Evidence {i}: Run {run_id[:8]}...")
                            else:
                                output.append(f"- {evidence}")
                        if len(pattern.evidence) > 5:
                            output.append(f"- ... and {len(pattern.evidence) - 5} more")
                        output.append("")

            # Recommendations
            if resolution_plan and resolution_plan.recommendations:
                output.append("## Recommendations\n")
                for i, rec in enumerate(resolution_plan.recommendations, 1):
                    output.append(f"### {i}. {rec.pattern_type.value}\n")
                    output.append(f"**Type**: {rec.resolution_type.value}")
                    output.append(f"**Description**: {rec.description}\n")
                    if rec.target_locations:
                        output.append(f"**Targets**: {', '.join(rec.target_locations[:3])}\n")

                if resolution_plan.next_steps:
                    output.append("## Next Steps\n")
                    for step in resolution_plan.next_steps:
                        output.append(f"- {step}")

            print("\n".join(output))
            return

        if export_format == "yaml":
            import yaml
            result = report.to_dict()
            if resolution_plan:
                result["resolution_plan"] = resolution_plan.to_dict()
            result["grouped_by"] = group_by
            result["grouped_patterns"] = {
                group: [p.to_dict() if hasattr(p, 'to_dict') else p for p in patterns]
                for group, patterns in grouped_patterns.items()
            }
            print(yaml.dump(result, default_flow_style=False, sort_keys=False))
            return

        # JSON output
        if is_json_output() or export_format == "json":
            result = report.to_dict()
            if resolution_plan:
                result["resolution_plan"] = resolution_plan.to_dict()
            result["grouped_by"] = group_by
            result["grouped_patterns"] = {
                group: [p.to_dict() if hasattr(p, 'to_dict') else p for p in patterns]
                for group, patterns in grouped_patterns.items()
            }
            print_json(result)
            return

        # Default table output
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

        # Patterns table (grouped)
        console.print(f"\n[bold magenta]Detected Patterns (grouped by {group_by})[/bold magenta]")

        for group_name in sorted(grouped_patterns.keys(), reverse=(group_by == "severity")):
            patterns = grouped_patterns[group_name]
            if not patterns:
                continue

            console.print(f"\n[bold cyan]{group_by.capitalize()}: {group_name}[/bold cyan] ({len(patterns)} patterns)")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Pattern", style="cyan")
            table.add_column("Severity")
            table.add_column("Freq", justify="right")
            table.add_column("Description", max_width=50)

            for pattern in patterns:
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


def cmd_session_analyze(args):
    """Analyze a specific session with detailed statistics.

    Implements: agentic langsmith session-analyze <session-id> [--project] [--export]
    """
    import csv
    import io
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

    service = _get_service()

    session_id = args.session_id
    project_name = getattr(args, "project", None)
    export_format = getattr(args, "export", None)

    try:
        # Fetch all runs for this session
        # Use a large limit to get all runs in the session
        runs = service.list_runs(project_name=project_name, limit=500)

        # Filter runs by session_id
        session_runs = [r for r in runs if r.get("session_id") == session_id]

        if not session_runs:
            print_error(f"Session {session_id} not found" + (f" in project {project_name}" if project_name else ""))
            sys.exit(1)

        # Calculate session statistics
        total_runs = len(session_runs)
        error_count = sum(1 for r in session_runs if r["status"] == "error")
        error_rate = (error_count / total_runs * 100) if total_runs > 0 else 0

        # Calculate duration
        start_times = [r["start_time"] for r in session_runs if r.get("start_time")]
        if start_times:
            start_times_dt = [datetime.fromisoformat(t) for t in start_times]
            first_run = min(start_times_dt)
            last_run = max(start_times_dt)
            duration_seconds = (last_run - first_run).total_seconds()
        else:
            duration_seconds = 0

        # Calculate token usage
        total_tokens = sum(r.get("total_tokens") or 0 for r in session_runs)

        # Calculate average latency
        latencies = [r["latency"] for r in session_runs if r.get("latency") is not None]
        avg_latency_ms = (sum(latencies) / len(latencies) * 1000) if latencies else 0

        # Run types breakdown
        run_types = {}
        for r in session_runs:
            rt = r.get("run_type", "unknown")
            run_types[rt] = run_types.get(rt, 0) + 1

        # Build timeline (sorted by start_time)
        timeline = sorted(
            session_runs,
            key=lambda r: r.get("start_time") or "",
        )

        # Handle export formats
        if export_format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["run_id", "name", "run_type", "status", "start_time", "latency_ms", "tokens"])
            for run in timeline:
                latency_ms = run.get("latency") * 1000 if run.get("latency") else ""
                tokens = run.get("total_tokens") or ""
                writer.writerow([
                    run["id"],
                    run["name"],
                    run.get("run_type", ""),
                    run.get("status", ""),
                    run.get("start_time", ""),
                    f"{latency_ms:.0f}" if latency_ms else "",
                    tokens,
                ])
            print(output.getvalue())
            return

        if export_format == "markdown":
            output = []
            output.append(f"# Session Analysis: {session_id}\n")
            output.append("## Statistics\n")
            output.append(f"- Total Runs: {total_runs}")
            output.append(f"- Error Rate: {error_rate:.1f}%")

            if duration_seconds > 0:
                minutes = int(duration_seconds // 60)
                seconds = int(duration_seconds % 60)
                output.append(f"- Duration: {minutes}m {seconds}s")

            output.append(f"- Total Tokens: {total_tokens:,}")
            output.append(f"- Average Latency: {avg_latency_ms:.0f}ms\n")

            output.append("## Run Types\n")
            for rt, count in sorted(run_types.items(), key=lambda x: -x[1]):
                output.append(f"- {rt}: {count}")

            output.append("\n## Timeline\n")
            output.append("| Run ID | Name | Type | Status | Time | Latency |")
            output.append("|--------|------|------|--------|------|---------|")
            for run in timeline:
                run_id_short = run["id"][:8] + "..."
                name = _truncate(run["name"], 20)
                run_type = run.get("run_type", "-")
                status = run.get("status", "-")
                start_time = run.get("start_time", "-")
                if start_time and start_time != "-":
                    try:
                        dt = datetime.fromisoformat(start_time)
                        start_time = dt.strftime("%H:%M:%S")
                    except ValueError:
                        pass
                latency = run.get("latency")
                latency_str = f"{latency * 1000:.0f}ms" if latency else "-"
                output.append(f"| {run_id_short} | {name} | {run_type} | {status} | {start_time} | {latency_str} |")

            print("\n".join(output))
            return

        # JSON output (including --json flag)
        if is_json_output() or export_format == "json":
            result = {
                "session_id": session_id,
                "statistics": {
                    "total_runs": total_runs,
                    "error_count": error_count,
                    "error_rate": round(error_rate, 2),
                    "duration_seconds": round(duration_seconds, 2),
                    "total_tokens": total_tokens,
                    "avg_latency_ms": round(avg_latency_ms, 2),
                },
                "run_types": run_types,
                "timeline": [
                    {
                        "run_id": r["id"],
                        "name": r["name"],
                        "run_type": r.get("run_type"),
                        "status": r.get("status"),
                        "start_time": r.get("start_time"),
                        "latency_ms": round(r["latency"] * 1000, 2) if r.get("latency") else None,
                        "tokens": r.get("total_tokens"),
                    }
                    for r in timeline
                ],
            }
            print_json(result)
            return

        # Default table output
        print_header(f"Session Analysis: {session_id[:8]}...")

        # Statistics panel
        stats_content = f"""[bold]Total Runs:[/bold] {total_runs}
[bold]Error Count:[/bold] {error_count} ({error_rate:.1f}%)"""

        if duration_seconds > 0:
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            stats_content += f"\n[bold]Duration:[/bold] {minutes}m {seconds}s"

        stats_content += f"""
[bold]Total Tokens:[/bold] {total_tokens:,}
[bold]Avg Latency:[/bold] {avg_latency_ms:.0f}ms"""

        console.print(Panel(stats_content, title="Statistics", border_style="cyan"))

        # Run types breakdown
        console.print("\n[bold magenta]Run Types[/bold magenta]")
        for rt, count in sorted(run_types.items(), key=lambda x: -x[1]):
            pct = (count / total_runs * 100) if total_runs > 0 else 0
            console.print(f"  [blue]{rt}[/blue]: {count} ({pct:.1f}%)")

        # Timeline table
        console.print("\n[bold magenta]Timeline[/bold magenta]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Run ID", style="cyan", max_width=12)
        table.add_column("Name", max_width=30)
        table.add_column("Type", style="blue")
        table.add_column("Status")
        table.add_column("Time")
        table.add_column("Latency", justify="right")

        for run in timeline:
            # Format ID
            run_id = run["id"][:8] + "..."

            # Format name
            name = _truncate(run["name"], 28)

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

            # Format time
            start_time = run.get("start_time", "-")
            if start_time and start_time != "-":
                try:
                    dt = datetime.fromisoformat(start_time)
                    time_str = dt.strftime("%H:%M:%S")
                except ValueError:
                    time_str = start_time[:8]
            else:
                time_str = "-"

            # Format latency
            latency = run.get("latency")
            latency_str = f"{latency * 1000:.0f}ms" if latency else "-"

            table.add_row(
                run_id,
                name,
                run.get("run_type", "-"),
                status_str,
                time_str,
                latency_str,
            )

        console.print(table)
        console.print(f"\n[dim]Session contains {total_runs} runs[/dim]")

    except Exception as e:
        print_error(f"Failed to analyze session: {e}")
        sys.exit(1)


def cmd_batch_search(args):
    """Search runs by regex pattern in inputs/outputs/errors.

    Implements: agentic langsmith batch-search <pattern> --project <name> [options]
    """
    import csv
    import io
    import re
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

    service = _get_service()

    pattern = args.pattern
    project_name = args.project
    field = getattr(args, "field", "all")
    run_type = getattr(args, "type", None)
    status_filter = getattr(args, "status", None)
    since_date = getattr(args, "since", None)
    until_date = getattr(args, "until", None)
    limit = getattr(args, "limit", 100)
    group_by = getattr(args, "group_by", "none")
    export_format = getattr(args, "export", None)

    # Validate regex pattern
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        print_error(f"Invalid regex pattern: {e}")
        sys.exit(1)

    try:
        # Fetch runs with filters
        error_only = status_filter == "error" if status_filter else False
        runs = service.list_runs(
            project_name=project_name,
            limit=limit,
            run_type=run_type,
            error_only=error_only,
        )

        # Filter by status if not error (since error_only only handles error status)
        if status_filter and status_filter != "error":
            runs = [r for r in runs if r.get("status") == status_filter]

        # Filter by date range
        if since_date or until_date:
            filtered_runs = []
            for r in runs:
                start_time = r.get("start_time")
                if not start_time:
                    continue
                try:
                    run_date = datetime.fromisoformat(start_time)
                    if since_date:
                        since_dt = datetime.fromisoformat(since_date)
                        if run_date < since_dt:
                            continue
                    if until_date:
                        until_dt = datetime.fromisoformat(until_date)
                        if run_date > until_dt:
                            continue
                    filtered_runs.append(r)
                except ValueError:
                    continue
            runs = filtered_runs

        # Search pattern in specified fields
        matches = []
        for run in runs:
            matched_field = None
            match_snippet = None

            # Search in inputs
            if field in ("inputs", "all"):
                inputs_str = str(run.get("inputs") or "")
                match = regex.search(inputs_str)
                if match:
                    matched_field = "inputs"
                    # Extract snippet around match
                    start = max(0, match.start() - 30)
                    end = min(len(inputs_str), match.end() + 30)
                    match_snippet = inputs_str[start:end]

            # Search in outputs
            if not matched_field and field in ("outputs", "all"):
                outputs_str = str(run.get("outputs") or "")
                match = regex.search(outputs_str)
                if match:
                    matched_field = "outputs"
                    start = max(0, match.start() - 30)
                    end = min(len(outputs_str), match.end() + 30)
                    match_snippet = outputs_str[start:end]

            # Search in error
            if not matched_field and field in ("error", "all"):
                error_str = str(run.get("error") or "")
                match = regex.search(error_str)
                if match:
                    matched_field = "error"
                    start = max(0, match.start() - 30)
                    end = min(len(error_str), match.end() + 30)
                    match_snippet = error_str[start:end]

            if matched_field:
                matches.append({
                    "run_id": run["id"],
                    "name": run["name"],
                    "matched_field": matched_field,
                    "match_snippet": match_snippet,
                    "session_id": run.get("session_id"),
                    "run_type": run.get("run_type"),
                    "status": run.get("status"),
                    "start_time": run.get("start_time"),
                })

        if not matches:
            if is_json_output() or export_format:
                print_json({"pattern": pattern, "matches": 0, "results": []})
            else:
                console.print(f"[dim]No matches found for pattern '{pattern}'[/dim]")
            return

        # Group results if requested
        grouped_results = {}
        if group_by != "none":
            for match in matches:
                if group_by == "session":
                    key = match.get("session_id") or "unknown"
                elif group_by == "type":
                    key = match.get("run_type") or "unknown"
                elif group_by == "status":
                    key = match.get("status") or "unknown"
                else:
                    key = "all"

                if key not in grouped_results:
                    grouped_results[key] = []
                grouped_results[key].append(match)
        else:
            grouped_results["all"] = matches

        # Handle export formats
        if export_format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "run_id", "name", "matched_field", "match_snippet",
                "session_id", "run_type", "status", "start_time"
            ])
            for match in matches:
                writer.writerow([
                    match["run_id"],
                    match["name"],
                    match["matched_field"],
                    _truncate(match["match_snippet"], 100),
                    match.get("session_id", ""),
                    match.get("run_type", ""),
                    match.get("status", ""),
                    match.get("start_time", ""),
                ])
            print(output.getvalue())
            return

        # JSON output
        if is_json_output() or export_format == "json":
            result = {
                "pattern": pattern,
                "matches": len(matches),
                "results": matches if group_by == "none" else grouped_results,
            }
            print_json(result)
            return

        # Default table output
        print_header(f"Search Results: '{pattern}'")

        # Summary panel
        summary = f"""[bold]Pattern:[/bold] {pattern}
[bold]Matches:[/bold] {len(matches)}
[bold]Searched:[/bold] {len(runs)} runs"""
        console.print(Panel(summary, title="Search Summary", border_style="cyan"))

        # Display grouped results
        for group_key, group_matches in grouped_results.items():
            if group_by != "none":
                console.print(f"\n[bold magenta]{group_by.capitalize()}: {group_key}[/bold magenta] ({len(group_matches)} matches)")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Run ID", style="cyan", max_width=12)
            table.add_column("Name", max_width=25)
            table.add_column("Field", style="blue")
            table.add_column("Snippet", max_width=40)
            table.add_column("Type")
            table.add_column("Time")

            for match in group_matches:
                # Format ID
                run_id = match["run_id"][:8] + "..."

                # Format name
                name = _truncate(match["name"], 23)

                # Format snippet
                snippet = _truncate(match["match_snippet"], 38)

                # Format time
                start_time = match.get("start_time", "-")
                if start_time and start_time != "-":
                    try:
                        dt = datetime.fromisoformat(start_time)
                        time_str = dt.strftime("%m-%d %H:%M")
                    except ValueError:
                        time_str = start_time[:10]
                else:
                    time_str = "-"

                table.add_row(
                    run_id,
                    name,
                    match["matched_field"],
                    snippet,
                    match.get("run_type", "-"),
                    time_str,
                )

            console.print(table)

        console.print(f"\n[dim]Found {len(matches)} matches across {len(runs)} runs[/dim]")

    except Exception as e:
        print_error(f"Failed to search runs: {e}")
        sys.exit(1)
