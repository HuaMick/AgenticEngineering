"""Shared epic lock for preventing concurrent orchestration of the same epic.

Provides file-based locking used by both PlannerLoopRunner (planning) and
ExecutionRunner (execution) to ensure only one orchestration process runs
per epic at a time.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from agenticcli.utils.state_store import is_process_running

logger = logging.getLogger(__name__)


def acquire_epic_lock(epic_folder: str) -> bool:
    """Acquire a file-based lock to prevent concurrent orchestration.

    Uses the same lock path for both planning and execution, so they
    contend on the same lock and cannot run simultaneously for the
    same epic.

    Args:
        epic_folder: Epic folder name.

    Returns:
        True if lock acquired, False if another process holds it.
    """
    lock_dir = Path.home() / ".agentic" / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / f"orchestrate_{epic_folder}.lock"
    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text())
            pid = data.get("pid")
            if pid and is_process_running(pid):
                logger.error(
                    "Epic %s already being orchestrated by PID %d (started %s)",
                    epic_folder, pid, data.get("started_at", "unknown"),
                )
                return False
            # Stale lock — owner process is dead
            logger.warning(
                "Clearing stale lock for %s (PID %d no longer running)",
                epic_folder, pid,
            )
        except (json.JSONDecodeError, OSError):
            pass  # Corrupt lock file — overwrite it
    lock_file.write_text(json.dumps({
        "pid": os.getpid(),
        "started_at": datetime.now().isoformat(),
    }))
    return True


def release_epic_lock(epic_folder: str):
    """Release the file-based orchestration lock.

    Args:
        epic_folder: Epic folder name.
    """
    lock_file = Path.home() / ".agentic" / "locks" / f"orchestrate_{epic_folder}.lock"
    lock_file.unlink(missing_ok=True)
