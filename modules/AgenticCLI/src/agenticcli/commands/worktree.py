"""Worktree management commands.

Handles git worktree operations with planning folder integration.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml


# Template header for stub files - clearly marks them as requiring action
STUB_TEMPLATE_HEADER = """# ============================================================================
# TEMPLATE FILE - ACTION REQUIRED
# ============================================================================
# This is a scaffold template created by `agentic plan init`.
#
# OPTIONS:
#   1. POPULATE: Replace TODO sections with actual plan content
#   2. DELETE: Remove this file if not needed for your plan
#
# A file with _template_status: stub will trigger validation warnings.
# Change to _template_status: active once populated.
# ============================================================================
"""


def handle(args, ctx=None):
    """Route worktree subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.worktree_command == "create":
        cmd_create(args)
    elif args.worktree_command == "list":
        cmd_list(args)
    elif args.worktree_command == "remove":
        cmd_remove(args)
    elif args.worktree_command == "status":
        cmd_status(args)
    elif args.worktree_command == "validate":
        cmd_validate(args)
    elif args.worktree_command == "sync":
        cmd_sync(args)
    else:
        print("Usage: agentic worktree <create|list|remove|status|sync|validate>", file=sys.stderr)
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


def load_worktree_registry(repo_root: Path) -> list[dict]:
    """Load the worktree registry from docs/worktrees.yml.

    Args:
        repo_root: Repository root path (or any worktree path).

    Returns:
        List of worktree entries, each with branch, abbreviation, description, path.
        Returns empty list if registry doesn't exist or can't be parsed.
    """
    registry_path = repo_root / "docs" / "worktrees.yml"
    if not registry_path.exists():
        # Try finding main worktree's registry
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                capture_output=True, text=True, check=True, cwd=repo_root,
            )
            for line in result.stdout.strip().split("\n"):
                if line.startswith("worktree "):
                    candidate = Path(line.split(" ", 1)[1]) / "docs" / "worktrees.yml"
                    if candidate.exists():
                        registry_path = candidate
                        break
        except subprocess.CalledProcessError:
            pass

    if not registry_path.exists():
        return []

    try:
        data = yaml.safe_load(registry_path.read_text())
        return data.get("worktrees", []) if data else []
    except (yaml.YAMLError, OSError):
        return []


def save_worktree_registry(repo_root: Path, entries: list[dict]) -> bool:
    """Save entries to the worktree registry at docs/worktrees.yml.

    Args:
        repo_root: Repository root path.
        entries: List of worktree entry dicts.

    Returns:
        True if saved successfully, False otherwise.
    """
    registry_path = repo_root / "docs" / "worktrees.yml"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        content = {
            "worktrees": entries,
        }
        header = (
            "# Worktree Registry\n"
            "# Maps branch names to abbreviations and descriptions for plan folder naming.\n"
            "# Used by `agentic worktree create` and `naming.generate_plan_folder_name()`.\n\n"
        )
        registry_path.write_text(header + yaml.dump(content, default_flow_style=False, sort_keys=False))
        return True
    except OSError:
        return False


def lookup_abbreviation(registry: list[dict], branch: str) -> str | None:
    """Look up abbreviation for a branch in the registry.

    Args:
        registry: List of worktree entries from load_worktree_registry().
        branch: Branch name to look up.

    Returns:
        2-letter abbreviation string, or None if not found.
    """
    for entry in registry:
        if entry.get("branch") == branch:
            return entry.get("abbreviation")
    return None


