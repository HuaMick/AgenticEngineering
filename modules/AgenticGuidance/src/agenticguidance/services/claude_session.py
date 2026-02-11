"""Claude Code Session State Service.

Manages state for Claude Code sessions spawned via subprocess.
Stores session data in individual JSON files under ~/.agentic/sessions/
with file locking for safe concurrent access and automatic cleanup of dead processes.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

# Import FileLock from state module to reuse the proven implementation
from .state import FileLock

# psutil is optional - gracefully degrade if not available
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class ClaudeSessionStatus(Enum):
    """Status of a Claude Code session."""

    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class SessionEntry:
    """Entry representing a Claude Code session.

    Attributes:
        session_id: Unique identifier (UUID) for the session.
        pid: Process ID of the Claude Code process.
        prompt: The prompt/task given to Claude Code.
        max_turns: Optional maximum number of turns for the session.
        status: Current status of the session.
        started_at: ISO timestamp when the session started.
        ended_at: Optional ISO timestamp when the session ended.
        background: Whether the session was started in background mode.
        working_dir: Working directory for the session.
        command: Full command used to start the session.
        error: Optional error message if the session failed.
        exit_code: Optional exit code from the process.
        metadata: Additional metadata for the session.
    """

    session_id: str
    pid: int
    prompt: str
    status: str
    started_at: str
    working_dir: str
    command: str
    max_turns: Optional[int] = None
    ended_at: Optional[str] = None
    background: bool = False
    error: Optional[str] = None
    exit_code: Optional[int] = None
    metadata: dict = field(default_factory=dict)
    last_activity: Optional[str] = None
    log_bytes: Optional[int] = None
    diagnostic_spawned: bool = False
    diagnostic_session_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "pid": self.pid,
            "prompt": self.prompt,
            "max_turns": self.max_turns,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "background": self.background,
            "working_dir": self.working_dir,
            "command": self.command,
            "error": self.error,
            "exit_code": self.exit_code,
            "metadata": self.metadata,
            "last_activity": self.last_activity,
            "log_bytes": self.log_bytes,
            "diagnostic_spawned": self.diagnostic_spawned,
            "diagnostic_session_id": self.diagnostic_session_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionEntry":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            pid=data["pid"],
            prompt=data["prompt"],
            max_turns=data.get("max_turns"),
            status=data.get("status", ClaudeSessionStatus.RUNNING.value),
            started_at=data["started_at"],
            ended_at=data.get("ended_at"),
            background=data.get("background", False),
            working_dir=data["working_dir"],
            command=data["command"],
            error=data.get("error"),
            exit_code=data.get("exit_code"),
            metadata=data.get("metadata", {}),
            last_activity=data.get("last_activity"),
            log_bytes=data.get("log_bytes"),
            diagnostic_spawned=data.get("diagnostic_spawned", False),
            diagnostic_session_id=data.get("diagnostic_session_id"),
        )

    @classmethod
    def create(
        cls,
        pid: int,
        prompt: str,
        working_dir: str,
        command: str,
        max_turns: Optional[int] = None,
        background: bool = False,
        metadata: Optional[dict] = None,
    ) -> "SessionEntry":
        """Factory method to create a new session entry.

        Args:
            pid: Process ID of the Claude Code process.
            prompt: The prompt/task given to Claude Code.
            working_dir: Working directory for the session.
            command: Full command used to start the session.
            max_turns: Optional maximum number of turns.
            background: Whether session runs in background.
            metadata: Additional metadata.

        Returns:
            New SessionEntry with generated UUID and timestamp.
        """
        return cls(
            session_id=str(uuid.uuid4()),
            pid=pid,
            prompt=prompt,
            max_turns=max_turns,
            status=ClaudeSessionStatus.STARTING.value,
            started_at=datetime.now().isoformat(),
            working_dir=working_dir,
            command=command,
            background=background,
            metadata=metadata or {},
        )

    def update_activity(self, timestamp: Optional[str] = None) -> None:
        """Update last_activity to the given or current timestamp.

        Args:
            timestamp: ISO timestamp string. Defaults to now.
        """
        self.last_activity = timestamp or datetime.now().isoformat()

    def mark_diagnostic_spawned(self, diagnostic_session_id: str) -> None:
        """Mark that a diagnostic session has been spawned for this session.

        Args:
            diagnostic_session_id: ID of the spawned diagnostic session.
        """
        self.diagnostic_spawned = True
        self.diagnostic_session_id = diagnostic_session_id


class SessionStateService:
    """Service for managing Claude Code session state.

    Stores session data in individual JSON files under ~/.agentic/sessions/
    for persistence across process boundaries. Uses file locking for
    safe concurrent access.

    Example:
        >>> service = SessionStateService()
        >>> entry = SessionEntry.create(
        ...     pid=12345,
        ...     prompt="Fix the bug",
        ...     working_dir="/path/to/project",
        ...     command="claude -p 'Fix the bug'",
        ... )
        >>> service.save(entry)
        >>> loaded = service.get_by_id(entry.session_id)
        >>> print(loaded.status)
        'starting'
    """

    def __init__(self, sessions_dir: Optional[Path] = None):
        """Initialize the service.

        Args:
            sessions_dir: Directory to store session files.
                         Defaults to ~/.agentic/sessions/
        """
        if sessions_dir is None:
            sessions_dir = Path.home() / ".agentic" / "sessions"

        self.sessions_dir = sessions_dir
        self._ensure_sessions_dir()

    def _ensure_sessions_dir(self) -> None:
        """Ensure sessions directory exists."""
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_file(self, session_id: str) -> Path:
        """Get the file path for a session.

        Args:
            session_id: The session UUID.

        Returns:
            Path to the session's JSON file.
        """
        return self.sessions_dir / f"{session_id}.json"

    def save(self, entry: SessionEntry) -> None:
        """Save a session entry to disk.

        Uses file locking to ensure atomic writes.

        Args:
            entry: The session entry to save.
        """
        file_path = self._session_file(entry.session_id)
        with FileLock(file_path):
            file_path.write_text(json.dumps(entry.to_dict(), indent=2))

    def load(self, session_id: str) -> Optional[SessionEntry]:
        """Load a session entry from disk.

        Args:
            session_id: The session UUID to load.

        Returns:
            SessionEntry if found, None otherwise.
        """
        file_path = self._session_file(session_id)
        if not file_path.exists():
            return None

        try:
            data = json.loads(file_path.read_text())
            return SessionEntry.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def get_by_id(self, session_id: str) -> Optional[SessionEntry]:
        """Get a session by its ID.

        Alias for load() for API consistency.

        Args:
            session_id: The session UUID.

        Returns:
            SessionEntry if found, None otherwise.
        """
        return self.load(session_id)

    def list_all(self) -> list[SessionEntry]:
        """List all session entries.

        Returns:
            List of all SessionEntry objects, sorted by started_at descending.
        """
        entries = []
        for file_path in self.sessions_dir.glob("*.json"):
            # Skip lock files
            if file_path.suffix == ".lock":
                continue
            if file_path.name.endswith(".json.lock"):
                continue

            try:
                data = json.loads(file_path.read_text())
                entries.append(SessionEntry.from_dict(data))
            except (json.JSONDecodeError, KeyError, OSError):
                # Skip corrupted files
                continue

        # Sort by started_at descending (most recent first)
        entries.sort(key=lambda e: e.started_at, reverse=True)
        return entries

    def list_active(self) -> list[SessionEntry]:
        """List only active (starting/running) sessions.

        Returns:
            List of SessionEntry objects with starting or running status.
        """
        active_statuses = {
            ClaudeSessionStatus.STARTING.value,
            ClaudeSessionStatus.RUNNING.value,
        }
        return [e for e in self.list_all() if e.status in active_statuses]

    def delete(self, session_id: str) -> bool:
        """Delete a session entry.

        Args:
            session_id: The session UUID to delete.

        Returns:
            True if session was found and deleted, False otherwise.
        """
        file_path = self._session_file(session_id)
        if not file_path.exists():
            return False

        try:
            # Also clean up any stale lock file
            lock_path = file_path.with_suffix(file_path.suffix + ".lock")
            if lock_path.exists():
                try:
                    lock_path.unlink()
                except OSError:
                    pass

            file_path.unlink()
            return True
        except OSError:
            return False

    def update_status(
        self,
        session_id: str,
        status: str,
        error: Optional[str] = None,
        exit_code: Optional[int] = None,
    ) -> bool:
        """Update the status of a session.

        Args:
            session_id: The session UUID.
            status: New status value.
            error: Optional error message (for failed status).
            exit_code: Optional exit code from the process.

        Returns:
            True if session was found and updated, False otherwise.
        """
        entry = self.load(session_id)
        if entry is None:
            return False

        entry.status = status

        if status in (
            ClaudeSessionStatus.COMPLETED.value,
            ClaudeSessionStatus.FAILED.value,
            ClaudeSessionStatus.STOPPED.value,
        ):
            entry.ended_at = datetime.now().isoformat()

        if error is not None:
            entry.error = error

        if exit_code is not None:
            entry.exit_code = exit_code

        self.save(entry)
        return True

    def cleanup_dead_processes(self) -> int:
        """Clean up sessions for processes that are no longer running.

        Checks all active sessions and marks them as failed if their
        process is no longer alive.

        Returns:
            Number of sessions cleaned up.
        """
        cleaned = 0
        for entry in self.list_active():
            if not self._is_process_alive(entry.pid):
                self.update_status(
                    entry.session_id,
                    ClaudeSessionStatus.FAILED.value,
                    error="Process died unexpectedly",
                )
                cleaned += 1
        return cleaned

    def clear_completed(self) -> int:
        """Remove all completed/failed/stopped sessions.

        Returns:
            Number of sessions removed.
        """
        removed = 0
        terminal_statuses = {
            ClaudeSessionStatus.COMPLETED.value,
            ClaudeSessionStatus.FAILED.value,
            ClaudeSessionStatus.STOPPED.value,
        }
        for entry in self.list_all():
            if entry.status in terminal_statuses:
                if self.delete(entry.session_id):
                    removed += 1
        return removed

    def clear_all(self) -> int:
        """Remove all session entries.

        Returns:
            Number of sessions removed.
        """
        removed = 0
        for entry in self.list_all():
            if self.delete(entry.session_id):
                removed += 1
        return removed

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
        # Fallback: try to send signal 0 (checks if process exists)
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def refresh_activity(self, session_id: str) -> Optional[SessionEntry]:
        """Update last_activity and log_bytes from filesystem state.

        Checks log file sizes and modification times to update the
        session's activity tracking fields.

        Args:
            session_id: The session UUID.

        Returns:
            Updated SessionEntry if found, None otherwise.
        """
        entry = self.load(session_id)
        if entry is None:
            return None

        logs_dir = self.sessions_dir / "logs"
        stdout_path = logs_dir / f"{session_id}.stdout.log"
        stderr_path = logs_dir / f"{session_id}.stderr.log"

        # Calculate combined log size
        total_bytes = 0
        log_mtime = None
        for log_path in [stdout_path, stderr_path]:
            if log_path.exists():
                stat = log_path.stat()
                total_bytes += stat.st_size
                mtime = stat.st_mtime
                if log_mtime is None or mtime > log_mtime:
                    log_mtime = mtime

        entry.log_bytes = total_bytes

        # Update last_activity to the most recent of log mtime or existing last_activity
        if log_mtime is not None:
            log_activity = datetime.fromtimestamp(log_mtime).isoformat()
            if entry.last_activity is None or log_activity > entry.last_activity:
                entry.last_activity = log_activity

        self.save(entry)
        return entry

    def get_by_pid(self, pid: int) -> Optional[SessionEntry]:
        """Find a session by its process ID.

        Args:
            pid: Process ID to search for.

        Returns:
            SessionEntry if found, None otherwise.
        """
        for entry in self.list_all():
            if entry.pid == pid:
                return entry
        return None
