"""Plan management commands.

Handles planning folder operations and task tracking.
"""

import sys
from datetime import datetime
from pathlib import Path

import yaml


def handle(args, ctx=None):
    """Route plan subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.plan_command == "init":
        cmd_init(args, ctx)
    elif args.plan_command == "scaffold":
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
        elif args.task_action == "prefill":
            cmd_task_prefill(args, ctx)
        elif args.task_action == "list":
            cmd_task_list(args, ctx)
        elif args.task_action == "status":
            cmd_task_status(args, ctx)
        elif args.task_action == "add":
            cmd_task_add(args, ctx)
        elif args.task_action == "update":
            cmd_task_update(args, ctx)
        elif args.task_action == "current":
            cmd_task_current(args, ctx)
        else:
            print("Usage: agentic plan task <start|complete|prefill|list|status|add|update|current> ...", file=sys.stderr)
            sys.exit(1)
    elif args.plan_command == "archive":
        cmd_archive(args)
    elif args.plan_command == "list":
        cmd_list(args)
    elif args.plan_command == "move":
        cmd_move(args, ctx)
    else:
        print("Usage: agentic plan <init|scaffold|status|validate|task|archive|list|move>", file=sys.stderr)
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


def find_main_worktree(repo_root: Path) -> Path | None:
    """Find the main worktree path (branch main or master).

    Main-First Planning: Plans should always be created in the main worktree
    for visibility and traceability.

    Args:
        repo_root: Path to any worktree in the repository.

    Returns:
        Path to main worktree, or None if not found.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
        lines = result.stdout.strip().split("\n")
        i = 0
        while i < len(lines):
            if lines[i].startswith("worktree "):
                wt_path = lines[i].split(" ", 1)[1]
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].startswith("branch "):
                        wt_branch = lines[j].split(" ", 1)[1].replace("refs/heads/", "")
                        if wt_branch in ("main", "master"):
                            return Path(wt_path)
                        break
                    elif lines[j].startswith("worktree "):
                        break
            i += 1
    except subprocess.CalledProcessError:
        pass
    return None


