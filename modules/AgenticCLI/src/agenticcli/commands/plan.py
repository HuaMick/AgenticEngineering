"""Plan management commands - REMOVED.

All plan commands have been replaced by 'agentic epic ...' commands.
This module retains helper functions used by other modules.
"""

import subprocess
import sys
from pathlib import Path

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


def find_plan_folder(path: str | None = None) -> Path:
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

    # Auto-detect: look for docs/epics/live/ in current directory tree
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


def handle(args, ctx=None):
    """All plan commands are removed. Use 'agentic epic' instead."""
    import json
    json_mode = getattr(args, 'json_output', False) or getattr(args, 'json_mode', False) or getattr(args, 'json', False)
    if json_mode:
        print(json.dumps({"error": "Command removed. Use 'agentic epic ...' instead."}))
    else:
        print("Command removed. Use 'agentic epic ...' instead.", file=sys.stderr)
        print("See 'agentic epic --help' for available commands.", file=sys.stderr)
    sys.exit(1)