def get_repo_abbreviation(repo_name: str) -> str:
    """Generate 2-letter abbreviation for repository name.

    Fallback when branch is not found in worktree registry.

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


def find_workspace_file(repo_root: Path) -> Path | None:
    """Find the .code-workspace file in the repository root.

    Args:
        repo_root: Repository root path

    Returns:
        Path to workspace file or None if not found
    """
    workspace_files = list(repo_root.glob("*.code-workspace"))
    return workspace_files[0] if workspace_files else None


def update_workspace_add(workspace_file: Path, worktree_path: Path, branch: str, repo_name: str) -> bool:
    """Add a worktree entry to the workspace file.

    Args:
        workspace_file: Path to the .code-workspace file
        worktree_path: Path to the new worktree
        branch: Branch name
        repo_name: Repository name for display

    Returns:
        True if updated successfully, False otherwise
    """
    try:
        from agenticguidance.services.state import FileLock

        # Use FileLock to prevent concurrent modifications
        with FileLock(workspace_file, timeout=5.0):
            with open(workspace_file) as f:
                workspace = json.load(f)

            # Calculate relative path from workspace file to worktree
            workspace_dir = workspace_file.parent
            try:
                relative_path = str(worktree_path.relative_to(workspace_dir))
            except ValueError:
                # Not relative, use ../<path> format
                relative_path = f"../{worktree_path.name}"

            # Add or update folders array
            folder_entry = {
                "name": f"{repo_name} ({branch})",
                "path": relative_path
            }
            if "folders" not in workspace:
                workspace["folders"] = []

            # Check for existing entry with same path
            existing_idx = next((i for i, f in enumerate(workspace["folders"]) if f.get("path") == relative_path), -1)
            if existing_idx >= 0:
                workspace["folders"][existing_idx] = folder_entry
            else:
                workspace["folders"].append(folder_entry)

            # Add to git.scanRepositories
            if "settings" not in workspace:
                workspace["settings"] = {}
            if "git.scanRepositories" not in workspace["settings"]:
                workspace["settings"]["git.scanRepositories"] = ["."]

            if relative_path not in workspace["settings"]["git.scanRepositories"]:
                workspace["settings"]["git.scanRepositories"].append(relative_path)

            # Write back
            with open(workspace_file, "w") as f:
                json.dump(workspace, f, indent="\t")

        return True
    except TimeoutError:
        # Lock timeout - return False instead of crashing
        return False
    except Exception:
        return False


def update_workspace_remove(workspace_file: Path, worktree_path: Path) -> bool:
    """Remove a worktree entry from the workspace file.

    Args:
        workspace_file: Path to the .code-workspace file
        worktree_path: Path to the worktree being removed

    Returns:
        True if updated successfully, False otherwise
    """
    try:
        from agenticguidance.services.state import FileLock

        # Use FileLock to prevent concurrent modifications
        with FileLock(workspace_file, timeout=5.0):
            with open(workspace_file) as f:
                workspace = json.load(f)

            # Calculate relative path
            workspace_dir = workspace_file.parent
            try:
                relative_path = str(worktree_path.relative_to(workspace_dir))
            except ValueError:
                relative_path = f"../{worktree_path.name}"

            # Remove from folders array
            if "folders" in workspace:
                workspace["folders"] = [
                    f for f in workspace["folders"]
                    if f.get("path") != relative_path
                ]

            # Remove from git.scanRepositories
            if "settings" in workspace and "git.scanRepositories" in workspace["settings"]:
                workspace["settings"]["git.scanRepositories"] = [
                    r for r in workspace["settings"]["git.scanRepositories"]
                    if r != relative_path
                ]

            # Write back
            with open(workspace_file, "w") as f:
                json.dump(workspace, f, indent="\t")

        return True
    except TimeoutError:
        # Lock timeout - return False instead of crashing
        return False
    except Exception:
        return False


def create_planning_folder(plan_path: Path):
    """Create planning folder structure with placeholder files.

    Creates (flattened structure):
        - plan_*.yml files directly in plan_path
        - plan_completed.yml for completed items
    """
    plan_path.mkdir(parents=True, exist_ok=True)

    # Create placeholder files with clear template markers
    created_date = datetime.now().strftime("%Y-%m-%d")
    current_worktree = str(Path.cwd())

    # Flattened naming: plan_*.yml (no live_ prefix)
    plan_files = {
        "plan_teach.yml": f"""{STUB_TEMPLATE_HEADER}
_template_status: stub  # Change to 'active' when populated

# Teaching/Implementation Plan
# Created: {created_date}
# Purpose: Define implementation phases for feature development or guidance updates

