"""State Registry - structured process and state management.

Replaces raw PID/state files with a centralized JSON registry that tracks
active processes with file locking and automatic dead process cleanup.
"""

import atexit
import fcntl
import json
import logging
import os
import signal
import threading
import time
import weakref
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# psutil is optional - gracefully degrade if not available
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ---------------------------------------------------------------------------
# Global lock registry + cleanup infrastructure
# ---------------------------------------------------------------------------

_lock_registry: weakref.WeakSet = weakref.WeakSet()
"""WeakSet of all currently-held FileLock instances.

Using WeakSet ensures garbage-collected FileLock objects don't leak.
"""


def _cleanup_all_locks() -> None:
    """Release every lock still tracked in the global registry.

    Called by atexit and signal handlers so that orderly shutdown (sys.exit,
    SIGTERM, SIGINT) does not leave lock files in a held state.
    """
    for lock in list(_lock_registry):
        try:
            lock.release()
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass


# Register atexit handler unconditionally (works in any thread).
atexit.register(_cleanup_all_locks)


def _signal_handler(signum: int, frame) -> None:  # type: ignore[override]
    """Release all locks, then chain to the previous signal handler."""
    _cleanup_all_locks()

    prev = _prev_handlers.get(signum)
    if callable(prev):
        prev(signum, frame)
    elif signum == signal.SIGINT:
        # Default SIGINT behaviour: raise KeyboardInterrupt
        signal.default_int_handler(signum, frame)
    else:
        # SIGTERM with no previous handler → exit cleanly
        raise SystemExit(128 + signum)


# Signal handlers can only be registered from the main thread.
_prev_handlers: dict[int, object] = {}

if threading.current_thread() is threading.main_thread():
    for _sig in (signal.SIGTERM, signal.SIGINT):
        _prev_handlers[_sig] = signal.getsignal(_sig)
        signal.signal(_sig, _signal_handler)


