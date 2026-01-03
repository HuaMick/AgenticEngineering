"""Worktree management commands.

Handles git worktree operations with planning folder integration.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path


def handle(args):
    """Route worktree subcommands."""
    if args.worktree_command == "create":
        cmd_create(args)
    elif args.worktree_command == "list":
        cmd_list(args)
    elif args.worktree_command == "remove":
        cmd_remove(args)
    elif args.worktree_command == "status":
        cmd_status(args)
    else:
        print("Usage: agentic worktree <create|list|remove|status>", file=sys.stderr)
        sys.exit(1)


def get_repo_root() -> Path:
    """Find the git repository root directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        print("Error: Not in a git repository", file=sys.stderr)
        sys.exit(1)


def get_repo_abbreviation(repo_name: str) -> str:
    """Generate 2-letter abbreviation for repository name.

    Examples:
        AgenticEngineering -> AE
        MyProject -> MP
    """
    # Extract capital letters
    caps = [c for c in repo_name if c.isupper()]
    if len(caps) >= 2:
        return caps[0] + caps[1]
    # Fall back to first two chars
    return repo_name[:2].upper()


def generate_plan_folder_name(branch: str, repo_root: Path) -> str:
    """Generate planning folder name: YYMMDD<Abbr>_<branch>.

    Args:
        branch: Branch name
        repo_root: Repository root path

    Returns:
        Folder name like "260103AE_feature-auth"
    """
    date_prefix = datetime.now().strftime("%y%m%d")
    repo_name = repo_root.name
    # Handle names like AgenticEngineering-agentic-cli
    if "-" in repo_name:
        repo_name = repo_name.split("-")[0]
    abbr = get_repo_abbreviation(repo_name)
    return f"{date_prefix}{abbr}_{branch}"


def create_planning_folder(plan_path: Path):
    """Create planning folder structure with placeholder files.

    Creates:
        - live/ subdirectory
        - completed/ subdirectory
        - 4 placeholder YAML files in live/
    """
    live_dir = plan_path / "live"
    completed_dir = plan_path / "completed"

    live_dir.mkdir(parents=True, exist_ok=True)
    completed_dir.mkdir(parents=True, exist_ok=True)

    # Create placeholder files
    plan_files = {
        "plan_live_teach.yml": f"""# Implementation Plan
# Created: {datetime.now().strftime("%Y-%m-%d")}

plan:
  name: "Implementation Plan"
  worktree: "{Path.cwd()}"
  branch: ""
  status: planning
  created: "{datetime.now().strftime("%Y-%m-%d")}"

  objective: |
    TODO: Describe the objective

  scope:
    includes: []
    excludes: []

  phases: []
""",
        "plan_live_test.yml": f"""# Test Plan
# Created: {datetime.now().strftime("%Y-%m-%d")}

plan:
  name: "Test Phases"
  worktree: "{Path.cwd()}"
  branch: ""
  status: pending

  phases: []

  test_strategy:
    - type: "unit"
      scope: "Individual functions"
      location: "tests/unit/"

    - type: "integration"
      scope: "Command execution"
      location: "tests/integration/"
""",
        "plan_live_audit_clean.yml": """# Audit and Cleanup Plan
# Created for cleanup phases

plan:
  name: "Audit and Cleanup"
  status: pending

  phases: []

  cleanup_targets: []

  documentation: []
""",
    }

    for filename, content in plan_files.items():
        file_path = live_dir / filename
        if not file_path.exists():
            file_path.write_text(content)

    # Create completed placeholder
    completed_file = completed_dir / "plan_completed.yml"
    if not completed_file.exists():
        completed_file.write_text("""# Completed Items
# Items moved here when completed during implementation

completed_items: []
""")