plan:
  name: "TODO: Plan Name (e.g., 'Add User Authentication', 'Update Context Guidelines')"
  worktree: "{current_worktree}"
  branch: ""  # TODO: Set branch name
  status: planning
  created: "{created_date}"

  objective: |
    TODO: Describe what this plan aims to accomplish.
    Example: "Implement user authentication with JWT tokens and session management."

  scope:
    includes:
      # TODO: List files/modules in scope
      # - "src/auth/"
      # - "tests/auth/"
    excludes:
      # TODO: List files/modules explicitly out of scope
      # - "src/legacy/"

  # Optional: Explicit file scoping for orchestration visibility
  # Schema: modules/AgenticGuidance/assets/specifications/plan-schema.yml#impacted_files_schema
  impacted_files:
    # TODO: List files that will be modified/created
    # - path: "src/feature/service.py"
    #   change_type: create
    #   change_category: implementation
    #   reason: "New service module"
    []

  # Optional: Higher-level artifact impacts
  # Schema: modules/AgenticGuidance/assets/specifications/plan-schema.yml#impacted_artifacts_schema
  impacted_artifacts:
    # TODO: List semantic impacts (APIs, CLI commands, services)
    # - artifact_type: cli_command
    #   artifact_identifier: "agentic feature run"
    #   impact_type: new
    #   description: "New CLI command for the feature"
    []

  phases:
    # TODO: Define implementation phases
    # Example:
    # - name: "Phase 1 - Database Schema"
    #   id: "phase_01"
    #   status: pending
    #   tasks:
    #     - id: "phase_01_001"
    #       name: "Create user table migration"
    #       status: pending
    #       target_files:
    #         - "migrations/001_users.sql"
    []
""",
        "plan_test.yml": f"""{STUB_TEMPLATE_HEADER}
_template_status: stub  # Change to 'active' when populated

# Test Plan
# Created: {created_date}
# Purpose: Define testing phases and validation strategy

plan:
  name: "TODO: Test Plan Name (e.g., 'Auth Module Tests', 'API Integration Tests')"
  worktree: "{current_worktree}"
  branch: ""  # TODO: Set branch name
  status: pending

  objective: |
    TODO: Describe testing goals.
    Example: "Validate authentication flow with unit and integration tests."

  phases:
    # TODO: Define test phases
    # Example:
    # - name: "Unit Tests"
    #   id: "test_unit"
    #   status: pending
    #   tasks:
    #     - id: "test_unit_001"
    #       name: "Test login validation"
    #       status: pending
    []

  test_strategy:
    - type: "unit"
      scope: "TODO: Define unit test scope"
      location: "tests/unit/"
      # TODO: Add specific test targets

    - type: "integration"
      scope: "TODO: Define integration test scope"
      location: "tests/integration/"
      # TODO: Add specific test targets
""",
        "plan_audit_clean.yml": f"""{STUB_TEMPLATE_HEADER}
_template_status: stub  # Change to 'active' when populated

# Audit and Cleanup Plan
# Created: {created_date}
# Purpose: Define audit checks and cleanup tasks for post-implementation

plan:
  name: "TODO: Audit Plan Name (e.g., 'Post-Auth Cleanup', 'Code Quality Audit')"
  status: pending

  objective: |
    TODO: Describe audit/cleanup goals.
    Example: "Remove deprecated auth code and verify no unused imports."

  phases:
    # TODO: Define audit/cleanup phases
    # Example:
    # - name: "Code Audit"
    #   id: "audit_01"
    #   status: pending
    #   tasks:
    #     - id: "audit_01_001"
    #       name: "Check for unused imports"
    #       status: pending
    []

  cleanup_targets:
    # TODO: List files/code to be cleaned up
    # - "src/old_auth.py"
    # - "tests/deprecated/"
    []

  documentation:
    # TODO: List documentation to update
    # - "README.md"
    # - "docs/auth.md"
    []
""",
    }

    # Flattened structure: files directly in plan_path
    for filename, content in plan_files.items():
        file_path = plan_path / filename
        if not file_path.exists():
            file_path.write_text(content)

    # Create completed placeholder (flattened: directly in plan_path)
    completed_file = plan_path / "plan_completed.yml"
    if not completed_file.exists():
        completed_file.write_text("""# Completed Items
# Items moved here when completed during implementation

