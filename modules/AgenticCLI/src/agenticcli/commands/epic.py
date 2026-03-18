"""Epic management commands.

Handles epic folder operations and ticket tracking.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# Cache for dynamic agent type discovery
_agent_types_cache: set | None = None

# Fallback set used when filesystem scanning fails
_FALLBACK_AGENT_TYPES = {
    "build-python", "build-flutter",
    "deploy-cicd",
    "orchestration-executor", "orchestration-planning", "orchestration-friction",
    "planner-build", "planner-test", "planner-guidance", "planner-cleaning",
    "planner-reviewer", "planner-audit", "planner-orchestration", "planner-guidance-testing",
    "teacher-update-guidance", "teacher-update-assets", "teacher-trace-diagnostics",
    "test-runner", "test-builder", "test-guidance-simulator", "test-final-output",
    "test-audit", "test-user-simulator", "test-service",
}


def get_valid_agent_types(agents_dir: Path | None = None) -> set[str]:
    """Discover valid agent types by scanning the agents directory.

    Scans modules/AgenticGuidance/agents/**/ for directories that represent
    agent types (leaf directories under category folders). Falls back to a
    hardcoded set if the directory is not found.

    Args:
        agents_dir: Optional override for the agents directory path.

    Returns:
        Set of valid agent type names (e.g., {"build-python", "test-runner"}).
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
    """Derive the repo-local TinyDB path (.agentic/epics.db under repo root).

    Matches the path that EpicService uses so reads and writes hit the same DB.
    """
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists():
            return current / ".agentic" / "epics.db"
        current = current.parent
    return Path.home() / ".agentic" / "epics.db"


def _get_repo():
    """Get EpicRepository instance for TinyDB-backed epic access.

    Uses the repo-local DB path (matching EpicService) and disables
    auto_bootstrap to avoid side-effects in test environments.
    """
    from agenticguidance.services.epic_repository import EpicRepository
    return EpicRepository(db_path=_get_repo_db_path(), auto_bootstrap=False)


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
    try:
        repo = _get_repo()
        phases = repo.list_phases(epic_folder_name)
        repo.close()
        if phases and any(phase.agent for phase in phases):
            return True
    except Exception:
        pass
    return False


def _ensure_epic_in_db(repo, plan_path: Path) -> bool:
    """Ensure the epic folder is registered in TinyDB.

    If the epic folder exists on disk but is not yet in TinyDB, this
    function auto-registers it so that subsequent phase/ticket operations
    succeed.

    Args:
        repo: EpicRepository instance.
        plan_path: Path to the epic folder on disk.

    Returns:
        True if the epic is now present in TinyDB (either already existed
        or was just created), False on failure.
    """
    plan_doc = repo.get_epic(plan_path.name)
    if plan_doc is not None:
        # Already registered - check folder matches
        if plan_doc.epic_folder.resolve() == plan_path.resolve():
            return True
        # Folder path is stale - resync it
        repo.resync_epic_folder(plan_path.name, str(plan_path))
        return True

    # Epic folder exists on disk but not in DB - auto-register it
    if plan_path.is_dir():
        result = repo.create_epic({
            "epic_folder_name": plan_path.name,
            "epic_folder": str(plan_path),
            "name": plan_path.name,
            "status": "active",
        })
        return result.success

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
    elif args.epic_command == "init":
        cmd_init(args, ctx)
    elif args.epic_command == "bootstrap":
        cmd_bootstrap(args, ctx)
    elif args.epic_command == "scaffold":
        cmd_scaffold(args)
    elif args.epic_command == "status":
        cmd_status(args)
    elif args.epic_command == "validate":
        cmd_validate(args)
    elif args.epic_command == "ticket":
        if args.ticket_action == "start":
            cmd_task_start(args)
        elif args.ticket_action == "complete":
            cmd_task_complete(args)
        elif args.ticket_action == "prefill":
            cmd_task_prefill(args, ctx)
        elif args.ticket_action == "list":
            cmd_task_list(args, ctx)
        elif args.ticket_action == "status":
            cmd_task_status(args, ctx)
        elif args.ticket_action == "add":
            cmd_task_add(args, ctx)
        elif args.ticket_action == "update":
            cmd_task_update(args, ctx)
        elif args.ticket_action == "remove":
            cmd_task_remove(args, ctx)
        elif args.ticket_action == "batch":
            cmd_task_batch(args, ctx)
        elif args.ticket_action == "current":
            cmd_task_current(args, ctx)
        else:
            print("Usage: agentic epic ticket <start|complete|prefill|list|status|add|update|remove|batch|current> ...", file=sys.stderr)
            sys.exit(1)
    elif args.epic_command == "archive":
        cmd_archive(args)
    elif args.epic_command == "unarchive":
        cmd_unarchive(args, ctx)
    elif args.epic_command == "list":
        cmd_list(args)
    elif args.epic_command == "move":
        cmd_move(args, ctx)
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
    elif args.epic_command == "replan":
        cmd_replan(args, ctx)
    elif args.epic_command == "orchestration":
        if args.orchestration_action == "generate":
            cmd_orchestration_generate(args, ctx)
        elif args.orchestration_action == "validate":
            cmd_orchestration_validate(args, ctx)
        else:
            print("Usage: agentic epic orchestration <generate|validate>", file=sys.stderr)
            sys.exit(1)
    elif args.epic_command == "stories":
        if args.stories_action == "list":
            cmd_stories_list(args, ctx)
        elif args.stories_action == "test":
            cmd_stories_test(args, ctx)
        else:
            print("Usage: agentic epic stories <list|test>", file=sys.stderr)
            sys.exit(1)
    elif args.epic_command == "cancel":
        cmd_cancel(args, ctx)
    elif args.epic_command == "db":
        if args.db_action == "sync":
            cmd_db_sync(args)
        elif args.db_action == "status":
            cmd_db_status(args)
        else:
            print("Usage: agentic epic db <sync|status>", file=sys.stderr)
            sys.exit(1)
    else:
        print("Usage: agentic epic <new|init|scaffold|status|validate|ticket|archive|unarchive|list|move|phase|orchestration|stories|db|cancel>", file=sys.stderr)
        sys.exit(1)


