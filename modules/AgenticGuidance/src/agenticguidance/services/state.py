"""State Registry - structured process and state management.

Replaces raw PID/state files with a centralized JSON registry that tracks
active processes with file locking and automatic dead process cleanup.
"""

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

# psutil is optional - gracefully degrade if not available
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


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


class FileLock:
    """Simple file-based lock for atomic operations.

    Uses a .lock file to prevent concurrent access to critical sections.
    """

    def __init__(self, path: Path, timeout: float = 10.0):
        """Initialize lock.

        Args:
            path: Path to the file being protected.
            timeout: Maximum time to wait for lock acquisition.
        """
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.timeout = timeout
        self._acquired = False

    def acquire(self) -> bool:
        """Acquire the lock.

        Returns:
            True if lock was acquired, False if timeout.
        """
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                # Try to create lock file exclusively
                fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self._acquired = True
                return True
            except FileExistsError:
                # Check if lock is stale (owner process dead)
                if self._is_stale_lock():
                    self._force_release()
                    continue
                time.sleep(0.1)
        return False

    def release(self) -> None:
        """Release the lock."""
        if self._acquired and self.lock_path.exists():
            try:
                self.lock_path.unlink()
            except OSError:
                pass
        self._acquired = False

    def _is_stale_lock(self) -> bool:
        """Check if lock file is stale (owner process is dead)."""
        if not self.lock_path.exists():
            return True
        try:
            pid = int(self.lock_path.read_text().strip())
            if HAS_PSUTIL:
                return not psutil.pid_exists(pid)
            # Fallback: try to send signal 0 (doesn't do anything but checks)
            try:
                os.kill(pid, 0)
                return False
            except OSError:
                return True
        except (ValueError, OSError):
            return True

    def _force_release(self) -> None:
        """Force release a stale lock."""
        try:
            self.lock_path.unlink()
        except OSError:
            pass

    def __enter__(self) -> "FileLock":
        """Context manager entry."""
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock: {self.lock_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.release()


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
