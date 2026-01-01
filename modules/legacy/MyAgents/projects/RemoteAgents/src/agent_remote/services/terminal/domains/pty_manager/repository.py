"""Repository Protocol for PTYManager domain.

This module defines the PTYRepository Protocol following the DDD repository pattern.
The Protocol acts as an interface that infrastructure layer implementations must satisfy.

Repository Pattern:
- Abstracts storage/retrieval without specifying implementation (in-memory, Redis, etc.)
- Domain layer depends on this Protocol, not concrete implementations
- Infrastructure layer provides concrete implementations (InMemoryPTYRepository, etc.)
- Supports dependency inversion principle (domain doesn't depend on infrastructure)

Thread Safety Requirements:
All repository implementations MUST be thread-safe as PTY sessions are accessed
concurrently by multiple I/O operations:
- Simultaneous read/write operations from PTY output handlers
- Concurrent WebSocket connections reading session state
- Background cleanup workers scanning for stale sessions
- Control plane operations (resize, close, etc.) from different threads

The repository provides CRUD operations for PTY session lifecycle management:
1. add(): Store new PTY session
2. get(): Retrieve session by ID for I/O operations
3. update(): Update session state (e.g., process PID, exit status)
4. remove(): Clean up terminated sessions
5. get_all_active(): Query for cleanup worker to find running sessions
"""

from typing import Optional, Protocol

from .entities import PTYSession


class PTYRepository(Protocol):
    """Protocol defining repository interface for PTYSession persistence.

    This Protocol specifies the contract that all PTYRepository implementations
    must satisfy. Implementations can use any storage mechanism (in-memory dict,
    Redis, database, etc.) as long as they implement these methods correctly.

    Query Patterns:
    - get(): Primary lookup for session I/O operations
    - get_all_active(): Used by cleanup worker to find running sessions
      that may need timeout handling or process cleanup

    Thread Safety:
    Implementations MUST be thread-safe as sessions are accessed concurrently
    by multiple I/O handlers, WebSocket connections, and cleanup workers.
    Consider using locks, thread-safe data structures, or async-safe patterns.
    """

    def add(self, session: PTYSession) -> None:
        """Add a new PTY session to the repository.

        This method stores a new session. The session must not already exist
        in the repository.

        Args:
            session: PTYSession entity to store

        Raises:
            ValueError: If a session with the same session_id already exists.
                       Prevents accidental overwrites of existing sessions.

        Example:
            session = PTYSession.create(
                session_id="sess_123",
                pty_fd=master_fd,
                process_pid=12345
            )
            repository.add(session)
        """
        ...

    def get(self, session_id: str) -> Optional[PTYSession]:
        """Retrieve a PTY session by its unique session ID.

        This is the primary lookup method for session I/O operations.
        Used when reading PTY output or writing input to a specific session.

        Args:
            session_id: Unique session identifier

        Returns:
            PTYSession if found, None if not found

        Note:
            Returns None rather than raising an exception to allow graceful
            handling of missing sessions (e.g., session terminated or never created).

        Example:
            session = repository.get("sess_123")
            if session is None:
                raise SessionNotFoundException(...)
            # Write to PTY
            os.write(session.pty_fd, data)
        """
        ...

    def update(self, session: PTYSession) -> None:
        """Update an existing PTY session.

        This method updates session state such as process PID, exit status,
        or last activity timestamp. The session must already exist.

        Args:
            session: Updated PTYSession entity

        Raises:
            ValueError: If session with session_id not found in repository.
                       Use add() for new sessions, update() only for existing ones.

        Example:
            session = repository.get("sess_123")
            if session:
                session.mark_exited(exit_code=0)
                repository.update(session)
        """
        ...

    def remove(self, session_id: str) -> None:
        """Remove a PTY session from the repository.

        This method is idempotent - removing a non-existent session is not an error.
        Used for cleanup after session termination and PTY resource cleanup.

        Args:
            session_id: Unique session identifier to remove

        Note:
            Idempotent operation - no error if session doesn't exist.
            This simplifies cleanup logic in the PTY manager.

        Example:
            # Close PTY resources
            session = repository.get("sess_123")
            if session:
                os.close(session.pty_fd)
                os.waitpid(session.process_pid, 0)
            # Remove from repository (safe to call even if not found)
            repository.remove("sess_123")
        """
        ...

    def get_all_active(self) -> list[PTYSession]:
        """Retrieve all sessions with state==RUNNING.

        Used by cleanup workers to find sessions that need monitoring or cleanup:
        - Check for zombie processes (process exited but session still tracked)
        - Detect sessions exceeding idle timeout
        - Close stale sessions with no active WebSocket connections
        - Monitor resource usage across all active PTY sessions

        Returns:
            List of active PTYSession entities (empty list if none found).
            Only returns sessions where state is RUNNING (excludes TERMINATED).

        Note:
            This method is called by background cleanup tasks. Implementations
            should be efficient as this may be called frequently.

        Example:
            for session in repository.get_all_active():
                # Check if process still alive
                try:
                    os.waitpid(session.process_pid, os.WNOHANG)
                except ChildProcessError:
                    # Process terminated
                    session.mark_exited(exit_code=-1)
                    repository.update(session)
        """
        ...
