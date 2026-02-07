"""Git repository utilities.

Provides helpers for discovering git repository information.
"""

import os
import subprocess
from pathlib import Path


def get_project_root() -> Path | None:
    """Discover the project root using git or environment variable.

    Checks in order:
        1. AGENTIC_PROJECT_ROOT environment variable (validated)
        2. Git repository root (via git rev-parse --show-toplevel)

    Returns:
        Path to project root, or None if not discoverable.
    """
    # Check environment variable first
    env_root = os.environ.get("AGENTIC_PROJECT_ROOT")
    if env_root:
        env_path = Path(env_root)
        if env_path.exists() and env_path.is_dir():
            return env_path

    # Fall back to git discovery
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_plans_dir() -> Path | None:
    """Get the plans directory path.

    Checks in order:
        1. AGENTIC_PLANS_DIR environment variable (validated)
        2. {project_root}/docs/plans/live

    Returns:
        Path to live plans directory, or None if not found.
    """
    # Get project root for fallback
    project_root = get_project_root()

    # Check environment variable first
    env_plans = os.environ.get("AGENTIC_PLANS_DIR")
    if env_plans:
        env_path = Path(env_plans)
        if env_path.exists() and env_path.is_dir():
            # Validate it's within project root if available (security)
            if project_root:
                try:
                    env_path.relative_to(project_root)
                    return env_path
                except ValueError:
                    # Path is outside project root, skip
                    pass
            else:
                # No project root to validate against, trust the env var
                return env_path

    # Fall back to standard location relative to project root
    if project_root:
        plans_dir = project_root / "docs" / "plans" / "live"
        if plans_dir.exists():
            return plans_dir

    return None


def find_main_worktree(repo_root: Path) -> Path | None:
    """Find the main worktree path (branch main or master).

    Main-First Planning: Plans should always be created in the main worktree
    for visibility and traceability.

    Args:
        repo_root: Path to any worktree in the repository.

    Returns:
        Path to main worktree, or None if not found.
    """
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
