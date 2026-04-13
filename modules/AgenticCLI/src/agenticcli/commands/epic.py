# story: US-PLN-001, US-PLN-009, US-PLN-015, US-STR-011
"""Epic management commands.

Handles epic folder operations and ticket tracking.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional


# Cache for dynamic agent type discovery
_agent_types_cache: set | None = None

# Fallback set used when filesystem scanning fails
_FALLBACK_AGENT_TYPES = {
    "build-docs-writer", "build-flutter", "build-python", "build-story-writer",
    "deploy-cicd",
    "epic-creator",
    "orchestration-executor", "orchestration-planning",
    "planner-audit", "planner-build", "planner-explore", "planner-orchestration", "planner-test",
    "teacher-update-assets", "teacher-update-guidance",
    "test-audit", "test-builder", "test-uat", "trace-explorer",
}


def get_valid_agent_types(agents_dir: Path | None = None) -> set[str]:
    """Discover valid agent types by scanning the agents directory.

    Scans modules/AgenticGuidance/agents/**/ for directories that represent
    agent types (leaf directories under category folders). Falls back to a
    hardcoded set if the directory is not found.

    Args:
        agents_dir: Optional override for the agents directory path.

    Returns:
        Set of valid agent type names (e.g., {"build-python", "test-builder"}).
    """
    global _agent_types_cache
    use_cache = agents_dir is None
    if use_cache and _agent_types_cache is not None:
        return _agent_types_cache

    if agents_dir is None:
        # Walk up from this file to find the repo root
        # plan.py -> commands/ -> agenticcli/ -> src/ -> AgenticCLI/ -> modules/ -> repo root
        repo_root = Path(__file__).resolve().parents[5]
        agents_dir = repo_root / "modules" / "AgenticGuidance" / "agents"

    if not agents_dir.is_dir():
        return _FALLBACK_AGENT_TYPES

    agent_types = set()
    for category_dir in agents_dir.iterdir():
        if not category_dir.is_dir():
            continue
        # Underscore-prefixed categories (e.g. `_mock/`) are UAT-only harnesses
        # and must never be routable as production agents. See
        # modules/AgenticGuidance/agents/_mock/README.md.
        if category_dir.name.startswith("_"):
            continue
        for agent_dir in category_dir.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("."):
                agent_types.add(agent_dir.name)

    if not agent_types:
        return _FALLBACK_AGENT_TYPES

    if use_cache:
        _agent_types_cache = agent_types
    return agent_types



def _get_phase_id(phase: dict) -> str:
    """Get phase ID from either phase_id or id field.

    Args:
        phase: Phase dictionary from YAML.

    Returns:
        Phase ID string, empty if not found.
    """
    return phase.get("phase_id", "") or phase.get("id", "")


def _get_repo_db_path() -> Path:
    """Return the global TinyDB path (~/.agentic/epics.db)."""
    return Path.home() / ".agentic" / "epics.db"


def _get_repo():
    """Get EpicRepository instance for TinyDB-backed epic access."""
    from agenticguidance.services.epic_repository import EpicRepository
    try:
        return EpicRepository()
    except TimeoutError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


def _check_has_orchestration(epic_folder_name: str, plan_path: Path = None) -> bool:
    """Check if an epic has orchestration phases in TinyDB.

    Checks TinyDB phases only (primary store). The legacy MMD file fallback
    has been removed as part of the epic folder elimination work.

    Args:
        epic_folder_name: Epic folder name (e.g. '260307EO_my_epic').
        plan_path: Unused, kept for backward-compatible call sites.

    Returns:
        True if orchestration phases with an agent exist in TinyDB.
    """
    from agenticcli.utils.phase_validation import has_any_routed_phase

    try:
        with _get_repo() as repo:
            phases = repo.list_phases(epic_folder_name)
            return has_any_routed_phase(phases)
    except Exception:
        pass
    return False


def _ensure_epic_in_db(repo, plan_path: Path) -> bool:
    """Check that the epic exists in TinyDB.

    TinyDB is the sole source of truth. No disk-based auto-registration.

    Args:
        repo: EpicRepository instance.
        plan_path: Path-like identifying the epic (only .name is used).

    Returns:
        True if the epic exists in TinyDB, False otherwise.
    """
    plan_doc = repo.get_epic(plan_path.name)
    if plan_doc is not None:
        # Already registered - optionally resync folder path (name-based comparison)
        if (
            plan_path
            and plan_doc.epic_folder
            and plan_doc.epic_folder_name != plan_path.name
        ):
            repo.resync_epic_folder(plan_path.name, str(plan_path))
        return True

    return False


def is_epic_fully_completed(plan_folder: Path) -> bool:
    """Check if all tasks across all plan files are completed.

    Uses TinyDB as the sole data source.

    Args:
        plan_folder: Path to the plan folder.

    Returns:
        True if ALL tasks have status "completed",
        False otherwise. Returns False if no tasks are found.
    """
    try:
        repo = _get_repo()
        if repo is not None:
            counts = repo.get_ticket_counts(plan_folder.name)
            if counts["total"] > 0:
                return repo.check_all_tickets_complete(plan_folder.name)
    except Exception:
        pass

    return False





def handle(args, ctx=None):
    """Route epic subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.epic_command == "new":
        cmd_new(args, ctx)
    elif args.epic_command == "seed":
        cmd_seed(args, ctx)
    elif args.epic_command == "init":
        cmd_init(args, ctx)
    elif args.epic_command == "status":
        cmd_status(args)
    elif args.epic_command == "ticket":
        if args.ticket_action == "start":
            cmd_task_start(args)
        elif args.ticket_action == "complete":
            cmd_task_complete(args)
        elif args.ticket_action == "list":
            cmd_task_list(args, ctx)
        elif args.ticket_action == "add":
            cmd_task_add(args, ctx)
        elif args.ticket_action == "update":
            cmd_task_update(args, ctx)
        elif args.ticket_action == "remove":
            cmd_task_remove(args, ctx)
        elif args.ticket_action == "current":
            cmd_task_current(args, ctx)
        else:
            print("Usage: agentic epic ticket <start|complete|list|add|update|remove|current> ...", file=sys.stderr)
            sys.exit(1)
    elif args.epic_command == "archive":
        cmd_archive(args)
    elif args.epic_command == "list":
        cmd_list(args)
    elif args.epic_command == "phase":
        if args.phase_action == "add":
            cmd_phase_add(args, ctx)
        elif args.phase_action == "list":
            cmd_phase_list(args, ctx)
        elif args.phase_action == "update":
            cmd_phase_update(args, ctx)
        elif args.phase_action == "remove":
            cmd_phase_remove(args, ctx)
        else:
            print("Usage: agentic epic phase <add|list|update|remove>", file=sys.stderr)
            sys.exit(1)
    elif args.epic_command == "cancel":
        cmd_cancel(args, ctx)
    elif args.epic_command == "from-plan":
        cmd_from_plan(args, ctx)
    elif args.epic_command == "link":
        cmd_link(args, ctx)
    elif args.epic_command == "unlink":
        cmd_unlink(args, ctx)
    elif args.epic_command == "set-priority":
        cmd_set_priority(args, ctx)
    else:
        print("Usage: agentic epic <new|from-plan|status|ticket|archive|list|phase|cancel|link|unlink|set-priority>", file=sys.stderr)
        sys.exit(1)


def _epic_folder_or_synthetic(epic_obj) -> Path:
    """Return epic_folder from an EpicData/EpicMetadata, or synthesize a Path from the name.

    When epic_folder is None or empty (folder-free epic), returns a synthetic
    Path using only the epic_folder_name. Callers use .name on the result to
    get the epic_folder_name for TinyDB lookups.
    """
    if epic_obj.epic_folder:
        return epic_obj.epic_folder
    return Path(epic_obj.epic_folder_name)