def cmd_create(args):
    """Create a new worktree with planning folder."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_info,
        print_json,
        print_success,
    )

    branch = args.branch
    base = args.base
    skip_plan = args.no_plan

    repo_root = get_repo_root()
    repo_name = repo_root.name

    # Generate worktree path: /home/code/<Repo>-<branch>
    worktree_path = repo_root.parent / f"{repo_name.split('-')[0]}-{branch}"

    # Check if worktree already exists
    if worktree_path.exists():
        print_error(f"Worktree path already exists: {worktree_path}")
        sys.exit(1)

    if not is_json_output():
        print_info(f"Creating worktree for branch '{branch}' at {worktree_path}")

    # Create the worktree
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
        print_error(f"Error creating worktree: {e}")
        sys.exit(1)

    # Create planning folder
    plan_folder_name = None
    if not skip_plan:
        plan_folder_name = generate_plan_folder_name(branch, repo_root)
        plan_path = worktree_path / "docs" / "plans" / "live" / plan_folder_name

        create_planning_folder(plan_path)
        if not is_json_output():
            console.print(f"  [green]Created planning folder[/green] at {plan_path}")

    if is_json_output():
        result = {
            "worktree": str(worktree_path),
            "branch": branch,
            "base": base,
        }
        if plan_folder_name:
            result["plan_folder"] = f"docs/plans/live/{plan_folder_name}"
        print_json(result)
    else:
        console.print()
        print_success(f"Worktree ready: {worktree_path}")
        if plan_folder_name:
            console.print(f"[dim]Planning folder:[/dim] docs/plans/live/{plan_folder_name}")


def cmd_list(args):
    """List all worktrees with their planning folders."""
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_table,
    )

    repo_root = get_repo_root()

    # Get worktree list
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
    except subprocess.CalledProcessError as e:
        print_error(f"Error listing worktrees: {e}")
        sys.exit(1)

    # Parse worktree output
    worktrees = []
    current_wt = {}
    for line in result.stdout.strip().split("\n"):
        if line.startswith("worktree "):
            if current_wt:
                worktrees.append(current_wt)
            current_wt = {"path": line.split(" ", 1)[1]}
        elif line.startswith("branch "):
            current_wt["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")
        elif line.strip() == "":
            continue
    if current_wt:
        worktrees.append(current_wt)

    # Build worktree data with plan folders
    worktree_data = []
    for wt in worktrees:
        wt_path = Path(wt.get("path", ""))
        branch = wt.get("branch", "(bare)")

        # Look for planning folder
        plan_dir = wt_path / "docs" / "plans" / "live"
        plan_folders = []
        if plan_dir.exists():
            plan_folders = [d.name for d in plan_dir.iterdir() if d.is_dir()]

        worktree_data.append({
            "path": str(wt_path),
            "branch": branch,
            "plan_folders": plan_folders,
        })

    if is_json_output():
        print_json({"worktrees": worktree_data})
    else:
        print_header("Git Worktrees")

        rows = []
        for wt in worktree_data:
            plan_str = ", ".join(wt["plan_folders"]) if wt["plan_folders"] else "[dim]-[/dim]"
            rows.append([
                f"[cyan]{wt['path']}[/cyan]",
                f"[green]{wt['branch']}[/green]",
                plan_str,
            ])

        print_table("", ["Path", "Branch", "Plan Folders"], rows)


def cmd_remove(args):
    """Remove a worktree."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_json,
        print_success,
        print_warning,
    )

    branch = args.branch
    force = args.force

    repo_root = get_repo_root()

    # Find the worktree path for this branch
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
    except subprocess.CalledProcessError as e:
        print_error(f"Error listing worktrees: {e}")
        sys.exit(1)

    # Find worktree for branch
    worktree_path = None
    lines = result.stdout.strip().split("\n")
    i = 0
    while i < len(lines):
        if lines[i].startswith("worktree "):
            path = lines[i].split(" ", 1)[1]
            # Check next lines for branch
            for j in range(i + 1, min(i + 5, len(lines))):
                if lines[j].startswith("branch "):
                    wt_branch = lines[j].split(" ", 1)[1].replace("refs/heads/", "")
                    if wt_branch == branch:
                        worktree_path = path
                        break
                elif lines[j].startswith("worktree "):
                    break
        i += 1

    if not worktree_path:
        print_error(f"No worktree found for branch '{branch}'")
        sys.exit(1)

    wt_path = Path(worktree_path)

    # Confirm removal
    if not force and not is_json_output():
        print_warning(f"About to remove worktree at {wt_path}")
        response = input("Remove worktree? [y/N] ")
        if response.lower() != "y":
            console.print("[dim]Aborted[/dim]")
            sys.exit(0)

    # Remove worktree
    try:
        subprocess.run(
            ["git", "worktree", "remove", str(wt_path)],
            check=True,
            cwd=repo_root,
            capture_output=is_json_output(),
        )
        if is_json_output():
            print_json({"removed": str(wt_path), "branch": branch})
        else:
            print_success(f"Removed worktree: {wt_path}")
    except subprocess.CalledProcessError as e:
        print_error(f"Error removing worktree: {e}")
        if not force and not is_json_output():
            console.print("[dim]Try with --force to force removal[/dim]")
        sys.exit(1)


