"""Terminal workflow layer for PTY session orchestration.

This layer coordinates domain entities with infrastructure to manage
the complete PTY session lifecycle:

- TerminalWorkflow: Orchestrates PTY session start, I/O, resize, and termination
- SessionWorkflow: Orchestrates complete remote session lifecycle (session creation, PTY, relay)
- OutputCallback: Type for PTY output delivery to callers
"""

from .terminal_workflow import (
    OutputCallback,
    SessionNotFoundError,
    TerminalWorkflow,
    TerminalWorkflowError,
)

# SessionWorkflow requires httpx - import conditionally
try:
    from .session_workflow import (
        SessionWorkflow,
        SessionWorkflowError,
    )
    _HAS_SESSION_WORKFLOW = True
except ImportError:
    SessionWorkflow = None  # type: ignore
    SessionWorkflowError = None  # type: ignore
    _HAS_SESSION_WORKFLOW = False

__all__ = [
    "TerminalWorkflow",
    "TerminalWorkflowError",
    "SessionNotFoundError",
    "OutputCallback",
]

if _HAS_SESSION_WORKFLOW:
    __all__.extend(["SessionWorkflow", "SessionWorkflowError"])
