"""Context retrieval commands.

CCI (CLI Context Injection) context commands for agents to fetch exactly what they need
via CLI instead of loading large static files.

Commands:
    bootstrap: Primary entrypoint for Seed Context (role + task + inputs)
    role: Get role-specific process/guidelines
    task: Get active task from Main-First plan
    inputs: Get CCI manifest of relevant project files
"""

import json
import sys
from pathlib import Path

import yaml


def handle(args, ctx=None):
    """Route context subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.context_command == "bootstrap":
        cmd_bootstrap(args, ctx)
    elif args.context_command == "role":
        cmd_role(args, ctx)
    elif args.context_command == "task":
        cmd_task(args, ctx)
    elif args.context_command == "inputs":
        cmd_inputs(args, ctx)
    elif args.context_command == "generate-agent":
        cmd_generate_agent(args, ctx)
    else:
        print(
            "Usage: agentic context <bootstrap|role|task|inputs|generate-agent> ...",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_bootstrap(args, ctx=None):
    """Get bootstrap context for an agent (Seed Context).

    Aggregates: Active Task + Primary Role Guidance + Essential Inputs.
    This is the primary entrypoint for agents to self-initialize.

    Args:
        args: Parsed arguments with optional --role.
        ctx: CLI context.
    """
    from agenticcli.console import is_json_output, print_error, print_json

    from agenticguidance.services import (
        MainFirstPlanResolver,
        get_role_process,
        get_role_inputs_manifest,
    )

    role_id = getattr(args, "role", None)
    json_output = is_json_output()

    resolver = MainFirstPlanResolver()

    # 1. Get active plan and task
    plan_info = resolver.resolve_active_plan()
    current_task = None

    if plan_info:
        current_task = resolver.extract_current_task(plan_info["plan_folder"])
        # If role not specified, try to infer from current task
        if not role_id and current_task:
            role_id = current_task.get("agent_type", "build")

    # Default role if still not set
    if not role_id:
        role_id = "build"

    # 2. Get role-specific process/guidelines
    role_process = get_role_process(role_id)

    # 3. Get essential inputs
    inputs_manifest = get_role_inputs_manifest(role_id)

    # 4. Build CLI command hints
    cli_commands = {
        "task_prefill": f"agentic plan task prefill --preset {role_id}",
        "task_status": "agentic plan task list",
        "task_update": "agentic plan task update <task-id> --status <status>",
        "task_current": "agentic context task",
    }

    # Construct bootstrap context
    bootstrap_context = {
        "role": role_id,
        "objective": plan_info.get("objective") if plan_info else None,
        "plan_folder": plan_info.get("plan_folder_name") if plan_info else None,
        "plan_path": str(plan_info.get("plan_folder")) if plan_info else None,
        "current_task": current_task,
        "process": role_process,
        "essential_inputs": inputs_manifest.get("inputs", [])[:10] if inputs_manifest else [],
        "cli_commands": cli_commands,
    }

    if json_output:
        print_json(bootstrap_context)
    else:
        _print_bootstrap_human_readable(bootstrap_context)


def _print_bootstrap_human_readable(context: dict):
    """Print bootstrap context in human-readable format."""
    from agenticcli.console import console
    from rich.panel import Panel
    from rich.table import Table

    console.print(Panel(f"[bold]Bootstrap Context[/bold] - Role: {context['role']}"))

    if context.get("objective"):
        console.print(f"\n[bold]Objective:[/bold] {context['objective'][:200]}...")

    if context.get("plan_folder"):
        console.print(f"[bold]Plan Folder:[/bold] {context['plan_folder']}")

    if context.get("current_task"):
        task = context["current_task"]
        console.print(f"\n[bold]Current Task:[/bold] {task.get('id', 'N/A')} - {task.get('name', 'N/A')}")
        console.print(f"[bold]Status:[/bold] {task.get('status', 'N/A')}")

    console.print("\n[bold]CLI Commands:[/bold]")
    for name, cmd in context.get("cli_commands", {}).items():
        console.print(f"  {name}: [cyan]{cmd}[/cyan]")


def cmd_role(args, ctx=None):
    """Get role-specific process and guidelines.

    Args:
        args: Parsed arguments with required role_id.
        ctx: CLI context.
    """
    from agenticcli.console import is_json_output, print_error, print_json

    from agenticguidance.services import get_role_process

    role_id = args.role_id
    json_output = is_json_output()
    output_format = getattr(args, "format", "yaml")

    role_process = get_role_process(role_id)

    if not role_process:
        print_error(f"Role not found: {role_id}")
        print(
            f"Hint: Agent should exist at modules/AgenticGuidance/agents/<category>/{role_id}/",
            file=sys.stderr,
        )
        sys.exit(1)

    if json_output or output_format == "json":
        print_json(role_process)
    else:
        # YAML output (default)
        print(yaml.dump(role_process, default_flow_style=False, sort_keys=False))


def cmd_task(args, ctx=None):
    """Get active task from Main-First plan.

    Crawls the repo's docs/plans/live/ to find and extract
    the active task for the current branch.

    Args:
        args: Parsed arguments with optional --all flag.
        ctx: CLI context.
    """
    from agenticcli.console import is_json_output, print_error, print_json, print_warning

    from agenticguidance.services import MainFirstPlanResolver

    json_output = is_json_output()
    show_all = getattr(args, "all", False)

    resolver = MainFirstPlanResolver()
    plan_info = resolver.resolve_active_plan()

    if not plan_info:
        if json_output:
            print_json({"error": "No active plan found", "tasks": []})
        else:
            print_warning("No active plan found for current branch.")
            print("Hint: Use 'agentic plan init <branch>' to create a plan.", file=sys.stderr)
        sys.exit(0)

    if show_all:
        # Return all tasks
        all_tasks = resolver.extract_all_tasks(plan_info["plan_folder"])
        if json_output:
            print_json({
                "plan_folder": plan_info.get("plan_folder_name"),
                "task_count": len(all_tasks),
                "tasks": all_tasks,
            })
        else:
            _print_tasks_human_readable(all_tasks, plan_info.get("plan_folder_name"))
    else:
        # Return current/next task
        current_task = resolver.extract_current_task(plan_info["plan_folder"])
        if json_output:
            print_json({
                "plan_folder": plan_info.get("plan_folder_name"),
                "task": current_task,
            })
        else:
            if current_task:
                _print_single_task(current_task, plan_info.get("plan_folder_name"))
            else:
                print("All tasks completed or no tasks found.")


def _print_tasks_human_readable(tasks: list, plan_folder: str):
    """Print tasks in a table format."""
    from agenticcli.console import console
    from rich.table import Table

    table = Table(title=f"Tasks in {plan_folder}")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Status", style="bold")
    table.add_column("Phase")

    for task in tasks:
        status_style = {
            "pending": "yellow",
            "in_progress": "blue",
            "completed": "green",
            "blocked": "red",
        }.get(task.get("status", "pending"), "")

        table.add_row(
            task.get("id", "N/A"),
            task.get("name", "N/A")[:50],
            f"[{status_style}]{task.get('status', 'pending')}[/]",
            task.get("phase", "N/A"),
        )

    console.print(table)


def _print_single_task(task: dict, plan_folder: str):
    """Print a single task with full details."""
    from agenticcli.console import console
    from rich.panel import Panel

    console.print(Panel(f"[bold]Current Task[/bold] - {plan_folder}"))
    console.print(f"[bold]ID:[/bold] {task.get('id', 'N/A')}")
    console.print(f"[bold]Name:[/bold] {task.get('name', 'N/A')}")
    console.print(f"[bold]Status:[/bold] {task.get('status', 'N/A')}")
    console.print(f"[bold]Phase:[/bold] {task.get('phase', 'N/A')}")

    if task.get("description"):
        console.print(f"\n[bold]Description:[/bold]\n{task.get('description')[:500]}")

    if task.get("guidance"):
        console.print(f"\n[bold]Guidance:[/bold]\n{task.get('guidance')[:500]}")

    if task.get("inputs"):
        console.print("\n[bold]Inputs:[/bold]")
        for inp in task.get("inputs", [])[:5]:
            console.print(f"  - {inp}")

    if task.get("target_files"):
        console.print("\n[bold]Target Files:[/bold]")
        for tf in task.get("target_files", [])[:5]:
            console.print(f"  - {tf}")


def cmd_inputs(args, ctx=None):
    """Get CCI manifest of relevant project files.

    Replaces static inputs.yml references with dynamic discovery
    and path resolution.

    Args:
        args: Parsed arguments with optional --role and --resolve.
        ctx: CLI context.
    """
    from agenticcli.console import is_json_output, print_error, print_json

    from agenticguidance.services import get_role_inputs_manifest

    role_id = getattr(args, "role", None)
    resolve_layers = getattr(args, "resolve", False)
    json_output = is_json_output()

    if not role_id:
        print_error("--role is required for inputs command")
        print("Usage: agentic context inputs --role <role-id>", file=sys.stderr)
        sys.exit(1)

    manifest = get_role_inputs_manifest(role_id, resolve_layers=resolve_layers)

    if not manifest:
        print_error(f"Could not load inputs for role: {role_id}")
        sys.exit(1)

    if json_output:
        print_json(manifest)
    else:
        _print_inputs_human_readable(manifest)


def _print_inputs_human_readable(manifest: dict):
    """Print inputs manifest in human-readable format."""
    from agenticcli.console import console
    from rich.table import Table

    console.print(f"\n[bold]Inputs for role:[/bold] {manifest.get('role', 'N/A')}")

    if manifest.get("inputs"):
        table = Table(title="Input Files")
        table.add_column("Path")
        table.add_column("Exists", style="bold")
        table.add_column("Description")

        for inp in manifest.get("inputs", []):
            exists_str = "[green]Yes[/]" if inp.get("exists") else "[red]No[/]"
            table.add_row(
                inp.get("path", "N/A")[:60],
                exists_str,
                inp.get("description", "")[:40],
            )

        console.print(table)

    if manifest.get("missing"):
        console.print("\n[bold red]Missing Files:[/bold red]")
        for missing in manifest.get("missing", []):
            console.print(f"  - {missing}")


def cmd_generate_agent(args, ctx=None):
    """Generate thin-client agent file from bootstrap template.

    Args:
        args: Parsed arguments with role_id and optional --output.
        ctx: CLI context.
    """
    from agenticcli.console import print_error, print_success

    from agenticguidance.services import generate_agent_bootstrap

    role_id = args.role_id
    output_path = getattr(args, "output", None)

    content = generate_agent_bootstrap(role_id)

    if not content:
        print_error(f"Could not generate agent file for role: {role_id}")
        sys.exit(1)

    if output_path:
        Path(output_path).write_text(content)
        print_success(f"Generated agent file: {output_path}")
    else:
        # Output to stdout
        print(content)