def find_epic_folder(path: str | None = None) -> Path:
    """Find an epic by name or path, using TinyDB as the sole lookup source.

    Args:
        path: Explicit path or partial epic name, or None to auto-detect.
              Can be an absolute path, or a partial folder name to match
              (e.g., "260129FI" matches "260129FI_cli_bug_fixes").

    Returns:
        Path to the epic folder (from TinyDB's epic_folder field).
    """
    with _get_repo() as repo:
        if path:
            # Extract folder name from absolute or relative path
            path_obj = Path(path)
            search_name = path_obj.name if path_obj.name else str(path)

            # Exact match in TinyDB
            try:
                epic_data = repo.get_epic(search_name)
                if epic_data:
                    return _epic_folder_or_synthetic(epic_data)
            except Exception:
                pass

            # Partial match: search all epics for prefix match
            try:
                all_epics = repo.list_epics()
                matches = [
                    e for e in all_epics
                    if e.epic_folder_name.startswith(search_name)
                ]
                if len(matches) == 1:
                    return _epic_folder_or_synthetic(matches[0])
                if len(matches) > 1:
                    matches.sort(key=lambda e: e.epic_folder_name)
                    names = "\n  ".join(e.epic_folder_name for e in matches)
                    print(
                        f"Error: Epic prefix '{path}' is ambiguous — {len(matches)} matches:\n"
                        f"  {names}\n"
                        f"Use the full folder name (or a longer prefix) to disambiguate.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
            except SystemExit:
                raise
            except Exception:
                pass

            print(f"Error: Epic '{path}' not found in TinyDB.", file=sys.stderr)
            sys.exit(1)

        # Auto-detect: find first live epic from TinyDB
        try:
            live_epics = repo.list_epics(status="live")
            if live_epics:
                return _epic_folder_or_synthetic(live_epics[0])
        except Exception:
            pass

        print("Error: No live epics found. Specify path explicitly.", file=sys.stderr)
        sys.exit(1)



def _slugify_objective(objective: str) -> str:
    """Convert an objective string into a valid git branch slug.

    Rules:
    - Lowercase
    - Replace spaces/underscores with hyphens
    - Remove special characters except hyphens
    - Collapse multiple hyphens
    - Max 50 characters
    - Prefix with "plan-"

    Args:
        objective: Human-readable objective text.

    Returns:
        Git-safe branch name like "plan-add-phone-notifications".
    """
    import re

    slug = objective.lower()
    slug = slug.replace(" ", "-").replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > 50:
        slug = slug[:50].rstrip("-")
    return f"plan-{slug}"


def cmd_new(args, ctx=None):
    """Create a new epic shell (TinyDB record + optional disk folder).

    As of the Story-Writer UAT-First Restructure, `epic new` is a pure CRUD
    command: it creates the epic shell and returns. It does NOT spawn a
    planner agent. Planning happens via the orchestration loop:

        agentic orchestrate session plan --epic <folder>

    The loop discovers seeded epics (status in {"seed", "planning"}) and
    invokes the appropriate planner agents. Making `epic new` auto-spawn a
    planner baked implicit wiring into a CRUD command; it's now symmetric
    with the old `epic seed` (which remains as a deprecation shim).

    Args:
        args: Parsed command arguments with:
            - objective: Planning objective description
            - branch: Optional git branch name
            - description: Optional plan description suffix
            - base: Base branch (default: main)
        ctx: Optional CLIContext.

    Returns:
        dict with plan_folder, branch, objective, status="seed" on success.

    Exit codes:
        0: Success
        1: Failure (missing objective, init failed, etc.)
    """
    from types import SimpleNamespace

    from agenticcli.console import (
        is_json_output,
        print_error,
        print_info,
        print_json,
        print_success,
    )

    objective = getattr(args, "objective", None)
    if not objective:
        print_error("Objective is required. Usage: agentic epic new \"your objective\"")
        sys.exit(1)

    branch = getattr(args, "branch", None)
    description = getattr(args, "description", None)
    base = getattr(args, "base", "main")

    # Auto-generate branch name from objective if not provided
    if not branch:
        branch = _slugify_objective(objective)

    # Use objective as description if not provided
    if not description:
        description = objective

    if not is_json_output():
        print_info(f"Creating epic for: {objective}")
        print_info(f"Branch: {branch}")

    # Create the epic shell by delegating to cmd_init.
    # Suppress cmd_init's own output; we produce our own summary.
    import io
    from contextlib import redirect_stdout

    from agenticcli.console import set_json_output as _set_json

    init_args = SimpleNamespace(
        command="plan",
        plan_command="init",
        json=False,  # Always suppress init's JSON - we emit our own
        debug=getattr(args, "debug", False),
        branch=branch,
        description=description,
        base=base,
        objective=objective,
    )

    was_json = is_json_output()
    if was_json:
        _set_json(False)

    init_stdout = io.StringIO()
    with redirect_stdout(init_stdout):
        cmd_init(init_args, ctx)

    if was_json:
        _set_json(True)

    # If we get here, init succeeded. Look up the created epic record from TinyDB.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        repo_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        print_error("Not in a git repository")
        sys.exit(1)

    # Look up the plan folder path from TinyDB (no filesystem scan needed)
    plan_folder = None
    try:
        from agenticcli.utils.naming import generate_epic_folder_name
        plan_folder_name = generate_epic_folder_name(repo_root, description, branch=branch)
        from agenticguidance.services.epic_repository import EpicRepository
        _init_repo = EpicRepository()
        epic_doc = _init_repo.get_epic(plan_folder_name)
        _init_repo.close()
        if epic_doc is not None and epic_doc.epic_folder is not None:
            plan_folder = Path(epic_doc.epic_folder)
    except Exception:
        pass

    # Fallback: reconstruct the expected path if TinyDB lookup failed
    if not plan_folder:
        try:
            from agenticcli.utils.naming import generate_epic_folder_name
            plan_folder_name = generate_epic_folder_name(repo_root, description, branch=branch)
            plan_folder = repo_root / "docs" / "epics" / "live" / plan_folder_name
        except Exception:
            pass

    if not plan_folder:
        print_error("Plan folder was not created. Check plan init output above.")
        sys.exit(1)

    # Epic shell is ready — do NOT spawn a planner. Planning happens via the
    # orchestration loop (`agentic orchestrate session plan --epic <folder>`),
    # which discovers seeded epics and invokes the appropriate planner agents.

    result_data = {
        "plan_folder": str(plan_folder),
        "branch": branch,
        "objective": objective,
        "status": "seed",
    }

    if is_json_output():
        print_json(result_data)
    else:
        print_success(f"Epic created: {plan_folder.name}")
        print(f"  Plan folder: {plan_folder}")
        print(f"  Branch: {branch}")
        print(f"  Objective: {objective}")
        print()
        print("  Next steps:")
        print(f"    1. Review epic: agentic epic status --epic {plan_folder.name}")
        print(f"    2. Plan phases: agentic orchestrate session plan --epic {plan_folder.name}")

    return result_data




def cmd_seed(args, ctx=None):
    """Deprecated alias for `agentic epic new`.

    As of the Story-Writer UAT-First Restructure, `epic new` no longer spawns
    a planner — it creates a pure CRUD seed record, identical to what `epic
    seed` used to do. Keeping `seed` around as a thin shim lets existing
    agent guidance and scripts keep working during the deprecation window.
    """
    from agenticcli.console import print_warning
    print_warning("'epic seed' is deprecated — use 'epic new' (behavior is identical)")
    return cmd_new(args, ctx)


def cmd_from_plan(args, ctx=None):
    """Create a seed epic from a Claude Code plan markdown file.

    Reads the plan file, extracts the title from the first ``# `` heading,
    and creates an epic with status "seed" so the orchestration planner
    can later structure it into phases and tickets.

    Args:
        args: Parsed arguments with plan_file, optional branch, dry_run.
        ctx: Optional CLIContext.
    """
    import re
    from types import SimpleNamespace

    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_info,
        print_json,
        print_success,
    )

    plan_file = getattr(args, "plan_file", None)
    if not plan_file:
        print_error("Plan file path is required.")
        sys.exit(1)

    plan_path = Path(plan_file).expanduser().resolve()
    if not plan_path.is_file():
        print_error(f"Plan file not found: {plan_path}")
        sys.exit(1)

    # Read and parse plan content
    plan_content = plan_path.read_text()
    if not plan_content.strip():
        print_error("Plan file is empty.")
        sys.exit(1)

    # Extract title from first heading
    title_match = re.search(r"^#\s+(.+)$", plan_content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else plan_path.stem

    dry_run = getattr(args, "dry_run", False)
    branch = getattr(args, "branch", None) or _slugify_objective(title)

    if dry_run:
        data = {
            "title": title,
            "branch": branch,
            "plan_file": str(plan_path),
            "content_length": len(plan_content),
        }
        if is_json_output():
            print_json(data)
        else:
            print_info(f"Title: {title}")
            print_info(f"Branch: {branch}")
            print_info(f"Content: {len(plan_content)} chars")
            print_info(f"Source: {plan_path}")
            console.print("[dim]Dry run — no epic created.[/dim]")
        return

    # Create epic via cmd_init (same pattern as cmd_new)
    import io
    from contextlib import redirect_stdout

    from agenticcli.console import set_json_output as _set_json

    # Use title as description for folder naming
    description = title

    init_args = SimpleNamespace(
        command="plan",
        plan_command="init",
        json=False,
        debug=getattr(args, "debug", False),
        branch=branch,
        description=description,
        base="main",
        objective=plan_content,
    )

    was_json = is_json_output()
    if was_json:
        _set_json(False)

    init_stdout = io.StringIO()
    with redirect_stdout(init_stdout):
        cmd_init(init_args, ctx)

    if was_json:
        _set_json(True)

    # Look up the created epic and set status to "seed"
    import subprocess as _sp

    try:
        result = _sp.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        repo_root = Path(result.stdout.strip())
    except _sp.CalledProcessError:
        print_error("Not in a git repository")
        sys.exit(1)

    from agenticcli.utils.naming import generate_epic_folder_name
    from agenticguidance.services.epic_repository import EpicRepository

    plan_folder_name = generate_epic_folder_name(repo_root, description, branch=branch)
    repo = EpicRepository()
    try:
        # Update status to seed and store plan source path in context
        repo.update_epic(plan_folder_name, {
            "status": "seed",
            "context": plan_content,
            "plan_source": str(plan_path),
        })
    except Exception:
        pass  # Best-effort — epic was already created by cmd_init
    finally:
        repo.close()

    epic_folder = repo_root / "docs" / "epics" / "live" / plan_folder_name
    result_data = {
        "epic_folder_name": plan_folder_name,
        "epic_folder": str(epic_folder),
        "status": "seed",
        "title": title,
        "branch": branch,
        "plan_source": str(plan_path),
    }

    if is_json_output():
        print_json(result_data)
    else:
        print_success(f"Seed epic created: {plan_folder_name}")
        console.print(f"  [dim]Status:[/dim] [magenta]seed[/magenta]")
        console.print(f"  [dim]Branch:[/dim] {branch}")
        console.print(f"  [dim]Source:[/dim] {plan_path}")
        console.print(f"\n[dim]Next: agentic orchestrate session plan --plan {plan_folder_name}[/dim]")


def cmd_init(args, ctx=None):
    """Initialize plan folder with proper naming convention.

    Creates a plan folder in docs/epics/live/ with YYMMDDXX_description naming.

    Exit codes:
        0: Success, folder created
        2: Folder already exists
        3: Invalid branch name or description
    """
    import subprocess

    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_json,
        print_success,
    )
    from agenticcli.utils.naming import generate_epic_folder_name, validate_epic_folder_name

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

    # Generate plan folder name
    plan_folder_name = generate_epic_folder_name(repo_root, description, branch=branch)

    # Validate the generated name
    is_valid, error = validate_epic_folder_name(plan_folder_name)
    if not is_valid:
        print_error(f"Generated name '{plan_folder_name}' is invalid: {error}")
        sys.exit(3)

    # Create epic in TinyDB (primary data store — no disk folder created)
    objective = getattr(args, "objective", None)

    try:
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository()
        epic_data = {
            "epic_folder_name": plan_folder_name,
            "epic_folder": "",
            "name": description,
            "branch": branch,
            "status": "seed",
            "priority": "high",
        }
        if objective:
            epic_data["context"] = objective
        create_result = repo.create_epic(epic_data)
        if not create_result.success:
            repo.close()
            print_error(f"Epic already exists: {plan_folder_name}")
            sys.exit(2)
        repo.close()
    except Exception:
        pass

    # Output results
    result_data = {
        "branch": branch,
        "base": base,
        "epic_folder_name": plan_folder_name,
    }
    if objective:
        result_data["objective"] = objective

    if is_json_output():
        print_json(result_data)
    else:
        console.print(f"  [green]Created epic[/green]: {plan_folder_name}")
        if objective:
            console.print(f"  [green]Epic created[/green] with objective")
        console.print()
        print_success(f"Epic initialized: {plan_folder_name}")
        console.print()
        console.print("[dim]Link related user stories:[/dim]")
        console.print(f"[dim]  agentic stories find --project <name>[/dim]")
        console.print(f"[dim]  agentic stories untested --project <name>[/dim]")