def cmd_init(args, ctx=None):
    """Initialize worktree and plan folder with proper naming convention.

    Combines worktree creation (if needed) with plan folder scaffolding.
    Enforces YYMMDDXX_description naming convention programmatically.

    Exit codes:
        0: Success, folder created
        1: Worktree creation failed
        2: Folder already exists
        3: Invalid branch name or description
    """
    import subprocess

    from agenticcli.commands.worktree import create_planning_folder
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_info,
        print_json,
        print_success,
    )
    from agenticcli.utils.naming import generate_plan_folder_name, validate_plan_folder_name

    branch = args.branch
    description = getattr(args, "description", None) or branch
    base = getattr(args, "base", "main")

    # Validate branch name
    if not branch or not branch.strip():
        print_error("Branch name is required")
        sys.exit(3)

    # Get current repo root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        print_error("Not in a git repository")
        sys.exit(1)

    repo_name = repo_root.name.split("-")[0] if "-" in repo_root.name else repo_root.name

    # Main-First Planning: Always create plans in main worktree
    main_worktree_path = find_main_worktree(repo_root)
    if main_worktree_path is None:
        # Fallback: use repo_root if main worktree detection fails
        main_worktree_path = repo_root

    # Calculate expected worktree path
    worktree_path = repo_root.parent / f"{repo_name}-{branch}"

    # Check if worktree exists for this branch
    worktree_exists = False
    existing_worktree_path = None

    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
        lines = result.stdout.strip().split("\n")
        i = 0
        while i < len(lines):
            if lines[i].startswith("worktree "):
                wt_path = lines[i].split(" ", 1)[1]
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].startswith("branch "):
                        wt_branch = lines[j].split(" ", 1)[1].replace("refs/heads/", "")
                        if wt_branch == branch:
                            worktree_exists = True
                            existing_worktree_path = Path(wt_path)
                            break
                    elif lines[j].startswith("worktree "):
                        break
            i += 1
    except subprocess.CalledProcessError:
        pass

    # Determine final worktree path
    if worktree_exists:
        worktree_path = existing_worktree_path
        if not is_json_output():
            print_info(f"Using existing worktree at {worktree_path}")
    else:
        # Create worktree
        if not is_json_output():
            print_info(f"Creating worktree for branch '{branch}' at {worktree_path}")

        try:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch, str(worktree_path), base],
                check=True,
                cwd=repo_root,
                capture_output=is_json_output(),
            )
            if not is_json_output():
                console.print(f"  [green]Created worktree[/green] at {worktree_path}")
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to create worktree: {e}")
            sys.exit(1)

    # Generate plan folder name using new naming algorithm
    plan_folder_name = generate_plan_folder_name(worktree_path, description)

    # Validate the generated name
    is_valid, error = validate_plan_folder_name(plan_folder_name)
    if not is_valid:
        print_error(f"Generated name '{plan_folder_name}' is invalid: {error}")
        sys.exit(3)

    # Main-First Planning: Plan goes in main worktree, execution in feature worktree
    plan_path = main_worktree_path / "docs" / "plans" / "live" / plan_folder_name

    # Check if folder already exists
    if plan_path.exists():
        print_error(f"Plan folder already exists: {plan_path}")
        sys.exit(2)

    # Create the folder structure
    create_planning_folder(plan_path)

    # Output results
    if is_json_output():
        print_json({
            "worktree": str(worktree_path),
            "worktree_created": not worktree_exists,
            "branch": branch,
            "base": base,
            "plan_folder": str(plan_path),
            "plan_folder_name": plan_folder_name,
            "main_worktree": str(main_worktree_path),
        })
    else:
        console.print(f"  [green]Created plan folder[/green] at {plan_path}")
        console.print("  [dim](Main-First Planning: plan in main worktree)[/dim]")
        console.print()
        print_success(f"Plan initialized: {plan_folder_name}")
        console.print(f"[dim]Execution worktree:[/dim] {worktree_path}")
        console.print(f"[dim]Plan folder:[/dim] {plan_path}")

    sys.exit(0)


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
            file_stats.append(
                {
                    "file": yaml_file.name,
                    "pending": pending,
                    "in_progress": in_progress,
                    "completed": completed,
                }
            )
            total_pending += pending
            total_in_progress += in_progress
            total_completed += completed

    total = total_pending + total_in_progress + total_completed
    pct = (total_completed / total) * 100 if total > 0 else 0

    if is_json_output():
        print_json(
            {
                "plan": plan_path.name,
                "files": file_stats,
                "totals": {
                    "pending": total_pending,
                    "in_progress": total_in_progress,
                    "completed": total_completed,
                },
                "progress_percent": round(pct, 1),
            }
        )
    else:
        print_header(f"Plan Status: {plan_path.name}")

        rows = []
        for stat in file_stats:
            if "error" in stat:
                rows.append([stat["file"], "[red]ERROR[/red]", "", ""])
            else:
                rows.append(
                    [
                        stat["file"],
                        f"[dim]{stat['pending']}[/dim]",
                        f"[yellow]{stat['in_progress']}[/yellow]",
                        f"[green]{stat['completed']}[/green]",
                    ]
                )

        if rows:
            print_table("Files", ["File", "Pending", "In Progress", "Completed"], rows)

        console.print()
        console.print(
            f"[bold]Total:[/bold] [dim]{total_pending} pending[/dim], "
            f"[yellow]{total_in_progress} in progress[/yellow], "
            f"[green]{total_completed} completed[/green]"
        )
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


