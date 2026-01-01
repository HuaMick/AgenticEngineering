"""Repository Protocol for SessionManager domain.

This module defines the SessionRepository Protocol following the DDD repository pattern.
The Protocol acts as an interface that infrastructure layer implementations must satisfy.

Repository Pattern:
- Abstracts storage/retrieval without specifying implementation (in-memory, Redis, etc.)
- Domain layer depends on this Protocol, not concrete implementations
- Infrastructure layer provides concrete implementations (InMemorySessionRepository, etc.)
- Supports dependency inversion principle (domain doesn't depend on infrastructure)

The repository provides CRUD operations and two query patterns:
1. Query by session ID (primary lookup)
2. Query by pairing code (for client pairing flow)
"""

from typing import List, Optional, Protocol

from .entities import Session
from .value_objects import PairingCode, SessionId


class SessionRepository(Protocol):
    """Protocol defining repository interface for Session persistence.

    This Protocol specifies the contract that all SessionRepository implementations
    must satisfy. Implementations can use any storage mechanism (in-memory dict,
    Redis, database, etc.) as long as they implement these methods correctly.

    Query Patterns:
    - get_by_id(): Primary lookup for session management operations
    - get_by_pairing_code(): Used during client pairing flow
    - get_all_active(): Used by cleanup worker to find expired sessions

    Thread Safety:
    Implementations should be thread-safe as sessions may be accessed
    concurrently by multiple WebSocket connections.
    """

    def add(self, session: Session) -> None:
        """Add a new session to the repository.

        This method stores a new session. The session must not already exist
        in the repository.

        Args:
            session: Session entity to store

        Raises:
            ValueError: If a session with the same session_id already exists.
                       Prevents accidental overwrites of existing sessions.

        Example:
            session = Session.create(desktop_public_key="...")
            repository.add(session)
        """
        ...

    def get_by_id(self, session_id: SessionId) -> Optional[Session]:
        """Retrieve a session by its unique session ID.

        This is the primary lookup method for session management operations.
        Used when desktop/client needs to access their session.

        Args:
            session_id: Unique session identifier

        Returns:
            Session if found, None if not found

        Note:
            Returns None rather than raising an exception to allow graceful
            handling of missing sessions (e.g., expired or never created).

        Example:
            session = repository.get_by_id(SessionId("123e4567-e89b-12d3-..."))
            if session is None:
                raise SessionNotFoundException(...)
        """
        ...

    def get_by_pairing_code(self, code: PairingCode) -> Optional[Session]:
        """Retrieve a session by its pairing code.

        Used during the client pairing flow when user enters a pairing code.
        This is a secondary index lookup.

        Args:
            code: Pairing code entered by user

        Returns:
            Session if found, None if not found

        Note:
            Returns None rather than raising an exception to allow graceful
            handling of invalid/expired codes.

        Example:
            session = repository.get_by_pairing_code(PairingCode("ABC123"))
            if session is None or session.is_expired():
                raise InvalidPairingCodeException(...)
        """
        ...

    def remove(self, session_id: SessionId) -> None:
        """Remove a session from the repository.

        This method is idempotent - removing a non-existent session is not an error.
        Used for cleanup after session closure.

        Args:
            session_id: Unique session identifier to remove

        Note:
            Idempotent operation - no error if session doesn't exist.
            This simplifies cleanup logic in the session manager.

        Example:
            repository.remove(SessionId("123e4567-e89b-12d3-..."))
            # Safe to call multiple times
            repository.remove(SessionId("123e4567-e89b-12d3-..."))
        """
        ...

    def get_all_active(self) -> List[Session]:
        """Retrieve all sessions that are not in CLOSED state.

        Used by cleanup workers to find sessions that need expiry checking
        or timeout handling. Returns sessions in CREATED, DESKTOP_CONNECTED,
        or PAIRED states.

        Returns:
            List of active sessions (empty list if none found)

        Note:
            This method is used by background cleanup tasks to:
            - Find sessions with expired pairing codes
            - Detect sessions with disconnected WebSockets
            - Remove stale sessions that exceeded timeout thresholds

        Example:
            for session in repository.get_all_active():
                if session.is_expired():
                    session.close("Pairing code expired")
                    repository.remove(session.session_id)
        """
        ...