completed_items: []
""")


def get_actual_worktrees(repo_root: Path) -> list[dict]:
    """Parse `git worktree list --porcelain` and return structured data.

    Args:
        repo_root: Repository root path to run git from.

    Returns:
        List of dicts with 'path' and 'branch' keys.
        Returns empty list on error.
    """
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )
    except subprocess.CalledProcessError:
        return []

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

    return worktrees


def find_idle_worktrees(repo_root: Path) -> list[dict]:
    """Find worktrees that have no active agent sessions.

    Checks all non-main worktrees against running sessions to determine
    which ones are idle and available for reuse.

    Args:
        repo_root: Repository root path.

    Returns:
        List of worktree dicts (with 'path' and 'branch') that have
        no active sessions. Excludes main/master worktrees.
    """
    from agenticcli.commands.session import _is_process_running, _list_all_sessions

    worktrees = get_actual_worktrees(repo_root)

    # Get active session working directories
    active_dirs = set()
    for session in _list_all_sessions():
        if session.get("status") in ("running", "starting"):
            pid = session.get("pid")
            if pid and _is_process_running(pid):
                wd = session.get("working_dir", "")
                if wd:
                    active_dirs.add(str(Path(wd).resolve()))

    idle = []
    for wt in worktrees:
        branch = wt.get("branch", "")
        if branch in ("main", "master"):
            continue
        wt_path = str(Path(wt["path"]).resolve())
        if wt_path not in active_dirs:
            idle.append(wt)

    return idle


def get_live_plan_folders(main_wt_path: Path) -> list[str]:
    """Scan docs/plans/live/ in the given worktree and return plan folder names.

    Args:
        main_wt_path: Path to the main worktree root.

    Returns:
        Sorted list of directory names under docs/plans/live/.
        Returns empty list if path doesn't exist.
    """
    plan_dir = main_wt_path / "docs" / "plans" / "live"
    if not plan_dir.exists():
        return []
    return sorted(d.name for d in plan_dir.iterdir() if d.is_dir())


def worktree_has_live_plans(worktree_path: Path, main_wt_path: Path, registry: list[dict]) -> bool:
    """Check if a worktree has any remaining live plans.

    Looks for plan folders in the main worktree's docs/plans/live/ that
    match the given worktree's branch.

    Args:
        worktree_path: Path to the worktree to check.
        main_wt_path: Path to the main worktree.
        registry: Worktree registry entries.

    Returns:
        True if the worktree has live plans, False otherwise.
    """
    # Get the branch for this worktree
    worktrees = get_actual_worktrees(main_wt_path)
    branch = None
    for wt in worktrees:
        if str(Path(wt["path"]).resolve()) == str(worktree_path.resolve()):
            branch = wt.get("branch")
            break

    if not branch or branch in ("main", "master"):
        return True  # Never report main as having no plans

    plan_folders = get_live_plan_folders(main_wt_path)
    matched = _match_plans_to_branch(plan_folders, branch, registry)
    return len(matched) > 0


def cleanup_worktree_if_idle(
    worktree_branch: str,
    repo_root: Path,
    main_wt_path: Path,
) -> dict:
    """Remove a worktree if it has no live plans and no active sessions.

    Called after plan archival to clean up worktrees that are no longer needed.

    Args:
        worktree_branch: Branch name of the worktree to potentially clean up.
        repo_root: Repository root path.
        main_wt_path: Path to the main worktree.

    Returns:
        Dict with 'cleaned' (bool), 'reason' (str), and optionally 'path' (str).
    """
    if worktree_branch in ("main", "master"):
        return {"cleaned": False, "reason": "main/master worktree is protected"}

    # Find the worktree path
    worktrees = get_actual_worktrees(repo_root)
    wt_path = None
    for wt in worktrees:
        if wt.get("branch") == worktree_branch:
            wt_path = wt["path"]
            break

    if not wt_path:
        return {"cleaned": False, "reason": f"no worktree found for branch '{worktree_branch}'"}

    # Check for remaining live plans
    registry = load_worktree_registry(repo_root)
    if worktree_has_live_plans(Path(wt_path), main_wt_path, registry):
        return {"cleaned": False, "reason": "worktree still has live plans"}

    # Check for active sessions
    from agenticcli.commands.session import _is_process_running, _list_all_sessions

    resolved_wt = str(Path(wt_path).resolve())
    for session in _list_all_sessions():
        if session.get("status") in ("running", "starting"):
            pid = session.get("pid")
            if pid and _is_process_running(pid):
                wd = session.get("working_dir", "")
                if wd and str(Path(wd).resolve()) == resolved_wt:
                    return {"cleaned": False, "reason": "worktree has active session"}

    # Safe to remove: no plans, no sessions
    try:
        subprocess.run(
            ["git", "worktree", "remove", str(wt_path)],
            check=True,
            cwd=repo_root,
            capture_output=True,
        )

        # Update workspace file
        workspace_file = find_workspace_file(repo_root)
        if workspace_file:
            update_workspace_remove(workspace_file, Path(wt_path))

        return {"cleaned": True, "path": wt_path, "reason": "no live plans, no active sessions"}
    except subprocess.CalledProcessError as e:
        return {"cleaned": False, "reason": f"git worktree remove failed: {e}"}


def cmd_create(args):
    """Create a new worktree (plan creation deprecated - use 'agentic plan init' instead)."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_info,
        print_json,
        print_success,
        print_warning,
    )
    from agenticcli.utils.naming import generate_plan_folder_name

    branch = args.branch
    base = args.base
    skip_plan = True  # DEPRECATED: Plan creation moved to 'agentic plan init'
    abbreviation = getattr(args, "abbreviation", None)
    description = getattr(args, "description", None)

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

    # Save to worktree registry if abbreviation or description provided
    registry_updated = False
    if abbreviation or description:
        registry = load_worktree_registry(repo_root)
        # Check if entry already exists for this branch
        existing = [e for e in registry if e.get("branch") == branch]
        if existing:
            entry = existing[0]
            if abbreviation:
                entry["abbreviation"] = abbreviation.upper()[:2]
            if description:
                entry["description"] = description
            entry["path"] = str(worktree_path)
        else:
            new_entry = {
                "branch": branch,
                "abbreviation": (abbreviation.upper()[:2]) if abbreviation else get_repo_abbreviation(repo_name.split("-")[0] if "-" in repo_name else repo_name),
                "description": description or branch,
                "path": str(worktree_path),
            }
            registry.append(new_entry)
        registry_updated = save_worktree_registry(repo_root, registry)
        if registry_updated and not is_json_output():
            console.print(f"  [green]Updated worktree registry[/green]")

    # Create planning folder
    plan_folder_name = None
    if not skip_plan:
        plan_folder_name = generate_plan_folder_name(branch, repo_root, abbreviation=abbreviation)
        plan_path = worktree_path / "docs" / "plans" / "live" / plan_folder_name

        create_planning_folder(plan_path)
        if not is_json_output():
            console.print(f"  [green]Created planning folder[/green] at {plan_path}")

    # Update workspace file
    workspace_updated = False
    workspace_file = find_workspace_file(repo_root)
    if workspace_file:
        workspace_updated = update_workspace_add(workspace_file, worktree_path, branch, repo_name.split("-")[0])
        if workspace_updated and not is_json_output():
            console.print(f"  [green]Updated workspace file[/green] {workspace_file.name}")
        elif not workspace_updated and not is_json_output():
            print_warning(f"Could not update workspace file {workspace_file.name}")

    if is_json_output():
        result = {
            "worktree": str(worktree_path),
            "branch": branch,
            "base": base,
            "workspace_updated": workspace_updated,
            "registry_updated": registry_updated,
        }
        if abbreviation:
            result["abbreviation"] = abbreviation.upper()[:2]
        if plan_folder_name:
            result["plan_folder"] = f"docs/plans/live/{plan_folder_name}"
        print_json(result)
    else:
        console.print()
        print_success(f"Worktree ready: {worktree_path}")
        if plan_folder_name:
            console.print(f"[dim]Planning folder:[/dim] docs/plans/live/{plan_folder_name}")
        console.print()
        console.print("[yellow]To create a plan for this worktree, use:[/yellow]")
        console.print(f"  agentic plan init {branch} --description <description>")