def cmd_task_prefill(args, ctx=None):
    """Load preset task list from template.

    Loads tasks from a preset YAML template and adds them to the
    current plan's task list for tracking.

    Args:
        args: Parsed arguments with preset, plan, dry_run.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_info,
        print_json,
        print_success,
        print_table,
    )

    # TaskPresetWorkflow will be created in Phase 3
    # For now, stub the import and show informative error
    try:
        from agenticcli.workflows.task_workflow import TaskPresetWorkflow
    except ImportError:
        print_error("TaskPresetWorkflow not yet available")
        print_info("This feature will be available after Phase 3 implementation.")
        sys.exit(1)

    preset_name = args.preset
    plan_path = find_plan_folder(getattr(args, "plan", None))
    dry_run = getattr(args, "dry_run", False)

    workflow = TaskPresetWorkflow(plan_path)

    try:
        result = workflow.load_preset(preset_name, dry_run=dry_run)
    except FileNotFoundError:
        print_error(f"Preset '{preset_name}' not found")
        print_info("Available presets: " + ", ".join(workflow.list_presets()))
        sys.exit(1)

    if is_json_output():
        print_json({
            "preset": preset_name,
            "tasks_added": result.tasks_added,
            "tasks": result.tasks,
            "dry_run": dry_run,
        })
    else:
        if dry_run:
            console.print(f"[dim][dry-run] Would add {len(result.tasks)} tasks from preset '{preset_name}'[/dim]")
        else:
            print_success(f"Added {result.tasks_added} tasks from preset '{preset_name}'")

        # Show tasks
        rows = [[t["id"], t["description"], t.get("priority", "medium")] for t in result.tasks]
        print_table("Tasks", ["ID", "Description", "Priority"], rows)


def cmd_task_list(args, ctx=None):
    """List all tasks in plan folder.

    Iterates through all YAML files in live/ and extracts tasks,
    supporting status filtering and verbose output.

    Args:
        args: Parsed arguments with plan, status filter, verbose.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        console,
        format_status,
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_table,
    )

    plan_path = find_plan_folder(getattr(args, "plan", None))
    status_filter = getattr(args, "status", "all")
    verbose = getattr(args, "verbose", False)
    live_dir = plan_path / "live"

    if not live_dir.exists():
        print_error(f"No live/ directory in {plan_path}")
        sys.exit(1)

    all_tasks = []

    for yaml_file in sorted(live_dir.glob("*.yml")):
        try:
            content = yaml.safe_load(yaml_file.read_text())
        except yaml.YAMLError:
            continue

        if not content:
            continue

        # Extract tasks from phases structure
        phases = content.get("phases", [])
        for phase in phases:
            phase_id = phase.get("phase_id", "")
            phase_name = phase.get("name", "")
            tasks = phase.get("tasks", [])

            for task in tasks:
                task_status = task.get("status", "pending")
                if status_filter != "all" and task_status != status_filter:
                    continue

                task_info = {
                    "id": task.get("task_id", ""),
                    "description": task.get("description", ""),
                    "status": task_status,
                    "phase_id": phase_id,
                    "phase_name": phase_name,
                    "source_file": yaml_file.name,
                }

                if verbose:
                    task_info["guidance"] = task.get("guidance", "")
                    task_info["success_criteria"] = task.get("success_criteria", [])

                all_tasks.append(task_info)

    if is_json_output():
        print_json({"tasks": all_tasks, "count": len(all_tasks)})
    else:
        print_header(f"Tasks in {plan_path.name}")

        if not all_tasks:
            console.print("[dim]No tasks found.[/dim]")
            return

        if verbose:
            for task in all_tasks:
                console.print(f"\n[bold]{task['id']}[/bold]: {task['description']}")
                console.print(f"  Status: {format_status(task['status'])}")
                console.print(f"  Phase: {task['phase_name']}")
                if task.get("guidance"):
                    guidance_preview = task["guidance"][:100].replace("\n", " ")
                    console.print(f"  [dim]Guidance: {guidance_preview}...[/dim]")
        else:
            rows = [
                [task["id"], task["description"][:50], format_status(task["status"]), task["phase_id"]]
                for task in all_tasks
            ]
            print_table("", ["ID", "Description", "Status", "Phase"], rows)

        console.print(f"\n[dim]Total: {len(all_tasks)} tasks[/dim]")