def cmd_status(args):
    """Show epic status and task summary.

    Shows unified status with next_action derived from the status field.
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_key_value,
        print_table,
    )

    # T3_4: Resolve epic via TinyDB-first, so status works even without folder on disk.
    # Try TinyDB lookup first (by name/id), then fall back to find_epic_folder for
    # epics that exist on disk but may not yet be indexed.
    plan_path = None
    epic_folder_name = None

    epic_arg = getattr(args, "path", None)
    if epic_arg:
        try:
            repo = _get_repo()
            search_key = Path(epic_arg).name if epic_arg else epic_arg
            epic_db_doc = repo.get_epic(search_key)
            repo.close()
            if epic_db_doc is not None:
                plan_path = epic_db_doc.epic_folder
                epic_folder_name = epic_db_doc.epic_folder_name
        except Exception:
            pass

    if plan_path is None:
        # Fall back to filesystem-based resolution (requires folder to exist)
        plan_path = find_epic_folder(epic_arg)
        epic_folder_name = plan_path.name

    # EN-003: Check for orchestration phases in TinyDB only (T3_1: no MMD fallback)
    has_orchestration = _check_has_orchestration(epic_folder_name)
    total_pending = 0
    total_completed = 0
    file_stats = []
    plan_status = "unknown"
    deferred_reason = None
    has_tasks = False

    # Get plan data via PlanService (TinyDB-first)
    try:
        from agenticguidance.services.epic import EpicService
        plan_service = EpicService()
        plan_data_obj = plan_service.get_epic(epic_folder_name)
    except Exception as e:
        print_error(f"Failed to load PlanService: {e}")
        sys.exit(1)

    if plan_data_obj is None:
        print_error(f"Plan not found in repository: {epic_folder_name}")
        sys.exit(1)

    plan_status = plan_data_obj.status or "unknown"
    tasks = plan_data_obj.tasks or []
    # Treat proposed and in_progress as pending for display (tickets are either pending or done)
    total_pending = sum(1 for t in tasks if t.status in ("proposed", "pending", "in_progress"))
    total_completed = sum(1 for t in tasks if t.status == "completed")
    has_tasks = len(tasks) > 0

    # Build file_stats summary (aggregate all tasks under a single entry for display)
    if has_tasks:
        file_stats.append(
            {
                "file": "(via EpicService)",
                "pending": total_pending,
                "completed": total_completed,
            }
        )

    # Get deferred_reason from PlanData (TinyDB-backed)
    if plan_status == "deferred":
        deferred_reason = plan_data_obj.deferred_reason

    total = total_pending + total_completed
    pct = (total_completed / total) * 100 if total > 0 else 0

    # Derive next_action and next_command from the unified status field
    _status_actions = {
        "seed": ("Spawn planning agent", f"agentic orchestrate session plan --epic {epic_folder_name}"),
        "planning": ("Planning in progress", f"agentic orchestrate session plan --epic {epic_folder_name}"),
        "in_progress": ("Execute current ticket", f"agentic epic ticket current --epic {epic_folder_name}"),
        "completed": ("Archive epic", f"agentic epic archive {epic_folder_name}"),
        "deferred": ("Resolve blockers", None),
        "blocked": ("Resolve blockers", None),
    }
    next_action, next_command = _status_actions.get(plan_status, ("Check epic state", None))

    # C6: If epic has orchestration and every phase is routed, recommend implement.
    phases_for_display = list(plan_data_obj.phases or [])
    if has_orchestration and phases_for_display and all(p.agent for p in phases_for_display):
        next_action = "Execute routed phases"
        next_command = f"agentic orchestrate session implement --epic {epic_folder_name}"

    # Dependency information
    depends_on = list(plan_data_obj.depends_on or [])
    priority = _to_int_priority(plan_data_obj.priority)
    dep_blocked = False
    blocked_by = []
    blocks = []
    try:
        from agenticguidance.services.dependency import DependencyService
        repo_for_deps = _get_repo()
        dep_service = DependencyService(repo_for_deps)
        dep_blocked, blocked_by = dep_service.is_blocked(epic_folder_name)
        # Find epics that depend on this one ("blocks" list)
        graph = dep_service.get_dependency_graph()
        blocks = [name for name, deps in graph.items() if epic_folder_name in deps]
        repo_for_deps.close()
    except Exception:
        pass

    # --validate: collect validation results
    validation_data = None
    if getattr(args, "validate", False):
        validation_data = _collect_validation(plan_path, args)

    if is_json_output():
        result_data = {
            "plan": plan_path.name,
            "status": plan_status,
            "priority": priority,
            "has_orchestration": has_orchestration,
            "next_action": next_action,
            "next_command": next_command,
            "deferred_reason": deferred_reason,
            "depends_on": depends_on,
            "blocked_by": blocked_by,
            "blocks": blocks,
            "dependency_blocked": dep_blocked,
            "files": file_stats,
            "totals": {
                "pending": total_pending,
                "completed": total_completed,
            },
            "progress_percent": round(pct, 1),
        }
        if validation_data is not None:
            result_data["validation"] = validation_data
        print_json(result_data)
    else:
        print_header(f"Epic Status: {plan_path.name}")

        # EN-003: Show orchestration status
        if has_orchestration:
            console.print(f"[bold]Orchestration:[/bold] [green]Phases in TinyDB[/green]")
        else:
            console.print("[bold]Orchestration:[/bold] [red]MISSING[/red]")
            console.print("  Run: agentic orchestrate session plan --epic <folder>")

        # C5: Render phase table when phases exist
        if phases_for_display:
            from agenticcli.console import format_status as _format_status
            phase_rows = []
            for i, phase in enumerate(phases_for_display):
                phase_rows.append([
                    f"[bold]{phase.phase_id or f'P{i + 1}'}[/bold]",
                    phase.name,
                    _format_status(phase.status or "planning"),
                    phase.agent or "-",
                ])
            print_table("Phases", ["ID", "Name", "Status", "Agent"], phase_rows)

        console.print(f"[bold]Status:[/bold] {plan_status}")

        # Priority — display as "N (label)" with color keyed by int
        # @story US-002
        _priority_colors = {1: "red bold", 2: "yellow", 3: "white", 4: "dim"}
        int_p = _to_int_priority(priority)
        p_color = _priority_colors.get(int_p, "white")
        p_display = _format_priority(priority)
        console.print(f"[bold]Priority:[/bold] [{p_color}]{p_display}[/{p_color}]")

        # EN-004: Show deferred reason
        if deferred_reason:
            console.print(f"[bold]Deferred Reason:[/bold] [yellow]{deferred_reason}[/yellow]")

        # Dependency information
        if depends_on:
            console.print(f"[bold]Depends On:[/bold]")
            for dep in depends_on:
                if dep in blocked_by:
                    console.print(f"  [red]✗[/red] {dep} [red](not completed)[/red]")
                else:
                    console.print(f"  [green]✓[/green] {dep} [green](completed)[/green]")
        if blocks:
            console.print(f"[bold]Blocks:[/bold] {', '.join(blocks)}")
        if dep_blocked:
            console.print(f"[red bold]⚠ BLOCKED by unsatisfied dependencies[/red bold]")

        console.print(f"[bold]Next Action:[/bold] {next_action}")
        if next_command:
            console.print(f"  Run: {next_command}")
        console.print()

        rows = []
        for stat in file_stats:
            if "error" in stat:
                rows.append([stat["file"], "[red]ERROR[/red]", ""])
            else:
                rows.append(
                    [
                        stat["file"],
                        f"[dim]{stat['pending']}[/dim]",
                        f"[green]{stat['completed']}[/green]",
                    ]
                )

        if rows:
            print_table("Files", ["File", "Pending", "Done"], rows)

        console.print()
        console.print(
            f"[bold]Total:[/bold] [dim]{total_pending} pending[/dim], "
            f"[green]{total_completed} done[/green]"
        )
        console.print(f"[bold]Progress:[/bold] [cyan]{pct:.1f}%[/cyan]")

        # EN-005: Show next action guidance
        console.print()
        console.print(f"[bold]Next Action:[/bold] {next_action}")
        if next_command:
            console.print(f"  [dim]Command: {next_command}[/dim]")

        # Print validation results in human-readable form
        if validation_data is not None:
            _print_validation(plan_path, validation_data)


def _collect_validation(plan_path, args):
    """Collect validation results for an epic (called from cmd_status --validate).

    Returns a dict with status, orchestration, errors, warnings, etc.
    Calls sys.exit(1) if there are errors.
    """
    strict = getattr(args, "strict", False)
    check_fences = getattr(args, "check_fences", False)

    errors = []
    warnings = []

    # Validate epic exists in TinyDB
    try:
        repo = _get_repo()
        plan_data_obj = repo.get_epic(plan_path.name)
        if plan_data_obj is None:
            errors.append(f"Epic '{plan_path.name}' not found in TinyDB")
    except Exception as e:
        errors.append(f"Failed to query TinyDB: {e}")

    # Orchestration validation - check TinyDB phases
    orchestration_result = {"status": "PASS", "details": []}

    has_tinydb_phases = False
    tinydb_phase_count = 0
    try:
        from agenticcli.utils.phase_validation import has_any_routed_phase

        repo = _get_repo()
        phases = repo.list_phases(plan_path.name)
        repo.close()
        if has_any_routed_phase(phases):
            has_tinydb_phases = True
            tinydb_phase_count = len(phases)
    except Exception:
        pass

    if has_tinydb_phases:
        orchestration_result["details"].append("Orchestration phases found in TinyDB")
        orchestration_result["details"].append(f"Phases found: {tinydb_phase_count}")
    else:
        orchestration_result["status"] = "FAIL"
        orchestration_result["details"].append("Missing: orchestration phases in TinyDB")
        orchestration_result["details"].append("Action: Spawn orchestration-planning agent")
        orchestration_result["details"].append("Command: agentic orchestrate session plan --epic <folder>")
        if strict:
            errors.append("Missing orchestration phases in TinyDB")
        else:
            warnings.append("Missing orchestration phases in TinyDB")

    # --check-fences: validate UAT fence compliance
    fence_results = {}
    if check_fences:
        fence_results = _check_fences(plan_path)
        for fence_name, result in fence_results.items():
            if result["status"] == "FAIL":
                errors.append(f"Fence {fence_name}: {result['message']}")
            elif result["status"] == "WARN":
                warnings.append(f"Fence {fence_name}: {result['message']}")

    # Additional structural validation via PlanService (non-fatal)
    try:
        from agenticguidance.services.epic import EpicService
        svc = EpicService()
        svc_result = svc.validate_epic_structure(plan_path)
        if svc_result and hasattr(svc_result, "errors") and svc_result.errors:
            for svc_err in svc_result.errors:
                if svc_err not in errors:
                    warnings.append(f"[PlanService] {svc_err}")
    except Exception:
        pass

    has_errors = len(errors) > 0
    overall_status = "FAIL" if has_errors else ("WARN" if warnings else "PASS")

    data = {
        "status": overall_status,
        "orchestration": orchestration_result,
        "errors": errors,
        "warnings": warnings,
    }
    if check_fences:
        data["fences"] = fence_results

    if has_errors:
        sys.exit(1)

    return data


def _print_validation(plan_path, validation_data):
    """Print validation results in human-readable form."""
    orchestration_result = validation_data.get("orchestration", {})
    errors = validation_data.get("errors", [])
    warnings = validation_data.get("warnings", [])
    fence_results = validation_data.get("fences", {})

    print(f"\nValidation: {plan_path}")
    print("=" * 60)

    print(f"\nOrchestration: {orchestration_result.get('status', 'UNKNOWN')}")
    for detail in orchestration_result.get("details", []):
        print(f"  - {detail}")

    if fence_results:
        print("\nFence Checks:")
        for fence_name, result in fence_results.items():
            status_marker = "PASS" if result["status"] == "PASS" else result["status"]
            print(f"  {fence_name}: {status_marker} - {result['message']}")

    if errors:
        print("\nErrors:")
        for err in errors:
            print(f"  - {err}")

    if warnings:
        print("\nWarnings:")
        for warn in warnings:
            print(f"  - {warn}")

    if not errors and not warnings and orchestration_result.get("status") == "PASS":
        print("\n  All checks passed")


def _check_fences(plan_path: Path) -> dict:
    """Run UAT fence validation checks on a plan folder.

    Three fences are checked:
    1. Story Discovery: plan has affected_stories or no_stories_rationale
    2. Story Coverage: all affected stories have test_status != untested
    3. Marker Coverage: all affected stories have @pytest.mark.story markers in test files

    Args:
        plan_path: Path to the plan folder.

    Returns:
        Dict of fence name -> {status, message}.
    """
    import re

    results = {}

    # Collect metadata from TinyDB epic record
    affected_stories = []
    no_stories_rationale = None
    try:
        repo = _get_repo()
        epic_data = repo.get_epic(plan_path.name)
        if epic_data:
            stories = getattr(epic_data, "affected_stories", None) or []
            if stories:
                affected_stories.extend(stories)
            rationale = getattr(epic_data, "no_stories_rationale", None)
            if rationale:
                no_stories_rationale = rationale
    except Exception:
        pass

    # Deduplicate
    affected_stories = sorted(set(affected_stories))

    # --- Fence 1: Story Discovery ---
    if affected_stories:
        results["Fence 1 (Story Discovery)"] = {
            "status": "PASS",
            "message": f"{len(affected_stories)} affected stories found",
        }
    elif no_stories_rationale:
        results["Fence 1 (Story Discovery)"] = {
            "status": "WARN",
            "message": f"No stories but rationale provided: {no_stories_rationale[:80]}",
        }
    else:
        results["Fence 1 (Story Discovery)"] = {
            "status": "FAIL",
            "message": "No affected_stories and no no_stories_rationale in plan metadata",
        }

    # --- Fence 2: Story Coverage ---
    if not affected_stories:
        results["Fence 2 (Story Coverage)"] = {
            "status": "WARN",
            "message": "No affected stories to check coverage for",
        }
    else:
        from agenticcli.commands.stories import _collect_all_stories

        all_stories = _collect_all_stories()
        story_map = {s["id"]: s for s in all_stories}

        untested = []
        tested = 0
        for sid in affected_stories:
            story = story_map.get(sid)
            if story:
                ts = story.get("test_status", "untested")
                if ts == "untested":
                    untested.append(sid)
                else:
                    tested += 1
            else:
                untested.append(sid)

        total = len(affected_stories)
        if untested:
            pct = (tested / total) * 100 if total > 0 else 0
            results["Fence 2 (Story Coverage)"] = {
                "status": "WARN",
                "message": f"Coverage: {tested}/{total} ({pct:.0f}%). Untested: {', '.join(untested)}",
            }
        else:
            results["Fence 2 (Story Coverage)"] = {
                "status": "PASS",
                "message": f"All {total} stories tested",
            }

    # --- Fence 3: Pytest Story Marker Coverage ---
    if not affected_stories:
        results["Fence 3 (Marker Coverage)"] = {
            "status": "WARN",
            "message": "No affected stories to check marker coverage for",
        }
    else:
        import subprocess

        # Find repo root from plan_path
        repo_root = plan_path
        while repo_root != repo_root.parent:
            if (repo_root / ".git").exists():
                break
            repo_root = repo_root.parent

        # Scan test files for @pytest.mark.story markers
        marker_ids: set[str] = set()
        test_dirs = [
            repo_root / "modules" / "AgenticCLI" / "tests",
            repo_root / "modules" / "AgenticGuidance" / "tests",
        ]
        for test_dir in test_dirs:
            if not test_dir.exists():
                continue
            try:
                result = subprocess.run(
                    ["grep", "-rh", r"@pytest.mark.story", str(test_dir)],
                    capture_output=True, text=True, timeout=30,
                )
                if result.stdout:
                    for match in re.findall(r'["\']([A-Z]{2}-[A-Z]+-\d+)["\']', result.stdout):
                        marker_ids.add(match)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Check which affected stories have markers
        stories_with_markers = [sid for sid in affected_stories if sid in marker_ids]
        stories_without_markers = [sid for sid in affected_stories if sid not in marker_ids]

        total_affected = len(affected_stories)
        marked = len(stories_with_markers)

        if stories_without_markers:
            pct = (marked / total_affected) * 100 if total_affected > 0 else 0
            results["Fence 3 (Marker Coverage)"] = {
                "status": "WARN",
                "message": (
                    f"Marker coverage: {marked}/{total_affected} ({pct:.0f}%). "
                    f"Stories without @pytest.mark.story markers: {', '.join(stories_without_markers)}"
                ),
            }
        else:
            results["Fence 3 (Marker Coverage)"] = {
                "status": "PASS",
                "message": f"All {total_affected} affected stories have @pytest.mark.story markers",
            }

    return results


def cmd_task_start(args):
    """Mark a task as in_progress.

    EN-006: Removed MMD gate - tasks can start without an MMD file since
    orchestration is now TinyDB-driven.
    """
    task_id = args.task_id
    plan_path = find_epic_folder(args.plan)

    _update_task_status(plan_path, task_id, "in_progress")
    print(f"Task {task_id} marked as in_progress")


def cmd_task_complete(args):
    """Mark a task as completed."""
    task_id = args.task_id
    plan_path = find_epic_folder(args.plan)

    _update_task_status(plan_path, task_id, "completed")
    print(f"Task {task_id} marked as completed")


def _update_task_status(plan_path: Path, task_id: str, new_status: str):
    """Update a task's status. TinyDB-first, YAML sync for git visibility.

    Args:
        plan_path: Path to plan folder (flattened structure)
        task_id: Task ID to update
        new_status: New status value
    """
    # TinyDB-first path
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_epic(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.epic_folder_name == plan_path.name
            )
            if folder_matches:
                updated = repo.update_ticket_status(plan_path.name, task_id, new_status)
                if updated:
                    return
    except Exception:
        pass

    print(f"Error: Task {task_id} not found in TinyDB", file=sys.stderr)
    sys.exit(1)


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

    plan_path = find_epic_folder(getattr(args, "plan", None))
    status_filter = getattr(args, "status", "all")
    verbose = getattr(args, "verbose", False)

    # Try PlanRepository (TinyDB) first.
    # Only use TinyDB results when TinyDB has data for this plan AND the stored folder path matches
    # the actual plan_path (guards against stale data from temp/test plans with the same folder name).
    all_tasks = None
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_epic(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.epic_folder_name == plan_path.name
            )
            if folder_matches:
                sf = status_filter if status_filter != "all" else None
                task_data_list = repo.get_tickets(plan_path.name, status_filter=sf)
                # Only use TinyDB results if tasks have non-empty ids
                if task_data_list and any(td.id for td in task_data_list):
                    all_tasks = []
                    for td in task_data_list:
                        task_info = {
                            "id": td.id,
                            "description": td.description or "",
                            "status": td.status or "pending",
                            "phase_id": td.phase_name or "",
                            "phase_name": td.phase_name or "",
                            "source_file": "(via TinyDB)",
                        }
                        if verbose:
                            task_info["guidance"] = td.guidance or ""
                            task_info["success_criteria"] = td.success_criteria or []
                            task_info["story_ids"] = td.story_ids or []
                        all_tasks.append(task_info)
            repo.close()
    except Exception:
        all_tasks = None

    if all_tasks is None:
        print_error(f"No task data found in TinyDB for epic: {plan_path.name}")
        sys.exit(1)

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


def cmd_task_add(args, ctx=None):
    """Add a new task to the plan.

    Creates a new task entry in the specified phase or appends
    to the default/last phase if not specified.

    Args:
        args: Parsed arguments with description, plan, phase, id, priority,
              agent, target_files, success_criteria, guidance, inputs.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
    )

    description = args.description
    plan_path = find_epic_folder(getattr(args, "plan", None))
    phase_id = getattr(args, "phase", None)
    custom_id = getattr(args, "id", None)
    priority = _to_int_priority(getattr(args, "priority", 3))
    agent = getattr(args, "agent", None)
    target_files_raw = getattr(args, "target_files", None)
    success_criteria_raw = getattr(args, "success_criteria", None)
    guidance = getattr(args, "guidance", None)
    inputs_raw = getattr(args, "inputs", None)
    story_ids_raw = getattr(args, "story_ids", None)

    # Parse comma-separated list fields
    target_files = [f.strip() for f in target_files_raw.split(",")] if target_files_raw else []
    success_criteria = [s.strip() for s in success_criteria_raw.split(",")] if success_criteria_raw else []
    inputs = [i.strip() for i in inputs_raw.split(",")] if inputs_raw else []
    story_ids = [s.strip() for s in story_ids_raw.split(",")] if story_ids_raw else []

    # @story US-001
    # Enforce --story-ids for build-plan epics
    if not story_ids:
        try:
            from agenticguidance.services.epic import EpicService

            epic_svc = EpicService()
            if epic_svc.is_build_plan(plan_path.name):
                print_error(
                    "story_ids is required for build-plan epics. "
                    "Use --story-ids US-XXX,... to link this ticket to user stories."
                )
                sys.exit(1)
        except ImportError:
            pass  # AgenticGuidance not available; skip enforcement

    # TinyDB-first: try to add task via PlanRepository
    tinydb_done = False
    new_task_id = custom_id
    phase_name_used = ""
    try:
        repo = _get_repo()
        if repo is not None:
            # Ensure the epic is registered in TinyDB (auto-create if folder
            # exists on disk but has no DB record yet).
            if not _ensure_epic_in_db(repo, plan_path):
                repo = None  # Skip TinyDB path
    except Exception:
        repo = None
    try:
        if repo is not None:
            # Determine target phase
            if phase_id:
                phase_obj = repo.get_phase(plan_path.name, phase_id)
                if phase_obj:
                    phase_name_used = phase_obj.name
                else:
                    print_error(f"Phase '{phase_id}' not found")
                    sys.exit(1)
            else:
                phases = repo.list_phases(plan_path.name)
                if phases:
                    phase_name_used = phases[-1].name
                else:
                    phase_name_used = "Ad-hoc Tasks"
                    repo.add_phase(plan_path.name, {"name": phase_name_used, "status": "planning"})

            # Generate task ID if not provided
            if not new_task_id:
                existing = repo.get_tickets(plan_path.name)
                phase_prefix = phase_id or "task"
                task_num = len(existing) + 1
                new_task_id = f"{phase_prefix}_{task_num:03d}"

            ticket_doc = {
                "id": new_task_id,
                "name": description,
                "description": description,
                "status": "proposed",
                "priority": priority,
            }
            if agent:
                ticket_doc["agent"] = agent
            if target_files:
                ticket_doc["target_files"] = target_files
            if success_criteria:
                ticket_doc["success_criteria"] = success_criteria
            if guidance:
                ticket_doc["guidance"] = guidance
            if inputs:
                ticket_doc["inputs"] = inputs
            if story_ids:
                ticket_doc["story_ids"] = story_ids

            added = repo.add_ticket(plan_path.name, phase_name_used, ticket_doc)
            if added:
                tinydb_done = True
    except Exception:
        pass

    if not tinydb_done:
        print_error("Failed to add task via TinyDB")
        sys.exit(1)

    if is_json_output():
        print_json({
            "task_id": new_task_id,
            "description": description,
            "phase": phase_name_used,
            "agent": agent,
            "target_files": target_files,
            "success_criteria": success_criteria,
            "guidance": guidance,
            "inputs": inputs,
            "story_ids": story_ids,
            "source": "TinyDB",
        })
    else:
        print_success(f"Added task '{new_task_id}' to phase '{phase_name_used}' (TinyDB)")


