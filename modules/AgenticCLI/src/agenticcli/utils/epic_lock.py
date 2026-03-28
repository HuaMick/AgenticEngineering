"""Shared epic lock for preventing concurrent orchestration of the same epic.

Provides file-based locking used by both PlannerLoopRunner (planning) and
ExecutionRunner (execution) to ensure only one orchestration process runs
per epic at a time.

Uses the hardened FileLock from agenticguidance.services.state which is
backed by fcntl.flock() — the kernel auto-releases flocks when the file
descriptor is closed, including on SIGKILL or OOM.
"""

# @story US-SET-017

import logging
from pathlib import Path

from agenticguidance.services.state import FileLock

logger = logging.getLogger(__name__)

# Module-level dict tracking currently-held epic locks by epic_folder name.
_held_locks: dict[str, FileLock] = {}


def acquire_epic_lock(epic_folder: str) -> bool:
    """Acquire a FileLock-based lock to prevent concurrent orchestration.

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

    # FileLock appends ".lock" to the path, so we use the base name
    # without .lock here.  The resulting lock file on disk is:
    #   ~/.agentic/locks/orchestrate_{epic_folder}.lock
    lock_path = lock_dir / f"orchestrate_{epic_folder}"
    lock = FileLock(lock_path, timeout=1.0)

    if lock.acquire():
        _held_locks[epic_folder] = lock
        logger.debug("Acquired epic lock for %s (PID %s)", epic_folder, __import__("os").getpid())
        return True

    logger.error(
        "Epic %s already being orchestrated by another process",
        epic_folder,
    )
    return False


def release_epic_lock(epic_folder: str) -> None:
    """Release the FileLock-based orchestration lock.

    No-op if the lock is not held (matching previous behavior).

    Args:
        epic_folder: Epic folder name.
    """
    lock = _held_locks.pop(epic_folder, None)
    if lock is not None:
        lock.release()
        logger.debug("Released epic lock for %s", epic_folder)
