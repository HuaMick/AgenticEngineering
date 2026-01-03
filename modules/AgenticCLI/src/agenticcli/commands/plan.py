"""Plan management commands.

Handles planning folder operations and task tracking.
"""

import sys
from datetime import datetime
from pathlib import Path

import yaml


def handle(args):
    """Route plan subcommands."""
    if args.plan_command == "scaffold":
        cmd_scaffold(args)
    elif args.plan_command == "status":
        cmd_status(args)
    elif args.plan_command == "validate":
        cmd_validate(args)
    elif args.plan_command == "task":
        if args.task_action == "start":
            cmd_task_start(args)
        elif args.task_action == "complete":
            cmd_task_complete(args)
        else:
            print("Usage: agentic plan task <start|complete> <task-id>", file=sys.stderr)
            sys.exit(1)
    elif args.plan_command == "archive":
        cmd_archive(args)
    elif args.plan_command == "list":
        cmd_list(args)
    else:
        print("Usage: agentic plan <scaffold|status|validate|task|archive|list>", file=sys.stderr)
        sys.exit(1)


def find_plan_folder(path: str | None = None) -> Path:
    """Find the active plan folder.

    Args:
        path: Explicit path to plan folder, or None to auto-detect.

    Returns:
        Path to the plan folder.
    """
    if path:
        return Path(path)

    # Auto-detect: look for docs/plans/live/ in current directory tree
    cwd = Path.cwd()

    # Check if we're in a plan folder
    if (cwd / "live").exists() and (cwd / "completed").exists():
        return cwd

    # Check if we're in a worktree with plans
    plans_dir = cwd / "docs" / "plans" / "live"
    if plans_dir.exists():
        # Return first plan folder found
        for item in plans_dir.iterdir():
            if item.is_dir() and (item / "live").exists():
                return item

    print("Error: Could not find a plan folder. Specify path explicitly.", file=sys.stderr)
    sys.exit(1)


def cmd_scaffold(args):
    """Create planning folder structure."""
    from agenticcli.commands.worktree import create_planning_folder

    name = args.name
    worktree = Path(args.worktree) if args.worktree else Path.cwd()

    plan_path = worktree / "docs" / "plans" / "live" / name

    if plan_path.exists():
        print(f"Error: Plan folder already exists: {plan_path}", file=sys.stderr)
        sys.exit(1)

    create_planning_folder(plan_path)
    print(f"Created planning folder: {plan_path}")
    print(f"  live/: {plan_path / 'live'}")
    print(f"  completed/: {plan_path / 'completed'}")


