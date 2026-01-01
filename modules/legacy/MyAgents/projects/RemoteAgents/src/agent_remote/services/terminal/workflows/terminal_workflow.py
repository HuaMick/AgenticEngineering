"""TerminalWorkflow orchestrates PTY session lifecycle.

Coordinates PTYSession entities with PTYSpawner infrastructure to:
- Start PTY sessions with Claude Code CLI
- Handle bidirectional I/O (input -> PTY, PTY output -> callback)
- Resize terminal dimensions
- Stop sessions with cleanup
"""

import asyncio
import logging
from typing import Callable, Optional

from agent_remote.services.terminal.domains.pty_manager import (
    ProcessState,
    PTYRepository,
    PTYSession,
    TerminalDimensions,
)
from agent_remote.services.terminal.infrastructure.pty_spawner import (
    PTYHandle,
    PTYSpawner,
    PTYSpawnError,
)

logger = logging.getLogger(__name__)

# Type alias for output callback
OutputCallback = Callable[[str, bytes], None]  # (session_id, data) -> None


class TerminalWorkflowError(Exception):
    """Error in terminal workflow operations."""
    pass


class SessionNotFoundError(TerminalWorkflowError):
    """Session not found in repository."""
    pass


class TerminalWorkflow:
    """Orchestrates PTY session lifecycle.

    Manages the complete lifecycle of PTY sessions:
    1. Start: Create session entity, spawn PTY, start output reader
    2. Input: Write data to PTY stdin
    3. Resize: Update PTY dimensions
    4. Stop: Terminate process, cleanup resources

    Uses an output callback to deliver PTY output to callers (e.g., relay client).
    """

    def __init__(
        self,
        repository: PTYRepository,
        spawner: PTYSpawner,
        output_callback: Optional[OutputCallback] = None,
    ):
        """Initialize workflow.

        Args:
            repository: PTY session storage
            spawner: PTY process spawner
            output_callback: Called with (session_id, output_bytes) when PTY produces output
        """
        self._repository = repository
        self._spawner = spawner
        self._output_callback = output_callback
        self._handles: dict[str, PTYHandle] = {}
        self._output_tasks: dict[str, asyncio.Task] = {}

    async def start_session(
        self,
        session_id: str,
        command: list[str],
        dimensions: TerminalDimensions,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> PTYSession:
        """Start a new PTY session.

        Creates session entity, spawns PTY process, and starts output reader.

        Args:
            session_id: Unique session identifier
            command: Command to run (e.g., ["claude"])
            dimensions: Terminal dimensions
            env: Optional environment variables
            cwd: Optional working directory

        Returns:
            Created PTYSession entity

        Raises:
            TerminalWorkflowError: If session already exists or spawn fails
        """
        # Check if session already exists
        if self._repository.get(session_id):
            raise TerminalWorkflowError(f"Session '{session_id}' already exists")

        # Create session entity
        session = PTYSession.create(
            session_id=session_id,
            command=command,
            dimensions=dimensions,
        )
        self._repository.add(session)

        try:
            # Spawn PTY process
            handle = self._spawner.spawn(
                command=command,
                dimensions=dimensions,
                env=env,
                cwd=cwd,
            )

            # Update session with PID
            session.set_running(handle.pid)
            self._repository.update(session)

            # Store handle
            self._handles[session_id] = handle

            # Start output reader task
            if self._output_callback:
                task = asyncio.create_task(
                    self._read_output_loop(session_id, handle)
                )
                self._output_tasks[session_id] = task

            logger.info(f"Started session '{session_id}' with PID {handle.pid}")
            return session

        except PTYSpawnError as e:
            # Update session to error state
            session.set_error(str(e))
            self._repository.update(session)
            raise TerminalWorkflowError(f"Failed to start session: {e}") from e

    async def send_input(self, session_id: str, data: bytes) -> None:
        """Send input to PTY.

        Args:
            session_id: Session to send input to
            data: Input bytes to write to PTY stdin

        Raises:
            SessionNotFoundError: If session not found
            TerminalWorkflowError: If session not running
        """
        session = self._repository.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        if not session.is_alive():
            raise TerminalWorkflowError(
                f"Session '{session_id}' is not running (state={session.state.value})"
            )

        handle = self._handles.get(session_id)
        if not handle:
            raise TerminalWorkflowError(f"No PTY handle for session '{session_id}'")

        self._spawner.write(handle, data)
        logger.debug(f"Sent {len(data)} bytes to session '{session_id}'")

    async def resize_terminal(
        self,
        session_id: str,
        dimensions: TerminalDimensions,
    ) -> None:
        """Resize terminal dimensions.

        Args:
            session_id: Session to resize
            dimensions: New terminal dimensions

        Raises:
            SessionNotFoundError: If session not found
            TerminalWorkflowError: If session not running
        """
        session = self._repository.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        if not session.is_alive():
            raise TerminalWorkflowError(
                f"Session '{session_id}' is not running (state={session.state.value})"
            )

        handle = self._handles.get(session_id)
        if not handle:
            raise TerminalWorkflowError(f"No PTY handle for session '{session_id}'")

        # Update domain entity
        session.resize(dimensions)
        self._repository.update(session)

        # Update PTY
        self._spawner.resize(handle, dimensions)
        logger.debug(f"Resized session '{session_id}' to {dimensions}")

    async def stop_session(self, session_id: str) -> int:
        """Stop a PTY session.

        Terminates process, cancels output reader, cleans up resources.

        Args:
            session_id: Session to stop

        Returns:
            Exit code from process

        Raises:
            SessionNotFoundError: If session not found
        """
        session = self._repository.get(session_id)
        if not session:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

        # Cancel output reader task
        task = self._output_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Terminate process
        exit_code = 0
        handle = self._handles.pop(session_id, None)
        if handle:
            exit_code = self._spawner.terminate(handle)

        # Update session entity
        if session.is_alive():
            session.terminate(exit_code)
            self._repository.update(session)

        logger.info(f"Stopped session '{session_id}' with exit code {exit_code}")
        return exit_code

    async def _read_output_loop(self, session_id: str, handle: PTYHandle) -> None:
        """Background task that reads PTY output and calls callback.

        Runs until PTY process exits or task is cancelled.
        """
        try:
            while self._spawner.is_alive(handle):
                try:
                    data = await self._spawner.read_async(handle, size=4096)
                    if data and self._output_callback:
                        self._output_callback(session_id, data)
                except Exception as e:
                    if not self._spawner.is_alive(handle):
                        break
                    logger.warning(f"Error reading output for '{session_id}': {e}")
                    await asyncio.sleep(0.1)

            # Process exited - update session
            session = self._repository.get(session_id)
            if session and session.is_alive():
                exit_code = self._spawner.get_exit_code(handle) or 0
                session.terminate(exit_code)
                self._repository.update(session)
                logger.info(f"Session '{session_id}' process exited with code {exit_code}")

        except asyncio.CancelledError:
            logger.debug(f"Output reader cancelled for session '{session_id}'")
            raise

    def get_session(self, session_id: str) -> Optional[PTYSession]:
        """Get session by ID."""
        return self._repository.get(session_id)

    def get_active_sessions(self) -> list[PTYSession]:
        """Get all active (running) sessions."""
        return self._repository.get_all_active()
