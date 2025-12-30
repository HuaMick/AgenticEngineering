"""PTY entity and domain exceptions for PTYManager.

This module defines the core PTYSession entity that models the lifecycle of a PTY process:
1. Session created with command and dimensions (STARTING state)
2. Process starts and gets PID (RUNNING state)
3. Process exits with code (TERMINATED state) or encounters error (ERROR state)

Domain exceptions provide clear error cases for business rule violations.
All logic is pure domain logic with no infrastructure dependencies.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .value_objects import ProcessState, TerminalDimensions


# ==============================================================================
# Domain Exceptions
# ==============================================================================


class PTYDomainException(Exception):
    """Base exception for all PTYManager domain errors."""
    pass


class ProcessAlreadyStartedException(PTYDomainException):
    """Raised when attempting to start a process that's already running."""

    def __init__(self, session_id: str, current_state: ProcessState):
        self.session_id = session_id
        self.current_state = current_state
        super().__init__(
            f"Process for session '{session_id}' is already in state "
            f"'{current_state.value}' and cannot be started again"
        )


class ProcessNotRunningException(PTYDomainException):
    """Raised when operation requires a running process but it's not running."""

    def __init__(self, session_id: str, current_state: ProcessState, operation: str):
        self.session_id = session_id
        self.current_state = current_state
        self.operation = operation
        super().__init__(
            f"Cannot {operation} for session '{session_id}': "
            f"process is in state '{current_state.value}', not running"
        )


class InvalidStateTransitionException(PTYDomainException):
    """Raised when attempting an invalid state transition."""

    def __init__(self, session_id: str, current_state: ProcessState, action: str):
        self.session_id = session_id
        self.current_state = current_state
        self.action = action
        super().__init__(
            f"Cannot {action} in state {current_state.value} "
            f"for session '{session_id}'"
        )


# ==============================================================================
# PTYSession Entity
# ==============================================================================


@dataclass
class PTYSession:
    """Domain entity representing a PTY session.

    A PTYSession models the complete lifecycle of a PTY process running Claude Code CLI:
    - Session created with command and terminal dimensions (STARTING state)
    - Process starts and receives PID (transitions to RUNNING)
    - Process can be resized while running (updates dimensions)
    - Process terminates with exit code (transitions to TERMINATED)
    - Process can encounter errors at any stage (transitions to ERROR)

    Attributes:
        session_id: Unique session identifier
        command: Command and arguments to execute
        dimensions: Terminal dimensions (rows x cols)
        state: Current process state in lifecycle
        pid: Process ID (set when process starts)
        exit_code: Exit code from terminated process
        started_at: Timestamp when session was created
        terminated_at: Timestamp when process terminated
        error_message: Error message if process encountered error
    """

    session_id: str
    command: list[str]
    dimensions: TerminalDimensions
    state: ProcessState
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    started_at: datetime = None
    terminated_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Factory method
    @classmethod
    def create(
        cls,
        session_id: str,
        command: list[str],
        dimensions: TerminalDimensions
    ) -> "PTYSession":
        """Create a new PTY session in STARTING state.

        This is the primary factory method for creating PTY sessions. It initializes
        the session with the provided command and dimensions, setting the state to
        STARTING and recording the creation timestamp.

        Args:
            session_id: Unique session identifier
            command: Command and arguments to execute in PTY
            dimensions: Terminal dimensions for the PTY

        Returns:
            New PTYSession instance in STARTING state

        Example:
            session = PTYSession.create(
                session_id="sess-123",
                command=["claude", "code"],
                dimensions=TerminalDimensions(rows=24, cols=80)
            )
            print(session.state)  # ProcessState.STARTING
            print(session.is_alive())  # False
        """
        return cls(
            session_id=session_id,
            command=command,
            dimensions=dimensions,
            state=ProcessState.STARTING,
            started_at=datetime.now()
        )

    # Domain methods
    def set_running(self, pid: int) -> None:
        """Mark process as running and store PID.

        Validates that the process is in STARTING state before transitioning
        to RUNNING. This ensures a process can only be started once.

        Args:
            pid: Process ID of the started PTY process

        Raises:
            ProcessAlreadyStartedException: If process is not in STARTING state
        """
        if self.state != ProcessState.STARTING:
            raise ProcessAlreadyStartedException(
                session_id=self.session_id,
                current_state=self.state
            )

        self.pid = pid
        self.state = ProcessState.RUNNING

    def resize(self, dimensions: TerminalDimensions) -> None:
        """Update terminal dimensions for running process.

        The process must be alive (RUNNING state) to be resized. This operation
        updates the dimensions which can then be applied to the actual PTY.

        Args:
            dimensions: New terminal dimensions

        Raises:
            ProcessNotRunningException: If process is not in RUNNING state
        """
        if not self.is_alive():
            raise ProcessNotRunningException(
                session_id=self.session_id,
                current_state=self.state,
                operation="resize terminal"
            )

        self.dimensions = dimensions

    def terminate(self, exit_code: int) -> None:
        """Mark process as terminated with exit code.

        Transitions the process to TERMINATED state and records the exit code
        and termination timestamp. Can only be called when process is running.

        Args:
            exit_code: Exit code from the terminated process

        Raises:
            ProcessNotRunningException: If process is not in RUNNING state
        """
        if not self.is_alive():
            raise ProcessNotRunningException(
                session_id=self.session_id,
                current_state=self.state,
                operation="terminate process"
            )

        self.state = ProcessState.TERMINATED
        self.exit_code = exit_code
        self.terminated_at = datetime.now()

    def set_error(self, error_message: str) -> None:
        """Mark process as errored with error message.

        Transitions to ERROR state and records the error message. Can be called
        from any state to indicate a failure occurred.

        Args:
            error_message: Description of the error that occurred
        """
        self.state = ProcessState.ERROR
        self.error_message = error_message
        if self.terminated_at is None:
            self.terminated_at = datetime.now()

    def is_alive(self) -> bool:
        """Check if process is currently running.

        Returns:
            True if process is in RUNNING state, False otherwise
        """
        return self.state == ProcessState.RUNNING

    def __repr__(self) -> str:
        """Developer representation."""
        return (
            f"PTYSession("
            f"session_id={self.session_id!r}, "
            f"state={self.state.value}, "
            f"pid={self.pid}, "
            f"command={self.command!r}, "
            f"dimensions={self.dimensions}"
            f")"
        )
