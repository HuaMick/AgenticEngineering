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


def get_epics_dir() -> Path | None:
    """Get the epics directory path.

    Checks in order:
        1. AGENTIC_EPICS_DIR environment variable (primary, validated)
        2. AGENTIC_PLANS_DIR environment variable (deprecated fallback)
        3. {project_root}/docs/epics/live

    Returns:
        Path to live epics directory, or None if not found.
    """
    # Get project root for fallback
    project_root = get_project_root()

    def _resolve_env_path(env_value: str) -> Path | None:
        """Resolve and validate an environment variable path."""
        env_path = Path(env_value)
        if env_path.exists() and env_path.is_dir():
            # Validate it's within project root if available (security)
            if project_root:
                try:
                    env_path.relative_to(project_root)
                    return env_path
                except ValueError:
                    # Path is outside project root, skip
                    return None
            else:
                # No project root to validate against, trust the env var
                return env_path
        return None

    # Check primary environment variable first
    env_epics = os.environ.get("AGENTIC_EPICS_DIR")
    if env_epics:
        resolved = _resolve_env_path(env_epics)
        if resolved is not None:
            return resolved

    # Check deprecated fallback environment variable
    env_plans = os.environ.get("AGENTIC_PLANS_DIR")
    if env_plans:
        resolved = _resolve_env_path(env_plans)
        if resolved is not None:
            return resolved

    # Fall back to standard location relative to project root
    if project_root:
        epics_dir = project_root / "docs" / "epics" / "live"
        if epics_dir.exists():
            return epics_dir

    return None


# Backward compatibility alias
get_plans_dir = get_epics_dir
