"""Plan management commands.

Handles planning folder operations and task tracking.
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


# Cache for loop type discovery
_loop_types_cache: set | None = None

# Fallback set used when agent-loops.yml cannot be read
_FALLBACK_LOOP_TYPES = {
    "test-fix-loop", "audit-test-fix-loop", "cleaner-dependency-loop",
    "documentation-loop", "user-story-validation-loop", "exploration-loop",
    "rlm-decomposition-loop", "rlm-context-refinement-loop", "rlm_loop_selection",
    "planner-loop", "guidance-test-loop", "agent-self-review", "guidance-self-review-loop",
}


def get_valid_loop_types(loops_file: Path | None = None) -> set[str]:
    """Read valid loop types from agent-loops.yml.

    Extracts keys from the loop_types section of agent-loops.yml. Falls back
    to a hardcoded set if the file is not found or cannot be parsed.

    Args:
        loops_file: Optional override for the agent-loops.yml file path.

    Returns:
        Set of valid loop type names (e.g., {"test-fix-loop", "planner-loop"}).
    """
    global _loop_types_cache
    use_cache = loops_file is None
    if use_cache and _loop_types_cache is not None:
        return _loop_types_cache

    if loops_file is None:
        repo_root = Path(__file__).resolve().parents[5]
        loops_file = repo_root / "modules" / "AgenticGuidance" / "assets" / "definitions" / "agent-loops.yml"

    if not loops_file.is_file():
        return _FALLBACK_LOOP_TYPES

    try:
        with open(loops_file) as f:
            content = yaml.safe_load(f)
        loop_types_section = content.get("loop_types", {})
        if not loop_types_section or not isinstance(loop_types_section, dict):
            return _FALLBACK_LOOP_TYPES
        loop_types = set(loop_types_section.keys())
    except Exception:
        return _FALLBACK_LOOP_TYPES

    if not loop_types:
        return _FALLBACK_LOOP_TYPES

    if use_cache:
        _loop_types_cache = loop_types
    return loop_types


def _get_phases_from_content(content: dict) -> list:
    """Get phases from either root or nested under plan.

    Supports both structures:
    - Root level: content["phases"]
    - Nested: content["plan"]["phases"]

    Args:
        content: Parsed YAML content from a plan file.

    Returns:
        List of phases, empty list if none found.
    """
    return content.get("phases", []) or content.get("plan", {}).get("phases", [])


def _get_phase_id(phase: dict) -> str:
    """Get phase ID from either phase_id or id field.

    Args:
        phase: Phase dictionary from YAML.

    Returns:
        Phase ID string, empty if not found.
    """
    return phase.get("phase_id", "") or phase.get("id", "")


def _get_repo():
    """Get PlanRepository instance for TinyDB-backed plan access."""
    from agenticguidance.services.plan_repository import PlanRepository
    return PlanRepository()


def is_plan_fully_completed(plan_folder: Path) -> bool:
    """Check if all tasks across all plan files are completed.

    Tries PlanRepository (TinyDB) first for fast lookup, then falls back
    to reading plan_*.yml files if TinyDB is unavailable.

    Args:
        plan_folder: Path to the plan folder containing plan_*.yml files.

    Returns:
        True if ALL tasks across ALL plan files have status "completed",
        False otherwise. Returns False if no plan files are found or
        if there are no tasks defined.

    Edge cases:
        - No plan_*.yml files found: Returns False
        - Plan files with no tasks: Returns False (nothing to complete)
        - Mixed statuses across files: Returns False
        - YAML parse errors: Skips the file (counts as incomplete)
    """
    # TinyDB path: fast lookup via PlanRepository
    try:
        repo = _get_repo()
        if repo is not None:
            # Only trust repo result if the plan actually has tasks in DB
            counts = repo.get_task_counts(plan_folder.name)
            if counts["total"] > 0:
                return repo.check_all_tasks_complete(plan_folder.name)
    except Exception:
        pass  # Fall through to YAML

    # YAML fallback
    yaml_files = list(plan_folder.glob("plan_*.yml"))

    # No plan files found - not completed
    if not yaml_files:
        return False

    total_tasks = 0
    completed_tasks = 0

    for yaml_file in yaml_files:
        try:
            content = yaml.safe_load(yaml_file.read_text())
        except yaml.YAMLError:
            # Parse error - treat as incomplete
            return False

        if not content:
            continue

        # Count tasks from phases structure
        phases = _get_phases_from_content(content)
        for phase in phases:
            tasks = phase.get("tasks", [])
            for task in tasks:
                total_tasks += 1
                status = task.get("status", "pending")
                if status == "completed":
                    completed_tasks += 1

        # Legacy: implementation_steps
        plan_data = content.get("plan", content.get("feature", {}))
        steps = plan_data.get("implementation_steps", [])
        for item in steps:
            total_tasks += 1
            status = item.get("status", "pending")
            if status == "completed":
                completed_tasks += 1

    # No tasks defined - not completed
    if total_tasks == 0:
        return False

    # All tasks must be completed
    return completed_tasks == total_tasks


def has_pending_questions(plan_path: Path) -> bool:
    """Check if a plan has unanswered questions in its pending queue.

    Args:
        plan_path: Path to the plan folder.

    Returns:
        True if any pending question YAML files exist, False otherwise.
    """
    pending_dir = plan_path / "questions" / "pending"
    if not pending_dir.is_dir():
        return False
    return any(pending_dir.glob("*.yml"))


def _get_plan_branch(plan_path: Path) -> str | None:
    """Extract the branch name associated with a plan folder.

    Tries PlanRepository (TinyDB) first for fast lookup, then falls back
    to reading YAML files.

    Args:
        plan_path: Path to the plan folder.

    Returns:
        Branch name string, or None if not determinable.
    """
    # TinyDB path: fast lookup via PlanRepository
    try:
        repo = _get_repo()
        if repo is not None:
            branch = repo.get_plan_branch(plan_path.name)
            if branch is not None:
                return branch
    except Exception:
        pass  # Fall through to YAML

    # YAML fallback: Try plan_build.yml first (most likely to have branch info)
    for yaml_name in ["plan_build.yml", "plan_teach.yml"]:
        yaml_file = plan_path / yaml_name
        if not yaml_file.exists():
            continue
        try:
            content = yaml.safe_load(yaml_file.read_text())
            if not content:
                continue

            # Check root-level branch field
            branch = content.get("branch")
            if branch and branch.strip() and branch.strip() not in ("main", "master", ""):
                return branch.strip().strip('"').strip("'")

            # Check nested under plan:
            plan_data = content.get("plan", {})
            if plan_data:
                branch = plan_data.get("branch")
                if branch and branch.strip() and branch.strip() not in ("main", "master", ""):
                    return branch.strip().strip('"').strip("'")

        except yaml.YAMLError:
            continue

    return None



def handle(args, ctx=None):
    """Route plan subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.plan_command == "new":
        cmd_new(args, ctx)
    elif args.plan_command == "init":
        cmd_init(args, ctx)
    elif args.plan_command == "bootstrap":
        cmd_bootstrap(args, ctx)
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
    elif args.plan_command == "unarchive":
        cmd_unarchive(args, ctx)
    elif args.plan_command == "list":
        cmd_list(args)
    elif args.plan_command == "move":
        cmd_move(args, ctx)
    elif args.plan_command == "phase":
        if args.phase_action == "add":
            cmd_phase_add(args, ctx)
        elif args.phase_action == "list":
            cmd_phase_list(args, ctx)
        elif args.phase_action == "update":
            cmd_phase_update(args, ctx)
        else:
            print("Usage: agentic plan phase <add|list|update>", file=sys.stderr)
            sys.exit(1)
    elif args.plan_command == "orchestration":
        if args.orchestration_action == "generate":
            cmd_orchestration_generate(args, ctx)
        elif args.orchestration_action == "validate":
            cmd_orchestration_validate(args, ctx)
        else:
            print("Usage: agentic plan orchestration <generate|validate>", file=sys.stderr)
            sys.exit(1)
    elif args.plan_command == "stories":
        if args.stories_action == "list":
            cmd_stories_list(args, ctx)
        elif args.stories_action == "test":
            cmd_stories_test(args, ctx)
        else:
            print("Usage: agentic plan stories <list|test>", file=sys.stderr)
            sys.exit(1)
    elif args.plan_command == "cancel":
        cmd_cancel(args, ctx)
    elif args.plan_command == "db":
        if args.db_action == "sync":
            cmd_db_sync(args)
        elif args.db_action == "status":
            cmd_db_status(args)
        else:
            print("Usage: agentic plan db <sync|status>", file=sys.stderr)
            sys.exit(1)
    else:
        print("Usage: agentic plan <new|init|scaffold|status|validate|task|archive|unarchive|list|move|phase|orchestration|stories|db|cancel>", file=sys.stderr)
        sys.exit(1)