def cmd_status(args):
    """Show detailed status of current worktree."""
    from agenticcli.console import (
        console,
        format_status,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )

    cwd = Path.cwd()

    # Get git status info
    try:
        # Get current branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        current_branch = branch_result.stdout.strip()

        # Get git status
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        changes = status_result.stdout.strip().split("\n") if status_result.stdout.strip() else []

        # Get last commit
        log_result = subprocess.run(
            ["git", "log", "-1", "--format=%h %s"],
            capture_output=True,
            text=True,
            check=True,
        )
        last_commit = log_result.stdout.strip().replace("\n", " ")

        # Check if this is a worktree
        worktree_result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_common = worktree_result.stdout.strip()
        is_worktree = ".git/worktrees" in git_common

    except subprocess.CalledProcessError:
        print_error("Not in a git repository")
        sys.exit(1)

    # Find plan folders
    plans_dir = cwd / "docs" / "plans" / "live"
    plan_folders = []
    plan_stats = []

    if plans_dir.exists():
        for plan_dir in sorted(plans_dir.iterdir()):
            if plan_dir.is_dir():
                plan_folders.append(plan_dir.name)
                # Count tasks in this plan
                live_dir = plan_dir / "live"
                if live_dir.exists():
                    pending = 0
                    in_progress = 0
                    completed = 0
                    for yml_file in live_dir.glob("*.yml"):
                        try:
                            import yaml
                            content = yaml.safe_load(yml_file.read_text())
                            if content:
                                plan_data = content.get("plan", content.get("feature", {}))
                                for item in plan_data.get("phases", []) + plan_data.get("implementation_steps", []):
                                    status = item.get("status", "pending")
                                    if status == "pending":
                                        pending += 1
                                    elif status == "in_progress":
                                        in_progress += 1
                                    elif status == "completed":
                                        completed += 1
                        except Exception:
                            pass
                    plan_stats.append({
                        "name": plan_dir.name,
                        "pending": pending,
                        "in_progress": in_progress,
                        "completed": completed,
                    })

    # Count changes by type
    staged = len([c for c in changes if c and c[0] in "MADRC"])
    unstaged = len([c for c in changes if c and len(c) > 1 and c[1] in "MADRC"])
    untracked = len([c for c in changes if c and c.startswith("??")])

    status_data = {
        "path": str(cwd),
        "branch": current_branch,
        "is_worktree": is_worktree,
        "last_commit": last_commit,
        "changes": {
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "total": len(changes),
        },
        "plans": plan_stats,
    }

    if is_json_output():
        print_json(status_data)
        return

    print_header("Worktree Status")

    # Basic info
    console.print(f"\n[bold]Path:[/bold] [cyan]{cwd}[/cyan]")
    console.print(f"[bold]Branch:[/bold] [green]{current_branch}[/green]")
    console.print(f"[bold]Type:[/bold] {'[magenta]worktree[/magenta]' if is_worktree else '[dim]main repo[/dim]'}")
    console.print(f"[bold]Last Commit:[/bold] [dim]{last_commit}[/dim]")

    # Changes
    console.print("\n[bold magenta]Git Changes:[/bold magenta]")
    if changes:
        console.print(f"  [green]Staged:[/green] {staged}")
        console.print(f"  [yellow]Unstaged:[/yellow] {unstaged}")
        console.print(f"  [dim]Untracked:[/dim] {untracked}")
    else:
        console.print("  [dim]Working tree clean[/dim]")

    # Plans
    console.print("\n[bold magenta]Active Plans:[/bold magenta]")
    if plan_stats:
        for plan in plan_stats:
            total = plan["pending"] + plan["in_progress"] + plan["completed"]
            pct = (plan["completed"] / total * 100) if total > 0 else 0
            status_str = format_status("completed") if pct == 100 else format_status("in_progress") if plan["in_progress"] > 0 else format_status("pending")
            console.print(f"  [cyan]{plan['name']}[/cyan]: {status_str} ({pct:.0f}% complete)")
    else:
        console.print("  [dim]No active plans[/dim]")

    console.print()
