"""Value objects for PTYManager domain.

This module defines immutable value objects that represent core domain concepts:
- TerminalDimensions: Terminal size with validation (rows/cols)
- ProcessState: Enum for PTY process lifecycle states
- TerminalMode: Enum for terminal input/output modes

Value objects are immutable and validated, ensuring domain integrity.
"""

from dataclasses import dataclass
from enum import Enum


class ProcessState(str, Enum):
    """State of a PTY process in its lifecycle.

    Valid state transitions:
    - STARTING -> RUNNING (when process successfully starts)
    - STARTING -> ERROR (when process fails to start)
    - RUNNING -> TERMINATED (when process exits normally)
    - RUNNING -> ERROR (when process crashes)
    """
    STARTING = "starting"
    RUNNING = "running"
    TERMINATED = "terminated"
    ERROR = "error"


class TerminalMode(str, Enum):
    """Terminal input/output processing mode.

    - RAW: Raw mode - minimal processing, all input passed directly to application
    - COOKED: Cooked mode - line editing, special character processing enabled
    """
    RAW = "raw"
    COOKED = "cooked"


@dataclass(frozen=True)
class TerminalDimensions:
    """Immutable value object representing terminal size.

    Terminal dimensions define the rows and columns of the PTY viewport.
    Both dimensions must be within reasonable bounds (1-1000) to prevent
    resource issues and ensure practical usability.

    Attributes:
        rows: Number of terminal rows (height)
        cols: Number of terminal columns (width)
    """

    rows: int
    cols: int

    def __post_init__(self):
        """Validate terminal dimensions after initialization.

        Raises:
            ValueError: If rows or cols are not within valid range (1-1000)
        """
        if not isinstance(self.rows, int):
            raise ValueError(f"rows must be an integer, got {type(self.rows).__name__}")

        if not isinstance(self.cols, int):
            raise ValueError(f"cols must be an integer, got {type(self.cols).__name__}")

        if not (1 <= self.rows <= 1000):
            raise ValueError(f"rows must be between 1 and 1000, got {self.rows}")

        if not (1 <= self.cols <= 1000):
            raise ValueError(f"cols must be between 1 and 1000, got {self.cols}")

    def __str__(self) -> str:
        """String representation."""
        return f"{self.rows}x{self.cols}"

    def __repr__(self) -> str:
        """Developer representation."""
        return f"TerminalDimensions(rows={self.rows}, cols={self.cols})"