def cmd_status(args):
    """Show plan status and task summary."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_table,
    )

    plan_path = find_plan_folder(args.path)
    live_dir = plan_path / "live"

    if not live_dir.exists():
        print_error(f"No live/ directory in {plan_path}")
        sys.exit(1)

    total_pending = 0
    total_in_progress = 0
    total_completed = 0
    file_stats = []

    for yaml_file in sorted(live_dir.glob("*.yml")):
        try:
            content = yaml.safe_load(yaml_file.read_text())
        except yaml.YAMLError as e:
            file_stats.append({"file": yaml_file.name, "error": str(e)})
            continue

        if not content:
            continue

        # Count tasks by status
        pending = 0
        in_progress = 0
        completed = 0

        # Check for phases or implementation_steps
        plan = content.get("plan", content.get("feature", {}))
        phases = plan.get("phases", [])
        steps = plan.get("implementation_steps", [])

        for item in phases + steps:
            status = item.get("status", "pending")
            if status == "pending":
                pending += 1
            elif status == "in_progress":
                in_progress += 1
            elif status == "completed":
                completed += 1

        if pending + in_progress + completed > 0:
            file_stats.append({
                "file": yaml_file.name,
                "pending": pending,
                "in_progress": in_progress,
                "completed": completed,
            })
            total_pending += pending
            total_in_progress += in_progress
            total_completed += completed

    total = total_pending + total_in_progress + total_completed
    pct = (total_completed / total) * 100 if total > 0 else 0

    if is_json_output():
        print_json({
            "plan": plan_path.name,
            "files": file_stats,
            "totals": {
                "pending": total_pending,
                "in_progress": total_in_progress,
                "completed": total_completed,
            },
            "progress_percent": round(pct, 1),
        })
    else:
        print_header(f"Plan Status: {plan_path.name}")

        rows = []
        for stat in file_stats:
            if "error" in stat:
                rows.append([stat["file"], "[red]ERROR[/red]", "", ""])
            else:
                rows.append([
                    stat["file"],
                    f"[dim]{stat['pending']}[/dim]",
                    f"[yellow]{stat['in_progress']}[/yellow]",
                    f"[green]{stat['completed']}[/green]",
                ])

        if rows:
            print_table(
                "Files",
                ["File", "Pending", "In Progress", "Completed"],
                rows
            )

        console.print()
        console.print(f"[bold]Total:[/bold] [dim]{total_pending} pending[/dim], "
                      f"[yellow]{total_in_progress} in progress[/yellow], "
                      f"[green]{total_completed} completed[/green]")
        console.print(f"[bold]Progress:[/bold] [cyan]{pct:.1f}%[/cyan]")


def cmd_validate(args):
    """Validate plan folder structure and YAML."""
    plan_path = Path(args.path)
    errors = []
    warnings = []

    # Check folder structure
    if not plan_path.exists():
        print(f"Error: Path does not exist: {plan_path}", file=sys.stderr)
        sys.exit(1)

    live_dir = plan_path / "live"
    completed_dir = plan_path / "completed"

    if not live_dir.exists():
        errors.append("Missing live/ subdirectory")
    if not completed_dir.exists():
        errors.append("Missing completed/ subdirectory")

    # Check for required files
    if live_dir.exists():
        yaml_files = list(live_dir.glob("*.yml"))
        if not yaml_files:
            warnings.append("No YAML files in live/ directory")

        # Validate YAML syntax
        for yaml_file in yaml_files:
            try:
                content = yaml.safe_load(yaml_file.read_text())
                if content is None:
                    warnings.append(f"{yaml_file.name}: Empty file")
            except yaml.YAMLError as e:
                errors.append(f"{yaml_file.name}: Invalid YAML - {e}")

    # Check completed directory
    if completed_dir.exists():
        completed_file = completed_dir / "plan_completed.yml"
        if not completed_file.exists():
            warnings.append("Missing completed/plan_completed.yml")

    # Report results
    print(f"Validating: {plan_path}")
    print("=" * 60)

    if errors:
        print("\nErrors:")
        for err in errors:
            print(f"  - {err}")

    if warnings:
        print("\nWarnings:")
        for warn in warnings:
            print(f"  - {warn}")

    if not errors and not warnings:
        print("  All checks passed")

    if errors:
        sys.exit(1)


def cmd_task_start(args):
    """Mark a task as in_progress."""
    task_id = args.task_id
    plan_path = find_plan_folder(args.plan)

    _update_task_status(plan_path, task_id, "in_progress")
    print(f"Task {task_id} marked as in_progress")


def cmd_task_complete(args):
    """Mark a task as completed."""
    task_id = args.task_id
    plan_path = find_plan_folder(args.plan)

    _update_task_status(plan_path, task_id, "completed")
    print(f"Task {task_id} marked as completed")


def _update_task_status(plan_path: Path, task_id: str, new_status: str):
    """Update a task's status in plan files.

    Args:
        plan_path: Path to plan folder
        task_id: Task ID to update
        new_status: New status value
    """
    live_dir = plan_path / "live"

    for yaml_file in live_dir.glob("*.yml"):
        content = yaml_file.read_text()
        data = yaml.safe_load(content)
        if not data:
            continue

        # Look for the task in phases or implementation_steps
        plan = data.get("plan", data.get("feature", {}))
        modified = False

        for key in ["phases", "implementation_steps"]:
            items = plan.get(key, [])
            for item in items:
                if item.get("id") == task_id:
                    item["status"] = new_status
                    modified = True
                    break
            if modified:
                break

        if modified:
            # Write back
            with open(yaml_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            return

    print(f"Error: Task {task_id} not found in plan files", file=sys.stderr)
    sys.exit(1)


def cmd_archive(args):
    """Copy plan to completed folder."""
    import shutil

    plan_path = Path(args.path)
    if not plan_path.exists():
        print(f"Error: Plan folder not found: {plan_path}", file=sys.stderr)
        sys.exit(1)

    # Determine destination
    # Go up from live/FOLDER to docs/plans/completed/
    dest_dir = plan_path.parent.parent / "completed" / plan_path.name

    if dest_dir.exists():
        print(f"Warning: Destination already exists: {dest_dir}")
        response = input("Overwrite? [y/N] ")
        if response.lower() != "y":
            print("Aborted")
            sys.exit(0)
        shutil.rmtree(dest_dir)

    # Copy the folder
    shutil.copytree(plan_path, dest_dir)

    # Update completion metadata
    completed_file = dest_dir / "completed" / "plan_completed.yml"
    if completed_file.exists():
        try:
            data = yaml.safe_load(completed_file.read_text())
            if data is None:
                data = {}
            data["archived_date"] = datetime.now().strftime("%Y-%m-%d")
            with open(completed_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
        except yaml.YAMLError:
            pass

    print(f"Archived plan to: {dest_dir}")


def cmd_list(args):
    """List all plans in the repository."""
    from agenticcli.console import (
        console,
        format_status,
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_table,
    )

    # Find docs/plans/live directory from current working directory
    cwd = Path.cwd()
    plans_dir = cwd / "docs" / "plans" / "live"

    if not plans_dir.exists():
        print_error("No docs/plans/live directory found in current repository.")
        sys.exit(1)

    plan_folders = [d for d in sorted(plans_dir.iterdir()) if d.is_dir()]
    plans_data = []

    for plan_folder in plan_folders:
        live_dir = plan_folder / "live"
        if not live_dir.exists():
            continue

        # Count tasks across all files
        total_pending = 0
        total_in_progress = 0
        total_completed = 0
        plan_status = "unknown"

        for yaml_file in live_dir.glob("*.yml"):
            try:
                content = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError:
                continue

            if not content:
                continue

            # Extract plan status if available
            plan_data = content.get("plan", content.get("feature", {}))
            if "status" in plan_data:
                plan_status = plan_data["status"]

            # Count tasks
            phases = plan_data.get("phases", [])
            steps = plan_data.get("implementation_steps", [])

            for item in phases + steps:
                status = item.get("status", "pending")
                if status == "pending":
                    total_pending += 1
                elif status == "in_progress":
                    total_in_progress += 1
                elif status == "completed":
                    total_completed += 1

        total = total_pending + total_in_progress + total_completed
        pct = (total_completed / total) * 100 if total > 0 else 0

        plans_data.append({
            "name": plan_folder.name,
            "status": plan_status,
            "pending": total_pending,
            "in_progress": total_in_progress,
            "completed": total_completed,
            "progress_percent": round(pct, 1),
        })

    if is_json_output():
        print_json({"plans": plans_data})
    else:
        print_header("Plans in Repository")

        if not plans_data:
            console.print("[dim]No plan folders found.[/dim]")
            return

        rows = []
        for plan in plans_data:
            progress = f"{plan['progress_percent']:.0f}%" if plan['progress_percent'] > 0 else "N/A"
            rows.append([
                f"[bold]{plan['name']}[/bold]",
                format_status(plan['status']),
                f"[dim]{plan['pending']}[/dim]",
                f"[yellow]{plan['in_progress']}[/yellow]",
                f"[green]{plan['completed']}[/green]",
                f"[cyan]{progress}[/cyan]",
            ])

        print_table(
            "",
            ["Plan", "Status", "Pending", "In Prog", "Done", "Progress"],
            rows
        )