def cmd_task_status(args, ctx=None):
    """Show detailed status for a specific task.

    Finds task by ID and displays all available information
    including guidance, success criteria, inputs, and target files.

    Args:
        args: Parsed arguments with task_id and plan.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        console,
        format_status,
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_key_value,
    )

    task_id = args.task_id
    plan_path = find_plan_folder(getattr(args, "plan", None))
    live_dir = plan_path / "live"

    task_data = None
    source_file = None
    phase_info = None

    for yaml_file in live_dir.glob("*.yml"):
        try:
            content = yaml.safe_load(yaml_file.read_text())
        except yaml.YAMLError:
            continue

        if not content:
            continue

        phases = content.get("phases", [])
        for phase in phases:
            tasks = phase.get("tasks", [])
            for task in tasks:
                if task.get("task_id") == task_id:
                    task_data = task
                    source_file = yaml_file.name
                    phase_info = {
                        "phase_id": phase.get("phase_id"),
                        "name": phase.get("name"),
                        "status": phase.get("status"),
                    }
                    break
            if task_data:
                break
        if task_data:
            break

    if not task_data:
        print_error(f"Task '{task_id}' not found")
        sys.exit(1)

    if is_json_output():
        print_json({
            "task": task_data,
            "phase": phase_info,
            "source_file": source_file,
        })
    else:
        print_header(f"Task: {task_id}")

        print_key_value("Description", task_data.get("description", "N/A"))
        print_key_value("Status", format_status(task_data.get("status", "pending")))
        print_key_value("Phase", f"{phase_info['phase_id']} - {phase_info['name']}")
        print_key_value("Source File", source_file)

        if task_data.get("inputs"):
            console.print("\n[bold]Inputs:[/bold]")
            for inp in task_data["inputs"]:
                if isinstance(inp, dict):
                    console.print(f"  - {inp.get('path', inp)}")
                else:
                    console.print(f"  - {inp}")

        if task_data.get("target_files"):
            console.print("\n[bold]Target Files:[/bold]")
            for tf in task_data["target_files"]:
                console.print(f"  - {tf}")

        if task_data.get("guidance"):
            console.print("\n[bold]Guidance:[/bold]")
            console.print(f"[dim]{task_data['guidance']}[/dim]")

        if task_data.get("success_criteria"):
            console.print("\n[bold]Success Criteria:[/bold]")
            for criterion in task_data["success_criteria"]:
                console.print(f"  - {criterion}")


def cmd_task_add(args, ctx=None):
    """Add a new task to the plan.

    Creates a new task entry in the specified phase or appends
    to the default/last phase if not specified.

    Args:
        args: Parsed arguments with description, plan, phase, id, priority.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
    )

    description = args.description
    plan_path = find_plan_folder(getattr(args, "plan", None))
    phase_id = getattr(args, "phase", None)
    custom_id = getattr(args, "id", None)
    priority = getattr(args, "priority", "medium")
    live_dir = plan_path / "live"

    # Find the first plan_live_*.yml file or plan_build*.yml
    target_file = None
    for pattern in ["plan_live_*.yml", "plan_build*.yml", "*.yml"]:
        files = list(live_dir.glob(pattern))
        if files:
            target_file = files[0]
            break

    if not target_file:
        print_error("No plan file found in live/ directory")
        sys.exit(1)

    try:
        content = yaml.safe_load(target_file.read_text())
    except yaml.YAMLError as e:
        print_error(f"Failed to parse {target_file.name}: {e}")
        sys.exit(1)

    if not content:
        content = {"phases": []}

    phases = content.get("phases", [])

    # Find target phase
    target_phase = None
    if phase_id:
        for phase in phases:
            if phase.get("phase_id") == phase_id:
                target_phase = phase
                break
        if not target_phase:
            print_error(f"Phase '{phase_id}' not found")
            sys.exit(1)
    else:
        if phases:
            target_phase = phases[-1]  # Add to last phase
        else:
            # Create default phase
            target_phase = {
                "phase_id": "adhoc_01",
                "name": "Ad-hoc Tasks",
                "status": "pending",
                "tasks": [],
            }
            phases.append(target_phase)
            content["phases"] = phases

    # Generate task ID
    if custom_id:
        new_task_id = custom_id
    else:
        existing_ids = [t.get("task_id", "") for t in target_phase.get("tasks", [])]
        phase_prefix = target_phase.get("phase_id", "task")
        task_num = len(existing_ids) + 1
        new_task_id = f"{phase_prefix}_{task_num:03d}"

    # Create task entry
    new_task = {
        "task_id": new_task_id,
        "description": description,
        "status": "pending",
        "priority": priority,
    }

    if "tasks" not in target_phase:
        target_phase["tasks"] = []
    target_phase["tasks"].append(new_task)

    # Write back
    with open(target_file, "w") as f:
        yaml.dump(content, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    if is_json_output():
        print_json({
            "task_id": new_task_id,
            "description": description,
            "phase_id": target_phase.get("phase_id"),
            "file": target_file.name,
        })
    else:
        print_success(f"Added task '{new_task_id}' to {target_file.name}")


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

        plans_data.append(
            {
                "name": plan_folder.name,
                "status": plan_status,
                "pending": total_pending,
                "in_progress": total_in_progress,
                "completed": total_completed,
                "progress_percent": round(pct, 1),
            }
        )

    if is_json_output():
        print_json({"plans": plans_data})
    else:
        print_header("Plans in Repository")

        if not plans_data:
            console.print("[dim]No plan folders found.[/dim]")
            return

        rows = []
        for plan in plans_data:
            progress = f"{plan['progress_percent']:.0f}%" if plan["progress_percent"] > 0 else "N/A"
            rows.append(
                [
                    f"[bold]{plan['name']}[/bold]",
                    format_status(plan["status"]),
                    f"[dim]{plan['pending']}[/dim]",
                    f"[yellow]{plan['in_progress']}[/yellow]",
                    f"[green]{plan['completed']}[/green]",
                    f"[cyan]{progress}[/cyan]",
                ]
            )

        print_table("", ["Plan", "Status", "Pending", "In Prog", "Done", "Progress"], rows)


def cmd_move(args, ctx=None):
    """Move completed tasks to plan_completed.yml or archive folder.

    Supports:
    - plan move task <task-id>: Move a single task
    - plan move tasks: Move all completed tasks
    - plan move folder: Archive the entire plan folder
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_json,
        print_success,
        print_warning,
    )
    from agenticcli.workflows.plan_workflow import MoveResult, PlanMovementWorkflow

    plan_path = find_plan_folder(getattr(args, "plan", None))
    workflow = PlanMovementWorkflow(plan_path)

    dry_run = getattr(args, "dry_run", False)
    force = getattr(args, "force", False)
    move_type = getattr(args, "move_type", None)

    if move_type == "task":
        task_id = args.task_id
        result = workflow.move_task_to_completed(task_id, dry_run=dry_run, force=force)

        if is_json_output():
            print_json({
                "task_id": result.task_id,
                "result": result.result.value,
                "message": result.message,
                "source_file": result.source_file,
                "target_file": result.target_file,
            })
        else:
            if result.result == MoveResult.SUCCESS:
                print_success(result.message)
            elif result.result == MoveResult.SKIPPED:
                print_warning(result.message)
            else:
                print_error(result.message)
                sys.exit(1)

    elif move_type == "tasks":
        results = workflow.move_all_completed_tasks(dry_run=dry_run, force=force)

        if is_json_output():
            print_json({
                "results": [
                    {
                        "task_id": r.task_id,
                        "result": r.result.value,
                        "message": r.message,
                    }
                    for r in results
                ],
                "success": sum(1 for r in results if r.result == MoveResult.SUCCESS),
                "skipped": sum(1 for r in results if r.result == MoveResult.SKIPPED),
                "failed": sum(1 for r in results if r.result == MoveResult.FAILED),
            })
        else:
            success = sum(1 for r in results if r.result == MoveResult.SUCCESS)
            skipped = sum(1 for r in results if r.result == MoveResult.SKIPPED)
            failed = sum(1 for r in results if r.result == MoveResult.FAILED)

            if success > 0:
                print_success(f"Moved {success} task(s) to plan_completed.yml")
            if skipped > 0:
                print_warning(f"Skipped {skipped} task(s)")
            if failed > 0:
                print_error(f"Failed {failed} task(s)")
            if not results:
                console.print("[dim]No completed tasks found to move.[/dim]")

    elif move_type == "folder":
        result = workflow.archive_plan_folder(dry_run=dry_run, force=force)

        if is_json_output():
            print_json({
                "source": result.source,
                "destination": result.destination,
                "result": result.result.value,
                "message": result.message,
            })
        else:
            if result.result == MoveResult.SUCCESS:
                print_success(result.message)
            elif result.result == MoveResult.SKIPPED:
                print_warning(result.message)
            else:
                print_error(result.message)
                sys.exit(1)

    else:
        print("Usage: agentic plan move <task|tasks|folder>", file=sys.stderr)
        sys.exit(1)


def cmd_task_update(args, ctx=None):
    """Update task status in plan YAML file.

    Enables agents to persist progress without holding plan in context.
    Modifies EXISTING plan files created by planner agents.

    Args:
        args: Parsed arguments with task_id, status, optional note.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
        print_warning,
    )

    task_id = args.task_id
    new_status = args.status
    note = getattr(args, "note", None)
    plan_path = find_plan_folder(getattr(args, "plan", None))
    live_dir = plan_path / "live"

    if not live_dir.exists():
        print_error(f"No live/ directory in {plan_path}")
        sys.exit(1)

    # Find and update the task
    task_found = False
    updated_file = None

    for yaml_file in live_dir.glob("*.yml"):
        try:
            content = yaml.safe_load(yaml_file.read_text())
        except yaml.YAMLError:
            continue

        if not content:
            continue

        # Look for the task in phases
        phases = content.get("phases", [])
        for phase in phases:
            tasks = phase.get("tasks", [])
            for task in tasks:
                # Match task by various ID field names
                tid = task.get("id") or task.get("task_id") or ""
                if tid == task_id:
                    # Found the task - update status
                    old_status = task.get("status", "pending")

                    # Validate status transition
                    valid_transitions = {
                        "pending": ["in_progress", "blocked"],
                        "in_progress": ["completed", "blocked", "pending"],
                        "completed": ["pending", "in_progress"],  # Allow rollback
                        "blocked": ["pending", "in_progress"],
                    }

                    if new_status not in valid_transitions.get(old_status, []) and old_status != new_status:
                        if is_json_output():
                            print_json({
                                "error": f"Invalid transition from {old_status} to {new_status}",
                                "task_id": task_id,
                                "current_status": old_status,
                            })
                        else:
                            print_warning(f"Status transition from '{old_status}' to '{new_status}' for task {task_id}")

                    task["status"] = new_status

                    # Add completion note if provided
                    if note:
                        task["completion_note"] = note

                    # Add timestamp for completed tasks
                    if new_status == "completed":
                        task["completed_at"] = datetime.now().isoformat()

                    task_found = True
                    updated_file = yaml_file
                    break
            if task_found:
                break

        if task_found:
            # Write back to file
            try:
                yaml_file.write_text(yaml.dump(content, default_flow_style=False, sort_keys=False))
            except IOError as e:
                print_error(f"Failed to write {yaml_file}: {e}")
                sys.exit(1)
            break

    if not task_found:
        if is_json_output():
            print_json({"error": f"Task not found: {task_id}"})
        else:
            print_error(f"Task not found: {task_id}")
            print("Hint: Use 'agentic plan task list' to see available task IDs", file=sys.stderr)
        sys.exit(1)

    if is_json_output():
        print_json({
            "task_id": task_id,
            "new_status": new_status,
            "file": updated_file.name if updated_file else None,
            "note": note,
        })
    else:
        print_success(f"Updated task {task_id} to '{new_status}'")


