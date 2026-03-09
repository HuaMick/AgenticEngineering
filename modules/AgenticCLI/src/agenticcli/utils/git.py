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