def _find_main_worktree_path(worktrees: list[dict]) -> str | None:
    """Find the main worktree path from parsed worktree list.

    Args:
        worktrees: List of parsed worktree dicts with 'path' and 'branch' keys.

    Returns:
        Path string of the main/master worktree, or None.
    """
    for wt in worktrees:
        if wt.get("branch") in ("main", "master"):
            return wt.get("path")
    return None


def _match_plans_to_branch(plan_folders: list[str], branch: str, registry: list[dict]) -> list[str]:
    """Match plan folder names to a branch using abbreviation or branch name.

    Args:
        plan_folders: List of plan folder names from main's docs/plans/live/.
        branch: Branch name to match against.
        registry: Worktree registry entries.

    Returns:
        List of matching plan folder names.
    """
    matches = []
    # Get abbreviation for this branch from registry
    abbr = lookup_abbreviation(registry, branch)

    for folder in plan_folders:
        # Match by abbreviation in the folder name (positions 6-8)
        if abbr and len(folder) >= 8 and folder[6:8] == abbr:
            matches.append(folder)
        # Match by branch name appearing after the underscore
        elif "_" in folder:
            desc_part = folder.split("_", 1)[1] if "_" in folder else ""
            if desc_part == branch or desc_part.startswith(branch + "_"):
                matches.append(folder)

    return matches