def cmd_archive(args):
    """Archive an epic by setting its TinyDB status to 'completed'."""
    plan_path = find_epic_folder(args.path)
    epic_folder_name = plan_path.name

    repo = _get_repo()
    if repo is None:
        print("Error: could not connect to TinyDB repository.")
        sys.exit(1)

    result = repo.archive_epic(epic_folder_name)
    if result.success:
        print(f"Archived epic: {epic_folder_name}")
    else:
        print(f"Error: {result.message}")
        sys.exit(1)


def cmd_cancel(args, ctx=None):
    """Cancel an active plan.

    Sets the plan status to 'cancelled' in TinyDB and optionally
    archives it to the completed folder.

    Args:
        args: Parsed arguments with path and optional force flag.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
        print_warning,
    )
    from types import SimpleNamespace

    path = getattr(args, "path", None)
    force = getattr(args, "force", False)

    if not path:
        print_error("Path is required. Usage: agentic plan cancel <path> or --plan <path>")
        sys.exit(1)

    plan_folder = find_epic_folder(path)

    # Get current status (TinyDB-first, YAML fallback)
    current_status = "unknown"
    folder_matches = False
    try:
        repo = _get_repo()
        if repo is not None:
            plan_data = repo.get_epic(plan_folder.name)
            folder_matches = (
                plan_data is not None
                and plan_data.epic_folder_name == plan_folder.name
            )
            if folder_matches:
                current_status = plan_data.status or "unknown"
    except Exception:
        pass

    if current_status == "cancelled":
        print_warning(f"Plan is already cancelled: {plan_folder.name}")
        return

    # Confirm unless --force
    if not force:
        print(f"Plan: {plan_folder.name}")
        print(f"Current status: {current_status}")
        response = input("Cancel this plan? [y/N] ")
        if response.lower() != "y":
            print("Aborted.")
            return

    # TinyDB-first: cancel via PlanRepository
    tinydb_done = False
    try:
        if folder_matches:
            repo = _get_repo()
        else:
            repo = None
        if repo is not None:
            result = repo.cancel_epic(plan_folder.name)
            if result.success:
                tinydb_done = True
    except Exception:
        pass

    if not tinydb_done:
        print_error(f"Failed to cancel plan via TinyDB: {plan_folder.name}")
        sys.exit(1)

    if is_json_output():
        print_json({
            "result": "success",
            "plan": plan_folder.name,
            "status": "cancelled",
        })
    else:
        print_success(f"Plan cancelled: {plan_folder.name}")

    # Optionally archive
    if not force:
        response = input("Archive cancelled plan? [y/N] ")
        if response.lower() == "y":
            archive_args = SimpleNamespace(path=str(plan_folder))
            cmd_archive(archive_args)


def cmd_list(args):
    """List all epics in the repository.

    Shows a simplified table with columns: Epic, Status, Proposed, Completed.
    Completed epics are hidden by default; use --all to show them.
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

    plans_data = []

    # Get plan data via EpicService (TinyDB)
    try:
        from agenticguidance.services.epic import EpicService
        plan_service = EpicService()
        plan_metas = plan_service.list_epics(status="live")
    except Exception as e:
        print_error(f"Failed to load EpicService: {e}")
        sys.exit(1)

    from agenticcli.utils.formatting import truncate_string
    from agenticcli.utils.phase_validation import validate_phase_routing

    try:
        repo = plan_service._repository
    except Exception:
        repo = None

    for meta in plan_metas:
        folder_name = meta.epic_folder_name
        plan_status = meta.status or "unknown"

        # Get ticket counts by status
        try:
            plan_data_obj = plan_service.get_epic(folder_name)
            tasks = plan_data_obj.tasks if plan_data_obj else []
        except Exception:
            tasks = []

        n_proposed = sum(1 for t in tasks if t.status == "proposed")
        n_pending = sum(1 for t in tasks if t.status == "pending")
        n_in_progress = sum(1 for t in tasks if t.status == "in_progress")
        n_completed = sum(1 for t in tasks if t.status == "completed")
        n_total = len(tasks)

        # Get phase counts
        phases = repo.list_phases(folder_name) if repo else []
        n_phases = len(phases)
        n_phases_routed = sum(1 for p in phases if p.agent)
        n_phases_done = sum(1 for p in phases if p.status == "completed")

        # Normalize display status based on actual state
        # "planning" that's stale (no running planner) is effectively "seed"
        if repo:
            is_valid, _reason = validate_phase_routing(repo, folder_name)
        else:
            is_valid = False

        if plan_status in ("seed", "planning") and not is_valid:
            display_status = "seed"
        elif is_valid and n_completed == n_total and n_total > 0:
            display_status = "completed"
        elif is_valid and n_completed > 0:
            display_status = "in_progress"
        elif is_valid:
            display_status = "ready"
        else:
            display_status = plan_status

        # Build progress string: "3/8 tickets, 1/3 phases"
        progress = f"{n_completed}/{n_total} tickets"
        if n_phases:
            progress += f", {n_phases_done}/{n_phases} phases"

        # Priority and dependency info
        priority = _to_int_priority(meta.priority)
        depends_on = list(meta.depends_on or [])

        plans_data.append(
            {
                "name": folder_name,
                "status": display_status,
                "raw_status": plan_status,
                "tickets": n_total,
                "completed": n_completed,
                "proposed": n_proposed,
                "pending": n_pending,
                "in_progress": n_in_progress,
                "phases": n_phases,
                "phases_routed": n_phases_routed,
                "phases_done": n_phases_done,
                "progress": progress,
                "priority": priority,
                "depends_on": depends_on,
            }
        )

    # Filter completed epics unless --all is passed
    show_all = getattr(args, "all", False)
    if not show_all:
        plans_data = [p for p in plans_data if p["status"] != "completed"]

    if is_json_output():
        print_json({"plans": plans_data})
    else:
        print_header("Epics in Repository")

        if not plans_data:
            console.print("[dim]No epics found.[/dim]")
            return

        # Build blocked set for dependency indicator
        try:
            from agenticguidance.services.dependency import DependencyService
            dep_service = DependencyService(repo) if repo else None
            blocked_epics = set(dep_service.get_blocked_epics()) if dep_service else set()
        except Exception:
            blocked_epics = set()

        # Priority color mapping — keyed by int (1-4)
        # @story US-002
        _priority_colors = {1: "red bold", 2: "yellow", 3: "white", 4: "dim"}

        rows = []
        for plan in plans_data:
            status_cell = format_status(plan["status"])
            # Add blocked indicator to status
            if plan["name"] in blocked_epics:
                status_cell = f"{status_cell} [red]BLOCKED[/red]"
            tickets_cell = f"[green]{plan['completed']}[/green]/{plan['tickets']}"
            phases_cell = f"[green]{plan['phases_done']}[/green]/{plan['phases']}" if plan["phases"] else "[dim]—[/dim]"
            # Priority with color — display as "N (label)"
            int_p = _to_int_priority(plan.get("priority", 3))
            p_color = _priority_colors.get(int_p, "white")
            p_display = _format_priority(plan.get("priority", 3))
            priority_cell = f"[{p_color}]{p_display}[/{p_color}]"
            rows.append(
                [
                    f"[bold]{truncate_string(plan['name'], 50)}[/bold]",
                    priority_cell,
                    status_cell,
                    tickets_cell,
                    phases_cell,
                ]
            )

        print_table("", ["Epic", "Priority", "Status", "Tickets", "Phases"], rows)

        needs_planning = sum(1 for p in plans_data if p["status"] == "seed")
        ready = sum(1 for p in plans_data if p["status"] == "ready")
        if needs_planning:
            console.print(f"\n[dim]Hint: {needs_planning} epic(s) need planning. Run: agentic orchestrate session plan[/dim]")
        if ready:
            console.print(f"\n[dim]Hint: {ready} epic(s) ready to implement. Run: agentic orchestrate session implement[/dim]")