def find_plan_folder(path: str | None = None) -> Path:
    """Find the active plan folder.

    Args:
        path: Explicit path to plan folder, or None to auto-detect.
              Can be a full path, or a partial folder name to search for
              in docs/plans/live/ (e.g., "260129FI" matches "260129FI_cli_bug_fixes").

    Returns:
        Path to the plan folder.
    """
    if path:
        # First check if path exists as-is
        path_obj = Path(path)
        if path_obj.exists() and path_obj.is_dir():
            return path_obj

        # Path doesn't exist - search for matching folder in docs/plans/live/
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

        plans_live_dir = repo_root / "docs" / "plans" / "live"

        # Search for matching folders
        search_name = path_obj.name if path_obj.name else path

        # Try PlanRepository for faster lookup (only trust results inside this repo)
        try:
            from agenticguidance.services.plan_repository import PlanRepository
            repo = PlanRepository(auto_bootstrap=False)
            plan_data = repo.get_plan(search_name)
            if plan_data and plan_data.plan_folder.is_dir():
                # Only accept if the plan folder belongs to this repo tree
                try:
                    plan_data.plan_folder.relative_to(repo_root)
                except ValueError:
                    repo.close()
                    pass  # Plan folder is outside this repo - fall through
                else:
                    resolved_folder = plan_data.plan_folder
                    # Live-preference: if TinyDB points to completed/ but a
                    # live/ version exists, prefer live/ and auto-correct TinyDB.
                    if "/plans/completed/" in str(resolved_folder):
                        live_path = Path(
                            str(resolved_folder).replace(
                                "/plans/completed/", "/plans/live/"
                            )
                        )
                        if live_path.is_dir():
                            resolved_folder = live_path
                            try:
                                repo.resync_plan_folder(
                                    plan_data.plan_folder_name,
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

    # Auto-detect: look for docs/plans/live/ in current directory tree
    cwd = Path.cwd()

    # Check if we're in a plan folder (flattened structure: plan_*.yml directly in cwd)
    if list(cwd.glob("plan_*.yml")):
        return cwd

    # Check if we're in a repo with plans
    plans_dir = cwd / "docs" / "plans" / "live"
    if plans_dir.exists():
        # Return first plan folder found (flattened: has plan_*.yml files)
        for item in plans_dir.iterdir():
            if item.is_dir() and list(item.glob("plan_*.yml")):
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
        print_error("Objective is required. Usage: agentic plan new \"your objective\"")
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

    # If we get here, init succeeded. Find the created plan folder.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        repo_root = Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        print_error("Not in a git repository")
        sys.exit(1)

    plans_live = repo_root / "docs" / "plans" / "live"

    # Find the folder we just created (most recently modified matching description)
    from agenticcli.utils.naming import sanitize_description
    sanitized = sanitize_description(description)
    matching = [p for p in plans_live.iterdir() if p.is_dir() and sanitized in p.name]
    plan_folder = matching[0] if matching else None

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
            sdk_options = ClaudeAgentOptions(
                permission_mode="bypassPermissions",
                cwd=str(plan_folder),
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
        # Subprocess fallback: use claude CLI
        claude_cmd = ["claude", "--print"]
        if dangerously_skip_permissions:
            claude_cmd.append("--dangerously-skip-permissions")
        if max_turns:
            claude_cmd.extend(["--max-turns", str(max_turns)])
        claude_cmd.append(planner_prompt)

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

    # Validate that plan_build.yml was created
    plan_build_file = plan_folder / "plan_build.yml"
    if not plan_build_file.exists() or plan_build_file.stat().st_size == 0:
        if not is_json_output():
            print_error("Planner did not create plan_build.yml")
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

    # Re-sync plan to TinyDB now that planner has populated plan_build.yml (non-fatal)
    try:
        from agenticguidance.services.plan_repository import PlanRepository
        repo = PlanRepository(auto_bootstrap=False)
        repo.import_from_yaml(plan_folder)
        repo.close()
    except Exception:
        pass

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
                print_warning("  Run: agentic plan orchestration generate --plan " + str(plan_folder))
        else:
            orchestration_success = True
    except Exception as e:
        if not is_json_output():
            print_warning(f"Orchestration generation failed: {e}")
            print_warning("  You can generate it manually later with:")
            print_warning("  agentic plan orchestration generate --plan " + str(plan_folder))

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
            plan_data_obj = repo.get_plan(plan_folder_name)
            if (plan_data_obj and plan_data_obj.phases
                    and plan_data_obj.plan_folder == plan_folder):
                phases = [
                    {
                        "name": phase.name,
                        "execution": phase.execution or "sequential",
                        "tasks": [
                            {"id": t.id, "name": t.name, "status": t.status or "pending"}
                            for t in (phase.tasks or [])
                        ],
                    }
                    for phase in plan_data_obj.phases
                ]
        except Exception:
            pass

        if phases is None:
            # Fallback: read plan_build.yml directly
            plan_build_file = plan_folder / "plan_build.yml"
            if not plan_build_file.exists():
                if not is_json_output():
                    print_error("plan_build.yml not found - cannot spawn builders")
                phases = []
            else:
                try:
                    plan_data = yaml.safe_load(plan_build_file.read_text())
                    phases = _get_phases_from_content(plan_data) if plan_data else []
                except (yaml.YAMLError, Exception):
                    phases = []

        if phases:
            try:

                total_tasks = 0
                spawned_sessions = []

                for phase_idx, phase in enumerate(phases, 1):
                    phase_name = phase.get("name", f"Phase {phase_idx}")
                    execution_mode = phase.get("execution", "sequential")
                    tasks = phase.get("tasks", [])

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

                        # Build the spawn command: agentic session spawn --task <id> --plan <folder>
                        spawn_cmd = ["agentic", "session", "spawn", "--task", task_id, "--plan", str(plan_folder)]
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
                                phase_sessions.append({
                                    "task_id": task_id,
                                    "sdk_prompt": task_prompt,
                                    "sdk_options": None,
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

                if is_plan_fully_completed(plan_folder):
                    if not is_json_output():
                        print_success("All tasks completed!")
                else:
                    if not is_json_output():
                        # Count remaining tasks
                        remaining = []
                        for phase in phases:
                            for task in phase.get("tasks", []):
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
        print_success(f"Plan created: {plan_folder.name}")
        print(f"  Plan folder: {plan_folder}")
        print(f"  Branch: {branch}")
        print(f"  Objective: {objective}")
        if not execute:
            print()
            print("  Next steps:")
            print(f"    1. Review plan: agentic plan status {plan_folder}")
            print(f"    2. Execute: agentic plan new \"{objective}\" --execute")

    return result_data


def cmd_init(args, ctx=None):
    """Initialize plan folder with proper naming convention.

    Creates a plan folder in docs/plans/live/ with YYMMDDXX_description naming.

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

    # Generate plan folder name
    plan_folder_name = generate_plan_folder_name(repo_root, description, branch=branch)

    # Validate the generated name
    is_valid, error = validate_plan_folder_name(plan_folder_name)
    if not is_valid:
        print_error(f"Generated name '{plan_folder_name}' is invalid: {error}")
        sys.exit(3)

    # Create plan folder in docs/plans/live/
    plan_path = repo_root / "docs" / "plans" / "live" / plan_folder_name

    # Check if folder already exists
    if plan_path.exists():
        print_error(f"Plan folder already exists: {plan_path}")
        sys.exit(2)

    # Create the folder structure
    plan_path.mkdir(parents=True, exist_ok=True)

    # If --objective provided, write plan_build.yml with objective
    objective = getattr(args, "objective", None)
    if objective:
        created_date = datetime.now().strftime("%Y-%m-%d")
        plan_build_content = f"""# Implementation Plan: {description}
# Plan ID: {plan_folder_name.split('_')[0]}
# Created: {created_date}

name: "{description}"
branch: "{branch}"
status: "active"
priority: "high"

context: |
  {objective}

phases:
  - name: "Initial Research and Planning"
    tasks:
      - id: "IM_001"
        name: "Research existing implementation"
        status: "pending"
        description: "Analyze the codebase to understand how to implement the objective."
"""
        (plan_path / "plan_build.yml").write_text(plan_build_content)

    # Sync new plan to TinyDB (non-fatal)
    try:
        from agenticguidance.services.plan_repository import PlanRepository
        repo = PlanRepository(auto_bootstrap=False)
        repo.import_from_yaml(plan_path)
        repo.close()
    except Exception:
        pass

    # Output results
    result_data = {
        "branch": branch,
        "base": base,
        "plan_folder": str(plan_path),
        "plan_folder_name": plan_folder_name,
    }
    if objective:
        result_data["objective"] = objective

    if is_json_output():
        print_json(result_data)
    else:
        console.print(f"  [green]Created plan folder[/green] at {plan_path}")
        if objective:
            console.print(f"  [green]Wrote plan_build.yml[/green] with objective")
        console.print()
        print_success(f"Plan initialized: {plan_folder_name}")
        console.print(f"[dim]Plan folder:[/dim] {plan_path}")
        console.print()
        console.print("[dim]Link related user stories in inputs.yml:[/dim]")
        console.print(f"[dim]  agentic stories find --project <name>[/dim]")
        console.print(f"[dim]  agentic stories untested --project <name>[/dim]")


def cmd_scaffold(args):
    """Create planning folder structure (DEPRECATED - use 'agentic plan init' instead)."""
    from agenticcli.console import is_json_output, print_json

    name = args.name
    base_path = Path.cwd()

    plan_path = base_path / "docs" / "plans" / "live" / name

    # Print deprecation warning
    if not is_json_output():
        print("\n[WARNING] 'agentic plan scaffold' is DEPRECATED", file=sys.stderr)
        print("Use 'agentic plan init <branch> --description <description>' instead", file=sys.stderr)
        print("The scaffold command creates only the folder structure.\n", file=sys.stderr)

    if plan_path.exists():
        print(f"Error: Plan folder already exists: {plan_path}", file=sys.stderr)
        sys.exit(1)

    plan_path.mkdir(parents=True, exist_ok=True)
    # Create a minimal stub plan_build.yml
    stub_content = f"""# Plan: {name}
# Created by: agentic plan scaffold (DEPRECATED)
_template_status: stub
name: "{name}"
status: "planning"
phases: []
"""
    (plan_path / "plan_build.yml").write_text(stub_content)

    if is_json_output():
        print_json({"name": name, "path": str(plan_path), "folder": str(plan_path), "deprecated": True})
    else:
        print(f"Created planning folder: {plan_path}")
        print(f"  (flattened structure: plan files directly in folder)")
        print("\n[RECOMMENDED] Next time, use: agentic plan init <branch> --description <description>")


def cmd_status(args):
    """Show plan status and task summary.

    Enhanced with orchestration status (EN-003, EN-004, EN-005):
    - Shows orchestration MMD path or MISSING status
    - Shows deferred reason if plan is deferred
    - Shows next action guidance for agents
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

    plan_path = find_plan_folder(args.path)

    # EN-003: Check for orchestration_*.mmd files (filesystem check, not in PlanService)
    mmd_files = list(plan_path.glob("orchestration_*.mmd"))
    has_orchestration = len(mmd_files) > 0
    orchestration_file = mmd_files[0].name if mmd_files else None

    # Flattened structure: YAML files directly in plan_path
    yaml_files = list(plan_path.glob("plan_*.yml"))
    if not yaml_files:
        print_error(f"No plan_*.yml files found in {plan_path}")
        sys.exit(1)

    total_pending = 0
    total_in_progress = 0
    total_completed = 0
    file_stats = []
    plan_status = "unknown"
    deferred_reason = None
    has_tasks = False

    # Get plan data via PlanService (TinyDB-first)
    try:
        from agenticguidance.services.plan import PlanService
        plan_service = PlanService()
        plan_data_obj = plan_service.get_plan(str(plan_path))
    except Exception as e:
        print_error(f"Failed to load PlanService: {e}")
        sys.exit(1)

    if plan_data_obj is None:
        print_error(f"Plan not found in repository: {plan_path.name}")
        sys.exit(1)

    plan_status = plan_data_obj.status or "unknown"
    tasks = plan_data_obj.tasks or []
    total_pending = sum(1 for t in tasks if t.status == "pending")
    total_in_progress = sum(1 for t in tasks if t.status == "in_progress")
    total_completed = sum(1 for t in tasks if t.status == "completed")
    has_tasks = len(tasks) > 0

    # Build file_stats summary (aggregate all tasks under a single entry for display)
    if has_tasks:
        file_stats.append(
            {
                "file": "(via PlanService)",
                "pending": total_pending,
                "in_progress": total_in_progress,
                "completed": total_completed,
            }
        )

    # Get deferred_reason from PlanData (TinyDB-backed)
    if plan_status == "deferred":
        deferred_reason = plan_data_obj.deferred_reason

    total = total_pending + total_in_progress + total_completed
    pct = (total_completed / total) * 100 if total > 0 else 0

    # EN-005: Determine next action and command
    if plan_status == "deferred":
        action_required = "blocked"
        next_action = "Resolve blockers"
        next_command = None
    elif not has_orchestration:
        action_required = "needs_planning"
        next_action = "Spawn orchestration-planning agent"
        next_command = "agentic entrypoint execute _plan_build --compile"
    elif not has_tasks or total == 0:
        action_required = "needs_planning"
        next_action = "Define tasks in plan"
        next_command = "agentic entrypoint execute _plan_build --compile"
    elif total_pending > 0 or total_in_progress > 0:
        action_required = "execute"
        next_action = "Execute current task"
        next_command = f"agentic plan task current --plan {plan_path}"
    elif total_completed == total and total > 0:
        action_required = "archive"
        next_action = "Archive completed plan"
        next_command = f"agentic plan move folder --plan {plan_path}"
    else:
        action_required = "blocked"
        next_action = "Check plan state"
        next_command = None

    if is_json_output():
        print_json(
            {
                "plan": plan_path.name,
                "status": plan_status,
                "has_orchestration": has_orchestration,
                "orchestration_file": orchestration_file,
                "has_tasks": has_tasks,
                "action_required": action_required,
                "next_action": next_action,
                "next_command": next_command,
                "deferred_reason": deferred_reason,
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

        # EN-003: Show orchestration status
        if has_orchestration:
            console.print(f"[bold]Orchestration:[/bold] [green]{orchestration_file}[/green]")
        else:
            console.print("[bold]Orchestration:[/bold] [red]MISSING[/red]")
            console.print("  [dim]Run: agentic entrypoint execute _plan_build --compile[/dim]")

        console.print(f"[bold]Status:[/bold] {plan_status}")

        # EN-004: Show deferred reason
        if deferred_reason:
            console.print(f"[bold]Deferred Reason:[/bold] [yellow]{deferred_reason}[/yellow]")

        console.print(f"[bold]Action Required:[/bold] {action_required}")
        console.print()

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

        # EN-005: Show next action guidance
        console.print()
        console.print(f"[bold]Next Action:[/bold] {next_action}")
        if next_command:
            console.print(f"  [dim]Command: {next_command}[/dim]")


def is_stub_template(content: dict) -> bool:
    """Check if content is an unpopulated stub template.

    Stub templates are scaffolds created by `agentic plan init` that need
    to be populated with actual content or deleted.

    Args:
        content: Parsed YAML content from a plan file.

    Returns:
        True if the file is a stub template, False otherwise.
    """
    if not content:
        return False

    # Check explicit template status field
    if content.get("_template_status") == "stub":
        return True

    # Check for legacy empty stub patterns (before _template_status was added)
    plan = content.get("plan", content.get("feature", {}))
    phases = plan.get("phases", [])
    objective = str(plan.get("objective", ""))

    # Empty phases array with TODO in objective indicates legacy stub
    if not phases and "TODO" in objective:
        return True

    return False


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

    Three fences are checked:
    1. Story Discovery: plan has affected_stories or no_stories_rationale
    2. UAT Existence: MMD has UAT subgraph
    3. Story Coverage: all affected stories have test_status != untested

    Args:
        plan_path: Path to the plan folder.
        yaml_files: List of plan_*.yml files found.
        mmd_files: List of orchestration_*.mmd files found.

    Returns:
        Dict of fence name -> {status, message}.
    """
    import re

    results = {}

    # Collect metadata from all plan YAML files
    affected_stories = []
    no_stories_rationale = None
    for yf in yaml_files:
        try:
            content = yaml.safe_load(yf.read_text())
        except yaml.YAMLError:
            continue
        if not content or not isinstance(content, dict):
            continue
        stories = content.get("affected_stories", [])
        if stories:
            affected_stories.extend(stories)
        rationale = content.get("no_stories_rationale")
        if rationale:
            no_stories_rationale = rationale

    # Also check user_stories.yml in plan folder
    user_stories_file = plan_path / "user_stories.yml"
    if user_stories_file.exists():
        try:
            us_content = yaml.safe_load(user_stories_file.read_text())
            if us_content and isinstance(us_content, dict):
                stories = us_content.get("affected_stories", [])
                if stories:
                    affected_stories.extend(stories)
        except yaml.YAMLError:
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

    return results


def cmd_validate(args):
    """Validate plan folder structure and YAML.

    Enhanced with orchestration validation (EN-007):
    - Checks for orchestration_*.mmd file
    - Parses MMD to extract phase references
    - Compares with phases in plan_*.yml files
    - Reports validation results (PASS/FAIL with details)
    """
    from agenticcli.console import is_json_output, print_json

    plan_path = find_plan_folder(args.path)
    strict = getattr(args, "strict", False)
    errors = []
    warnings = []
    stub_files = []

    # Check folder structure
    if not plan_path.exists():
        print(f"Error: Path does not exist: {plan_path}", file=sys.stderr)
        sys.exit(1)

    # Flattened structure: plan_*.yml files directly in plan_path
    yaml_files = list(plan_path.glob("plan_*.yml"))
    if not yaml_files:
        errors.append("No plan_*.yml files in directory")

    # Validate YAML syntax and check for stub templates
    for yaml_file in yaml_files:
        try:
            content = yaml.safe_load(yaml_file.read_text())
            if content is None:
                warnings.append(f"{yaml_file.name}: Empty file")
            elif is_stub_template(content):
                stub_files.append(yaml_file.name)
        except yaml.YAMLError as e:
            errors.append(f"{yaml_file.name}: Invalid YAML - {e}")

    # Check for plan_completed.yml (optional in flattened structure)
    completed_file = plan_path / "plan_completed.yml"
    if not completed_file.exists():
        warnings.append("Missing plan_completed.yml (optional for new plans)")

    # Handle stub files - promote to errors in strict mode
    if stub_files:
        stub_message = "Stub template - needs population or deletion"
        for stub_file in stub_files:
            if strict:
                errors.append(f"{stub_file}: {stub_message}")
            else:
                warnings.append(f"{stub_file}: {stub_message}")

    # EN-007: Orchestration validation
    mmd_files = list(plan_path.glob("orchestration_*.mmd"))
    orchestration_result = {"status": "PASS", "details": []}

    if not mmd_files:
        orchestration_result["status"] = "FAIL"
        orchestration_result["details"].append("Missing: orchestration_*.mmd")
        orchestration_result["details"].append("Action: Spawn orchestration-planning agent")
        orchestration_result["details"].append("Command: agentic entrypoint execute _plan_build --compile")
        if strict:
            errors.append("Missing orchestration_*.mmd file")
        else:
            warnings.append("Missing orchestration_*.mmd file")
    else:
        # Parse MMD for phases and tasks
        mmd_file = mmd_files[0]
        try:
            mmd_content = mmd_file.read_text()
            mmd_phases = _parse_mmd_phases(mmd_content)
            mmd_tasks = _parse_mmd_tasks(mmd_content)

            # Collect phases and tasks from PlanRepository (TinyDB-first)
            yaml_phases = set()
            yaml_tasks = set()

            try:
                repo = _get_repo()
                plan_data_obj = repo.get_plan(plan_path.name)
                if (plan_data_obj and plan_data_obj.phases
                        and plan_data_obj.plan_folder == plan_path):
                    for phase in plan_data_obj.phases:
                        for task in (phase.tasks or []):
                            if task.id:
                                yaml_tasks.add(task.id.upper())
            except Exception:
                # Fallback: read YAML files directly
                for yaml_file in yaml_files:
                    try:
                        content = yaml.safe_load(yaml_file.read_text())
                        if not content:
                            continue
                        phases = _get_phases_from_content(content)
                        for phase in phases:
                            phase_id = _get_phase_id(phase)
                            if phase_id:
                                yaml_phases.add(phase_id.upper())
                            for task in phase.get("tasks", []):
                                task_id = task.get("id") or task.get("task_id", "")
                                if task_id:
                                    yaml_tasks.add(task_id.upper())
                    except yaml.YAMLError:
                        continue

            # Compare phases
            mmd_phase_set = set(p.upper() for p in mmd_phases)
            if yaml_phases and mmd_phase_set:
                missing_in_mmd = yaml_phases - mmd_phase_set
                missing_in_yaml = mmd_phase_set - yaml_phases

                if missing_in_mmd:
                    orchestration_result["details"].append(
                        f"Phases in YAML but not in MMD: {', '.join(sorted(missing_in_mmd))}"
                    )
                if missing_in_yaml:
                    orchestration_result["details"].append(
                        f"Phases in MMD but not in YAML: {', '.join(sorted(missing_in_yaml))}"
                    )

            # Compare tasks
            mmd_task_set = set(t.upper() for t in mmd_tasks)
            if yaml_tasks and mmd_task_set:
                missing_tasks_in_mmd = yaml_tasks - mmd_task_set
                if missing_tasks_in_mmd and len(missing_tasks_in_mmd) > len(yaml_tasks) // 2:
                    # Only warn if more than half the tasks are missing
                    orchestration_result["details"].append(
                        f"Many YAML tasks not referenced in MMD ({len(missing_tasks_in_mmd)} tasks)"
                    )

            # Set status based on findings
            if orchestration_result["details"]:
                orchestration_result["status"] = "WARN"
            else:
                orchestration_result["details"].append(f"Orchestration file: {mmd_file.name}")
                orchestration_result["details"].append(f"Phases found: {len(mmd_phases)}")
                orchestration_result["details"].append(f"Tasks referenced: {len(mmd_tasks)}")

        except IOError as e:
            orchestration_result["status"] = "FAIL"
            orchestration_result["details"].append(f"Cannot read MMD: {e}")
            errors.append(f"Cannot read {mmd_file.name}: {e}")

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

    # Loop type validation: check loop_structures.type against agent-loops.yml
    valid_loop_types = get_valid_loop_types()
    for yaml_file in yaml_files:
        try:
            content = yaml.safe_load(yaml_file.read_text())
            if not content:
                continue
            # Check root-level loop_structures
            loop_structures = content.get("loop_structures", [])
            # Also check under plan: key
            if not loop_structures and isinstance(content.get("plan"), dict):
                loop_structures = content["plan"].get("loop_structures", [])
            if not loop_structures or not isinstance(loop_structures, list):
                continue
            for loop in loop_structures:
                if not isinstance(loop, dict):
                    continue
                loop_type = loop.get("type")
                if loop_type and loop_type not in valid_loop_types:
                    warnings.append(
                        f"{yaml_file.name}: Loop type '{loop_type}' not defined in agent-loops.yml"
                    )
        except (yaml.YAMLError, Exception):
            continue

    # Additional structural validation via PlanService (non-fatal)
    try:
        from agenticguidance.services.plan import PlanService
        svc = PlanService()
        svc_result = svc.validate_plan_structure(plan_path)
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

    EN-006: Validates that orchestration_*.mmd exists before allowing
    task execution. Plans must be orchestrated before execution.
    """
    from agenticcli.console import (
        is_json_output,
        print_error,
        print_json,
    )

    task_id = args.task_id
    plan_path = find_plan_folder(args.plan)

    # EN-006: Validate orchestration MMD exists before task start
    mmd_files = list(plan_path.glob("orchestration_*.mmd"))
    if not mmd_files:
        if is_json_output():
            print_json({
                "error": "Cannot start task - plan has no orchestration_*.mmd",
                "task_id": task_id,
                "plan": plan_path.name,
                "hint": "Run 'agentic entrypoint execute _plan_build --compile' and spawn orchestration-planning agent",
            })
        else:
            print_error("Cannot start task - plan has no orchestration_*.mmd")
            print("Hint: Run 'agentic entrypoint execute _plan_build --compile' and spawn planner", file=sys.stderr)
        sys.exit(1)

    _update_task_status(plan_path, task_id, "in_progress")
    print(f"Task {task_id} marked as in_progress")


def cmd_task_complete(args):
    """Mark a task as completed."""
    task_id = args.task_id
    plan_path = find_plan_folder(args.plan)

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
            plan_doc = repo.get_plan(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.plan_folder.resolve() == plan_path.resolve()
            )
            if folder_matches:
                updated = repo.update_task_status(plan_path.name, task_id, new_status)
                if updated:
                    try:
                        repo.sync_to_yaml(plan_path.name)
                    except Exception:
                        pass
                    return
    except Exception:
        pass

    # YAML fallback: direct file mutation
    for yaml_file in plan_path.glob("plan_*.yml"):
        content = yaml_file.read_text()
        data = yaml.safe_load(content)
        if not data:
            continue

        plan = data.get("plan", data.get("feature", {}))
        modified = False

        for key in ["phases", "implementation_steps"]:
            items = plan.get(key, []) or data.get(key, [])
            for item in items:
                nested_tasks = item.get("tasks", [])
                for task in nested_tasks:
                    if task.get("id") == task_id or task.get("task_id") == task_id:
                        task["status"] = new_status
                        modified = True
                        break
                if modified:
                    break
                if item.get("id") == task_id or item.get("task_id") == task_id:
                    item["status"] = new_status
                    modified = True
                    break
            if modified:
                break

        if modified:
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

    from agenticcli.workflows.task_workflow import TaskPresetWorkflow

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

    # Try PlanRepository (TinyDB) first.
    # Only use TinyDB results when TinyDB has data for this plan AND the stored folder path matches
    # the actual plan_path (guards against stale data from temp/test plans with the same folder name).
    all_tasks = None
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_plan(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.plan_folder.resolve() == plan_path.resolve()
            )
            if folder_matches:
                sf = status_filter if status_filter != "all" else None
                task_data_list = repo.get_tasks(plan_path.name, status_filter=sf)
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
        # Fallback: existing YAML scanning logic
        yaml_files = list(plan_path.glob("plan_*.yml"))
        if not yaml_files:
            print_error(f"No plan_*.yml files found in {plan_path}")
            sys.exit(1)

        all_tasks = []

        for yaml_file in sorted(yaml_files):
            try:
                content = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError:
                continue

            if not content:
                continue

            # Extract tasks from phases structure (check both root and nested under plan)
            phases = _get_phases_from_content(content)
            for phase in phases:
                phase_id = _get_phase_id(phase)
                phase_name = phase.get("name", "")
                tasks = phase.get("tasks", [])

                for task in tasks:
                    task_status = task.get("status", "pending")
                    if status_filter != "all" and task_status != status_filter:
                        continue

                    task_info = {
                        "id": task.get("id") or task.get("task_id", ""),
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

    task_data = None
    source_file = None
    phase_info = None

    # Try PlanRepository (TinyDB) first
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_plan(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.plan_folder.resolve() == plan_path.resolve()
            )
            if folder_matches:
                td = repo.get_task(plan_path.name, task_id)
                if td is not None:
                    task_data = {
                        "id": td.id,
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

    # YAML fallback
    if task_data is None:
        for yaml_file in plan_path.glob("plan_*.yml"):
            try:
                content = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError:
                continue

            if not content:
                continue

            phases = _get_phases_from_content(content)
            for phase in phases:
                tasks = phase.get("tasks", [])
                for task in tasks:
                    if task.get("id") == task_id or task.get("task_id") == task_id:
                        task_data = task
                        source_file = yaml_file.name
                        phase_info = {
                            "phase_id": _get_phase_id(phase),
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

    # TinyDB-first: try to add task via PlanRepository
    tinydb_done = False
    new_task_id = custom_id
    phase_name_used = ""
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_plan(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.plan_folder.resolve() == plan_path.resolve()
            )
            if not folder_matches:
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
                existing = repo.get_tasks(plan_path.name)
                phase_prefix = phase_id or "task"
                task_num = len(existing) + 1
                new_task_id = f"{phase_prefix}_{task_num:03d}"

            added = repo.add_task(plan_path.name, phase_name_used, {
                "id": new_task_id,
                "name": description,
                "description": description,
                "status": "pending",
            })
            if added:
                tinydb_done = True
                # Sync to YAML for git visibility
                try:
                    repo.sync_to_yaml(plan_path.name)
                except Exception:
                    pass
    except Exception:
        pass

    # YAML fallback if TinyDB path failed
    if not tinydb_done:
        target_file = None
        for pattern in ["plan_build*.yml", "plan_*.yml"]:
            files = list(plan_path.glob(pattern))
            if files:
                target_file = files[0]
                break

        if not target_file:
            print_error("No plan_*.yml file found in plan directory")
            sys.exit(1)

        try:
            content = yaml.safe_load(target_file.read_text())
        except yaml.YAMLError as e:
            print_error(f"Failed to parse {target_file.name}: {e}")
            sys.exit(1)

        if not content:
            content = {"phases": []}

        phases = _get_phases_from_content(content)
        target_phase = None
        if phase_id:
            for phase in phases:
                if _get_phase_id(phase) == phase_id:
                    target_phase = phase
                    break
            if not target_phase:
                print_error(f"Phase '{phase_id}' not found")
                sys.exit(1)
        else:
            if phases:
                target_phase = phases[-1]
            else:
                target_phase = {"phase_id": "adhoc_01", "name": "Ad-hoc Tasks", "status": "pending", "tasks": []}
                phases.append(target_phase)
                content["phases"] = phases

        if not new_task_id:
            existing_ids = [t.get("task_id", "") for t in target_phase.get("tasks", [])]
            phase_prefix = _get_phase_id(target_phase) or "task"
            task_num = len(existing_ids) + 1
            new_task_id = f"{phase_prefix}_{task_num:03d}"

        new_task = {"task_id": new_task_id, "description": description, "status": "pending", "priority": priority}
        if "tasks" not in target_phase:
            target_phase["tasks"] = []
        target_phase["tasks"].append(new_task)

        with open(target_file, "w") as f:
            yaml.dump(content, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        phase_name_used = target_phase.get("name", "")

    if is_json_output():
        print_json({
            "task_id": new_task_id,
            "description": description,
            "phase": phase_name_used,
            "source": "TinyDB" if tinydb_done else "YAML",
        })
    else:
        source = "TinyDB" if tinydb_done else "YAML"
        print_success(f"Added task '{new_task_id}' to phase '{phase_name_used}' ({source})")


def cmd_archive(args):
    """Copy plan to completed folder."""
    import shutil

    plan_path = find_plan_folder(args.path)

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

    # Update completion metadata (flattened structure: plan_completed.yml in dest_dir)
    completed_file = dest_dir / "plan_completed.yml"
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

    # TinyDB: archive plan (update status + path)
    try:
        repo = _get_repo()
        if repo is not None:
            repo.archive_plan(plan_path.name)
    except Exception:
        pass


def cmd_unarchive(args, ctx=None):
    """Move a plan folder from completed/ back to live/.

    This is the reverse of archiving - useful when a plan was archived
    prematurely or needs to be resumed.

    Args:
        args: Parsed arguments with plan name and optional force flag.
        ctx: Optional CLIContext.
    """
    import shutil

    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_json,
        print_success,
        print_warning,
    )

    plan_name = args.plan
    force = getattr(args, "force", False)

    # Find the repository root by looking for docs/plans
    cwd = Path.cwd()
    plans_base = cwd / "docs" / "plans"

    if not plans_base.exists():
        print_error("No docs/plans directory found in current repository.")
        sys.exit(1)

    completed_dir = plans_base / "completed"
    live_dir = plans_base / "live"

    if not completed_dir.exists():
        print_error("No docs/plans/completed directory found.")
        sys.exit(1)

    # Find the plan in completed/
    # Support both exact name and partial match
    source_path = None

    # First try exact match
    exact_path = completed_dir / plan_name
    if exact_path.exists() and exact_path.is_dir():
        source_path = exact_path
    else:
        # Try to find by partial match (folder name contains plan_name)
        matches = [
            d for d in completed_dir.iterdir()
            if d.is_dir() and plan_name.lower() in d.name.lower()
        ]
        if len(matches) == 1:
            source_path = matches[0]
        elif len(matches) > 1:
            if is_json_output():
                print_json({
                    "error": "Multiple plans match the given name",
                    "matches": [m.name for m in matches],
                })
            else:
                print_error(f"Multiple plans match '{plan_name}':")
                for m in matches:
                    console.print(f"  - {m.name}")
                console.print("\nPlease specify the full folder name.")
            sys.exit(1)

    if source_path is None:
        if is_json_output():
            print_json({
                "error": f"Plan '{plan_name}' not found in completed/",
                "searched_in": str(completed_dir),
            })
        else:
            print_error(f"Plan '{plan_name}' not found in {completed_dir}")
        sys.exit(1)

    # Check destination
    dest_path = live_dir / source_path.name

    if dest_path.exists():
        if force:
            # --force: live/ already exists, just remove the completed/ copy
            # and update TinyDB to point to live/.
            try:
                shutil.rmtree(str(source_path))
            except OSError as e:
                if is_json_output():
                    print_json({"error": f"Failed to remove completed copy: {e}"})
                else:
                    print_error(f"Failed to remove completed copy: {e}")
                sys.exit(1)
            # Update TinyDB to point to live/ (non-fatal)
            try:
                from agenticguidance.services.plan_repository import PlanRepository
                repo = PlanRepository(auto_bootstrap=False)
                repo.resync_plan_folder(source_path.name, str(dest_path))
                repo.close()
            except Exception:
                pass
            if is_json_output():
                print_json({
                    "result": "success",
                    "action": "force_resync",
                    "removed": str(source_path),
                    "destination": str(dest_path),
                    "plan_name": source_path.name,
                })
            else:
                print_success(f"Removed completed copy and resynced to: {dest_path}")
            return
        else:
            if is_json_output():
                print_json({
                    "error": "Destination already exists",
                    "source": str(source_path),
                    "destination": str(dest_path),
                    "hint": "Use --force to remove the completed/ copy and resync to live/",
                })
            else:
                print_error(f"Destination already exists: {dest_path}")
                console.print("[dim]Use --force to remove the completed/ copy and resync TinyDB to live/.[/dim]")
            sys.exit(1)

    # Confirm unless --force is set
    if not force and not is_json_output():
        console.print(f"[bold]Unarchiving plan:[/bold] {source_path.name}")
        console.print(f"  From: {source_path}")
        console.print(f"  To:   {dest_path}")
        response = input("\nProceed? [y/N] ")
        if response.lower() != "y":
            print_warning("Aborted")
            sys.exit(0)

    # Ensure live directory exists
    live_dir.mkdir(parents=True, exist_ok=True)

    # Move the folder
    try:
        shutil.move(str(source_path), str(dest_path))
    except OSError as e:
        if is_json_output():
            print_json({
                "error": f"Failed to move folder: {e}",
                "source": str(source_path),
                "destination": str(dest_path),
            })
        else:
            print_error(f"Failed to move folder: {e}")
        sys.exit(1)

    # Update metadata to reflect unarchival
    completed_file = dest_path / "plan_completed.yml"
    if completed_file.exists():
        try:
            data = yaml.safe_load(completed_file.read_text())
            if data is None:
                data = {}
            data["unarchived_date"] = datetime.now().strftime("%Y-%m-%d")
            data["unarchived_from"] = str(source_path)
            with open(completed_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        except yaml.YAMLError:
            pass  # Non-fatal if metadata update fails

    # TinyDB: unarchive plan (update status + path)
    try:
        repo = _get_repo()
        if repo is not None:
            repo.unarchive_plan(source_path.name)
    except Exception:
        pass

    # Output result
    if is_json_output():
        print_json({
            "result": "success",
            "source": str(source_path),
            "destination": str(dest_path),
            "plan_name": source_path.name,
        })
    else:
        print_success(f"Unarchived plan to: {dest_path}")


def cmd_cancel(args, ctx=None):
    """Cancel an active plan.

    Sets the plan status to 'cancelled' in plan_build.yml and optionally
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

    plan_folder = find_plan_folder(path)

    # Get current status (TinyDB-first, YAML fallback)
    current_status = "unknown"
    folder_matches = False
    try:
        repo = _get_repo()
        if repo is not None:
            plan_data = repo.get_plan(plan_folder.name)
            folder_matches = (
                plan_data is not None
                and plan_data.plan_folder.resolve() == plan_folder.resolve()
            )
            if folder_matches:
                current_status = plan_data.status or "unknown"
    except Exception:
        pass

    if current_status == "unknown":
        build_file = plan_folder / "plan_build.yml"
        if build_file.exists():
            try:
                data = yaml.safe_load(build_file.read_text()) or {}
                current_status = data.get("status", "unknown")
            except yaml.YAMLError:
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
            result = repo.cancel_plan(plan_folder.name)
            if result.success:
                tinydb_done = True
                try:
                    repo.sync_to_yaml(plan_folder.name)
                except Exception:
                    pass
    except Exception:
        pass

    # YAML fallback
    if not tinydb_done:
        build_file = plan_folder / "plan_build.yml"
        if not build_file.exists():
            print_error(f"No plan_build.yml found in {plan_folder}")
            sys.exit(1)
        try:
            data = yaml.safe_load(build_file.read_text()) or {}
        except yaml.YAMLError as e:
            print_error(f"Failed to parse plan_build.yml: {e}")
            sys.exit(1)
        data["status"] = "cancelled"
        data["cancelled_date"] = datetime.now().strftime("%Y-%m-%d")
        with open(build_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

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
    """List all plans in the repository.

    Enhanced with orchestration status fields (EN-001, EN-002):
    - has_orchestration: Whether plan has orchestration_*.mmd file
    - action_required: What action the orchestration agent should take
      - blocked: Plan is deferred or has dependencies
      - needs_planning: No MMD file or no tasks defined
      - execute: Has pending tasks ready for execution
      - archive: All tasks completed, ready to archive
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

    # Find docs/plans/live directory from current working directory
    cwd = Path.cwd()
    plans_dir = cwd / "docs" / "plans" / "live"

    if not plans_dir.exists():
        print_error("No docs/plans/live directory found in current repository.")
        sys.exit(1)

    plans_data = []

    # Get plan data via PlanService (TinyDB-first)
    try:
        from agenticguidance.services.plan import PlanService
        plan_service = PlanService()
        plan_metas = plan_service.list_plans(status="live")
    except Exception as e:
        print_error(f"Failed to load PlanService: {e}")
        sys.exit(1)

    for meta in plan_metas:
        plan_folder = meta.plan_folder
        if not plan_folder.is_dir():
            continue

        # Only include plans that have plan_*.yml files (skip empty scaffolds)
        yaml_files = list(plan_folder.glob("plan_*.yml"))
        if not yaml_files:
            continue

        # Get task counts via PlanService
        try:
            plan_data_obj = plan_service.get_plan(str(plan_folder))
            tasks = plan_data_obj.tasks if plan_data_obj else []
        except Exception:
            tasks = []

        total_pending = sum(1 for t in tasks if t.status == "pending")
        total_in_progress = sum(1 for t in tasks if t.status == "in_progress")
        total_completed = sum(1 for t in tasks if t.status == "completed")
        has_tasks = len(tasks) > 0
        plan_status = meta.status or "unknown"

        # EN-001: Filesystem check for orchestration (NOT in PlanService)
        mmd_files = list(plan_folder.glob("orchestration_*.mmd"))
        has_orchestration = len(mmd_files) > 0

        total = total_pending + total_in_progress + total_completed

        # EN-002: Determine action_required based on plan state
        # Priority order matters - check from most blocking to least
        if plan_status == "deferred":
            action_required = "blocked"
        elif not has_orchestration:
            action_required = "needs_planning"
        elif not has_tasks or total == 0:
            action_required = "needs_planning"
        elif total_pending > 0 or total_in_progress > 0:
            action_required = "execute"
        elif total_completed == total and total > 0:
            action_required = "archive"
        else:
            action_required = "blocked"

        pct = (total_completed / total) * 100 if total > 0 else 0

        plans_data.append(
            {
                "name": plan_folder.name,
                "status": plan_status,
                "has_orchestration": has_orchestration,
                "has_tasks": has_tasks,
                "action_required": action_required,
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
            # Format orchestration status
            orch = "[green]Yes[/green]" if plan["has_orchestration"] else "[red]No[/red]"
            # Format action_required with color coding
            action = plan["action_required"]
            if action == "blocked":
                action_fmt = "[dim]blocked[/dim]"
            elif action == "needs_planning":
                action_fmt = "[yellow]needs_planning[/yellow]"
            elif action == "execute":
                action_fmt = "[green]execute[/green]"
            elif action == "archive":
                action_fmt = "[cyan]archive[/cyan]"
            else:
                action_fmt = action

            rows.append(
                [
                    f"[bold]{plan['name']}[/bold]",
                    format_status(plan["status"]),
                    orch,
                    action_fmt,
                    f"[dim]{plan['pending']}[/dim]",
                    f"[yellow]{plan['in_progress']}[/yellow]",
                    f"[green]{plan['completed']}[/green]",
                    f"[cyan]{progress}[/cyan]",
                ]
            )

        print_table("", ["Plan", "Status", "Orch", "Action", "Pending", "In Prog", "Done", "Progress"], rows)


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
    from agenticguidance.services import MoveResult, PlanMovementWorkflow

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
        print_info,
        print_json,
        print_success,
        print_warning,
    )

    task_id = args.task_id
    new_status = args.status
    note = getattr(args, "note", None)
    plan_path = find_plan_folder(getattr(args, "plan", None))

    # TinyDB-first: update task status via PlanRepository
    task_found = False
    updated_file = None
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_plan(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.plan_folder.resolve() == plan_path.resolve()
            )
            if not folder_matches:
                repo = None  # Skip TinyDB path
    except Exception:
        repo = None
    try:
        if repo is not None:
            # Check current status for transition validation
            current_task = repo.get_task(plan_path.name, task_id)
            if current_task is not None:
                old_status = current_task.status or "pending"

                valid_transitions = {
                    "pending": ["in_progress", "blocked"],
                    "in_progress": ["completed", "blocked", "pending"],
                    "completed": ["pending", "in_progress"],
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

                updated = repo.update_task_status(plan_path.name, task_id, new_status)
                if updated:
                    task_found = True
                    updated_file = "(via TinyDB)"
                    # Sync to YAML for git visibility
                    try:
                        repo.sync_to_yaml(plan_path.name)
                    except Exception:
                        pass
    except Exception:
        pass

    # YAML fallback
    if not task_found:
        yaml_files = list(plan_path.glob("plan_*.yml"))
        if not yaml_files:
            print_error(f"No plan_*.yml files found in {plan_path}")
            sys.exit(1)

        for yaml_file in yaml_files:
            try:
                content = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError:
                continue

            if not content:
                continue

            phases = _get_phases_from_content(content)
            for phase in phases:
                tasks = phase.get("tasks", [])
                for task in tasks:
                    tid = task.get("id") or task.get("task_id") or ""
                    if tid == task_id:
                        old_status = task.get("status", "pending")

                        valid_transitions = {
                            "pending": ["in_progress", "blocked"],
                            "in_progress": ["completed", "blocked", "pending"],
                            "completed": ["pending", "in_progress"],
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
                        if note:
                            task["completion_note"] = note
                        if new_status == "completed":
                            task["completed_at"] = datetime.now().isoformat()

                        task_found = True
                        updated_file = yaml_file
                        break
                if task_found:
                    break

            if task_found:
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

    # Try PlanRepository (TinyDB) first for both current task and all-tasks stats.
    current_task = None
    all_tasks = None
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_plan(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.plan_folder.resolve() == plan_path.resolve()
            )
            if folder_matches:
                repo_task = repo.get_current_task(plan_path.name)
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
                counts = repo.get_task_counts(plan_path.name)
                all_tasks = counts  # Used for completion stats below
            repo.close()
    except Exception:
        current_task = None
        all_tasks = None

    # YAML fallback: scan plan files for full task details
    if current_task is None and all_tasks is None:
        yaml_files = list(plan_path.glob("plan_*.yml"))
        if not yaml_files:
            print_error(f"No plan_*.yml files found in {plan_path}")
            sys.exit(1)

        yaml_tasks = []
        for yaml_file in sorted(yaml_files):
            try:
                content = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError:
                continue

            if not content:
                continue

            phases = _get_phases_from_content(content)
            for phase in phases:
                phase_name = phase.get("name", "")
                phase_id = _get_phase_id(phase)
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
                    yaml_tasks.append(task_info)

        # Find current task from YAML scan
        for task in yaml_tasks:
            if task["status"] == "in_progress":
                current_task = task
                break
        if not current_task:
            for task in yaml_tasks:
                if task["status"] == "pending":
                    current_task = task
                    break

        # Build completion stats from YAML tasks
        completed_count = sum(1 for t in yaml_tasks if t["status"] == "completed")
        all_tasks = {
            "total": len(yaml_tasks),
            "completed": completed_count,
        }

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
    """Add a new phase to plan_build.yml.

    Creates or updates plan_build.yml to include a new phase with the
    specified ID, name, and description.

    Args:
        args: Parsed arguments with id, name, description, plan.
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
    plan_path = find_plan_folder(getattr(args, "plan", None))

    # TinyDB-first: add phase via PlanRepository
    tinydb_done = False
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_plan(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.plan_folder.resolve() == plan_path.resolve()
            )
            if folder_matches:
                # Check for duplicate
                existing = repo.get_phase(plan_path.name, phase_name)
                if existing:
                    print_error(f"Phase with name '{phase_name}' already exists")
                    sys.exit(1)

                added = repo.add_phase(plan_path.name, {
                    "name": phase_name,
                    "description": phase_description,
                    "status": "pending",
                })
                if added:
                    tinydb_done = True
                    try:
                        repo.sync_to_yaml(plan_path.name)
                    except Exception:
                        pass
    except Exception:
        pass

    # YAML fallback
    if not tinydb_done:
        build_file = plan_path / "plan_build.yml"

        if build_file.exists():
            try:
                content = yaml.safe_load(build_file.read_text())
                if content is None:
                    content = {}
            except yaml.YAMLError as e:
                print_error(f"Failed to parse {build_file.name}: {e}")
                sys.exit(1)
        else:
            print_error(f"plan_build.yml not found in {plan_path}")
            print("Hint: Create a plan first with 'agentic plan init' or 'agentic plan scaffold'", file=sys.stderr)
            sys.exit(1)

        if "phases" in content:
            phases = content["phases"]
        elif "plan" in content and "phases" in content["plan"]:
            phases = content["plan"]["phases"]
        else:
            phases = []
            content["phases"] = phases

        for existing_phase in phases:
            existing_id = _get_phase_id(existing_phase)
            if existing_id == phase_id:
                print_error(f"Phase with ID '{phase_id}' already exists")
                sys.exit(1)

        new_phase = {
            "phase_id": phase_id,
            "name": phase_name,
            "status": "pending",
            "tasks": [],
        }
        if phase_description:
            new_phase["description"] = phase_description

        phases.append(new_phase)

        # Update the content (handle both structures)
        if "plan" in content and "phases" in content["plan"]:
            content["plan"]["phases"] = phases
        else:
            content["phases"] = phases

        try:
            with open(build_file, "w") as f:
                yaml.dump(content, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        except IOError as e:
            print_error(f"Failed to write {build_file}: {e}")
            sys.exit(1)

    source = "TinyDB" if tinydb_done else "YAML"
    if is_json_output():
        print_json({
            "phase_id": phase_id,
            "name": phase_name,
            "description": phase_description,
            "source": source,
            "plan_path": str(plan_path),
        })
    else:
        print_success(f"Added phase '{phase_id}' ({phase_name}) to {plan_path.name} ({source})")


def cmd_phase_list(args, ctx=None):
    """List all phases in the plan with task counts.

    Displays a table showing phase ID, name, status, and task count
    from plan_build.yml.

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

    plan_path = find_plan_folder(getattr(args, "plan", None))

    # Try PlanRepository for phase data (TinyDB-first)
    phases_data = None
    try:
        repo = _get_repo()
        plan_data_obj = repo.get_plan(plan_path.name)
        if (plan_data_obj and plan_data_obj.phases
                and plan_data_obj.plan_folder == plan_path):
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
        # Fallback: Load plan_build.yml directly
        build_file = plan_path / "plan_build.yml"
        if not build_file.exists():
            print_error(f"plan_build.yml not found in {plan_path}")
            sys.exit(1)

        try:
            content = yaml.safe_load(build_file.read_text())
        except yaml.YAMLError as e:
            print_error(f"Failed to parse {build_file.name}: {e}")
            sys.exit(1)

        if not content:
            print_error(f"{build_file.name} is empty")
            sys.exit(1)

        # Get phases from content
        phases = _get_phases_from_content(content)

        if not phases:
            if is_json_output():
                print_json({"phases": [], "count": 0})
            else:
                console.print("[dim]No phases found in plan_build.yml[/dim]")
            return

        # Build phase data with task counts
        phases_data = []
        for phase in phases:
            phase_id = _get_phase_id(phase)
            phase_name = phase.get("name", "")
            phase_status = phase.get("status", "pending")
            tasks = phase.get("tasks", [])
            task_count = len(tasks)

            phases_data.append({
                "id": phase_id,
                "name": phase_name,
                "status": phase_status,
                "tasks": task_count,
            })

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
    """Update a phase in plan_build.yml.

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
    plan_path = find_plan_folder(getattr(args, "plan", None))

    # Validate that at least one update field is provided
    if not new_status and not new_name:
        print_error("At least one of --status or --name must be provided")
        sys.exit(1)

    # TinyDB-first: update phase via PlanRepository
    phase_found = False
    old_status = None
    old_name = None
    try:
        repo = _get_repo()
        if repo is not None:
            plan_doc = repo.get_plan(plan_path.name)
            folder_matches = (
                plan_doc is not None
                and plan_doc.plan_folder.resolve() == plan_path.resolve()
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

                if updates:
                    updated = repo.update_phase(plan_path.name, phase_id, updates)
                    if updated:
                        phase_found = True
                        try:
                            repo.sync_to_yaml(plan_path.name)
                        except Exception:
                            pass
    except Exception:
        pass

    # YAML fallback
    if not phase_found:
        build_file = plan_path / "plan_build.yml"
        if not build_file.exists():
            print_error(f"plan_build.yml not found in {plan_path}")
            sys.exit(1)

        try:
            content = yaml.safe_load(build_file.read_text())
            if content is None:
                content = {}
        except yaml.YAMLError as e:
            print_error(f"Failed to parse {build_file.name}: {e}")
            sys.exit(1)

        if "phases" in content:
            phases = content["phases"]
            phases_location = "root"
        elif "plan" in content and "phases" in content["plan"]:
            phases = content["plan"]["phases"]
            phases_location = "nested"
        else:
            print_error("No phases found in plan_build.yml")
            sys.exit(1)

        for phase in phases:
            existing_id = _get_phase_id(phase)
            if existing_id == phase_id:
                phase_found = True
                old_status = phase.get("status", "pending")
                old_name = phase.get("name", "")

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
                    phase["status"] = new_status
                if new_name:
                    phase["name"] = new_name
                break

        if not phase_found:
            if is_json_output():
                print_json({"error": f"Phase not found: {phase_id}"})
            else:
                print_error(f"Phase not found: {phase_id}")
                print("Hint: Use 'agentic plan phase list' to see available phase IDs", file=sys.stderr)
            sys.exit(1)
        # YAML write-back (only in fallback path)
        if phases_location == "nested":
            content["plan"]["phases"] = phases
        else:
            content["phases"] = phases

        try:
            with open(build_file, "w") as f:
                yaml.dump(content, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        except IOError as e:
            print_error(f"Failed to write {build_file}: {e}")
            sys.exit(1)

    if is_json_output():
        result = {
            "phase_id": phase_id,
            "file": build_file.name,
            "plan_path": str(plan_path),
        }
        if new_status:
            result["old_status"] = old_status
            result["new_status"] = new_status
        if new_name:
            result["old_name"] = old_name
            result["new_name"] = new_name
        print_json(result)
    else:
        changes = []
        if new_status:
            changes.append(f"status: {old_status} -> {new_status}")
        if new_name:
            changes.append(f"name: '{old_name}' -> '{new_name}'")
        print_success(f"Updated phase '{phase_id}' in {build_file.name} ({', '.join(changes)})")


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
    tasks = phase.get("tasks", [])

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
    """Generate orchestration MMD from plan YAML files.

    Reads plan_*.yml files in the plan folder and generates a Mermaid
    flowchart diagram with:
    - Phase nodes from YAML
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

    plan_path = find_plan_folder(getattr(args, "plan", None))
    output_name = getattr(args, "output", None)
    force = getattr(args, "force", False)

    # Collect all phases via PlanRepository (TinyDB-first)
    all_phases = []
    plan_name = None
    plan_objective = None

    try:
        repo = _get_repo()
        plan_data_obj = repo.get_plan(plan_path.name)
        if (plan_data_obj and plan_data_obj.phases
                and plan_data_obj.plan_folder == plan_path):
            plan_name = plan_data_obj.name or ""
            plan_objective = plan_data_obj.objective or ""
            for phase in plan_data_obj.phases:
                all_phases.append({
                    "name": phase.name,
                    "status": phase.status,
                    "execution": phase.execution,
                    "tasks": [
                        {"id": t.id, "task_id": t.id, "name": t.name, "status": t.status, "agent": t.agent}
                        for t in (phase.tasks or [])
                    ],
                })
    except Exception:
        pass

    if not all_phases:
        # Fallback: read plan YAML files directly
        yaml_files = list(plan_path.glob("plan_*.yml"))
        if not yaml_files:
            print_error(f"No plan_*.yml files found in {plan_path}")
            sys.exit(1)

        for yaml_file in sorted(yaml_files):
            try:
                content = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError as e:
                print_warning(f"Skipping {yaml_file.name}: {e}")
                continue

            if not content:
                continue

            if not plan_name:
                plan_name = content.get("name", "")
            if not plan_objective:
                plan_objective = content.get("objective", "")

            phases = _get_phases_from_content(content)
            for phase in phases:
                all_phases.append(phase)

    if not all_phases:
        print_error("No phases found in plan YAML files")
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
    mmd_lines.append(f"%% INPUT_PATH: {plan_path}/plan_build.yml")
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
            tasks = phase.get("tasks", [])
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
    mmd_lines.append("    %% agentic plan move folder --plan <path>")
    mmd_lines.append("    UpdatePlanStatus --> ArchivePlan[Archive to docs/plans/completed/]")
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
    """Validate orchestration MMD against plan YAML files.

    Compares the orchestration_*.mmd file against plan_*.yml files to detect:
    - Missing phases: YAML phases not mentioned in MMD
    - Missing task IDs: Task IDs from YAML not referenced in MMD
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

    plan_path = find_plan_folder(getattr(args, "plan", None))
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
    yaml_files = list(plan_path.glob("plan_*.yml"))

    try:
        repo = _get_repo()
        plan_data_obj = repo.get_plan(plan_path.name)
        if (plan_data_obj and plan_data_obj.phases
                and plan_data_obj.plan_folder == plan_path):
            source = "(via TinyDB)"
            for phase in plan_data_obj.phases:
                phase_name = phase.name or ""
                # PhaseData doesn't carry explicit phase_id; downstream
                # comparison only uses IDs when present
                for task in (phase.tasks or []):
                    if task.id:
                        yaml_tasks.append({
                            "id": task.id,
                            "phase_id": "",
                            "name": task.name or "",
                            "source": source,
                        })
    except Exception:
        pass

    if not yaml_tasks:
        # Fallback: read plan YAML files
        if not yaml_files:
            print_error(f"No plan_*.yml files found in {plan_path}")
            sys.exit(2)

        for yaml_file in sorted(yaml_files):
            try:
                content = yaml.safe_load(yaml_file.read_text())
            except yaml.YAMLError as e:
                print_warning(f"Skipping {yaml_file.name}: YAML parse error - {e}")
                continue

            if not content:
                continue

            # Collect phases
            phases = _get_phases_from_content(content)
            for phase in phases:
                phase_id = _get_phase_id(phase)
                phase_name = phase.get("name", "")
                if phase_id:
                    yaml_phases.append({"id": phase_id, "name": phase_name, "source": yaml_file.name})
                    yaml_phase_ids.add(phase_id)

                # Collect tasks from this phase
                tasks = phase.get("tasks", [])
                for task in tasks:
                    task_id = task.get("id") or task.get("task_id", "")
                    if task_id:
                        yaml_tasks.append({
                            "id": task_id,
                            "phase_id": phase_id,
                            "name": task.get("name", ""),
                            "source": yaml_file.name,
                        })

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
            "yaml_files": [f.name for f in yaml_files],
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
        print_info(f"Against: {', '.join(f.name for f in yaml_files)}")
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
    """List user stories from plan YAML files.

    Reads user_stories arrays from plan_*.yml files and displays
    them in a table with ID, As (persona), I Want (action), and Command columns.

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

    plan_path = find_plan_folder(getattr(args, "plan", None))

    # Flattened structure: YAML files directly in plan_path
    yaml_files = list(plan_path.glob("plan_*.yml"))
    if not yaml_files:
        print_error(f"No plan_*.yml files found in {plan_path}")
        sys.exit(1)

    all_stories = []

    for yaml_file in sorted(yaml_files):
        try:
            content = yaml.safe_load(yaml_file.read_text())
        except yaml.YAMLError:
            continue

        if not content:
            continue

        # Extract user_stories from content
        # Can be at root level or nested under plan/feature
        user_stories = content.get("user_stories", [])
        if not user_stories:
            plan_data = content.get("plan", content.get("feature", {}))
            user_stories = plan_data.get("user_stories", [])

        for story in user_stories:
            story_info = {
                "id": story.get("id", ""),
                "as": story.get("as", ""),
                "i_want": story.get("i_want", ""),
                "so_that": story.get("so_that", ""),
                "command": story.get("command", ""),
                "acceptance": story.get("acceptance", ""),
                "source_file": yaml_file.name,
            }
            all_stories.append(story_info)

    if is_json_output():
        print_json({"user_stories": all_stories, "count": len(all_stories)})
    else:
        print_header(f"User Stories in {plan_path.name}")

        if not all_stories:
            console.print("[dim]No user stories found.[/dim]")
            return

        rows = []
        for story in all_stories:
            # Truncate i_want to fit in table
            i_want = story["i_want"]
            if len(i_want) > 40:
                i_want = i_want[:37] + "..."

            rows.append([
                f"[bold]{story['id']}[/bold]",
                story["as"],
                i_want,
                f"[dim]{story['command']}[/dim]" if story["command"] else "[dim]-[/dim]",
            ])

        print_table("", ["ID", "As", "I Want", "Command"], rows)

        console.print(f"\n[dim]Total: {len(all_stories)} user stories[/dim]")


def cmd_stories_test(args, ctx=None):
    """Generate blind test scenarios from user stories.

    Reads user_stories arrays from plan_*.yml files and generates
    executable test cases in YAML format.

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

    plan_path = find_plan_folder(getattr(args, "plan", None))
    output_file = getattr(args, "output", None)
    output_format = getattr(args, "format", "yaml")

    # Flattened structure: YAML files directly in plan_path
    yaml_files = list(plan_path.glob("plan_*.yml"))
    if not yaml_files:
        print_error(f"No plan_*.yml files found in {plan_path}")
        sys.exit(1)

    all_stories = []

    for yaml_file in sorted(yaml_files):
        try:
            content = yaml.safe_load(yaml_file.read_text())
        except yaml.YAMLError:
            continue

        if not content:
            continue

        # Extract user_stories from content
        # Can be at root level or nested under plan/feature
        user_stories = content.get("user_stories", [])
        if not user_stories:
            plan_data = content.get("plan", content.get("feature", {}))
            user_stories = plan_data.get("user_stories", [])

        for story in user_stories:
            story_info = {
                "id": story.get("id", ""),
                "as": story.get("as", ""),
                "i_want": story.get("i_want", ""),
                "so_that": story.get("so_that", ""),
                "command": story.get("command", ""),
                "acceptance": story.get("acceptance", ""),
                "source_file": yaml_file.name,
            }
            all_stories.append(story_info)

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

    DEPRECATED: Use `agentic plan init --objective` instead.
    This command is kept for backward compatibility and redirects to cmd_init.
    """
    import sys

    from agenticcli.console import (
        is_json_output,
        print_warning,
    )

    if not is_json_output():
        print_warning(
            "plan bootstrap is deprecated. Use: agentic plan init <branch> --objective '<objective>' --description '<desc>'"
        )

    # Redirect to cmd_init by forwarding args
    cmd_init(args, ctx)


def _find_plans_base() -> Optional[Path]:
    """Find the docs/plans base directory.

    Walks up from CWD looking for a docs/plans directory.

    Returns:
        Path to docs/plans if found, None otherwise.
    """
    current = Path.cwd()
    while current != current.parent:
        plans_dir = current / "docs" / "plans"
        if plans_dir.is_dir():
            return plans_dir
        current = current.parent
    return None


def cmd_db_sync(args):
    """Rebuild TinyDB from YAML files or export DB to YAML.

    With --export: writes TinyDB state back to YAML files (reverse sync).
    Without --export: imports all YAML plan files into TinyDB.
    """
    from agenticguidance.services.plan_repository import PlanRepository

    json_output = getattr(args, "json", False)
    export_mode = getattr(args, "export", False)

    try:
        repo = PlanRepository(auto_bootstrap=False)

        if export_mode:
            # Export TinyDB to YAML
            plans = repo.list_plans()
            exported = 0
            failed = 0
            for plan_meta in plans:
                ok = repo.sync_to_yaml(plan_meta.plan_folder_name)
                if ok:
                    exported += 1
                else:
                    failed += 1
            result = {"exported": exported, "failed": failed}
            if json_output:
                import json
                print(json.dumps(result))
            else:
                print(f"Exported {exported} plans to YAML ({failed} failed)")
        else:
            # Import YAML to TinyDB
            plans_base = _find_plans_base()
            if not plans_base:
                if json_output:
                    import json
                    print(json.dumps({"error": "Could not find docs/plans directory"}))
                else:
                    print("Error: Could not find docs/plans directory", file=sys.stderr)
                sys.exit(1)

            stats = repo.import_all_yaml(plans_base)
            if json_output:
                import json
                print(json.dumps(stats))
            else:
                print(f"Sync complete: {stats['imported']} imported, {stats['skipped']} skipped, {stats['failed']} failed")

        repo.close()
    except Exception as e:
        if json_output:
            import json
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_db_status(args):
    """Show TinyDB database statistics."""
    from agenticguidance.services.plan_repository import PlanRepository

    json_output = getattr(args, "json", False)

    try:
        repo = PlanRepository(auto_bootstrap=False)

        plans = repo.list_plans()
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