def find_epic_folder(path: str | None = None) -> Path:
    """Find the active plan folder.

    Args:
        path: Explicit path to plan folder, or None to auto-detect.
              Can be a full path, or a partial folder name to search for
              in docs/epics/live/ (e.g., "260129FI" matches "260129FI_cli_bug_fixes").

    Returns:
        Path to the plan folder.
    """
    if path:
        # First check if path exists as-is
        path_obj = Path(path)
        if path_obj.exists() and path_obj.is_dir():
            return path_obj

        # Path doesn't exist - search for matching folder in docs/epics/live/
        # Find repo root to locate plans directory
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            # Not in a git repo, can't search for plans
            print(f"Error: Path '{path}' not found and not in a git repository.", file=sys.stderr)
            sys.exit(1)

        plans_live_dir = repo_root / "docs" / "epics" / "live"

        # Search for matching folders
        search_name = path_obj.name if path_obj.name else path

        # Try PlanRepository for faster lookup (only trust results inside this repo)
        try:
            from agenticguidance.services.epic_repository import EpicRepository
            repo = EpicRepository(db_path=_get_repo_db_path(), auto_bootstrap=False)
            plan_data = repo.get_epic(search_name)
            if plan_data and plan_data.epic_folder.is_dir():
                # Only accept if the plan folder belongs to this repo tree
                try:
                    plan_data.epic_folder.relative_to(repo_root)
                except ValueError:
                    repo.close()
                    pass  # Plan folder is outside this repo - fall through
                else:
                    resolved_folder = plan_data.epic_folder
                    # Live-preference: if TinyDB points to completed/ but a
                    # live/ version exists, prefer live/ and auto-correct TinyDB.
                    if "/epics/completed/" in str(resolved_folder):
                        live_path = Path(
                            str(resolved_folder).replace(
                                "/epics/completed/", "/epics/live/"
                            )
                        )
                        if live_path.is_dir():
                            resolved_folder = live_path
                            try:
                                repo.resync_epic_folder(
                                    plan_data.epic_folder_name,
                                    str(live_path),
                                )
                            except Exception:
                                pass  # Non-fatal: TinyDB correction is best-effort
                    repo.close()
                    return resolved_folder
            else:
                repo.close()
        except Exception:
            pass

        if plans_live_dir.exists():
            # Search for matching folders
            exact_match = None
            partial_matches = []

            for item in plans_live_dir.iterdir():
                if item.is_dir():
                    if item.name == search_name:
                        # Exact match - return immediately
                        exact_match = item
                        break
                    elif item.name.startswith(search_name):
                        # Partial match (e.g., "260129FI" matches "260129FI_cli_bug_fixes")
                        partial_matches.append(item)

            if exact_match:
                return exact_match
            if partial_matches:
                # Return first partial match (sorted for consistency)
                partial_matches.sort(key=lambda p: p.name)
                return partial_matches[0]

        # No match found
        print(f"Error: Plan folder '{path}' not found.", file=sys.stderr)
        sys.exit(1)

    # Auto-detect: check if we're in an epic folder or find one via TinyDB
    cwd = Path.cwd()

    # Check if we're in a plan folder (check TinyDB for current directory)
    try:
        repo = _get_repo()
        if repo is not None:
            # Check if cwd IS an epic folder known to TinyDB
            epic_doc = repo.get_epic(cwd.name)
            if epic_doc is not None and epic_doc.epic_folder.resolve() == cwd.resolve():
                return cwd

            # Find first live epic from TinyDB
            from agenticguidance.services.epic import EpicService
            svc = EpicService()
            metas = svc.list_epics(status="live")
            for meta in metas:
                if meta.epic_folder.is_dir():
                    return meta.epic_folder
    except Exception:
        pass

    # Filesystem fallback: check docs/epics/live/ for any epic subdirectory
    epics_dir = cwd / "docs" / "epics" / "live"
    if epics_dir.exists():
        for item in sorted(epics_dir.iterdir()):
            if item.is_dir():
                return item

    print("Error: Could not find a plan folder. Specify path explicitly.", file=sys.stderr)
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
    """Create a new plan and optionally spawn a planner agent.

    Automates the full planning loop:
    1. Creates plan folder via plan init logic
    2. [Phase 2] Spawns planner agent session (not yet implemented)
    3. [Phase 3] Generates orchestration MMD (not yet implemented)
    4. [Phase 4] Spawns builder agents with --execute (not yet implemented)

    Args:
        args: Parsed command arguments with:
            - objective: Planning objective description
            - branch: Optional git branch name
            - description: Optional plan description suffix
            - base: Base branch (default: main)
            - execute: Auto-execute flag
            - max_turns: Max turns for planner agent
            - dangerously_skip_permissions: Skip permissions flag
        ctx: Optional CLIContext.

    Returns:
        dict with plan_folder, branch, objective on success.

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
        print_warning,
    )

    objective = getattr(args, "objective", None)
    if not objective:
        print_error("Objective is required. Usage: agentic epic new \"your objective\"")
        sys.exit(1)

    branch = getattr(args, "branch", None)
    description = getattr(args, "description", None)
    base = getattr(args, "base", "main")
    execute = getattr(args, "execute", False)
    max_turns = getattr(args, "max_turns", 25)
    dangerously_skip_permissions = getattr(args, "dangerously_skip_permissions", False)

    # Auto-generate branch name from objective if not provided
    if not branch:
        branch = _slugify_objective(objective)

    # Use objective as description if not provided
    if not description:
        description = objective

    if not is_json_output():
        print_info(f"Creating plan for: {objective}")
        print_info(f"Branch: {branch}")

    # Step 1: Create plan folder by delegating to cmd_init
    # Suppress cmd_init's own output (we produce our own summary)
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

    # Capture cmd_init stdout so it doesn't leak into our output
    init_stdout = io.StringIO()
    with redirect_stdout(init_stdout):
        cmd_init(init_args, ctx)

    if was_json:
        _set_json(True)

    # If we get here, init succeeded. Find the created plan record from TinyDB.
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
        _init_repo = EpicRepository(db_path=_get_repo_db_path(), auto_bootstrap=False)
        epic_doc = _init_repo.get_epic(plan_folder_name)
        _init_repo.close()
        if epic_doc is not None:
            plan_folder = epic_doc.epic_folder
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

    # Step 2: Spawn planner agent
    from agenticcli.console import console, get_status
    from agenticcli.utils.planner_prompt import build_planner_prompt

    if not is_json_output():
        print_info("[Step 2] Spawning planner agent...")

    # Build planner prompt
    planner_prompt = build_planner_prompt(objective, plan_folder)

    # Try SDK-first path for plan generation
    from agenticcli.utils.sdk_runner import SDK_AVAILABLE, run_agent_sync

    planner_stdout = ""
    planner_stderr = ""
    planner_exitcode = 0

    if SDK_AVAILABLE:
        # SDK path: run planner agent via SDK (no subprocess needed)
        try:
            from claude_agent_sdk import ClaudeAgentOptions
            from agenticcli.utils.subprocess_utils import get_clean_env
            sdk_options = ClaudeAgentOptions(
                permission_mode="bypassPermissions",
                cwd=str(plan_folder),
                env=get_clean_env(),
            )
        except ImportError:
            sdk_options = None

        if not is_json_output():
            status_message = "Running planner agent (SDK)..."
            with get_status(status_message):
                sdk_result = run_agent_sync(planner_prompt, sdk_options, timeout_seconds=1800)
        else:
            sdk_result = run_agent_sync(planner_prompt, sdk_options, timeout_seconds=1800)

        planner_stdout = sdk_result.result
        planner_exitcode = 0 if sdk_result.status == "completed" else 1
        if sdk_result.status != "completed":
            planner_stderr = sdk_result.result
    else:
        # Subprocess fallback: use claude CLI in -p (pipe/print) mode.
        # NOTE: -p must come last since it consumes the next argument as prompt.
        claude_cmd = ["claude"]
        if dangerously_skip_permissions:
            claude_cmd.append("--dangerously-skip-permissions")
        if max_turns:
            claude_cmd.extend(["--max-turns", str(max_turns)])
        claude_cmd.extend(["-p", planner_prompt])

        try:
            if not is_json_output():
                status_message = "Running planner agent..."
                with get_status(status_message):
                    result = subprocess.run(
                        claude_cmd,
                        cwd=plan_folder,
                        capture_output=True,
                        text=True,
                    )
                    planner_stdout = result.stdout
                    planner_stderr = result.stderr
                    planner_exitcode = result.returncode
            else:
                # In JSON mode, run without status indicator
                result = subprocess.run(
                    claude_cmd,
                    cwd=plan_folder,
                    capture_output=True,
                    text=True,
                )
                planner_stdout = result.stdout
                planner_stderr = result.stderr
                planner_exitcode = result.returncode

        except FileNotFoundError:
            print_error("Claude CLI not found. Make sure 'claude' is installed and in PATH.")
            sys.exit(1)
        except Exception as e:
            print_error(f"Failed to spawn planner: {e}")
            sys.exit(1)

    # Validate that the planner created tickets in TinyDB
    planner_created_tickets = False
    try:
        from agenticguidance.services.epic_repository import EpicRepository
        _repo = EpicRepository(db_path=_get_repo_db_path(), auto_bootstrap=False)
        _tickets = _repo.get_tickets(plan_folder.name)
        # Check if planner added tickets beyond the initial IM_001 stub
        planner_created_tickets = len(_tickets) > 1 or (
            len(_tickets) == 1 and _tickets[0].id != "IM_001"
        )
        _repo.close()
    except Exception:
        pass

    if not planner_created_tickets:
        if not is_json_output():
            print_error("Planner did not create tickets in TinyDB")
            if planner_stdout:
                console.print("[yellow]Planner output:[/yellow]")
                console.print(planner_stdout)
            if planner_stderr:
                console.print("[red]Planner errors:[/red]")
                console.print(planner_stderr)
        sys.exit(1)

    if not is_json_output():
        if planner_exitcode == 0:
            print_success("Planner agent completed")
        else:
            print_error(f"Planner agent failed with exit code {planner_exitcode}")
            if planner_stderr:
                console.print(f"[red]{planner_stderr}[/red]")

    # Step 3: Generate orchestration MMD (Phase 3)
    if not is_json_output():
        print_info("[Step 3] Generating orchestration MMD...")

    # Generate orchestration by calling cmd_orchestration_generate
    orch_args = SimpleNamespace(
        plan=str(plan_folder),
        output=None,  # Use default naming
        force=True,  # Overwrite if exists
    )

    orchestration_success = False
    try:
        # Suppress orchestration output - we produce our own summary
        orch_stdout = io.StringIO()
        with redirect_stdout(orch_stdout):
            cmd_orchestration_generate(orch_args, ctx)
        orchestration_success = True
        if not is_json_output():
            print_success("Orchestration MMD generated")
    except SystemExit as e:
        if e.code != 0:
            if not is_json_output():
                print_warning("Orchestration generation failed - you can generate it manually later")
                print_warning("  Run: agentic epic orchestration generate --plan " + str(plan_folder))
        else:
            orchestration_success = True
    except Exception as e:
        if not is_json_output():
            print_warning(f"Orchestration generation failed: {e}")
            print_warning("  You can generate it manually later with:")
            print_warning("  agentic epic orchestration generate --plan " + str(plan_folder))

    # Step 3b: Validate orchestration MMD (Phase 3)
    validation_success = False
    if orchestration_success:
        if not is_json_output():
            print_info("[Step 3b] Validating orchestration MMD...")

        validate_args = SimpleNamespace(
            plan=str(plan_folder),
            strict=False,
        )

        try:
            # Suppress validation output
            val_stdout = io.StringIO()
            with redirect_stdout(val_stdout):
                cmd_orchestration_validate(validate_args, ctx)
            validation_success = True
            if not is_json_output():
                print_success("Orchestration validation passed")
        except SystemExit as e:
            if e.code == 0:
                validation_success = True
            else:
                if not is_json_output():
                    print_warning("Orchestration validation found issues")
                    if execute:
                        print_error("Cannot execute with invalid orchestration. Fix issues and retry with --execute.")
                        execute = False  # Block execution
        except Exception as e:
            if not is_json_output():
                print_warning(f"Orchestration validation failed: {e}")
                if execute:
                    print_error("Cannot execute without valid orchestration.")
                    execute = False

    # If --execute was NOT passed, stop here
    if not execute:
        # Skip to result reporting
        pass
    else:
        # Step 4: Spawn builder agents (Phase 4)
        if not is_json_output():
            print_info("[Step 4] Spawning builder agents...")

        # Read phases and tasks via PlanRepository (TinyDB-first)
        plan_folder_name = plan_folder.name
        phases = None
        try:
            repo = _get_repo()
            plan_data_obj = repo.get_epic(plan_folder_name)
            if (plan_data_obj and plan_data_obj.phases
                    and plan_data_obj.epic_folder == plan_folder):
                phases = [
                    {
                        "name": phase.name,
                        "execution": phase.execution or "sequential",
                        "tickets": [
                            {"id": t.id, "name": t.name, "status": t.status or "pending"}
                            for t in (phase.tasks or [])
                        ],
                    }
                    for phase in plan_data_obj.phases
                ]
        except Exception:
            pass

        if phases is None:
            if not is_json_output():
                print_error("No phase data found in TinyDB for this epic - cannot spawn builders")
            phases = []

        if phases:
            try:

                total_tasks = 0
                spawned_sessions = []

                for phase_idx, phase in enumerate(phases, 1):
                    phase_name = phase.get("name", f"Phase {phase_idx}")
                    execution_mode = phase.get("execution", "sequential")
                    tasks = phase.get("tickets", [])

                    if not tasks:
                        continue

                    if not is_json_output():
                        print_info(f"  Phase {phase_idx}: {phase_name} ({len(tasks)} tasks, {execution_mode})")

                    # Spawn sessions for each task in this phase
                    phase_sessions = []
                    for task in tasks:
                        task_id = task.get("id", "")
                        if not task_id:
                            continue

                        # Check if task is already completed
                        task_status = task.get("status", "pending")
                        if task_status == "completed":
                            if not is_json_output():
                                print_info(f"    Task {task_id}: already completed (skipped)")
                            continue

                        # Legacy path: uses --task instead of --role, not eligible for build_spawn_command.
                        spawn_cmd = ["agentic", "session", "spawn", "--task", task_id, "--epic", str(plan_folder)]
                        if dangerously_skip_permissions:
                            spawn_cmd.append("--dangerously-skip-permissions")

                        # Use SDK for task spawning when available (avoids PID polling)
                        from agenticcli.utils.sdk_runner import SDK_AVAILABLE as _PLAN_SDK_AVAILABLE
                        if _PLAN_SDK_AVAILABLE:
                            try:
                                from agenticcli.utils.sdk_runner import run_agent_sync as _plan_run_sdk
                                task_prompt = (
                                    f"Execute task {task_id} from plan {str(plan_folder).split('/')[-1]}.\n"
                                    f"Run: agentic -j agent plan task start {task_id} --plan {str(plan_folder).split('/')[-1]}\n"
                                    "Then complete the task as described in the plan."
                                )
                                from agenticcli.utils.subprocess_utils import get_clean_env as _get_clean
                                from claude_agent_sdk import ClaudeAgentOptions as _TaskOptions
                                phase_sessions.append({
                                    "task_id": task_id,
                                    "sdk_prompt": task_prompt,
                                    "sdk_options": _TaskOptions(
                                        permission_mode="bypassPermissions",
                                        env=_get_clean(),
                                    ),
                                    "command": " ".join(spawn_cmd),
                                    "use_sdk": True,
                                })
                                total_tasks += 1
                                if not is_json_output():
                                    print_info(f"    Task {task_id}: queued for SDK execution")
                            except Exception as e:
                                if not is_json_output():
                                    print_error(f"    Task {task_id}: failed to queue - {e}")
                        else:
                            # Subprocess fallback: spawn via Popen
                            try:
                                proc = subprocess.Popen(
                                    spawn_cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True,
                                )
                                phase_sessions.append({
                                    "task_id": task_id,
                                    "process": proc,
                                    "command": " ".join(spawn_cmd),
                                    "use_sdk": False,
                                })
                                total_tasks += 1
                                if not is_json_output():
                                    print_info(f"    Task {task_id}: spawned (PID {proc.pid})")
                            except Exception as e:
                                if not is_json_output():
                                    print_error(f"    Task {task_id}: failed to spawn - {e}")

                    spawned_sessions.extend(phase_sessions)

                    # If phase is sequential, wait for all tasks to complete before next phase
                    if execution_mode == "sequential" and phase_sessions:
                        if not is_json_output():
                            print_info(f"  Waiting for phase {phase_idx} to complete...")

                        for session in phase_sessions:
                            try:
                                if session.get("use_sdk"):
                                    from agenticcli.utils.sdk_runner import run_agent_sync as _wait_sdk
                                    sdk_res = _wait_sdk(
                                        session["sdk_prompt"],
                                        session.get("sdk_options"),
                                        timeout_seconds=1800,
                                    )
                                    if not is_json_output():
                                        if sdk_res.status == "completed":
                                            print_success(f"    Task {session['task_id']}: completed")
                                        else:
                                            print_error(f"    Task {session['task_id']}: failed")
                                else:
                                    session["process"].wait()
                                    if not is_json_output():
                                        exit_code = session["process"].returncode
                                        if exit_code == 0:
                                            print_success(f"    Task {session['task_id']}: completed")
                                        else:
                                            print_error(f"    Task {session['task_id']}: failed (exit code {exit_code})")
                            except Exception as e:
                                if not is_json_output():
                                    print_error(f"    Task {session['task_id']}: error waiting - {e}")

                if not is_json_output():
                    if total_tasks > 0:
                        print_success(f"Spawned {total_tasks} builder sessions")
                    else:
                        print_warning("No tasks to spawn (all completed or no pending tasks)")

                # Step 5: Check plan completion status
                if not is_json_output():
                    print_info("[Step 5] Checking plan completion status...")

                if is_epic_fully_completed(plan_folder):
                    if not is_json_output():
                        print_success("All tasks completed!")
                else:
                    if not is_json_output():
                        # Count remaining tasks
                        remaining = []
                        for phase in phases:
                            for task in phase.get("tickets", []):
                                if task.get("status", "pending") != "completed":
                                    remaining.append(task.get("id", "unknown"))

                        print_info(f"Plan incomplete: {len(remaining)} tasks remaining")
                        if remaining[:3]:  # Show first 3
                            print_info("  Remaining tasks: " + ", ".join(remaining[:3]))
                            if len(remaining) > 3:
                                print_info(f"    ... and {len(remaining) - 3} more")

            except Exception as e:
                if not is_json_output():
                    print_error(f"Failed to spawn builders: {e}")

    # Return result
    result_data = {
        "plan_folder": str(plan_folder),
        "branch": branch,
        "objective": objective,
        "execute": execute,
        "max_turns": max_turns,
    }

    if is_json_output():
        print_json(result_data)
    else:
        print_success(f"Epic created: {plan_folder.name}")
        print(f"  Plan folder: {plan_folder}")
        print(f"  Branch: {branch}")
        print(f"  Objective: {objective}")
        if not execute:
            print()
            print("  Next steps:")
            print(f"    1. Review plan: agentic epic status {plan_folder}")
            print(f"    2. Execute: agentic epic new \"{objective}\" --execute")

    return result_data


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

    # Compute plan path (no folder creation — TinyDB is the sole data store)
    plan_path = repo_root / "docs" / "epics" / "live" / plan_folder_name

    # Create epic in TinyDB
    objective = getattr(args, "objective", None)

    # Create epic in TinyDB (primary data store)
    try:
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_get_repo_db_path(), auto_bootstrap=False)
        epic_data = {
            "epic_folder_name": plan_folder_name,
            "epic_folder": str(plan_path),
            "name": description,
            "branch": branch,
            "status": "active",
            "priority": "high",
        }
        if objective:
            epic_data["context"] = objective
        create_result = repo.create_epic(epic_data)
        if not create_result.success:
            repo.close()
            print_error(f"Epic already exists: {plan_folder_name}")
            sys.exit(2)
        # Also create a default ticket for the initial phase
        if objective:
            repo.add_phase(
                plan_folder_name,
                {
                    "name": "Initial Research and Planning",
                },
            )
            repo.add_ticket(
                plan_folder_name,
                "Initial Research and Planning",
                {
                    "task_id": "IM_001",
                    "name": "Research existing implementation",
                    "description": "Analyze the codebase to understand how to implement the objective.",
                    "status": "pending",
                },
            )
        repo.close()
    except Exception:
        pass

    # Output results
    result_data = {
        "branch": branch,
        "base": base,
        "epic_folder": str(plan_path),
        "epic_folder_name": plan_folder_name,
    }
    if objective:
        result_data["objective"] = objective

    if is_json_output():
        print_json(result_data)
    else:
        console.print(f"  [green]Created epic folder[/green] at {plan_path}")
        if objective:
            console.print(f"  [green]Epic created in TinyDB[/green] with objective")
        console.print()
        print_success(f"Epic initialized: {plan_folder_name}")
        console.print(f"[dim]Epic folder:[/dim] {plan_path}")
        console.print()
        console.print("[dim]Link related user stories in inputs.yml:[/dim]")
        console.print(f"[dim]  agentic stories find --project <name>[/dim]")
        console.print(f"[dim]  agentic stories untested --project <name>[/dim]")


def cmd_scaffold(args):
    """Create planning folder structure (DEPRECATED - use 'agentic epic init' instead)."""
    from agenticcli.console import is_json_output, print_json

    name = args.name
    base_path = Path.cwd()

    plan_path = base_path / "docs" / "epics" / "live" / name

    # Print deprecation warning
    if not is_json_output():
        print("\n[WARNING] 'agentic plan scaffold' is DEPRECATED", file=sys.stderr)
        print("Use 'agentic epic init <branch> --description <description>' instead", file=sys.stderr)
        print("The scaffold command creates only the folder structure.\n", file=sys.stderr)

    # Create epic in TinyDB (primary data store — no folder creation)
    try:
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=_get_repo_db_path(), auto_bootstrap=False)
        repo.create_epic({
            "epic_folder_name": name,
            "epic_folder": str(plan_path),
            "name": name,
            "status": "active",
        })
        repo.close()
    except Exception:
        pass

    if is_json_output():
        print_json({"name": name, "path": str(plan_path), "folder": str(plan_path), "deprecated": True})
    else:
        print(f"Created planning folder: {plan_path}")
        print(f"  (epic data stored in TinyDB)")
        print("\n[RECOMMENDED] Next time, use: agentic epic init <branch> --description <description>")


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
        "active": ("Spawn planning agent", f"agentic session orchestrate planning --epic {epic_folder_name}"),
        "planning": ("Planning in progress", None),
        "in_progress": ("Execute current ticket", f"agentic epic ticket current --epic {epic_folder_name}"),
        "completed": ("Archive epic", f"agentic epic move folder --epic {epic_folder_name}"),
        "deferred": ("Resolve blockers", None),
        "blocked": ("Resolve blockers", None),
    }
    next_action, next_command = _status_actions.get(plan_status, ("Check epic state", None))

    if is_json_output():
        print_json(
            {
                "plan": plan_path.name,
                "status": plan_status,
                "has_orchestration": has_orchestration,
                "next_action": next_action,
                "next_command": next_command,
                "deferred_reason": deferred_reason,
                "files": file_stats,
                "totals": {
                    "pending": total_pending,
                    "completed": total_completed,
                },
                "progress_percent": round(pct, 1),
            }
        )
    else:
        print_header(f"Epic Status: {plan_path.name}")

        # EN-003: Show orchestration status
        if has_orchestration:
            console.print(f"[bold]Orchestration:[/bold] [green]Phases in TinyDB[/green]")
        else:
            console.print("[bold]Orchestration:[/bold] [red]MISSING[/red]")
            console.print("  Run: agentic session orchestrate planning --epic <folder>")

        console.print(f"[bold]Status:[/bold] {plan_status}")

        # EN-004: Show deferred reason
        if deferred_reason:
            console.print(f"[bold]Deferred Reason:[/bold] [yellow]{deferred_reason}[/yellow]")

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



def _parse_mmd_phases(mmd_content: str) -> list[str]:
    """Parse phase IDs from MMD file content.

    Looks for:
    - subgraph patterns: subgraph "Phase 1: Name" or subgraph Phase1_SG
    - Phase node patterns: P1[...], Phase1[...]

    Args:
        mmd_content: Raw MMD file content.

    Returns:
        List of phase IDs found (e.g., ["P1", "P2", "P3"]).
    """
    import re

    phases = set()

    # Pattern 1: subgraph "Phase N: Name" or subgraph Phase_N_SG
    # Examples: subgraph "Phase 1: Plan List Enhancement"
    subgraph_pattern = r'subgraph\s+["\']?(?:Phase\s*)?(\d+|P\d+)[:\s]'
    for match in re.finditer(subgraph_pattern, mmd_content, re.IGNORECASE):
        phase_num = match.group(1)
        if phase_num.isdigit():
            phases.add(f"P{phase_num}")
        else:
            phases.add(phase_num.upper())

    # Pattern 2: subgraph with ID like "Phase1_SG" or "CLISessionCommands_SG"
    # We skip these as they are internal subgraph names, not phase IDs

    # Pattern 3: Phase node definitions like P1[P1: description] or P1[Enter Phase 1]
    phase_node_pattern = r'\b(P\d+)\s*\['
    for match in re.finditer(phase_node_pattern, mmd_content):
        phases.add(match.group(1).upper())

    return sorted(phases)


def _parse_mmd_tasks(mmd_content: str) -> list[str]:
    """Parse task IDs from MMD file content.

    Looks for task node patterns like:
    - P1_T1[EN-001: description]
    - EN-001, EN-002, CC-001, etc.

    Args:
        mmd_content: Raw MMD file content.

    Returns:
        List of task IDs found.
    """
    import re

    tasks = set()

    # Pattern: Task IDs like EN-001, CC-001, etc. (2-3 letter prefix + hyphen + 3 digits)
    task_id_pattern = r'\b([A-Z]{2,3}-\d{3})\b'
    for match in re.finditer(task_id_pattern, mmd_content):
        tasks.add(match.group(1))

    return sorted(tasks)


def _check_fences(plan_path: Path, yaml_files: list, mmd_files: list) -> dict:
    """Run UAT fence validation checks on a plan folder.

    Four fences are checked:
    1. Story Discovery: plan has affected_stories or no_stories_rationale
    2. UAT Existence: MMD has UAT subgraph
    3. Story Coverage: all affected stories have test_status != untested
    4. Marker Coverage: all affected stories have @pytest.mark.story markers in test files

    Args:
        plan_path: Path to the plan folder.
        yaml_files: Unused (kept for signature compatibility). YAML scanning removed.
        mmd_files: List of orchestration_*.mmd files found.

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

    # --- Fence 2: UAT Existence ---
    has_uat_subgraph = False
    if mmd_files:
        try:
            mmd_content = mmd_files[0].read_text()
            # Check for UAT subgraph or UAT-related nodes
            if re.search(r'(?i)(UAT|User.?Acceptance)', mmd_content):
                has_uat_subgraph = True
        except IOError:
            pass

    if has_uat_subgraph:
        results["Fence 2 (UAT Existence)"] = {
            "status": "PASS",
            "message": "UAT subgraph found in MMD",
        }
    elif not mmd_files:
        results["Fence 2 (UAT Existence)"] = {
            "status": "WARN",
            "message": "No MMD file found (cannot check for UAT subgraph)",
        }
    else:
        results["Fence 2 (UAT Existence)"] = {
            "status": "FAIL",
            "message": "No UAT subgraph found in MMD",
        }

    # --- Fence 3: Story Coverage ---
    if not affected_stories:
        results["Fence 3 (Story Coverage)"] = {
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
            results["Fence 3 (Story Coverage)"] = {
                "status": "WARN",
                "message": f"Coverage: {tested}/{total} ({pct:.0f}%). Untested: {', '.join(untested)}",
            }
        else:
            results["Fence 3 (Story Coverage)"] = {
                "status": "PASS",
                "message": f"All {total} stories tested",
            }

    # --- Fence 4: Pytest Story Marker Coverage ---
    if not affected_stories:
        results["Fence 4 (Marker Coverage)"] = {
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
            results["Fence 4 (Marker Coverage)"] = {
                "status": "WARN",
                "message": (
                    f"Marker coverage: {marked}/{total_affected} ({pct:.0f}%). "
                    f"Stories without @pytest.mark.story markers: {', '.join(stories_without_markers)}"
                ),
            }
        else:
            results["Fence 4 (Marker Coverage)"] = {
                "status": "PASS",
                "message": f"All {total_affected} affected stories have @pytest.mark.story markers",
            }

    return results


def cmd_validate(args):
    """Validate epic structure and orchestration.

    Enhanced with orchestration validation (EN-007):
    - Checks for orchestration phases in TinyDB
    - Falls back to checking orchestration_*.mmd file
    - Reports validation results (PASS/FAIL with details)
    """
    from agenticcli.console import is_json_output, print_json

    plan_path = find_epic_folder(args.path)
    strict = getattr(args, "strict", False)
    errors = []
    warnings = []
    stub_files = []

    # Check folder structure
    if not plan_path.exists():
        print(f"Error: Path does not exist: {plan_path}", file=sys.stderr)
        sys.exit(1)

    # Validate epic exists in TinyDB
    yaml_files = []  # Unused; kept for _check_fences signature compatibility
    try:
        repo = _get_repo()
        plan_data_obj = repo.get_epic(plan_path.name)
        if plan_data_obj is None:
            errors.append(f"Epic '{plan_path.name}' not found in TinyDB")
    except Exception as e:
        errors.append(f"Failed to query TinyDB: {e}")

    # EN-007: Orchestration validation - check TinyDB phases first, then legacy MMD
    mmd_files = list(plan_path.glob("orchestration_*.mmd"))
    orchestration_result = {"status": "PASS", "details": []}

    # Check TinyDB phases (primary)
    has_tinydb_phases = False
    tinydb_phase_count = 0
    try:
        repo = _get_repo()
        phases = repo.list_phases(plan_path.name)
        repo.close()
        if phases and any(phase.agent for phase in phases):
            has_tinydb_phases = True
            tinydb_phase_count = len(phases)
    except Exception:
        pass

    if has_tinydb_phases:
        orchestration_result["status"] = "PASS"
        orchestration_result["details"].append("Orchestration phases found in TinyDB")
        orchestration_result["details"].append(f"Phases found: {tinydb_phase_count}")
    elif mmd_files:
        # Legacy: MMD file still valid
        mmd_file = mmd_files[0]
        try:
            mmd_content = mmd_file.read_text()
            mmd_phases = _parse_mmd_phases(mmd_content)
            mmd_tasks = _parse_mmd_tasks(mmd_content)
            orchestration_result["details"].append(f"Orchestration file: {mmd_file.name}")
            orchestration_result["details"].append(f"Phases found: {len(mmd_phases)}")
            orchestration_result["details"].append(f"Tasks referenced: {len(mmd_tasks)}")
        except IOError as e:
            orchestration_result["status"] = "FAIL"
            orchestration_result["details"].append(f"Cannot read MMD: {e}")
            errors.append(f"Cannot read {mmd_file.name}: {e}")
    else:
        orchestration_result["status"] = "FAIL"
        orchestration_result["details"].append("Missing: orchestration phases in TinyDB or MMD file")
        orchestration_result["details"].append("Action: Spawn orchestration-planning agent")
        orchestration_result["details"].append("Command: agentic session orchestrate planning --epic <folder>")
        if strict:
            errors.append("Missing orchestration phases (TinyDB) or orchestration_*.mmd file")
        else:
            warnings.append("Missing orchestration phases (TinyDB) or orchestration_*.mmd file")

    # --check-fences: validate UAT fence compliance
    check_fences = getattr(args, "check_fences", False)
    fence_results = {}
    if check_fences:
        fence_results = _check_fences(plan_path, yaml_files, mmd_files)
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

    # Determine overall validation result
    has_errors = len(errors) > 0
    overall_status = "FAIL" if has_errors else ("WARN" if warnings else "PASS")

    # Report results
    if is_json_output():
        result_data = {
            "plan": plan_path.name,
            "status": overall_status,
            "orchestration": orchestration_result,
            "errors": errors,
            "warnings": warnings,
            "stub_files": stub_files,
        }
        if check_fences:
            result_data["fences"] = fence_results
        print_json(result_data)
    else:
        print(f"Validating: {plan_path}")
        print("=" * 60)

        # Orchestration validation section
        print(f"\nOrchestration: {orchestration_result['status']}")
        for detail in orchestration_result["details"]:
            print(f"  - {detail}")

        # Fence validation section
        if check_fences:
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

        # Special message for stub templates
        if stub_files and not strict:
            print("\nNote: Stub templates detected. Use --strict to fail validation on stubs.")
            print("      Either populate these files with content or delete them if unused.")

        if not errors and not warnings and orchestration_result["status"] == "PASS":
            print("\n  All checks passed")

    if has_errors:
        sys.exit(1)


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
                and plan_doc.epic_folder.resolve() == plan_path.resolve()
            )
            if folder_matches:
                updated = repo.update_ticket_status(plan_path.name, task_id, new_status)
                if updated:
                    return
    except Exception:
        pass

    print(f"Error: Task {task_id} not found in TinyDB", file=sys.stderr)
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

    from agenticcli.workflows.ticket_workflow import TicketPresetWorkflow

    preset_name = args.preset
    plan_path = find_epic_folder(getattr(args, "plan", None))
    dry_run = getattr(args, "dry_run", False)

    workflow = TicketPresetWorkflow(plan_path)

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
                and plan_doc.epic_folder.resolve() == plan_path.resolve()
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
    plan_path = find_epic_folder(getattr(args, "plan", None))

    task_data = None
    source_file = None
    phase_info = None

    # Try PlanRepository (TinyDB) first
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_epic(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.epic_folder.resolve() == plan_path.resolve()
            )
            if folder_matches:
                td = repo.get_ticket(plan_path.name, task_id)
                if td is not None:
                    task_data = {
                        "id": td.id,
                        "task_id": td.id,
                        "name": td.name or "",
                        "description": td.description or "",
                        "status": td.status or "pending",
                        "inputs": td.inputs or [],
                        "target_files": td.target_files or [],
                        "guidance": td.guidance or "",
                        "success_criteria": td.success_criteria or [],
                    }
                    source_file = "(via TinyDB)"
                    # Get phase info
                    phase_name = td.phase_name or ""
                    phase_obj = repo.get_phase(plan_path.name, phase_name) if phase_name else None
                    phase_info = {
                        "phase_id": phase_name,
                        "name": phase_name,
                        "status": phase_obj.status if phase_obj else None,
                    }
            repo.close()
    except Exception:
        task_data = None

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
        pid = phase_info['phase_id']
        pname = phase_info['name']
        phase_display = f"{pid} - {pname}" if pid and pid != pname else (pname or pid or "N/A")
        print_key_value("Phase", phase_display)
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
    priority = getattr(args, "priority", "medium")
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
                    # Try matching by phase name
                    phases = repo.list_phases(plan_path.name)
                    for p in phases:
                        if p.name == phase_id or (hasattr(p, 'phase_id') and getattr(p, 'phase_id', '') == phase_id):
                            phase_name_used = p.name
                            break
                    if not phase_name_used:
                        print_error(f"Phase '{phase_id}' not found")
                        sys.exit(1)
            else:
                phases = repo.list_phases(plan_path.name)
                if phases:
                    phase_name_used = phases[-1].name
                else:
                    phase_name_used = "Ad-hoc Tasks"
                    repo.add_phase(plan_path.name, {"name": phase_name_used, "status": "pending"})

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


def cmd_unarchive(args, ctx=None):
    """Unarchive an epic by setting its TinyDB status to 'in_progress'.

    This is the reverse of archiving - useful when an epic was archived
    prematurely or needs to be resumed.

    Args:
        args: Parsed arguments with plan name.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
    )

    plan_name = args.plan

    repo = _get_repo()
    if repo is None:
        if is_json_output():
            print_json({"error": "Could not connect to TinyDB repository."})
        else:
            print_error("Could not connect to TinyDB repository.")
        sys.exit(1)

    result = repo.unarchive_epic(plan_name)
    if result.success:
        if is_json_output():
            print_json({
                "result": "success",
                "plan_name": plan_name,
                "status": "in_progress",
            })
        else:
            print_success(f"Unarchived epic: {plan_name}")
    else:
        if is_json_output():
            print_json({"error": result.message})
        else:
            print_error(result.message)
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
                and plan_data.epic_folder.resolve() == plan_folder.resolve()
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

    for meta in plan_metas:
        plan_folder = meta.epic_folder

        # Get task counts via PlanService
        try:
            plan_data_obj = plan_service.get_epic(str(plan_folder))
            tasks = plan_data_obj.tasks if plan_data_obj else []
        except Exception:
            tasks = []

        # Treat in_progress as proposed for display (tickets are either proposed or done)
        total_proposed = sum(1 for t in tasks if t.status in ("pending", "in_progress", "proposed"))
        total_completed = sum(1 for t in tasks if t.status == "completed")
        plan_status = meta.status or "unknown"

        plans_data.append(
            {
                "name": plan_folder.name,
                "status": plan_status,
                "proposed": total_proposed,
                "completed": total_completed,
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

        rows = []
        for plan in plans_data:
            rows.append(
                [
                    f"[bold]{plan['name']}[/bold]",
                    format_status(plan["status"]),
                    f"[dim]{plan['proposed']}[/dim]",
                    f"[green]{plan['completed']}[/green]",
                ]
            )

        print_table("", ["Epic", "Status", "Proposed", "Completed"], rows)


def cmd_move(args, ctx=None):
    """Move completed tasks or archive folder.

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
    from agenticguidance.services import MoveResult, EpicMovementWorkflow

    plan_path = find_epic_folder(getattr(args, "plan", None))
    workflow = EpicMovementWorkflow(plan_path)

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
                print_success(f"Moved {success} task(s) to completed")
            if skipped > 0:
                print_warning(f"Skipped {skipped} task(s)")
            if failed > 0:
                print_error(f"Failed {failed} task(s)")
            if not results:
                console.print("[dim]No completed tasks found to move.[/dim]")

    elif move_type == "folder":
        result = workflow.archive_epic_folder(dry_run=dry_run, force=force)

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
        print("Usage: agentic epic move <task|tasks|folder>", file=sys.stderr)
        sys.exit(1)


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
                and plan_doc.epic_folder.resolve() == plan_path.resolve()
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


def cmd_task_batch(args, ctx=None):
    """Bulk import tickets and phases from JSON (stdin or --file).

    Reads JSON with format: {"phases": [...], "tickets": [...]}
    and populates TinyDB in one shot.

    Args:
        args: Parsed arguments with plan, file.
        ctx: Optional CLIContext.
    """
    import json

    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
        print_warning,
    )

    plan_path = find_epic_folder(getattr(args, "plan", None))
    input_file = getattr(args, "file", None)

    # Read JSON from file or stdin
    try:
        if input_file:
            with open(input_file) as f:
                data = json.load(f)
        else:
            data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON input: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error reading input: {e}")
        sys.exit(1)

    phases_input = data.get("phases", [])
    tickets_input = data.get("tickets", [])

    if not phases_input and not tickets_input:
        print_error("Input JSON must contain 'phases' or 'tickets' (or both)")
        sys.exit(1)

    phases_added = 0
    phases_skipped = 0
    tickets_added = 0
    tickets_skipped = 0
    errors = []

    try:
        repo = _get_repo()
        if repo is None:
            print_error("TinyDB repository unavailable")
            sys.exit(1)

        if not _ensure_epic_in_db(repo, plan_path):
            print_error(f"Epic '{plan_path.name}' could not be registered in TinyDB")
            sys.exit(1)

        # Insert phases first
        for phase_doc in phases_input:
            phase_name = phase_doc.get("name", "")
            if not phase_name:
                errors.append("Phase missing 'name' field - skipped")
                phases_skipped += 1
                continue
            ok = repo.add_phase(plan_path.name, phase_doc)
            if ok:
                phases_added += 1
            else:
                phases_skipped += 1

        # Insert tickets
        for ticket_doc in tickets_input:
            ticket_id = ticket_doc.get("id") or ticket_doc.get("task_id", "")
            if not ticket_id:
                errors.append("Ticket missing 'id' field - skipped")
                tickets_skipped += 1
                continue
            phase_name = ticket_doc.get("phase_name") or ticket_doc.get("phase", "")
            if not phase_name:
                # Use last inserted phase or default
                all_phases = repo.list_phases(plan_path.name)
                phase_name = all_phases[-1].name if all_phases else "Ad-hoc Tasks"
            ok = repo.add_ticket(plan_path.name, phase_name, ticket_doc)
            if ok:
                tickets_added += 1
            else:
                tickets_skipped += 1

    except Exception as e:
        print_error(f"Error during batch import: {e}")
        sys.exit(1)

    if is_json_output():
        print_json({
            "phases_added": phases_added,
            "phases_skipped": phases_skipped,
            "tickets_added": tickets_added,
            "tickets_skipped": tickets_skipped,
            "errors": errors,
            "epic": plan_path.name,
        })
    else:
        print_success(
            f"Batch import complete: {phases_added} phases added, "
            f"{tickets_added} tickets added "
            f"({phases_skipped} phases skipped, {tickets_skipped} tickets skipped)"
        )
        if errors:
            for err in errors:
                print_warning(err)


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

    # Try PlanRepository (TinyDB) first for both current task and all-tasks stats.
    current_task = None
    all_tasks = None
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_epic(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.epic_folder.resolve() == plan_path.resolve()
            )
            if folder_matches:
                repo_task = repo.get_current_ticket(plan_path.name)
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

    # TinyDB-first: add phase via PlanRepository
    tinydb_done = False
    try:
        repo = _get_repo()
        if repo is not None:
            # Ensure the epic is registered in TinyDB (auto-create if folder
            # exists on disk but has no DB record yet).
            if _ensure_epic_in_db(repo, plan_path):
                # Check for duplicate
                existing = repo.get_phase(plan_path.name, phase_name)
                if existing:
                    if is_json_output():
                        print_json({"status": "exists", "phase": phase_name, "message": f"Phase '{phase_name}' already exists"})
                    else:
                        print_success(f"Phase '{phase_name}' already exists (skipped)")
                    return

                phase_doc = {
                    "name": phase_name,
                    "phase_id": phase_id,
                    "description": phase_description,
                    "status": "pending",
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
    except Exception:
        pass

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
        if plan_data_obj and plan_data_obj.epic_folder == plan_path:
            phases_data = []
            for i, phase in enumerate(plan_data_obj.phases):
                phases_data.append({
                    "id": f"P{i + 1}",
                    "name": phase.name,
                    "status": phase.status or "pending",
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
                f"[cyan]{phase['tasks']}[/cyan]",
            ])

        print_table("", ["ID", "Name", "Status", "Tasks"], rows)

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
        new_triggers is not None,
    ])
    if not has_updates:
        print_error("At least one field to update must be provided (--status, --name, --agent, --execution, --loop-type, --loop-max-iterations, --max-turns, --timeout, --feedback-triggers)")
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
                and plan_doc.epic_folder.resolve() == plan_path.resolve()
            )
            if not folder_matches:
                repo = None  # Skip TinyDB path
        if repo is not None:
            phase_obj = repo.get_phase(plan_path.name, phase_id)
            if phase_obj:
                old_status = phase_obj.status or "pending"
                old_name = phase_obj.name

                updates = {}
                if new_status:
                    valid_transitions = {
                        "pending": ["in_progress", "blocked"],
                        "in_progress": ["completed", "blocked", "pending"],
                        "completed": ["pending", "in_progress"],
                        "blocked": ["pending", "in_progress"],
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


def cmd_replan(args, ctx=None):
    """Prepare an epic for new planning.

    Resets all completed ticket statuses back to 'proposed' and removes
    the orchestration MMD file, ready for a fresh planning cycle.

    Args:
        args: Parsed arguments with plan, force.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
        print_warning,
    )

    plan_path = find_epic_folder(getattr(args, "plan", None))
    force = getattr(args, "force", False)

    if not force and not is_json_output():
        print_warning(
            f"About to replan epic '{plan_path.name}':\n"
            "  - All completed/in_progress ticket statuses will be reset to 'proposed'\n"
            "  - The orchestration MMD file will be removed"
        )
        response = input("Confirm? [y/N] ")
        if response.lower() != "y":
            print("Aborted")
            sys.exit(0)

    tickets_reset = 0
    mmd_removed = False
    mmd_path = None

    try:
        repo = _get_repo()
        if repo is None:
            print_error("TinyDB repository unavailable")
            sys.exit(1)

        if not _ensure_epic_in_db(repo, plan_path):
            print_error(f"Epic '{plan_path.name}' not found in TinyDB")
            sys.exit(1)

        # Reset all non-proposed tickets back to proposed
        all_tickets = repo.get_tickets(plan_path.name)
        for ticket in all_tickets:
            if ticket.status and ticket.status != "proposed":
                repo.update_ticket_status(plan_path.name, ticket.id, "proposed")
                tickets_reset += 1

    except Exception as e:
        print_error(f"Error resetting tickets: {e}")
        sys.exit(1)

    # Remove orchestration MMD file
    try:
        mmd_files = list(plan_path.glob("orchestration_*.mmd"))
        for mmd_file in mmd_files:
            mmd_path = mmd_file
            mmd_file.unlink()
            mmd_removed = True
    except Exception as e:
        print_warning(f"Could not remove MMD file: {e}")

    if is_json_output():
        print_json({
            "epic": plan_path.name,
            "tickets_reset": tickets_reset,
            "mmd_removed": mmd_removed,
            "mmd_path": str(mmd_path) if mmd_path else None,
        })
    else:
        print_success(
            f"Replanned '{plan_path.name}': "
            f"{tickets_reset} ticket(s) reset to 'proposed'"
            + (f", removed {mmd_path.name}" if mmd_removed else "")
        )


def _determine_agent_type(phase_name: str, phase_id: str) -> str:
    """Determine the agent type for a phase based on its name or ID.

    Uses keyword matching to route phases to appropriate agents.

    Args:
        phase_name: The name of the phase.
        phase_id: The ID of the phase.

    Returns:
        Agent type string matching a valid agent type (e.g., build-python, test-builder).
    """
    name_lower = phase_name.lower()
    id_lower = phase_id.lower()

    # Check for test-related phases
    if any(kw in name_lower for kw in ["test", "testing", "validation", "verify"]):
        return "test-builder"

    # Check for documentation phases
    if any(kw in name_lower for kw in ["doc", "documentation", "readme", "guide"]):
        return "build-python"

    # Check for cleanup/audit phases
    if any(kw in name_lower for kw in ["cleanup", "clean", "audit", "archive"]):
        return "planner-cleaning"

    # Check for deploy-related phases
    if any(kw in name_lower for kw in ["deploy", "release", "cicd", "ci/cd"]):
        return "deploy-cicd"

    # Default to build-python for build/implementation phases
    return "build-python"


def _generate_phase_subgraph(phase: dict, phase_index: int) -> list[str]:
    """Generate MMD subgraph content for a single phase.

    Args:
        phase: Phase dictionary from YAML.
        phase_index: Index of the phase (1-based).

    Returns:
        List of MMD lines for this phase subgraph.
    """
    phase_id = _get_phase_id(phase) or f"P{phase_index}"
    phase_name = phase.get("name", f"Phase {phase_index}")
    agent_type = _determine_agent_type(phase_name, phase_id)
    tasks = phase.get("tickets", [])

    # Create a safe subgraph ID (alphanumeric only)
    sg_id = f"{phase_id.replace('-', '_')}_SG"

    lines = []
    lines.append(f'    subgraph {sg_id} ["{phase_name}"]')
    lines.append(f"        Phase{phase_index}[Enter {phase_name}] --> SpawnAgent{phase_index}[Spawn {agent_type} Agent]")

    # Add task nodes
    prev_node = f"SpawnAgent{phase_index}"
    for i, task in enumerate(tasks):
        task_id = task.get("id") or task.get("task_id", f"T{i+1}")
        task_name = task.get("name", task.get("description", "")[:40])
        task_node = f"Task_{phase_id.replace('-', '_')}_{i+1}"
        lines.append(f"        {prev_node} --> {task_node}[{task_id}: {task_name}]")
        prev_node = task_node

    lines.append(f"        {prev_node} --> Phase{phase_index}Complete[{phase_name} Complete]")
    lines.append("    end")

    return lines


def _generate_test_fix_loop(phase_index: int, phase_name: str) -> list[str]:
    """Generate MMD content for a test-fix loop phase.

    Args:
        phase_index: Index of the phase (1-based).
        phase_name: Name of the testing phase.

    Returns:
        List of MMD lines for the test-fix loop.
    """
    lines = []
    sg_id = f"Testing{phase_index}_SG"

    lines.append(f'    subgraph {sg_id} ["{phase_name} (Test-Fix-Loop)"]')
    lines.append(f"        Phase{phase_index}[Enter {phase_name}] --> SpawnTestBuilder{phase_index}[Spawn test-builder Agent]")
    lines.append(f"        SpawnTestBuilder{phase_index} --> RunTests{phase_index}[Run Tests]")
    lines.append(f"        RunTests{phase_index} --> TestsPassed{phase_index}{{Tests Passed?}}")
    lines.append("")
    lines.append("        %% Test-Fix Loop: retry path")
    lines.append(f'        TestsPassed{phase_index} -- "No: Fix in Iteration" --> SpawnBuilderFix{phase_index}[Spawn builder Agent for Fixes]')
    lines.append(f"        SpawnBuilderFix{phase_index} --> ApplyFixes{phase_index}[Apply Implementation Fixes]")
    lines.append(f"        ApplyFixes{phase_index} --> RunTests{phase_index}")
    lines.append("")
    lines.append("        %% Success path")
    lines.append(f'        TestsPassed{phase_index} -- "Yes: All Pass" --> Phase{phase_index}Complete[{phase_name} Complete]')
    lines.append("    end")
    lines.append("")
    lines.append("    %% Escalation path for persistent test failures")
    lines.append(f'    TestsPassed{phase_index} -- "No: Escalate" --> CheckIterations{phase_index}{{Max Iterations Reached?}}')
    lines.append(f'    CheckIterations{phase_index} -- "No" --> SpawnTestBuilder{phase_index}')
    lines.append(f'    CheckIterations{phase_index} -- "Yes" --> EscalateTests{phase_index}((Ask User: Test Failures Persist))')

    return lines


def cmd_orchestration_generate(args, ctx=None):
    """Generate orchestration MMD from TinyDB phase data.

    Reads phases from TinyDB and generates a Mermaid flowchart diagram with:
    - Phase nodes from TinyDB
    - Agent routing based on phase type
    - Test-fix loop structure for test phases
    - Feedback triggers
    - CLI commands in comments

    Args:
        args: Parsed arguments with plan path, output, force flags.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_json,
        print_success,
        print_warning,
    )

    plan_path = find_epic_folder(getattr(args, "plan", None))
    output_name = getattr(args, "output", None)
    force = getattr(args, "force", False)

    # Collect all phases via PlanRepository (TinyDB-first)
    all_phases = []
    plan_name = None
    plan_objective = None

    try:
        repo = _get_repo()
        plan_data_obj = repo.get_epic(plan_path.name)
        if (plan_data_obj and plan_data_obj.phases
                and plan_data_obj.epic_folder == plan_path):
            plan_name = plan_data_obj.name or ""
            plan_objective = plan_data_obj.objective or ""
            for phase in plan_data_obj.phases:
                all_phases.append({
                    "name": phase.name,
                    "status": phase.status,
                    "execution": phase.execution,
                    "tickets": [
                        {"id": t.id, "task_id": t.id, "name": t.name, "status": t.status, "agent": t.agent}
                        for t in (phase.tasks or [])
                    ],
                })
    except Exception:
        pass

    if not all_phases:
        print_error("No phases found in TinyDB for this epic")
        sys.exit(1)

    # Determine output file name
    if output_name:
        mmd_file = plan_path / output_name
    else:
        # Use plan folder name for the MMD file
        folder_name = plan_path.name
        # Extract the short name part (after date prefix)
        if "_" in folder_name:
            short_name = folder_name.split("_", 1)[1]
        else:
            short_name = folder_name
        mmd_file = plan_path / f"orchestration_{short_name}.mmd"

    # Check if file exists
    if mmd_file.exists() and not force:
        print_error(f"MMD file already exists: {mmd_file.name}")
        print("Use --force to overwrite", file=sys.stderr)
        sys.exit(1)

    # Build phase metadata for header comments
    phase_names = []
    agent_routing = []
    phase_statuses = []

    for phase in all_phases:
        phase_id = _get_phase_id(phase) or f"P{len(phase_names)+1}"
        phase_name = phase.get("name", f"Phase {len(phase_names)+1}")
        phase_status = phase.get("status", "pending")
        agent_type = _determine_agent_type(phase_name, phase_id)

        phase_names.append(f"{phase_id}: {phase_name}")
        agent_routing.append(f"{phase_id} -> {agent_type}")
        phase_statuses.append(f"{phase_id}={phase_status}")

    # Generate MMD content
    mmd_lines = []

    # Header with metadata comments
    mmd_lines.append("%% =============================================================================")
    mmd_lines.append(f"%% GOAL: {plan_objective or 'Execute plan tasks'}")
    mmd_lines.append("%% =============================================================================")
    mmd_lines.append(f"%% PROFILE: Orchestration-{plan_name or plan_path.name}")
    mmd_lines.append(f"%% INPUT_SOURCE: TinyDB epic={plan_path.name}")
    mmd_lines.append("%%")
    mmd_lines.append("%% PHASES:")
    for pn in phase_names:
        mmd_lines.append(f"%%   {pn}")
    mmd_lines.append("%%")
    mmd_lines.append(f"%% AGENT_ROUTING: {', '.join(agent_routing)}")
    mmd_lines.append(f"%% STATUS: {', '.join(phase_statuses)}")
    mmd_lines.append("%% FEEDBACK_TRIGGERS: TEST_FAILURE -> test-fix-loop, BUILD_FAILURE -> escalate")
    mmd_lines.append("%% =============================================================================")
    mmd_lines.append("")

    # Flowchart start
    mmd_lines.append("flowchart LR")
    mmd_lines.append("    Start((Start)) --> LoadInputs[Load Context Inputs]")
    mmd_lines.append("")

    # Input validation phase
    mmd_lines.append("    %% ========================================")
    mmd_lines.append("    %% INPUT VALIDATION PHASE")
    mmd_lines.append("    %% ========================================")
    mmd_lines.append("    LoadInputs --> ReviewInputs[Review All Listed Inputs]")
    mmd_lines.append("    ReviewInputs --> CheckInputs{All Inputs Found?}")
    mmd_lines.append("")
    mmd_lines.append('    CheckInputs -- "No: Missing" --> SearchInputs[Search for Missing Inputs]')
    mmd_lines.append("    SearchInputs --> Found{Found?}")
    mmd_lines.append('    Found -- "Yes: Update paths" --> UpdateRefs[Update References]')
    mmd_lines.append("    UpdateRefs --> ReviewInputs")
    mmd_lines.append('    Found -- "No: Stop" --> AskUser((Ask User for Clarification))')
    mmd_lines.append("")
    mmd_lines.append('    CheckInputs -- "Yes: Verified" --> Phase1')
    mmd_lines.append("")

    # Generate phase subgraphs
    for i, phase in enumerate(all_phases, 1):
        phase_name = phase.get("name", f"Phase {i}")
        phase_id = _get_phase_id(phase) or f"P{i}"

        mmd_lines.append("    %% ========================================")
        mmd_lines.append(f"    %% PHASE {i}: {phase_name.upper()}")
        mmd_lines.append("    %% ========================================")

        # Determine if this is a test phase (use test-fix loop)
        is_test_phase = any(kw in phase_name.lower() for kw in ["test", "testing", "validation"])

        if is_test_phase:
            # Generate test-fix loop
            agent_type = "test-builder"
            mmd_lines.append(f"    %% AGENT_ROUTING: {agent_type} agent with test-fix loop")
            mmd_lines.append("    %% LOOP_DEFINITION: test-fix-loop")
            mmd_lines.append("    %% MAX_ITERATIONS: 5")
            mmd_lines.append("")

            loop_lines = _generate_test_fix_loop(i, phase_name)
            mmd_lines.extend(loop_lines)
        else:
            # Generate standard phase subgraph
            agent_type = _determine_agent_type(phase_name, phase_id)
            tasks = phase.get("tickets", [])
            task_ids = [t.get("id") or t.get("task_id", "") for t in tasks]

            mmd_lines.append(f"    %% AGENT_ROUTING: {agent_type} agent")
            if task_ids:
                mmd_lines.append(f"    %% Tasks: {', '.join(filter(None, task_ids))}")
            mmd_lines.append("")

            sg_lines = _generate_phase_subgraph(phase, i)
            mmd_lines.extend(sg_lines)

        mmd_lines.append("")

        # Connect to next phase
        if i < len(all_phases):
            mmd_lines.append(f"    Phase{i}Complete --> Phase{i+1}")
        mmd_lines.append("")

    # Validation and finalization
    mmd_lines.append("    %% ========================================")
    mmd_lines.append("    %% FINALIZATION")
    mmd_lines.append("    %% ========================================")
    last_phase = len(all_phases)
    mmd_lines.append(f"    Phase{last_phase}Complete --> UpdatePlanStatus[Update Plan Status: completed]")
    mmd_lines.append("    %% agentic epic move folder --plan <path>")
    mmd_lines.append("    UpdatePlanStatus --> ArchivePlan[Archive to docs/epics/completed/]")
    mmd_lines.append("    ArchivePlan --> End((End: Plan Complete))")
    mmd_lines.append("")

    # Styling
    mmd_lines.append("    %% ========================================")
    mmd_lines.append("    %% STYLING")
    mmd_lines.append("    %% ========================================")
    mmd_lines.append("    classDef entrypoint fill:#90EE90,stroke:#228B22")
    mmd_lines.append("    classDef exitpoint fill:#FFB6C1,stroke:#DC143C")
    mmd_lines.append("    classDef userpoint fill:#87CEEB,stroke:#4682B4")
    mmd_lines.append("    classDef keyaction fill:#FFD700,stroke:#DAA520")
    mmd_lines.append("    class Start entrypoint")
    mmd_lines.append("    class End exitpoint")

    # Collect user points (escalation nodes)
    user_points = ["AskUser"]
    for i in range(1, len(all_phases) + 1):
        phase_name = all_phases[i-1].get("name", "")
        if any(kw in phase_name.lower() for kw in ["test", "testing", "validation"]):
            user_points.append(f"EscalateTests{i}")

    if user_points:
        mmd_lines.append(f"    class {','.join(user_points)} userpoint")

    mmd_lines.append("")

    # Write the MMD file
    mmd_content = "\n".join(mmd_lines)

    try:
        mmd_file.write_text(mmd_content)
    except IOError as e:
        print_error(f"Failed to write {mmd_file}: {e}")
        sys.exit(1)

    if is_json_output():
        print_json({
            "output_file": str(mmd_file),
            "plan_path": str(plan_path),
            "phases_count": len(all_phases),
            "phases": [_get_phase_id(p) or f"P{i+1}" for i, p in enumerate(all_phases)],
        })
    else:
        print_success(f"Generated orchestration MMD: {mmd_file.name}")
        console.print(f"[dim]Phases: {len(all_phases)}[/dim]")
        console.print(f"[dim]Plan: {plan_path.name}[/dim]")