def cmd_task_update(args, ctx=None):
    """Update task fields in plan YAML file.

    Enables agents to persist progress without holding plan in context.
    Supports updating status and/or any ticket metadata fields.

    Args:
        args: Parsed arguments with task_id, optional status/description/name/
              agent/target_files/success_criteria/guidance/inputs, optional note.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_info,
        print_json,
        print_success,
        print_warning,
    )

    task_id = args.task_id
    new_status = getattr(args, "status", None)
    note = getattr(args, "note", None)
    plan_path = find_epic_folder(getattr(args, "plan", None))

    # Additional fields for T7_2
    new_description = getattr(args, "description", None)
    new_name = getattr(args, "name", None)
    new_agent = getattr(args, "agent", None)
    target_files_raw = getattr(args, "target_files", None)
    success_criteria_raw = getattr(args, "success_criteria", None)
    new_guidance = getattr(args, "guidance", None)
    inputs_raw = getattr(args, "inputs", None)
    story_ids_raw = getattr(args, "story_ids", None)

    # Parse comma-separated list fields
    new_target_files = [f.strip() for f in target_files_raw.split(",")] if target_files_raw else None
    new_success_criteria = [s.strip() for s in success_criteria_raw.split(",")] if success_criteria_raw else None
    new_inputs = [i.strip() for i in inputs_raw.split(",")] if inputs_raw else None
    new_story_ids = [s.strip() for s in story_ids_raw.split(",")] if story_ids_raw else None

    # Validate: at least one field to update
    has_updates = any([
        new_status, new_description, new_name, new_agent,
        new_target_files, new_success_criteria, new_guidance, new_inputs,
        new_story_ids,
    ])
    if not has_updates:
        print_error("At least one field to update must be provided (--status, --description, --name, --agent, --target-files, --success-criteria, --guidance, --inputs, --story-ids)")
        sys.exit(1)

    # TinyDB-first: update task via EpicRepository
    task_found = False
    updated_file = None
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_epic(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.epic_folder_name == plan_path.name
            )
            if not folder_matches:
                repo = None  # Skip TinyDB path
    except Exception:
        repo = None
    try:
        if repo is not None:
            current_task = repo.get_ticket(plan_path.name, task_id)
            if current_task is not None:
                # Handle status update with transition validation
                if new_status:
                    old_status = current_task.status or "proposed"
                    valid_transitions = {
                        "proposed": ["in_progress", "blocked", "pending"],
                        "pending": ["in_progress", "blocked", "proposed"],
                        "in_progress": ["completed", "blocked", "pending", "proposed"],
                        "completed": ["pending", "in_progress", "proposed"],
                        "blocked": ["pending", "in_progress", "proposed"],
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
                    repo.update_ticket_status(plan_path.name, task_id, new_status)

                # Build generic field updates
                field_updates = {}
                if new_description is not None:
                    field_updates["description"] = new_description
                if new_name is not None:
                    field_updates["name"] = new_name
                if new_agent is not None:
                    field_updates["agent"] = new_agent
                if new_target_files is not None:
                    field_updates["target_files"] = new_target_files
                if new_success_criteria is not None:
                    field_updates["success_criteria"] = new_success_criteria
                if new_guidance is not None:
                    field_updates["guidance"] = new_guidance
                if new_inputs is not None:
                    field_updates["inputs"] = new_inputs
                if new_story_ids is not None:
                    field_updates["story_ids"] = new_story_ids

                if field_updates:
                    repo.update_ticket(plan_path.name, task_id, field_updates)

                task_found = True
                updated_file = "(via TinyDB)"
    except Exception:
        pass

    if not task_found:
        if is_json_output():
            print_json({"error": f"Task not found: {task_id}"})
        else:
            print_error(f"Task not found: {task_id}")
            print("Hint: Use 'agentic epic ticket list' to see available task IDs", file=sys.stderr)
        sys.exit(1)

    if is_json_output():
        result = {
            "task_id": task_id,
            "file": updated_file,
            "note": note,
        }
        if new_status:
            result["new_status"] = new_status
        if new_description:
            result["description"] = new_description
        if new_name:
            result["name"] = new_name
        if new_agent:
            result["agent"] = new_agent
        if new_target_files:
            result["target_files"] = new_target_files
        if new_success_criteria:
            result["success_criteria"] = new_success_criteria
        if new_guidance:
            result["guidance"] = new_guidance
        if new_inputs:
            result["inputs"] = new_inputs
        if new_story_ids:
            result["story_ids"] = new_story_ids
        print_json(result)
    else:
        changes = []
        if new_status:
            changes.append(f"status={new_status}")
        if new_name:
            changes.append(f"name={new_name}")
        if new_description:
            changes.append("description updated")
        if new_agent:
            changes.append(f"agent={new_agent}")
        if new_target_files:
            changes.append(f"target_files={len(new_target_files)} items")
        if new_success_criteria:
            changes.append(f"success_criteria={len(new_success_criteria)} items")
        if new_guidance:
            changes.append("guidance updated")
        if new_inputs:
            changes.append(f"inputs={len(new_inputs)} items")
        if new_story_ids:
            changes.append(f"story_ids={len(new_story_ids)} items")
        print_success(f"Updated task {task_id}: {', '.join(changes)}")


def cmd_task_remove(args, ctx=None):
    """Remove a ticket from the epic.

    Permanently deletes a ticket from TinyDB. Use --force to skip confirmation.

    Args:
        args: Parsed arguments with task_id, plan, force.
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
    plan_path = find_epic_folder(getattr(args, "plan", None))
    force = getattr(args, "force", False)

    # Confirm deletion unless --force
    if not force and not is_json_output():
        print_warning(f"About to permanently remove ticket '{task_id}' from {plan_path.name}")
        response = input("Confirm? [y/N] ")
        if response.lower() != "y":
            print("Aborted")
            sys.exit(0)

    removed = False
    try:
        repo = _get_repo()
        if repo is not None:
            if not _ensure_epic_in_db(repo, plan_path):
                print_error(f"Epic '{plan_path.name}' not found in TinyDB")
                sys.exit(1)
            removed = repo.delete_ticket(plan_path.name, task_id)
    except Exception as e:
        print_error(f"Error removing ticket: {e}")
        sys.exit(1)

    if not removed:
        if is_json_output():
            print_json({"error": f"Ticket not found: {task_id}"})
        else:
            print_error(f"Ticket not found: {task_id}")
            print("Hint: Use 'agentic epic ticket list' to see available ticket IDs", file=sys.stderr)
        sys.exit(1)

    if is_json_output():
        print_json({"task_id": task_id, "removed": True, "epic": plan_path.name})
    else:
        print_success(f"Removed ticket '{task_id}' from {plan_path.name}")


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

    plan_path = find_epic_folder(getattr(args, "plan", None))
    phase_filter = getattr(args, "phase", None)

    # Try PlanRepository (TinyDB) first for both current task and all-tasks stats.
    current_task = None
    all_tasks = None
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_epic(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.epic_folder_name == plan_path.name
            )
            if folder_matches:
                repo_task = repo.get_current_ticket(
                    plan_path.name, phase_name=phase_filter,
                )
                if repo_task is not None:
                    current_task = {
                        "id": repo_task.id,
                        "name": repo_task.name or "",
                        "description": repo_task.description or "",
                        "status": repo_task.status or "pending",
                        "phase": repo_task.phase_name or "",
                        "phase_id": repo_task.phase_name or "",
                        "inputs": repo_task.inputs or [],
                        "target_files": repo_task.target_files or [],
                        "guidance": repo_task.guidance or "",
                        "success_criteria": repo_task.success_criteria or [],
                        "agent_type": repo_task.agent or "",
                        "story_ids": repo_task.story_ids or [],
                        "source_file": "(via TinyDB)",
                    }
                # Get task counts for all-complete check
                counts = repo.get_ticket_counts(plan_path.name)
                all_tasks = counts  # Used for completion stats below
            repo.close()
    except Exception:
        current_task = None
        all_tasks = None

    if current_task is None and all_tasks is None:
        from agenticcli.console import print_error
        print_error(f"No task data found in TinyDB for epic: {plan_path.name}")
        sys.exit(1)

    if is_json_output():
        if current_task:
            print_json({
                "plan_folder": plan_path.name,
                "task": current_task,
                "all_complete": False,
            })
        else:
            total = all_tasks.get("total", 0) if all_tasks else 0
            completed = all_tasks.get("completed", 0) if all_tasks else 0
            print_json({
                "plan_folder": plan_path.name,
                "task": None,
                "all_complete": total > 0 and completed == total,
                "total_tasks": total,
                "completed_tasks": completed,
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

            if current_task.get("story_ids"):
                console.print(f"\n[bold]Affected Stories:[/bold]")
                for sid in current_task["story_ids"]:
                    console.print(f"  - {sid}")

            if current_task.get("success_criteria"):
                console.print(f"\n[bold]Success Criteria:[/bold]")
                for sc in current_task["success_criteria"][:3]:
                    console.print(f"  - {sc}")
        else:
            total = all_tasks.get("total", 0) if all_tasks else 0
            completed = all_tasks.get("completed", 0) if all_tasks else 0
            if total > 0 and completed == total:
                console.print("[green]All tasks completed![/green]")
            else:
                console.print("[dim]No tasks found or no pending tasks.[/dim]")


def cmd_phase_add(args, ctx=None):
    """Add a new phase to the epic in TinyDB.

    Creates a new phase record in TinyDB with the specified ID, name,
    and description.

    Args:
        args: Parsed arguments with id, name, description, plan, agent,
              execution, loop_type, loop_max_iterations, feedback_triggers.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
    )

    phase_id = args.id
    phase_name = args.name
    phase_description = getattr(args, "description", None) or ""
    plan_path = find_epic_folder(getattr(args, "plan", None))

    # New routing/metadata fields
    agent = getattr(args, "agent", None)
    execution = getattr(args, "execution", None)
    loop_type = getattr(args, "loop_type", None)
    loop_max_iterations = getattr(args, "loop_max_iterations", None)
    max_turns = getattr(args, "max_turns", None)
    timeout = getattr(args, "timeout", None)
    feedback_triggers_str = getattr(args, "feedback_triggers", None)

    # Parse --feedback-triggers from comma-separated KEY=VALUE string to dict
    triggers = {}
    if feedback_triggers_str:
        for item in feedback_triggers_str.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                triggers[k.strip()] = v.strip()

    # Validate agent name against roster if provided
    if agent:
        valid_agents = get_valid_agent_types()
        if valid_agents and agent not in valid_agents:
            sorted_agents = sorted(valid_agents)
            print_error(
                f"Unknown agent '{agent}'. Valid agents: {', '.join(sorted_agents)}"
            )
            sys.exit(1)

    # TinyDB-first: add phase via PlanRepository
    tinydb_done = False
    repo = _get_repo()
    if repo is not None:
        # Ensure the epic is registered in TinyDB
        if not _ensure_epic_in_db(repo, plan_path):
            print_error(f"Epic not found in TinyDB: {plan_path.name}")
            sys.exit(1)

        # Check for duplicate by phase_id (primary key)
        existing = repo.get_phase(plan_path.name, phase_id) if phase_id else None
        if not existing:
            existing = repo.get_phase(plan_path.name, phase_name)
        if existing:
            if is_json_output():
                print_json({"status": "exists", "phase": phase_id or phase_name, "message": f"Phase '{phase_id or phase_name}' already exists"})
            else:
                print_success(f"Phase '{phase_id or phase_name}' already exists (skipped)")
            return

        phase_doc = {
            "name": phase_name,
            "phase_id": phase_id,
            "description": phase_description,
            "status": "planning",
        }
        if agent is not None:
            phase_doc["agent"] = agent
        if execution is not None:
            phase_doc["execution"] = execution
        if loop_type is not None:
            phase_doc["loop_type"] = loop_type
        if loop_max_iterations is not None:
            phase_doc["loop_max_iterations"] = loop_max_iterations
        if max_turns is not None:
            phase_doc["max_turns"] = max_turns
        if timeout is not None:
            phase_doc["timeout"] = timeout
        if triggers:
            phase_doc["feedback_triggers"] = triggers

        added = repo.add_phase(plan_path.name, phase_doc)
        if added:
            tinydb_done = True

    if not tinydb_done:
        print_error("Failed to add phase via TinyDB")
        sys.exit(1)

    source = "TinyDB"
    if is_json_output():
        result = {
            "phase_id": phase_id,
            "name": phase_name,
            "description": phase_description,
            "source": source,
            "plan_path": str(plan_path),
        }
        if agent is not None:
            result["agent"] = agent
        if execution is not None:
            result["execution"] = execution
        if loop_type is not None:
            result["loop_type"] = loop_type
        if loop_max_iterations is not None:
            result["loop_max_iterations"] = loop_max_iterations
        if max_turns is not None:
            result["max_turns"] = max_turns
        if triggers:
            result["feedback_triggers"] = triggers
        print_json(result)
    else:
        print_success(f"Added phase '{phase_id}' ({phase_name}) to {plan_path.name} ({source})")


def cmd_phase_list(args, ctx=None):
    """List all phases in the plan with task counts.

    Displays a table showing phase ID, name, status, and task count
    from TinyDB.

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
        print_table,
    )

    plan_path = find_epic_folder(getattr(args, "plan", None))

    # Try PlanRepository for phase data (TinyDB-first)
    phases_data = None
    try:
        repo = _get_repo()
        plan_data_obj = repo.get_epic(plan_path.name)
        if plan_data_obj and plan_data_obj.epic_folder_name == plan_path.name:
            phases_data = []
            for i, phase in enumerate(plan_data_obj.phases):
                phases_data.append({
                    "id": phase.phase_id or f"P{i + 1}",
                    "name": phase.name,
                    "status": phase.status or "planning",
                    "agent": phase.agent or "-",
                    "tasks": len(phase.tasks),
                })
    except Exception:
        phases_data = None

    if phases_data is None:
        print_error(f"No phase data found in TinyDB for epic: {plan_path.name}")
        sys.exit(1)

    if not phases_data:
        if is_json_output():
            print_json({"phases": [], "count": 0})
        else:
            console.print("[dim]No phases found[/dim]")
        return

    if is_json_output():
        print_json({"phases": phases_data, "count": len(phases_data)})
    else:
        print_header(f"Phases in {plan_path.name}")

        rows = []
        for phase in phases_data:
            rows.append([
                f"[bold]{phase['id']}[/bold]",
                phase["name"],
                format_status(phase["status"]),
                phase["agent"],
                f"[cyan]{phase['tasks']}[/cyan]",
            ])

        print_table("", ["ID", "Name", "Status", "Agent", "Tasks"], rows)

        console.print(f"\n[dim]Total: {len(phases_data)} phases[/dim]")


def cmd_phase_update(args, ctx=None):
    """Update a phase in TinyDB.

    Updates the status and/or name of an existing phase by ID.

    Args:
        args: Parsed arguments with phase_id, optional status, optional name, plan.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
        print_warning,
    )

    phase_id = args.phase_id
    new_status = getattr(args, "status", None)
    new_name = getattr(args, "name", None)
    plan_path = find_epic_folder(getattr(args, "plan", None))

    # New routing/metadata fields
    new_agent = getattr(args, "agent", None)
    new_execution = getattr(args, "execution", None)
    new_loop_type = getattr(args, "loop_type", None)
    new_loop_max_iterations = getattr(args, "loop_max_iterations", None)
    new_max_turns = getattr(args, "max_turns", None)
    new_timeout = getattr(args, "timeout", None)
    feedback_triggers_str = getattr(args, "feedback_triggers", None)
    new_blocked_reason = getattr(args, "blocked_reason", None)

    # Parse --feedback-triggers from comma-separated KEY=VALUE string to dict
    new_triggers = None
    if feedback_triggers_str:
        new_triggers = {}
        for item in feedback_triggers_str.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                new_triggers[k.strip()] = v.strip()

    # Validate that at least one update field is provided
    has_updates = any([
        new_status, new_name, new_agent, new_execution,
        new_loop_type, new_loop_max_iterations is not None,
        new_max_turns is not None, new_timeout is not None,
        new_triggers is not None, new_blocked_reason is not None,
    ])
    if not has_updates:
        print_error("At least one field to update must be provided (--status, --name, --agent, --execution, --loop-type, --loop-max-iterations, --max-turns, --timeout, --feedback-triggers, --blocked-reason)")
        sys.exit(1)

    # TinyDB-first: update phase via PlanRepository
    phase_found = False
    old_status = None
    old_name = None
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_epic(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.epic_folder_name == plan_path.name
            )
            if not folder_matches:
                repo = None  # Skip TinyDB path
        if repo is not None:
            phase_obj = repo.get_phase(plan_path.name, phase_id)
            if phase_obj:
                old_status = phase_obj.status or "planning"
                old_name = phase_obj.name

                updates = {}
                if new_status:
                    valid_transitions = {
                        "planning": ["in_progress", "blocked"],
                        "in_progress": ["completed", "blocked", "planning"],
                        "completed": ["planning", "in_progress"],
                        "blocked": ["planning", "in_progress"],
                    }
                    if new_status not in valid_transitions.get(old_status, []) and old_status != new_status:
                        if not is_json_output():
                            print_warning(f"Status transition from '{old_status}' to '{new_status}' for phase {phase_id}")
                    updates["status"] = new_status

                if new_name:
                    updates["name"] = new_name
                if new_agent is not None:
                    updates["agent"] = new_agent
                if new_execution is not None:
                    updates["execution"] = new_execution
                if new_loop_type is not None:
                    updates["loop_type"] = new_loop_type
                if new_loop_max_iterations is not None:
                    updates["loop_max_iterations"] = new_loop_max_iterations
                if new_max_turns is not None:
                    updates["max_turns"] = new_max_turns
                if new_timeout is not None:
                    updates["timeout"] = new_timeout
                if new_triggers is not None:
                    updates["feedback_triggers"] = new_triggers
                if new_blocked_reason is not None:
                    updates["blocked_reason"] = new_blocked_reason

                if updates:
                    updated = repo.update_phase(plan_path.name, phase_id, updates)
                    if updated:
                        phase_found = True
    except Exception:
        pass

    if not phase_found:
        if is_json_output():
            print_json({"error": f"Phase not found: {phase_id}"})
        else:
            print_error(f"Phase not found: {phase_id}")
            print("Hint: Use 'agentic epic phase list' to see available phase IDs", file=sys.stderr)
        sys.exit(1)

    if is_json_output():
        result = {
            "phase_id": phase_id,
            "plan_path": str(plan_path),
        }
        if new_status:
            result["old_status"] = old_status
            result["new_status"] = new_status
        if new_name:
            result["old_name"] = old_name
            result["new_name"] = new_name
        if new_agent is not None:
            result["agent"] = new_agent
        if new_execution is not None:
            result["execution"] = new_execution
        if new_loop_type is not None:
            result["loop_type"] = new_loop_type
        if new_loop_max_iterations is not None:
            result["loop_max_iterations"] = new_loop_max_iterations
        if new_max_turns is not None:
            result["max_turns"] = new_max_turns
        if new_triggers is not None:
            result["feedback_triggers"] = new_triggers
        if new_blocked_reason is not None:
            result["blocked_reason"] = new_blocked_reason
        print_json(result)
    else:
        changes = []
        if new_status:
            changes.append(f"status: {old_status} -> {new_status}")
        if new_name:
            changes.append(f"name: '{old_name}' -> '{new_name}'")
        if new_agent is not None:
            changes.append(f"agent={new_agent}")
        if new_execution is not None:
            changes.append(f"execution={new_execution}")
        if new_loop_type is not None:
            changes.append(f"loop_type={new_loop_type}")
        if new_loop_max_iterations is not None:
            changes.append(f"loop_max_iterations={new_loop_max_iterations}")
        if new_max_turns is not None:
            changes.append(f"max_turns={new_max_turns}")
        if new_triggers is not None:
            changes.append(f"feedback_triggers={len(new_triggers)} items")
        if new_blocked_reason is not None:
            changes.append(f"blocked_reason='{new_blocked_reason}'")
        print_success(f"Updated phase '{phase_id}' in {plan_path.name} ({', '.join(changes)})")


def cmd_phase_remove(args, ctx=None):
    """Remove a phase from the epic.

    Without --cascade, fails if the phase still has tickets.
    With --cascade, also removes all tickets in that phase.

    Args:
        args: Parsed arguments with phase_id, plan, cascade, force.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
        print_warning,
    )

    phase_id = args.phase_id
    plan_path = find_epic_folder(getattr(args, "plan", None))
    cascade = getattr(args, "cascade", False)
    force = getattr(args, "force", False)

    try:
        repo = _get_repo()
        if repo is None:
            print_error("TinyDB repository unavailable")
            sys.exit(1)

        if not _ensure_epic_in_db(repo, plan_path):
            print_error(f"Epic '{plan_path.name}' not found in TinyDB")
            sys.exit(1)

        # Verify the phase exists
        phase_obj = repo.get_phase(plan_path.name, phase_id)
        if phase_obj is None:
            if is_json_output():
                print_json({"error": f"Phase not found: {phase_id}"})
            else:
                print_error(f"Phase not found: {phase_id}")
                print("Hint: Use 'agentic epic phase list' to see available phases", file=sys.stderr)
            sys.exit(1)

        phase_name = phase_obj.name

        # Check for tickets in this phase
        tickets_in_phase = repo.get_tickets_for_phase(plan_path.name, phase_name)
        if tickets_in_phase and not cascade:
            if is_json_output():
                print_json({
                    "error": f"Phase '{phase_id}' has {len(tickets_in_phase)} ticket(s). Use --cascade to remove them too.",
                    "ticket_count": len(tickets_in_phase),
                })
            else:
                print_error(
                    f"Phase '{phase_id}' has {len(tickets_in_phase)} ticket(s). "
                    "Use --cascade to also remove them."
                )
            sys.exit(1)

        # Confirm unless --force
        if not force and not is_json_output():
            cascade_msg = f" and {len(tickets_in_phase)} ticket(s)" if tickets_in_phase else ""
            print_warning(f"About to permanently remove phase '{phase_id}'{cascade_msg} from {plan_path.name}")
            response = input("Confirm? [y/N] ")
            if response.lower() != "y":
                print("Aborted")
                sys.exit(0)

        # Remove cascaded tickets first
        tickets_removed = 0
        if cascade and tickets_in_phase:
            for ticket in tickets_in_phase:
                if repo.delete_ticket(plan_path.name, ticket.id):
                    tickets_removed += 1

        # Remove the phase
        removed = repo.delete_phase(plan_path.name, phase_id)

    except Exception as e:
        print_error(f"Error removing phase: {e}")
        sys.exit(1)

    if not removed:
        if is_json_output():
            print_json({"error": f"Failed to remove phase: {phase_id}"})
        else:
            print_error(f"Failed to remove phase: {phase_id}")
        sys.exit(1)

    if is_json_output():
        print_json({
            "phase_id": phase_id,
            "phase_name": phase_name,
            "removed": True,
            "tickets_removed": tickets_removed,
            "epic": plan_path.name,
        })
    else:
        msg = f"Removed phase '{phase_id}'"
        if tickets_removed:
            msg += f" and {tickets_removed} ticket(s)"
        msg += f" from {plan_path.name}"
        print_success(msg)


