"""In-memory implementation of PTYRepository.

This module provides a thread-safe in-memory implementation of the PTYRepository
Protocol using Python dictionaries. Suitable for single-instance deployments where
PTY session state doesn't need to be shared across multiple server instances.

Features:
- Thread-safe operations using threading.Lock
- O(1) session lookup by session ID
- O(n) retrieval of all active sessions
- No external dependencies (no Redis, database, etc.)

Thread Safety:
All public methods acquire a lock before accessing shared state to prevent
race conditions under concurrent PTY I/O operations, WebSocket connections,
and background cleanup workers.

Performance:
- add(): O(1) - dict insert
- get(): O(1) - dict lookup
- update(): O(1) - dict replacement
- remove(): O(1) - dict removal
- get_all_active(): O(n) - iterate all sessions and filter by state
"""

import threading
from typing import Optional

from agent_remote.services.terminal.domains.pty_manager import (
    ProcessState,
    PTYSession,
)


class InMemoryPTYRepository:
    """Thread-safe in-memory implementation of PTYRepository Protocol.

    This implementation uses a single dict for storage:
    - sessions: dict[str, PTYSession] - Primary storage indexed by session_id

    Thread Safety:
    A single threading.Lock protects the dictionary. All operations acquire
    the lock before accessing shared state, ensuring no race conditions occur
    when multiple PTY I/O handlers, WebSocket connections, or cleanup workers
    access the repository concurrently.

    Example:
        repository = InMemoryPTYRepository()

        # Add session
        session = PTYSession.create(
            session_id="sess-123",
            command=["claude"],
            dimensions=TerminalDimensions(rows=24, cols=80)
        )
        repository.add(session)

        # Lookup by session ID
        session = repository.get("sess-123")

        # Update session
        session.set_running(pid=12345)
        repository.update(session)

        # Get active sessions
        active_sessions = repository.get_all_active()

        # Remove session
        repository.remove("sess-123")
    """

    def __init__(self):
        """Initialize the in-memory repository with empty storage."""
        # Primary storage: session_id -> PTYSession
        self._sessions: dict[str, PTYSession] = {}

        # Thread lock for concurrent access protection
        self._lock = threading.Lock()

    def add(self, session: PTYSession) -> None:
        """Add a new PTY session to the repository.

        Args:
            session: PTYSession entity to store

        Raises:
            ValueError: If a session with the same session_id already exists.
                       Prevents accidental overwrites of existing sessions.

        Thread Safety:
            Acquires lock before checking existence and adding session.
        """
        with self._lock:
            # Check if session already exists
            if session.session_id in self._sessions:
                raise ValueError(
                    f"Session '{session.session_id}' already exists in repository"
                )

            # Add to primary storage
            self._sessions[session.session_id] = session

    def get(self, session_id: str) -> Optional[PTYSession]:
        """Retrieve a PTY session by its unique session ID.

        Args:
            session_id: Unique session identifier

        Returns:
            PTYSession if found, None if not found

        Thread Safety:
            Acquires lock before accessing sessions dict.
        """
        with self._lock:
            return self._sessions.get(session_id)

    def update(self, session: PTYSession) -> None:
        """Update an existing PTY session.

        This method updates session state such as process PID, exit status,
        or last activity timestamp. The session must already exist.

        Args:
            session: Updated PTYSession entity

        Raises:
            ValueError: If session with session_id not found in repository.
                       Use add() for new sessions, update() only for existing ones.

        Thread Safety:
            Acquires lock before checking existence and updating session.
        """
        with self._lock:
            # Check if session exists
            if session.session_id not in self._sessions:
                raise ValueError(
                    f"Session '{session.session_id}' not found in repository"
                )

            # Update in primary storage
            self._sessions[session.session_id] = session

    def remove(self, session_id: str) -> None:
        """Remove a PTY session from the repository.

        This method is idempotent - removing a non-existent session is not an error.
        Used for cleanup after session termination and PTY resource cleanup.

        Args:
            session_id: Unique session identifier to remove

        Thread Safety:
            Acquires lock before removing from dict.
        """
        with self._lock:
            # Idempotent - no error if session doesn't exist
            self._sessions.pop(session_id, None)

    def get_all_active(self) -> list[PTYSession]:
        """Retrieve all sessions with state==RUNNING.

        Used by cleanup workers to find sessions that need monitoring or cleanup:
        - Check for zombie processes (process exited but session still tracked)
        - Detect sessions exceeding idle timeout
        - Close stale sessions with no active connections
        - Monitor resource usage across all active PTY sessions

        Returns:
            List of active PTYSession entities (empty list if none found).
            Only returns sessions where state is RUNNING (excludes TERMINATED/ERROR).

        Thread Safety:
            Acquires lock before iterating sessions.
        """
        with self._lock:
            # Filter sessions that are in RUNNING state
            active_sessions = [
                session
                for session in self._sessions.values()
                if session.state == ProcessState.RUNNING
            ]
            return active_sessions

    def __len__(self) -> int:
        """Get the number of sessions in the repository.

        Returns:
            Total number of sessions (including terminated/error sessions)

        Thread Safety:
            Acquires lock before accessing sessions dict.
        """
        with self._lock:
            return len(self._sessions)

    def __repr__(self) -> str:
        """Developer representation."""
        with self._lock:
            num_sessions = len(self._sessions)
            num_active = len([s for s in self._sessions.values() if s.state == ProcessState.RUNNING])
            return (
                f"InMemoryPTYRepository("
                f"total={num_sessions}, "
                f"active={num_active})"
            )