def cmd_orchestration_validate(args, ctx=None):
    """Validate orchestration MMD against TinyDB phase/ticket data.

    Compares the orchestration_*.mmd file against TinyDB data to detect:
    - Missing phases: TinyDB phases not mentioned in MMD
    - Missing task IDs: Task IDs from TinyDB not referenced in MMD
    - Invalid agent routing: Agent types not matching expected patterns

    Args:
        args: Parsed arguments with plan path and strict flag.
        ctx: Optional CLIContext.

    Exit codes:
        0: Validation passed (no errors)
        1: Validation failed (errors found, or warnings with --strict)
        2: File not found or parsing error
    """
    import re

    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_info,
        print_json,
        print_success,
        print_warning,
    )

    plan_path = find_epic_folder(getattr(args, "plan", None))
    strict = getattr(args, "strict", False)

    # Find orchestration MMD file
    mmd_files = list(plan_path.glob("orchestration_*.mmd"))
    if not mmd_files:
        print_error(f"No orchestration_*.mmd file found in {plan_path}")
        sys.exit(2)

    mmd_file = mmd_files[0]  # Use first match
    if len(mmd_files) > 1:
        print_warning(f"Multiple MMD files found, using: {mmd_file.name}")

    # Read MMD content
    try:
        mmd_content = mmd_file.read_text()
    except IOError as e:
        print_error(f"Failed to read {mmd_file}: {e}")
        sys.exit(2)

    # Collect all phases and tasks via PlanRepository (TinyDB-first)
    yaml_phases = []
    yaml_tasks = []
    yaml_phase_ids = set()

    try:
        repo = _get_repo()
        plan_data_obj = repo.get_epic(plan_path.name)
        if (plan_data_obj and plan_data_obj.phases
                and plan_data_obj.epic_folder == plan_path):
            source = "(via TinyDB)"
            for idx, phase in enumerate(plan_data_obj.phases):
                phase_name = phase.name or ""
                phase_id = f"P{idx + 1}"
                yaml_phases.append({
                    "id": phase_id,
                    "name": phase_name,
                    "source": source,
                })
                yaml_phase_ids.add(phase_id)
                for task in (phase.tasks or []):
                    if task.id:
                        yaml_tasks.append({
                            "id": task.id,
                            "phase_id": phase_id,
                            "name": task.name or "",
                            "source": source,
                        })
    except Exception:
        pass

    if not yaml_tasks:
        print_error(f"No task data found in TinyDB for epic: {plan_path.name}")
        sys.exit(2)

    # Validation results
    errors = []
    warnings = []

    # --- Validation 1: All YAML phases present in MMD ---
    # Check for phase references in MMD (comments or nodes)
    # Patterns to look for: "P1", "Phase 1", "P1:" in comments, phase_id in PHASES section
    for phase in yaml_phases:
        phase_id = phase["id"]
        phase_name = phase["name"]

        # Check various patterns that indicate phase is mentioned
        patterns = [
            rf"\b{re.escape(phase_id)}\b",  # Exact phase ID (e.g., P1)
            rf"{re.escape(phase_id)}:",  # Phase ID with colon
            rf"{re.escape(phase_id)} ->",  # Phase ID in routing
            rf"Phase{phase_id.lstrip('P')}",  # Phase1, Phase2, etc.
        ]

        found = False
        for pattern in patterns:
            if re.search(pattern, mmd_content, re.IGNORECASE):
                found = True
                break

        if not found:
            errors.append({
                "type": "missing_phase",
                "phase_id": phase_id,
                "phase_name": phase_name,
                "source": phase["source"],
                "message": f"Phase {phase_id} ({phase_name}) not found in MMD",
            })

    # --- Validation 2: Task IDs referenced in MMD ---
    # Task IDs should appear in comments or node labels (e.g., CR-001, 01.1)
    for task in yaml_tasks:
        task_id = task["id"]

        # Search for task ID in MMD
        pattern = rf"\b{re.escape(task_id)}\b"
        if not re.search(pattern, mmd_content):
            warnings.append({
                "type": "missing_task_id",
                "task_id": task_id,
                "phase_id": task["phase_id"],
                "task_name": task["name"],
                "source": task["source"],
                "message": f"Task {task_id} not referenced in MMD",
            })

    # --- Validation 3: Agent routing valid ---
    # Extract AGENT_ROUTING comments and validate format
    # Uses dynamic agent type discovery from filesystem (with fallback)
    valid_agent_types = get_valid_agent_types()

    # Find AGENT_ROUTING lines in MMD (supports both %% and # comment styles)
    routing_pattern = r"(?:%%|#)\s*AGENT_ROUTING:\s*(.+)"
    routing_matches = re.findall(routing_pattern, mmd_content)

    for routing_line in routing_matches:
        # Parse individual routings (comma-separated)
        # Supports both "Phase -> agent-type" and "Phase=agent-type" formats
        routings = routing_line.split(",")
        for routing in routings:
            routing = routing.strip()
            match = re.match(r"([\w-]+)\s*(?:->|=)\s*(\S+)", routing)
            if match:
                route_phase_id, agent_type = match.groups()
                agent_type = agent_type.strip().lower()

                # Check if agent type is valid (error, not warning - per plan-mmd-schema.yml)
                if agent_type not in valid_agent_types:
                    errors.append({
                        "type": "invalid_agent_routing",
                        "phase_id": route_phase_id,
                        "agent_type": agent_type,
                        "message": f"Unknown agent type '{agent_type}' for phase {route_phase_id}. Valid types: {', '.join(sorted(valid_agent_types))}",
                    })

                # Check if routed phase exists in YAML (if we have yaml_phase_ids)
                if yaml_phase_ids and route_phase_id not in yaml_phase_ids:
                    # Could be a generic reference, so just warn
                    warnings.append({
                        "type": "routing_unknown_phase",
                        "phase_id": route_phase_id,
                        "agent_type": agent_type,
                        "message": f"Agent routing references unknown phase {route_phase_id}",
                    })

    # --- Validation 4: Check PHASES comment section matches YAML ---
    # Extract PHASES from MMD comments and compare
    phases_section_pattern = r"%%\s*PHASES:\s*\n((?:%%\s+.+\n)*)"
    phases_section_match = re.search(phases_section_pattern, mmd_content)

    if phases_section_match:
        mmd_phases_text = phases_section_match.group(1)
        # Extract phase IDs from the comment section
        mmd_phase_ids = set()
        for line in mmd_phases_text.split("\n"):
            # Pattern: %%   P1: Phase name
            phase_match = re.match(r"%%\s+([\w-]+):", line)
            if phase_match:
                mmd_phase_ids.add(phase_match.group(1))

        # Check for phases in YAML not in MMD PHASES section
        for phase_id in yaml_phase_ids:
            if phase_id not in mmd_phase_ids:
                errors.append({
                    "type": "phase_not_in_header",
                    "phase_id": phase_id,
                    "message": f"Phase {phase_id} missing from MMD PHASES header section",
                })

    # --- Output results ---
    total_errors = len(errors)
    total_warnings = len(warnings)
    validation_passed = total_errors == 0 and (not strict or total_warnings == 0)

    if is_json_output():
        print_json({
            "plan_path": str(plan_path),
            "mmd_file": mmd_file.name,
            "data_source": "TinyDB",
            "validation_passed": validation_passed,
            "strict_mode": strict,
            "yaml_phases_count": len(yaml_phases),
            "yaml_tasks_count": len(yaml_tasks),
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "errors": total_errors,
                "warnings": total_warnings,
            },
        })
    else:
        print_info(f"Validating: {mmd_file.name}")
        print_info("Against: TinyDB phase/ticket data")
        console.print()

        # Print errors
        if errors:
            console.print("[bold red]Errors:[/bold red]")
            for err in errors:
                console.print(f"  [red]ERROR[/red] [{err['type']}] {err['message']}")
            console.print()

        # Print warnings
        if warnings:
            console.print("[bold yellow]Warnings:[/bold yellow]")
            for warn in warnings:
                console.print(f"  [yellow]WARN[/yellow] [{warn['type']}] {warn['message']}")
            console.print()

        # Summary
        console.print(f"[dim]YAML phases: {len(yaml_phases)}, tasks: {len(yaml_tasks)}[/dim]")

        if validation_passed:
            print_success(f"Validation passed ({total_errors} errors, {total_warnings} warnings)")
        else:
            if total_errors > 0:
                print_error(f"Validation failed: {total_errors} errors, {total_warnings} warnings")
            else:
                print_warning(f"Validation failed (strict mode): {total_warnings} warnings")

    # Exit code
    if not validation_passed:
        sys.exit(1)
    sys.exit(0)