def cmd_link(args, ctx=None):
    """Link an epic dependency: epic depends on another epic.

    Usage: agentic epic link --epic A --depends-on B

    Args:
        args: Parsed arguments with epic and depends_on fields.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    epic_name = getattr(args, "epic", None) or getattr(args, "path", None)
    depends_on = getattr(args, "depends_on", None)

    if not epic_name or not depends_on:
        print_error("Usage: agentic epic link --epic <epic> --depends-on <epic>")
        sys.exit(1)

    repo = _get_repo()
    if repo is None:
        print_error("Could not connect to TinyDB repository.")
        sys.exit(1)

    # Resolve epic names
    epic_folder = find_epic_folder(epic_name)
    dep_folder = find_epic_folder(depends_on)

    # Validate via DependencyService
    from agenticguidance.services.dependency import DependencyService

    dep_service = DependencyService(repo)
    valid, message = dep_service.validate_dependency(epic_folder.name, dep_folder.name)
    if not valid:
        if is_json_output():
            print_json({"error": message, "epic": epic_folder.name, "depends_on": dep_folder.name})
        else:
            print_error(message)
        sys.exit(1)

    # Add the dependency
    result = repo.add_dependency(epic_folder.name, dep_folder.name)
    if not result.success:
        if is_json_output():
            print_json({"error": result.message})
        else:
            print_error(result.message)
        sys.exit(1)

    if is_json_output():
        print_json({
            "result": "success",
            "epic": epic_folder.name,
            "depends_on": dep_folder.name,
            "message": result.message,
        })
    else:
        print_success(f"Linked: {epic_folder.name} depends on {dep_folder.name}")


def cmd_unlink(args, ctx=None):
    """Remove an epic dependency.

    Usage: agentic epic unlink --epic A --depends-on B

    Args:
        args: Parsed arguments with epic and depends_on fields.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    epic_name = getattr(args, "epic", None) or getattr(args, "path", None)
    depends_on = getattr(args, "depends_on", None)

    if not epic_name or not depends_on:
        print_error("Usage: agentic epic unlink --epic <epic> --depends-on <epic>")
        sys.exit(1)

    repo = _get_repo()
    if repo is None:
        print_error("Could not connect to TinyDB repository.")
        sys.exit(1)

    epic_folder = find_epic_folder(epic_name)
    dep_folder = find_epic_folder(depends_on)

    result = repo.remove_dependency(epic_folder.name, dep_folder.name)
    if not result.success:
        if is_json_output():
            print_json({"error": result.message})
        else:
            print_error(result.message)
        sys.exit(1)

    if is_json_output():
        print_json({
            "result": "success",
            "epic": epic_folder.name,
            "removed_dependency": dep_folder.name,
            "message": result.message,
        })
    else:
        print_success(f"Unlinked: {epic_folder.name} no longer depends on {dep_folder.name}")


