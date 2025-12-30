"""In-memory implementation of SessionRepository.

This module provides a thread-safe in-memory implementation of the SessionRepository
Protocol using Python dictionaries. Suitable for single-instance deployments such
as desktop relay servers where session state doesn't need to be shared across
multiple server instances.

Features:
- Thread-safe operations using threading.Lock
- O(1) session lookup by session ID
- O(1) session lookup by pairing code (using index)
- No external dependencies (no Redis, database, etc.)

Thread Safety:
All public methods acquire a lock before accessing shared state to prevent
race conditions under concurrent WebSocket connections.

Performance:
- add(): O(1) - dict insert + index update
- get_by_id(): O(1) - dict lookup
- get_by_pairing_code(): O(1) - index lookup + dict lookup
- remove(): O(1) - dict removal + index removal
- get_all_active(): O(n) - iterate all sessions and filter
"""

import threading
from typing import Dict, List, Optional

from agent_remote.services.relay.domains.session_manager.entities import Session
from agent_remote.services.relay.domains.session_manager.value_objects import (
    PairingCode,
    SessionId,
    SessionState,
)


class InMemorySessionRepository:
    """Thread-safe in-memory implementation of SessionRepository Protocol.

    This implementation uses two data structures:
    1. sessions: Dict[str, Session] - Primary storage indexed by session_id
    2. pairing_code_index: Dict[str, str] - Secondary index mapping pairing_code -> session_id

    The pairing code index enables O(1) lookups by pairing code without iterating
    all sessions. The index is kept in sync with the sessions dict during add/remove.

    Thread Safety:
    A single threading.Lock protects both dictionaries. All operations acquire
    the lock before accessing shared state, ensuring no race conditions occur
    when multiple WebSocket handlers access the repository concurrently.

    Example:
        repository = InMemorySessionRepository()

        # Add session
        session = Session.create(desktop_public_key="...")
        repository.add(session)

        # Lookup by session ID
        session = repository.get_by_id(session.session_id)

        # Lookup by pairing code
        session = repository.get_by_pairing_code(session.pairing_code)

        # Get active sessions
        active_sessions = repository.get_all_active()

        # Remove session
        repository.remove(session.session_id)
    """

    def __init__(self):
        """Initialize the in-memory repository with empty storage."""
        # Primary storage: session_id -> Session
        self._sessions: Dict[str, Session] = {}

        # Secondary index: pairing_code -> session_id
        # Enables O(1) lookup by pairing code
        self._pairing_code_index: Dict[str, str] = {}

        # Thread lock for concurrent access protection
        self._lock = threading.Lock()

    def add(self, session: Session) -> None:
        """Add a new session to the repository.

        Args:
            session: Session entity to store

        Raises:
            ValueError: If a session with the same session_id already exists

        Thread Safety:
            Acquires lock before checking existence and adding session.
        """
        with self._lock:
            session_id_str = str(session.session_id)

            # Check if session already exists
            if session_id_str in self._sessions:
                raise ValueError(
                    f"Session with id '{session_id_str}' already exists in repository"
                )

            # Add to primary storage
            self._sessions[session_id_str] = session

            # Update pairing code index
            pairing_code_str = str(session.pairing_code)
            self._pairing_code_index[pairing_code_str] = session_id_str

    def get_by_id(self, session_id: SessionId) -> Optional[Session]:
        """Retrieve a session by its unique session ID.

        Args:
            session_id: Unique session identifier

        Returns:
            Session if found, None if not found

        Thread Safety:
            Acquires lock before accessing sessions dict.
        """
        with self._lock:
            session_id_str = str(session_id)
            return self._sessions.get(session_id_str)

    def get_by_pairing_code(self, code: PairingCode) -> Optional[Session]:
        """Retrieve a session by its pairing code.

        Uses the pairing_code_index for O(1) lookup instead of iterating
        all sessions (which would be O(n)).

        Args:
            code: Pairing code to search for

        Returns:
            Session if found, None if not found

        Thread Safety:
            Acquires lock before accessing index and sessions dict.
        """
        with self._lock:
            code_str = str(code)

            # Lookup session_id in index
            session_id_str = self._pairing_code_index.get(code_str)
            if session_id_str is None:
                return None

            # Lookup session in primary storage
            return self._sessions.get(session_id_str)

    def remove(self, session_id: SessionId) -> None:
        """Remove a session from the repository.

        This method is idempotent - removing a non-existent session is not an error.
        Updates both the primary storage and the pairing code index.

        Args:
            session_id: Unique session identifier to remove

        Thread Safety:
            Acquires lock before removing from dict and index.
        """
        with self._lock:
            session_id_str = str(session_id)

            # Get session before removing (to clean up index)
            session = self._sessions.get(session_id_str)
            if session is None:
                # Idempotent - no error if session doesn't exist
                return

            # Remove from pairing code index
            pairing_code_str = str(session.pairing_code)
            self._pairing_code_index.pop(pairing_code_str, None)

            # Remove from primary storage
            self._sessions.pop(session_id_str, None)

    def get_all_active(self) -> List[Session]:
        """Retrieve all sessions that are not in CLOSED state.

        Returns sessions in CREATED, DESKTOP_CONNECTED, or PAIRED states.
        Used by cleanup workers to find sessions needing expiry checking.

        Returns:
            List of active sessions (empty list if none found)

        Thread Safety:
            Acquires lock before iterating sessions.
        """
        with self._lock:
            # Filter sessions that are not CLOSED
            active_sessions = [
                session
                for session in self._sessions.values()
                if session.state != SessionState.CLOSED
            ]
            return active_sessions

    def __len__(self) -> int:
        """Get the number of sessions in the repository.

        Returns:
            Total number of sessions (including closed sessions)

        Thread Safety:
            Acquires lock before accessing sessions dict.
        """
        with self._lock:
            return len(self._sessions)

    def __repr__(self) -> str:
        """Developer representation."""
        with self._lock:
            num_sessions = len(self._sessions)
            num_active = len([s for s in self._sessions.values() if s.state != SessionState.CLOSED])
            return (
                f"InMemorySessionRepository("
                f"total={num_sessions}, "
                f"active={num_active})"
            )