class ProcessState(Enum):
    """State of a registered process."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STALE = "stale"


@dataclass
class ProcessEntry:
    """Entry in the state registry."""

    pid: int
    name: str
    command: str
    started_at: float
    state: ProcessState = ProcessState.RUNNING
    metadata: dict = field(default_factory=dict)
    ended_at: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pid": self.pid,
            "name": self.name,
            "command": self.command,
            "started_at": self.started_at,
            "state": self.state.value,
            "metadata": self.metadata,
            "ended_at": self.ended_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProcessEntry":
        """Create from dictionary."""
        return cls(
            pid=data["pid"],
            name=data["name"],
            command=data["command"],
            started_at=data["started_at"],
            state=ProcessState(data.get("state", "running")),
            metadata=data.get("metadata", {}),
            ended_at=data.get("ended_at"),
        )


# Default timeout for FileLock acquisition (seconds).
# Increased from 10s to 30s to accommodate parallel explore agent scenarios
# where up to 6 agents may contend on the same TinyDB lock file.
FILELOCK_DEFAULT_TIMEOUT: float = 30.0


# @story US-SET-017
class FileLock:
    """POSIX flock-based lock for atomic operations.

    Uses fcntl.flock() on a .lock file to prevent concurrent access to
    critical sections.  The kernel automatically releases flocks when the
    file descriptor is closed — including on SIGKILL or OOM — so locks
    cannot be left orphaned by crashed processes.
    """

    def __init__(self, path: Path, timeout: float = FILELOCK_DEFAULT_TIMEOUT, max_age: float = 300.0):
        """Initialize lock.

        Args:
            path: Path to the file being protected.
            timeout: Maximum time to wait for lock acquisition.
            max_age: Maximum age in seconds before a lock is considered stale.
                     Handles NFS/cross-platform edge cases and PID recycling.
                     Default 300 s (5 minutes).
        """
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.timeout = timeout
        self.max_age = max_age
        self._acquired = False
        self._fd: int | None = None

    def acquire(self) -> bool:
        """Acquire the lock via fcntl.flock().

        Opens (or creates) the lock file and attempts a non-blocking
        exclusive flock in a polling loop with exponential backoff
        (0.05s -> 0.1s -> 0.2s -> ... capped at 1.0s) until *timeout*
        seconds elapse.

        If the lock appears held but is older than *max_age*, a force-break
        is attempted (unlink + recreate) as a fallback for NFS / PID-recycle
        edge cases.

        Returns:
            True if lock was acquired, False if timeout.
        """
        start = time.time()
        backoff = 0.05
        max_backoff = 1.0
        # Open/create lock file (NOT O_EXCL — file persists across locks)
        fd = os.open(
            str(self.lock_path),
            os.O_CREAT | os.O_WRONLY,
            0o644,
        )
        while time.time() - start < self.timeout:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Lock acquired — write JSON with PID + timestamp.
                # Write the full payload in one shot, then truncate any
                # trailing bytes from a previous longer payload.  This
                # avoids a window where the file appears empty (between
                # ftruncate and write) that could trick another process's
                # staleness check.
                lock_data = json.dumps(
                    {"pid": os.getpid(), "timestamp": time.time()}
                ).encode()
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, lock_data)
                os.ftruncate(fd, len(lock_data))
                self._fd = fd
                self._acquired = True
                _lock_registry.add(self)
                logger.debug("Acquired lock: %s", self.lock_path)
                return True
            except BlockingIOError:
                # Check lock-age expiration before sleeping
                if self._is_lock_expired():
                    stale_info = self._read_lock_metadata()
                    logger.warning(
                        "Stale lock detected (age > %ss): %s (holder pid=%s). "
                        "Force-breaking.",
                        self.max_age,
                        self.lock_path,
                        stale_info.get("pid", "?"),
                    )
                    # Force-break: close fd, unlink old file, open new inode
                    os.close(fd)
                    try:
                        self.lock_path.unlink()
                    except OSError:
                        pass
                    fd = os.open(
                        str(self.lock_path),
                        os.O_CREAT | os.O_WRONLY,
                        0o644,
                    )
                    backoff = 0.05  # Reset backoff after force-break
                    continue  # retry flock immediately on new inode
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        # Timed out — close the fd we opened (we never acquired the lock)
        os.close(fd)
        holder = self._read_lock_metadata()
        elapsed = time.time() - start
        logger.warning(
            "Timed out acquiring lock: %s after %.1fs "
            "(holder pid=%s, holder age=%.1fs)",
            self.lock_path,
            elapsed,
            holder.get("pid", "?"),
            time.time() - holder.get("timestamp", time.time()),
        )
        return False

    def _is_lock_expired(self) -> bool:
        """Check if the lock file's timestamp exceeds max_age.

        Returns:
            True if the lock is older than max_age or the metadata cannot
            be read (treat as stale on error).
        """
        metadata = self._read_lock_metadata()
        ts = metadata.get("timestamp")
        if ts is None:
            return True  # unreadable → treat as stale
        return (time.time() - ts) > self.max_age

    def _read_lock_metadata(self) -> dict:
        """Read JSON metadata from the lock file.

        Returns:
            Dict with 'pid' and 'timestamp' keys, or empty dict on error.
        """
        try:
            raw = self.lock_path.read_text().strip()
            return json.loads(raw)
        except (OSError, json.JSONDecodeError, ValueError):
            return {}

    def release(self) -> None:
        """Release the lock.

        Unlocks via fcntl.flock(LOCK_UN) then closes the file descriptor.
        The lock file is intentionally NOT unlinked — flock is tied to the
        fd, not the file's existence.
        """
        if not self._acquired or self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(self._fd)
        except OSError:
            pass
        self._fd = None
        self._acquired = False
        _lock_registry.discard(self)
        logger.debug("Released lock: %s", self.lock_path)

    def __enter__(self) -> "FileLock":
        """Context manager entry."""
        if not self.acquire():
            holder = self._read_lock_metadata()
            raise TimeoutError(
                f"Could not acquire lock: {self.lock_path} "
                f"after {self.timeout}s "
                f"(holder pid={holder.get('pid', '?')}, "
                f"holder age={time.time() - holder.get('timestamp', time.time()):.1f}s)"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.release()


# Default retry settings for RetryingFileLock
FILELOCK_RETRY_MAX: int = 3
FILELOCK_RETRY_BACKOFF_BASE: float = 1.0


class RetryingFileLock:
    """Context manager that retries ``FileLock`` acquisition with exponential backoff.

    Wraps an existing :class:`FileLock` and catches :class:`TimeoutError`
    raised by ``__enter__``.  On each timeout, the lock holder PID and lock
    file age are logged before sleeping.

    Usage::

        lock = FileLock(path)
        with RetryingFileLock(lock):
            ...  # critical section

    Args:
        lock: The underlying ``FileLock`` instance.
        max_retries: Maximum number of retry attempts after the first failure.
        backoff_base: Base delay in seconds; actual delay is
            ``backoff_base * 2^attempt`` (1s, 2s, 4s, …).
    """

    def __init__(
        self,
        lock: FileLock,
        max_retries: int = FILELOCK_RETRY_MAX,
        backoff_base: float = FILELOCK_RETRY_BACKOFF_BASE,
    ):
        self._lock = lock
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    def __enter__(self) -> FileLock:
        total_attempts = self._max_retries + 1
        for attempt in range(total_attempts):
            try:
                return self._lock.__enter__()
            except TimeoutError:
                holder = self._lock._read_lock_metadata()
                holder_pid = holder.get("pid", "?")
                holder_ts = holder.get("timestamp")
                lock_age = (
                    f"{time.time() - holder_ts:.1f}s"
                    if holder_ts
                    else "unknown"
                )
                if attempt < self._max_retries:
                    delay = self._backoff_base * (2 ** attempt)
                    logger.warning(
                        "FileLock timeout (attempt %d/%d) on %s — "
                        "holder pid=%s, lock age=%s, retrying in %.1fs",
                        attempt + 1,
                        total_attempts,
                        self._lock.lock_path,
                        holder_pid,
                        lock_age,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "FileLock acquisition failed after %d attempts on %s — "
                        "holder pid=%s, lock age=%s",
                        total_attempts,
                        self._lock.lock_path,
                        holder_pid,
                        lock_age,
                    )
                    raise
        # Unreachable — the loop either returns or raises on final attempt
        raise TimeoutError("FileLock retry exhausted")  # pragma: no cover

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._lock.__exit__(exc_type, exc_val, exc_tb)


class StateRegistry:
    """Centralized registry for tracking process state.

    Stores state in ~/.config/agenticguidance/state.json with file locking
    for safe concurrent access.
    """

    def __init__(self, state_file: Optional[Path] = None):
        """Initialize registry.

        Args:
            state_file: Path to state file. Defaults to ~/.config/agenticguidance/state.json.
        """
        if state_file is None:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                config_dir = Path(xdg_config) / "agenticguidance"
            else:
                config_dir = Path.home() / ".config" / "agenticguidance"
            state_file = config_dir / "state.json"

        self.state_file = state_file
        self._ensure_parent_dir()

    def _ensure_parent_dir(self) -> None:
        """Ensure parent directory exists."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        """Load state from file.

        Returns:
            State dictionary with 'processes' key.
        """
        if not self.state_file.exists():
            return {"version": 1, "processes": {}}

        try:
            data = json.loads(self.state_file.read_text())
            if "processes" not in data:
                data["processes"] = {}
            return data
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "processes": {}}

    def _save(self, data: dict) -> None:
        """Save state to file."""
        self.state_file.write_text(json.dumps(data, indent=2))

    def register(
        self,
        name: str,
        command: str,
        metadata: Optional[dict] = None,
    ) -> ProcessEntry:
        """Register current process in the registry.

        Args:
            name: Human-readable name for this process.
            command: Command being executed.
            metadata: Optional additional metadata.

        Returns:
            ProcessEntry for the registered process.
        """
        entry = ProcessEntry(
            pid=os.getpid(),
            name=name,
            command=command,
            started_at=time.time(),
            metadata=metadata or {},
        )

        with FileLock(self.state_file):
            data = self._load()
            data["processes"][str(entry.pid)] = entry.to_dict()
            self._save(data)

        return entry

    def unregister(self, pid: Optional[int] = None) -> bool:
        """Remove a process from the registry.

        Args:
            pid: Process ID to remove. Defaults to current process.

        Returns:
            True if process was found and removed.
        """
        if pid is None:
            pid = os.getpid()

        with FileLock(self.state_file):
            data = self._load()
            pid_key = str(pid)
            if pid_key in data["processes"]:
                del data["processes"][pid_key]
                self._save(data)
                return True
        return False

    def update_state(
        self,
        pid: Optional[int] = None,
        state: Optional[ProcessState] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Update a process entry's state.

        Args:
            pid: Process ID to update. Defaults to current process.
            state: New state to set.
            metadata: Additional metadata to merge.

        Returns:
            True if process was found and updated.
        """
        if pid is None:
            pid = os.getpid()

        with FileLock(self.state_file):
            data = self._load()
            pid_key = str(pid)
            if pid_key not in data["processes"]:
                return False

            entry = data["processes"][pid_key]
            if state is not None:
                entry["state"] = state.value
                if state in (ProcessState.COMPLETED, ProcessState.FAILED):
                    entry["ended_at"] = time.time()
            if metadata:
                entry.setdefault("metadata", {}).update(metadata)

            self._save(data)
        return True

    def get(self, pid: int) -> Optional[ProcessEntry]:
        """Get a process entry by PID.

        Args:
            pid: Process ID to look up.

        Returns:
            ProcessEntry if found, None otherwise.
        """
        data = self._load()
        entry_data = data["processes"].get(str(pid))
        if entry_data:
            return ProcessEntry.from_dict(entry_data)
        return None

    def list_all(self) -> list[ProcessEntry]:
        """List all registered processes.

        Returns:
            List of ProcessEntry objects.
        """
        data = self._load()
        return [ProcessEntry.from_dict(e) for e in data["processes"].values()]

    def list_active(self) -> list[ProcessEntry]:
        """List only active (running) processes.

        Returns:
            List of ProcessEntry objects with RUNNING state.
        """
        return [e for e in self.list_all() if e.state == ProcessState.RUNNING]

    def cleanup_dead_processes(self) -> int:
        """Remove entries for processes that are no longer running.

        Returns:
            Number of stale entries removed.
        """
        removed = 0
        with FileLock(self.state_file):
            data = self._load()
            to_remove = []

            for pid_str, entry in data["processes"].items():
                pid = int(pid_str)
                if entry.get("state") == ProcessState.RUNNING.value:
                    if not self._is_process_alive(pid):
                        to_remove.append(pid_str)

            for pid_str in to_remove:
                # Mark as stale rather than delete (preserves history)
                data["processes"][pid_str]["state"] = ProcessState.STALE.value
                data["processes"][pid_str]["ended_at"] = time.time()
                removed += 1

            if removed > 0:
                self._save(data)

        return removed

    def clear_completed(self) -> int:
        """Remove all completed/failed/stale entries.

        Returns:
            Number of entries removed.
        """
        removed = 0
        with FileLock(self.state_file):
            data = self._load()
            non_running_states = {
                ProcessState.COMPLETED.value,
                ProcessState.FAILED.value,
                ProcessState.STALE.value,
            }
            to_remove = [
                pid for pid, entry in data["processes"].items()
                if entry.get("state") in non_running_states
            ]

            for pid in to_remove:
                del data["processes"][pid]
                removed += 1

            if removed > 0:
                self._save(data)

        return removed

    def clear_all(self) -> int:
        """Remove all entries from the registry.

        Returns:
            Number of entries removed.
        """
        with FileLock(self.state_file):
            data = self._load()
            count = len(data["processes"])
            data["processes"] = {}
            self._save(data)
        return count

    @staticmethod
    def _is_process_alive(pid: int) -> bool:
        """Check if a process is still running.

        Args:
            pid: Process ID to check.

        Returns:
            True if process is alive.
        """
        if HAS_PSUTIL:
            return psutil.pid_exists(pid)
        # Fallback: try to send signal 0
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