def cmd_task_current(args, ctx=None):
    """Get the current/next task to work on.

    Returns the first in_progress task, or first pending if none in progress.
    This is the primary "what should I do next?" query for agents.

    Args:
        args: Parsed arguments with optional plan path.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        console,
        format_status,
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_key_value,
    )

    plan_path = find_plan_folder(getattr(args, "plan", None))
    live_dir = plan_path / "live"

    if not live_dir.exists():
        print_error(f"No live/ directory in {plan_path}")
        sys.exit(1)

    # Collect all tasks with full details
    all_tasks = []

    for yaml_file in sorted(live_dir.glob("*.yml")):
        try:
            content = yaml.safe_load(yaml_file.read_text())
        except yaml.YAMLError:
            continue

        if not content:
            continue

        phases = content.get("phases", [])
        for phase in phases:
            phase_name = phase.get("name", "")
            phase_id = phase.get("id", "")
            tasks = phase.get("tasks", [])

            for task in tasks:
                task_info = {
                    "id": task.get("id") or task.get("task_id", ""),
                    "name": task.get("name", ""),
                    "description": task.get("description", ""),
                    "status": task.get("status", "pending"),
                    "phase": phase_name,
                    "phase_id": phase_id,
                    "inputs": task.get("inputs", []),
                    "target_files": task.get("target_files", []),
                    "guidance": task.get("guidance", ""),
                    "success_criteria": task.get("success_criteria", []),
                    "agent_type": task.get("agent_type", ""),
                    "source_file": yaml_file.name,
                }
                all_tasks.append(task_info)

    # Find current task: first in_progress, or first pending
    current_task = None

    for task in all_tasks:
        if task["status"] == "in_progress":
            current_task = task
            break

    if not current_task:
        for task in all_tasks:
            if task["status"] == "pending":
                current_task = task
                break

    if is_json_output():
        if current_task:
            print_json({
                "plan_folder": plan_path.name,
                "task": current_task,
                "all_complete": False,
            })
        else:
            # Check if all are completed
            completed_count = sum(1 for t in all_tasks if t["status"] == "completed")
            print_json({
                "plan_folder": plan_path.name,
                "task": None,
                "all_complete": completed_count == len(all_tasks),
                "total_tasks": len(all_tasks),
                "completed_tasks": completed_count,
            })
    else:
        print_header(f"Current Task - {plan_path.name}")

        if current_task:
            console.print(f"\n[bold]Task:[/bold] {current_task['id']} - {current_task['name']}")
            console.print(f"[bold]Status:[/bold] {format_status(current_task['status'])}")
            console.print(f"[bold]Phase:[/bold] {current_task['phase']}")

            if current_task.get("description"):
                console.print(f"\n[bold]Description:[/bold]")
                console.print(current_task["description"][:500])

            if current_task.get("guidance"):
                console.print(f"\n[bold]Guidance:[/bold]")
                console.print(current_task["guidance"][:500])

            if current_task.get("inputs"):
                console.print(f"\n[bold]Inputs:[/bold]")
                for inp in current_task["inputs"][:5]:
                    console.print(f"  - {inp}")

            if current_task.get("target_files"):
                console.print(f"\n[bold]Target Files:[/bold]")
                for tf in current_task["target_files"][:5]:
                    console.print(f"  - {tf}")

            if current_task.get("success_criteria"):
                console.print(f"\n[bold]Success Criteria:[/bold]")
                for sc in current_task["success_criteria"][:3]:
                    console.print(f"  - {sc}")
        else:
            completed_count = sum(1 for t in all_tasks if t["status"] == "completed")
            if completed_count == len(all_tasks) and all_tasks:
                console.print("[green]All tasks completed![/green]")
            else:
                console.print("[dim]No tasks found or no pending tasks.[/dim]")