def cmd_list(args):
    """List all worktrees with their planning folders.

    Main-First Planning aware: scans main worktree's docs/plans/live/
    and matches plans to feature worktrees via registry abbreviation.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_table,
    )

    repo_root = get_repo_root()

    # Get worktree list
    worktrees = get_actual_worktrees(repo_root)
    if not worktrees:
        print_error("No worktrees found or error listing worktrees")
        sys.exit(1)

    # Load registry and find main worktree for Main-First Planning
    registry = load_worktree_registry(repo_root)
    main_wt_path = _find_main_worktree_path(worktrees)

    # Scan main worktree's plans
    main_plan_folders = get_live_plan_folders(Path(main_wt_path)) if main_wt_path else []

    # Build worktree data with plan folders
    worktree_data = []
    for wt in worktrees:
        wt_path = Path(wt.get("path", ""))
        branch = wt.get("branch", "(bare)")

        # Look for local planning folders (legacy behavior)
        local_plan_dir = wt_path / "docs" / "plans" / "live"
        local_plan_folders = []
        if local_plan_dir.exists():
            local_plan_folders = [d.name for d in local_plan_dir.iterdir() if d.is_dir()]

        # Match plans from main worktree (Main-First Planning)
        main_matched_plans = []
        if main_wt_path and str(wt_path) != main_wt_path:
            main_matched_plans = _match_plans_to_branch(main_plan_folders, branch, registry)

        # Get registry metadata
        reg_entry = next((e for e in registry if e.get("branch") == branch), None)
        abbreviation = reg_entry.get("abbreviation", "") if reg_entry else ""
        description = reg_entry.get("description", "") if reg_entry else ""

        worktree_data.append(
            {
                "path": str(wt_path),
                "branch": branch,
                "abbreviation": abbreviation,
                "description": description,
                "plan_folders": local_plan_folders,
                "main_plans": main_matched_plans,
            }
        )

    if is_json_output():
        print_json({"worktrees": worktree_data})
    else:
        print_header("Git Worktrees")

        rows = []
        for wt in worktree_data:
            # Combine local and main-first plans for display
            all_plans = []
            if wt["plan_folders"]:
                all_plans.extend(wt["plan_folders"])
            if wt["main_plans"]:
                all_plans.extend([f"{p} [dim](main)[/dim]" for p in wt["main_plans"]])

            plan_str = ", ".join(all_plans) if all_plans else "[dim]-[/dim]"
            abbr_str = f"[yellow]{wt['abbreviation']}[/yellow]" if wt["abbreviation"] else "[dim]-[/dim]"

            rows.append(
                [
                    f"[cyan]{wt['path']}[/cyan]",
                    f"[green]{wt['branch']}[/green]",
                    abbr_str,
                    plan_str,
                ]
            )

        print_table("", ["Path", "Branch", "Abbr", "Plans"], rows)


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
    all_worktrees = get_actual_worktrees(repo_root)
    worktree_path = None
    for wt in all_worktrees:
        if wt.get("branch") == branch:
            worktree_path = wt["path"]
            break

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

        # Update workspace file
        workspace_updated = False
        workspace_file = find_workspace_file(repo_root)
        if workspace_file:
            workspace_updated = update_workspace_remove(workspace_file, wt_path)
            if workspace_updated and not is_json_output():
                console.print(f"  [green]Updated workspace file[/green] {workspace_file.name}")

        if is_json_output():
            print_json({"removed": str(wt_path), "branch": branch, "workspace_updated": workspace_updated})
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
                # Count tasks in this plan (flattened structure: plan_*.yml directly in plan_dir)
                plan_files = list(plan_dir.glob("plan_*.yml"))
                if plan_files:
                    pending = 0
                    in_progress = 0
                    completed = 0
                    for yml_file in plan_files:
                        try:
                            import yaml

                            content = yaml.safe_load(yml_file.read_text())
                            if content:
                                plan_data = content.get("plan", content.get("feature", {}))
                                for item in plan_data.get("phases", []) + plan_data.get(
                                    "implementation_steps", []
                                ):
                                    status = item.get("status", "pending")
                                    if status == "pending":
                                        pending += 1
                                    elif status == "in_progress":
                                        in_progress += 1
                                    elif status == "completed":
                                        completed += 1
                        except Exception:
                            pass
                    plan_stats.append(
                        {
                            "name": plan_dir.name,
                            "pending": pending,
                            "in_progress": in_progress,
                            "completed": completed,
                        }
                    )

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
    console.print(
        f"[bold]Type:[/bold] {'[magenta]worktree[/magenta]' if is_worktree else '[dim]main repo[/dim]'}"
    )
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
            status_str = (
                format_status("completed")
                if pct == 100
                else format_status("in_progress")
                if plan["in_progress"] > 0
                else format_status("pending")
            )
            console.print(f"  [cyan]{plan['name']}[/cyan]: {status_str} ({pct:.0f}% complete)")
    else:
        console.print("  [dim]No active plans[/dim]")

    console.print()


def cmd_validate(args):
    """Validate worktree-plan synchronization.

    Cross-references three data sources:
    1. Actual git worktrees (git worktree list)
    2. Worktree registry (docs/worktrees.yml)
    3. Live plan folders (docs/plans/live/)

    Reports orphaned plans, stale worktrees, and registry drift.
    Exits with code 1 if any issues found.
    """
    repo_root = get_repo_root()

    # Gather data from all three sources
    actual_worktrees = get_actual_worktrees(repo_root)
    registry = load_worktree_registry(repo_root)
    main_wt_path = _find_main_worktree_path(actual_worktrees)
    plan_folders = get_live_plan_folders(Path(main_wt_path)) if main_wt_path else []

    # Collect actual branch names (excluding bare worktrees)
    actual_branches = {wt["branch"] for wt in actual_worktrees if "branch" in wt}

    # 1. Orphaned plans: plan folders with no matching worktree
    orphaned_plans = []
    for folder in plan_folders:
        matched = False
        for wt in actual_worktrees:
            branch = wt.get("branch", "")
            if not branch or branch in ("main", "master"):
                continue
            matches = _match_plans_to_branch([folder], branch, registry)
            if matches:
                matched = True
                break
        if not matched:
            orphaned_plans.append(folder)

    # 2. Stale worktrees: non-main worktrees with no matching plan
    stale_worktrees = []
    for wt in actual_worktrees:
        branch = wt.get("branch", "")
        if not branch or branch in ("main", "master"):
            continue
        matches = _match_plans_to_branch(plan_folders, branch, registry)
        if not matches:
            stale_worktrees.append({"path": wt["path"], "branch": branch})

    # 3. Registry drift
    # 3a. Registry entries with no matching actual worktree
    missing_worktrees = []
    for entry in registry:
        reg_branch = entry.get("branch", "")
        if reg_branch not in actual_branches:
            missing_worktrees.append({
                "branch": reg_branch,
                "abbreviation": entry.get("abbreviation", ""),
            })

    # 3b. Actual non-main worktrees not in registry
    registry_branches = {e.get("branch", "") for e in registry}
    unregistered = []
    for wt in actual_worktrees:
        branch = wt.get("branch", "")
        if not branch or branch in ("main", "master"):
            continue
        if branch not in registry_branches:
            unregistered.append({"path": wt["path"], "branch": branch})

    # Build result
    validation_result = {
        "orphaned_plans": orphaned_plans,
        "stale_worktrees": stale_worktrees,
        "registry_drift": {
            "missing_worktrees": missing_worktrees,
            "unregistered": unregistered,
        },
        "valid": (
            not orphaned_plans
            and not stale_worktrees
            and not missing_worktrees
            and not unregistered
        ),
    }

    from agenticcli.console import is_json_output, print_json

    if is_json_output():
        print_json(validation_result)
    else:
        _print_validation_result(validation_result)

    sys.exit(0 if validation_result["valid"] else 1)


def _print_validation_result(result: dict):
    """Print human-readable validation output."""
    from agenticcli.console import console

    console.print("\n[bold magenta]Worktree Validation[/bold magenta]\n")

    # Orphaned plans
    if result["orphaned_plans"]:
        console.print("[yellow]Orphaned Plans[/yellow] (no matching worktree):")
        for plan in result["orphaned_plans"]:
            console.print(f"  [yellow]![/yellow] {plan}")
    else:
        console.print("[green]Orphaned Plans:[/green] none")

    # Stale worktrees
    if result["stale_worktrees"]:
        console.print("[yellow]Stale Worktrees[/yellow] (no matching plan):")
        for wt in result["stale_worktrees"]:
            console.print(f"  [yellow]![/yellow] {wt['branch']} ({wt['path']})")
    else:
        console.print("[green]Stale Worktrees:[/green] none")

    # Registry drift
    drift = result["registry_drift"]
    if drift["missing_worktrees"]:
        console.print("[yellow]Registry Drift[/yellow] (entries without actual worktrees):")
        for entry in drift["missing_worktrees"]:
            console.print(f"  [yellow]![/yellow] {entry['branch']} (abbr: {entry['abbreviation']})")
    if drift["unregistered"]:
        console.print("[yellow]Unregistered Worktrees[/yellow] (not in registry):")
        for wt in drift["unregistered"]:
            console.print(f"  [yellow]![/yellow] {wt['branch']} ({wt['path']})")
    if not drift["missing_worktrees"] and not drift["unregistered"]:
        console.print("[green]Registry Drift:[/green] none")

    # Summary
    console.print()
    if result["valid"]:
        console.print("[bold green]All checks passed[/bold green]")
    else:
        issue_count = (
            len(result["orphaned_plans"])
            + len(result["stale_worktrees"])
            + len(drift["missing_worktrees"])
            + len(drift["unregistered"])
        )
        console.print(f"[bold red]{issue_count} issue(s) found[/bold red]")
    console.print()


def cmd_sync(args):
    """Synchronize workspace file with actual worktrees.

    Removes stale entries for worktrees that no longer exist on disk.
    Adds missing entries for worktrees not yet in the workspace file.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_info,
        print_json,
        print_success,
    )

    repo_root = get_repo_root()
    workspace_file = find_workspace_file(repo_root)

    if not workspace_file:
        print_error("No .code-workspace file found in repository root")
        sys.exit(1)

    # Get actual worktree paths from git
    actual_worktrees = get_actual_worktrees(repo_root)
    actual_paths = {Path(wt["path"]).resolve() for wt in actual_worktrees}

    # Read workspace JSON
    try:
        with open(workspace_file) as f:
            workspace = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print_error(f"Failed to read workspace file: {e}")
        sys.exit(1)

    workspace_dir = workspace_file.parent
    folders = workspace.get("folders", [])

    # Identify stale entries: folder paths that don't exist on disk
    # OR don't match any actual git worktree
    stale_paths = []
    for entry in folders:
        entry_path = (workspace_dir / entry.get("path", "")).resolve()
        if not entry_path.exists() or (
            entry_path.resolve() not in actual_paths
            and entry_path.resolve() != repo_root.resolve()
        ):
            stale_paths.append(entry_path)

    # Remove stale entries
    removed = 0
    for stale in stale_paths:
        if update_workspace_remove(workspace_file, stale):
            removed += 1
            if not is_json_output():
                print_info(f"Removed stale entry: {stale}")

    # Re-read workspace after removals to get current state
    try:
        with open(workspace_file) as f:
            workspace = json.load(f)
    except (json.JSONDecodeError, OSError):
        workspace = {"folders": []}

    # Identify workspace folder paths (resolved)
    current_folder_paths = set()
    for entry in workspace.get("folders", []):
        current_folder_paths.add((workspace_dir / entry.get("path", "")).resolve())

    # Add missing worktree entries
    added = 0
    repo_name = repo_root.name.split("-")[0] if "-" in repo_root.name else repo_root.name
    for wt in actual_worktrees:
        wt_path = Path(wt["path"]).resolve()
        if wt_path not in current_folder_paths:
            branch = wt.get("branch", wt_path.name)
            if update_workspace_add(workspace_file, Path(wt["path"]), branch, repo_name):
                added += 1
                if not is_json_output():
                    print_info(f"Added missing entry: {wt['path']} ({branch})")

    # Clean up worktree registry (docs/worktrees.yml)
    registry_cleaned = 0
    registry = load_worktree_registry(repo_root)
    if registry:
        # Keep only entries for worktrees that still exist
        cleaned_registry = []
        for entry in registry:
            entry_path = entry.get("path")
            if entry_path and Path(entry_path).exists():
                cleaned_registry.append(entry)
            else:
                registry_cleaned += 1
                if not is_json_output():
                    print_info(f"Removed stale registry entry: {entry.get('branch', 'unknown')} at {entry_path}")

        # Save cleaned registry if changes were made
        if registry_cleaned > 0:
            save_worktree_registry(repo_root, cleaned_registry)

    # Report results
    if is_json_output():
        print_json({"removed": removed, "added": added, "registry_cleaned": registry_cleaned})
    else:
        print_success(f"Removed {removed} stale entries, added {added} missing entries")
        if registry_cleaned > 0:
            print_info(f"Cleaned {registry_cleaned} stale registry entries")
