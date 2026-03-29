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
    "orchestration-executor", "orchestration-loop", "orchestration-planning",
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
    else:
        print("Usage: agentic epic <new|from-plan|status|ticket|archive|list|phase|cancel>", file=sys.stderr)
        sys.exit(1)


def _epic_folder_or_synthetic(epic_obj) -> Path:
    """Return epic_folder from an EpicData/EpicMetadata, or synthesize a Path from the name.

    When epic_folder is None (folder-free epic), returns a synthetic Path
    using only the epic_folder_name. Callers use .name on the result to
    get the epic_folder_name for TinyDB lookups.
    """
    if epic_obj.epic_folder is not None:
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
                if matches:
                    matches.sort(key=lambda e: e.epic_folder_name)
                    return _epic_folder_or_synthetic(matches[0])
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
                cwd=str(repo_root),
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
        if max_turns is not None:
            claude_cmd.extend(["--max-turns", str(max_turns)])
        claude_cmd.extend(["-p", planner_prompt])

        try:
            if not is_json_output():
                status_message = "Running planner agent..."
                with get_status(status_message):
                    result = subprocess.run(
                        claude_cmd,
                        cwd=str(repo_root),
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
                    cwd=str(repo_root),
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
        _repo = EpicRepository()
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
                    and plan_data_obj.epic_folder_name == plan_folder_name):
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


def cmd_seed(args, ctx=None):
    """Create an epic shell without spawning a planner agent.

    Runs only the init step of epic creation (TinyDB record + optional disk
    folder) and returns immediately. Use this when you want to manually
    add phases and tickets before planning/executing.

    Args:
        args: Parsed arguments with objective, optional branch, description, base.
        ctx: Optional CLIContext.
    """
    from types import SimpleNamespace

    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
        print_success,
    )

    objective = getattr(args, "objective", None)
    if not objective:
        print_error("Objective is required. Usage: agentic epic seed \"your objective\"")
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

    # Delegate to cmd_init (Step 1 only — no planner spawn)
    import io
    from contextlib import redirect_stdout

    from agenticcli.console import set_json_output as _set_json

    init_args = SimpleNamespace(
        command="plan",
        plan_command="init",
        json=False,
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

    # Look up created epic from TinyDB
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

    plan_folder_name = None
    try:
        from agenticcli.utils.naming import generate_epic_folder_name
        plan_folder_name = generate_epic_folder_name(repo_root, description, branch=branch)
    except Exception:
        pass

    if is_json_output():
        print_json({
            "status": "created",
            "epic_folder": plan_folder_name or "",
            "objective": objective,
            "branch": branch,
        })
    else:
        print_success(f"Epic seeded: {plan_folder_name or branch}")
        from agenticcli.console import console
        console.print("[dim]No planner spawned. Add phases/tickets manually.[/dim]")


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
        "active": ("Spawn planning agent", f"agentic orchestrate session plan --epic {epic_folder_name}"),
        "planning": ("Planning in progress", None),
        "in_progress": ("Execute current ticket", f"agentic epic ticket current --epic {epic_folder_name}"),
        "completed": ("Archive epic", f"agentic epic archive {epic_folder_name}"),
        "deferred": ("Resolve blockers", None),
        "blocked": ("Resolve blockers", None),
    }
    next_action, next_command = _status_actions.get(plan_status, ("Check epic state", None))

    # --validate: collect validation results
    validation_data = None
    if getattr(args, "validate", False):
        validation_data = _collect_validation(plan_path, args)

    if is_json_output():
        result_data = {
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
        # "active" with unplanned tickets is really just "seed"
        # "planning" that's stale (no running planner) is also "seed"
        if repo:
            is_valid, _reason = validate_phase_routing(repo, folder_name)
        else:
            is_valid = False

        if plan_status in ("seed", "active", "planning") and not is_valid:
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
            status_cell = format_status(plan["status"])
            tickets_cell = f"[green]{plan['completed']}[/green]/{plan['tickets']}"
            phases_cell = f"[green]{plan['phases_done']}[/green]/{plan['phases']}" if plan["phases"] else "[dim]—[/dim]"
            rows.append(
                [
                    f"[bold]{plan['name']}[/bold]",
                    status_cell,
                    tickets_cell,
                    phases_cell,
                ]
            )

        print_table("", ["Epic", "Status", "Tickets", "Phases"], rows)

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
        if plan_data_obj and plan_data_obj.epic_folder_name == plan_path.name:
            phases_data = []
            for i, phase in enumerate(plan_data_obj.phases):
                phases_data.append({
                    "id": phase.phase_id or f"P{i + 1}",
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
                and plan_doc.epic_folder_name == plan_path.name
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


