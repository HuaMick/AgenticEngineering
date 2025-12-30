"""PTYManager domain - Process lifecycle for pseudo-terminal sessions.

This domain models the lifecycle of PTY (pseudo-terminal) sessions running
Claude Code CLI. It provides:

- Value Objects: TerminalDimensions, ProcessState, TerminalMode
- Entity: PTYSession with state machine for process lifecycle
- Repository: PTYRepository Protocol for session storage

Example usage:
    from agent_remote.services.terminal.domains.pty_manager import (
        PTYSession,
        TerminalDimensions,
        ProcessState,
    )

    # Create a new PTY session
    session = PTYSession.create(
        session_id="sess-123",
        command=["claude"],
        dimensions=TerminalDimensions(rows=24, cols=80)
    )

    # Mark as running with PID
    session.set_running(pid=12345)

    # Check if alive
    if session.is_alive():
        session.resize(TerminalDimensions(rows=40, cols=120))
"""

from .entities import (
    InvalidStateTransitionException,
    ProcessAlreadyStartedException,
    ProcessNotRunningException,
    PTYDomainException,
    PTYSession,
)
from .repository import PTYRepository
from .value_objects import ProcessState, TerminalDimensions, TerminalMode

__all__ = [
    # Value Objects
    "TerminalDimensions",
    "ProcessState",
    "TerminalMode",
    # Entity
    "PTYSession",
    # Repository Protocol
    "PTYRepository",
    # Exceptions
    "PTYDomainException",
    "ProcessAlreadyStartedException",
    "ProcessNotRunningException",
    "InvalidStateTransitionException",
]