def cmd_stories_list(args, ctx=None):
    """List user stories for an epic.

    User stories are not yet stored in TinyDB -- this is a stub.

    Args:
        args: Parsed arguments with optional plan path.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_table,
    )

    plan_path = find_epic_folder(getattr(args, "plan", None))

    # User stories are not stored in TinyDB - feature needs migration
    all_stories = []

    if is_json_output():
        print_json({"user_stories": all_stories, "count": len(all_stories)})
    else:
        print_header(f"User Stories in {plan_path.name}")
        console.print("[dim]No user stories found. User stories are not yet stored in TinyDB.[/dim]")


def cmd_stories_test(args, ctx=None):
    """Generate blind test scenarios from user stories.

    Generates executable test cases from user story data.

    For each story:
    - Extracts command (if present)
    - Generates test_id based on story id
    - Creates expected_outcome from so_that or i_want
    - Determines validation_type based on command type

    Args:
        args: Parsed arguments with optional plan, output, format.
        ctx: Optional CLIContext.
    """
    import json

    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_info,
        print_json,
        print_success,
    )

    plan_path = find_epic_folder(getattr(args, "plan", None))
    output_file = getattr(args, "output", None)
    output_format = getattr(args, "format", "yaml")

    # User stories are not stored in TinyDB - feature needs migration
    all_stories = []

    if not all_stories:
        print_error("No user stories found in plan files")
        sys.exit(1)

    # Generate test cases from stories
    test_cases = []
    for story in all_stories:
        test_case = _generate_test_case_from_story(story)
        test_cases.append(test_case)

    # Build output structure
    test_output = {
        "test_suite": {
            "name": f"User Story Tests - {plan_path.name}",
            "plan_folder": str(plan_path),
            "generated_at": datetime.now().isoformat(),
            "test_count": len(test_cases),
        },
        "test_cases": test_cases,
    }

    # Output results
    if output_file:
        output_path = Path(output_file)
        if output_format == "json":
            output_path.write_text(json.dumps(test_output, indent=2))
        else:
            output_path.write_text(yaml.dump(test_output, default_flow_style=False, sort_keys=False))

        if not is_json_output():
            print_success(f"Generated {len(test_cases)} test cases to {output_path}")
    else:
        # Output to stdout
        if is_json_output() or output_format == "json":
            print_json(test_output)
        else:
            print(yaml.dump(test_output, default_flow_style=False, sort_keys=False))


def _generate_test_case_from_story(story: dict) -> dict:
    """Generate a test case structure from a user story.

    Args:
        story: User story dictionary with id, i_want, so_that, command, etc.

    Returns:
        Test case dictionary with test_id, command, expected_outcome, validation_type.
    """
    story_id = story.get("id", "unknown")
    command = story.get("command", "")
    i_want = story.get("i_want", "")
    so_that = story.get("so_that", "")
    acceptance = story.get("acceptance", "")

    # Generate test_id from story id
    test_id = f"test_{story_id}" if story_id else "test_unknown"

    # Determine expected outcome - prefer so_that, then i_want
    if so_that:
        expected_outcome = so_that
    elif i_want:
        expected_outcome = f"User can {i_want}"
    else:
        expected_outcome = "Feature works as expected"

    # Determine validation type based on command
    validation_type = _determine_validation_type(command)

    # Build test case
    test_case = {
        "test_id": test_id,
        "story_id": story_id,
        "description": i_want,
        "command": command if command else None,
        "expected_outcome": expected_outcome,
        "validation_type": validation_type,
    }

    # Add acceptance criteria if present
    if acceptance:
        if isinstance(acceptance, list):
            test_case["acceptance_criteria"] = acceptance
        else:
            test_case["acceptance_criteria"] = [acceptance]

    # Add suggested assertions based on validation type
    test_case["assertions"] = _generate_assertions(validation_type, command, expected_outcome)

    return test_case


def _determine_validation_type(command: str) -> str:
    """Determine the validation type based on the command.

    Args:
        command: CLI command string.

    Returns:
        Validation type: exit_code, output_contains, file_exists, json_schema, or manual.
    """
    if not command:
        return "manual"

    command_lower = command.lower()

    # JSON output commands should validate schema
    if "--json" in command_lower or "-j" in command_lower:
        return "json_schema"

    # File creation/modification commands
    file_keywords = ["create", "scaffold", "init", "write", "generate"]
    if any(kw in command_lower for kw in file_keywords):
        return "file_exists"

    # List/show commands should check output content
    list_keywords = ["list", "show", "status", "get", "find"]
    if any(kw in command_lower for kw in list_keywords):
        return "output_contains"

    # Default to exit code check
    return "exit_code"


def _generate_assertions(validation_type: str, command: str, expected_outcome: str) -> list:
    """Generate test assertions based on validation type.

    Args:
        validation_type: Type of validation to perform.
        command: The CLI command being tested.
        expected_outcome: Expected outcome description.

    Returns:
        List of assertion dictionaries.
    """
    assertions = []

    if validation_type == "exit_code":
        assertions.append({
            "type": "exit_code",
            "expected": 0,
            "description": "Command completes successfully",
        })

    elif validation_type == "output_contains":
        assertions.append({
            "type": "exit_code",
            "expected": 0,
            "description": "Command completes successfully",
        })
        assertions.append({
            "type": "output_contains",
            "pattern": "# TODO: Add expected output pattern",
            "description": expected_outcome,
        })

    elif validation_type == "file_exists":
        assertions.append({
            "type": "exit_code",
            "expected": 0,
            "description": "Command completes successfully",
        })
        assertions.append({
            "type": "file_exists",
            "path": "# TODO: Add expected file path",
            "description": "Expected file is created",
        })

    elif validation_type == "json_schema":
        assertions.append({
            "type": "exit_code",
            "expected": 0,
            "description": "Command completes successfully",
        })
        assertions.append({
            "type": "json_valid",
            "description": "Output is valid JSON",
        })
        assertions.append({
            "type": "json_has_key",
            "key": "# TODO: Add expected JSON key",
            "description": expected_outcome,
        })

    else:  # manual
        assertions.append({
            "type": "manual",
            "description": expected_outcome,
            "steps": ["# TODO: Add manual verification steps"],
        })

    return assertions

def cmd_bootstrap(args, ctx=None):
    """Bootstrap a new plan with an objective.

    DEPRECATED: Use `agentic epic init --objective` instead.
    This command is kept for backward compatibility and redirects to cmd_init.
    """
    import sys

    from agenticcli.console import (
        is_json_output,
        print_warning,
    )

    if not is_json_output():
        print_warning(
            "plan bootstrap is deprecated. Use: agentic epic init <branch> --objective '<objective>' --description '<desc>'"
        )

    # Redirect to cmd_init by forwarding args
    cmd_init(args, ctx)


def _find_epics_base() -> Optional[Path]:
    """Find the docs/epics base directory.

    Walks up from CWD looking for a docs/epics directory.

    Returns:
        Path to docs/epics if found, None otherwise.
    """
    current = Path.cwd()
    while current != current.parent:
        epics_dir = current / "docs" / "epics"
        if epics_dir.is_dir():
            return epics_dir
        current = current.parent
    return None


def cmd_db_sync(args):
    """db sync is disabled. TinyDB is the sole data store.

    YAML epic files are no longer used for data storage.
    """
    json_output = getattr(args, "json", False)

    error_msg = "Error: db sync is disabled. TinyDB is the sole data store. YAML epic files are no longer used."
    if json_output:
        import json
        print(json.dumps({"error": error_msg}))
    else:
        print(error_msg, file=sys.stderr)
    sys.exit(1)


def cmd_db_status(args):
    """Show TinyDB database statistics."""
    from agenticguidance.services.epic_repository import EpicRepository

    json_output = getattr(args, "json", False)

    try:
        repo = EpicRepository(db_path=_get_repo_db_path(), auto_bootstrap=False)

        plans = repo.list_epics()
        plan_count = len(plans)

        # Count by status
        status_counts: dict = {}
        for p in plans:
            s = p.status or "unknown"
            status_counts[s] = status_counts.get(s, 0) + 1

        db_size = repo.db_path.stat().st_size if repo.db_path.exists() else 0

        result = {
            "db_path": str(repo.db_path),
            "db_size_bytes": db_size,
            "plan_count": plan_count,
            "status_breakdown": status_counts,
        }

        if json_output:
            import json
            print(json.dumps(result))
        else:
            print(f"Database: {repo.db_path}")
            print(f"Size: {db_size / 1024:.1f} KB")
            print(f"Plans: {plan_count}")
            for status, count in sorted(status_counts.items()):
                print(f"  {status}: {count}")

        repo.close()
    except Exception as e:
        if json_output:
            import json
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