# Priority mapping: int→label for display, label→int for input conversion.
# @story US-001
_INT_TO_LABEL: dict[int, str] = {1: "critical", 2: "high", 3: "medium", 4: "low"}
_LABEL_TO_INT: dict[str, int] = {v: k for k, v in _INT_TO_LABEL.items()}


def _to_int_priority(value) -> int:
    """Convert a priority value to int (1-4).

    Handles int, numeric string, label string, or None.
    Returns 3 (medium) for unrecognised or missing values.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return _LABEL_TO_INT.get(value.lower(), 3)
    return 3


def _format_priority(value) -> str:
    """Format an int priority as 'N (label)' for display."""
    n = _to_int_priority(value)
    label = _INT_TO_LABEL.get(n, "medium")
    return f"{n} ({label})"


def cmd_set_priority(args, ctx=None):
    """Set the priority of an epic.

    Usage: agentic epic set-priority --epic A --priority 2
           agentic epic set-priority --epic A --priority high

    Accepts both numeric (1-4) and label (critical/high/medium/low) values.

    Args:
        args: Parsed arguments with epic and priority fields.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import is_json_output, print_error, print_json, print_success

    epic_name = getattr(args, "epic", None) or getattr(args, "path", None)
    raw_priority = getattr(args, "priority", None)

    if not epic_name or not raw_priority:
        print_error("Usage: agentic epic set-priority --epic <epic> --priority <1-4 | critical|high|medium|low>")
        sys.exit(1)

    # Validate and convert to int
    int_priority = _to_int_priority(raw_priority)
    if int_priority not in _INT_TO_LABEL:
        print_error(f"Invalid priority: {raw_priority}. Valid: 1 (critical), 2 (high), 3 (medium), 4 (low)")
        sys.exit(1)

    # Extra guard: reject values that didn't match any known label or 1-4 range
    if isinstance(raw_priority, str) and raw_priority.lower() not in _LABEL_TO_INT and raw_priority not in ("1", "2", "3", "4"):
        print_error(f"Invalid priority: {raw_priority}. Valid: 1 (critical), 2 (high), 3 (medium), 4 (low)")
        sys.exit(1)

    repo = _get_repo()
    if repo is None:
        print_error("Could not connect to TinyDB repository.")
        sys.exit(1)

    epic_folder = find_epic_folder(epic_name)
    result = repo.update_epic(epic_folder.name, {"priority": int_priority})

    if not result.success:
        if is_json_output():
            print_json({"error": result.message})
        else:
            print_error(result.message)
        sys.exit(1)

    label = _INT_TO_LABEL[int_priority]
    if is_json_output():
        print_json({
            "result": "success",
            "epic": epic_folder.name,
            "priority": int_priority,
        })
    else:
        print_success(f"Set priority of {epic_folder.name} to {int_priority} ({label})")


