"""Terminal protocol messages for RemoteAgents PTY communication.

This module defines all terminal-related protocol messages:
- TerminalOutput: Server -> Client PTY output data
- TerminalInput: Client -> Server PTY input (keystrokes, commands)
- TerminalResize: Client -> Server terminal dimension changes
- TerminalClose: Bidirectional session termination request

All terminal messages inherit from SessionMessage and require a valid session_id.
Output and Input messages also inherit from TimestampedMessage for ordering.

Terminal data (input/output) is transported as bytes to preserve binary PTY data
(ANSI escape codes, colors, control characters). Bytes are serialized as base64
in JSON for WebSocket transport.

Example usage:
    # Terminal output from PTY to client
    output = TerminalOutput(
        session_id=generate_session_id(),
        data=b"\x1b[32mHello\x1b[0m"  # Green "Hello" with ANSI codes
    )
    json_str = output.to_json()

    # Terminal input from client to PTY
    input_msg = TerminalInput(
        session_id="existing-session-id",
        data=b"ls -la\r"  # Command with carriage return
    )

    # Resize terminal dimensions
    resize = TerminalResize(
        session_id="existing-session-id",
        rows=24,
        cols=80
    )

    # Close terminal session
    close = TerminalClose(
        session_id="existing-session-id",
        reason="User disconnected"
    )
"""

from typing import Annotated, Literal

from pydantic import Field, PlainSerializer, field_validator

from agent_remote.shared.protocol.base import (
    MESSAGE_TYPES,
    SessionMessage,
    TimestampedMessage,
    base64_to_bytes,
    bytes_to_base64,
)


class TerminalOutput(SessionMessage, TimestampedMessage):
    """Terminal output data from PTY to client.

    Sent whenever the PTY process generates output (stdout/stderr combined).
    This is a high-frequency message type (one per output chunk).

    The data field contains raw bytes from the PTY, which may include:
    - ANSI escape codes (colors, cursor movement, etc.)
    - Control characters (newlines, tabs, bells, etc.)
    - Binary data (if running binary programs)
    - UTF-8 encoded text

    Bytes are automatically serialized as base64 when converted to JSON.

    Fields:
        type: Message type discriminator "terminal.output"
        session_id: UUID identifying the terminal session (inherited)
        timestamp: Unix epoch timestamp when output was generated (inherited, auto-populated)
        data: Raw bytes from PTY output

    Example JSON:
        {
            "type": "terminal.output",
            "session_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": 1234567890.123,
            "data": "SGVsbG8gV29ybGQK"  // base64("Hello World\n")
        }
    """

    type: Literal["terminal.output"] = "terminal.output"
    data: Annotated[
        bytes,
        PlainSerializer(lambda x: bytes_to_base64(x), return_type=str, when_used='json')
    ] = Field(..., description="Raw PTY output bytes")

    @field_validator("data", mode="before")
    @classmethod
    def decode_base64_data(cls, v):
        """Decode base64 string to bytes when deserializing from JSON."""
        if isinstance(v, str):
            return base64_to_bytes(v)
        return v


class TerminalInput(SessionMessage, TimestampedMessage):
    """Terminal input data from client to PTY.

    Sent when the client types keys or sends input to the terminal.
    This is a high-frequency message type (one per keystroke or paste).

    The data field contains raw bytes to be written to the PTY stdin:
    - Regular characters (letters, numbers, etc.)
    - Special keys encoded as escape sequences (arrows, function keys, etc.)
    - Control characters (Ctrl+C, Ctrl+D, etc.)
    - Pasted text (potentially multi-line)

    Bytes are automatically serialized as base64 when converted to JSON.

    Fields:
        type: Message type discriminator "terminal.input"
        session_id: UUID identifying the terminal session (inherited)
        timestamp: Unix epoch timestamp when input was sent (inherited, auto-populated)
        data: Raw bytes to write to PTY stdin

    Example JSON:
        {
            "type": "terminal.input",
            "session_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": 1234567890.123,
            "data": "bHMgLWxhDQ=="  // base64("ls -la\r")
        }
    """

    type: Literal["terminal.input"] = "terminal.input"
    data: Annotated[
        bytes,
        PlainSerializer(lambda x: bytes_to_base64(x), return_type=str, when_used='json')
    ] = Field(..., description="Raw input bytes to write to PTY")

    @field_validator("data", mode="before")
    @classmethod
    def decode_base64_data(cls, v):
        """Decode base64 string to bytes when deserializing from JSON."""
        if isinstance(v, str):
            return base64_to_bytes(v)
        return v


class TerminalResize(SessionMessage):
    """Terminal resize notification from client to server.

    Sent when the client's terminal window is resized. The server must
    resize the PTY to match the new dimensions to ensure proper line wrapping
    and screen layout.

    Terminals typically range from 1x1 (minimum) to 1000x1000 (maximum).
    Common sizes: 24x80 (classic), 25x80, 40x132, 50x132.

    Fields:
        type: Message type discriminator "terminal.resize"
        session_id: UUID identifying the terminal session (inherited)
        rows: Number of rows (lines) in terminal (1-1000)
        cols: Number of columns (characters per line) in terminal (1-1000)

    Example JSON:
        {
            "type": "terminal.resize",
            "session_id": "123e4567-e89b-12d3-a456-426614174000",
            "rows": 24,
            "cols": 80
        }
    """

    type: Literal["terminal.resize"] = "terminal.resize"
    rows: int = Field(
        ..., ge=1, le=1000, description="Number of rows (lines) in terminal"
    )
    cols: int = Field(
        ..., ge=1, le=1000, description="Number of columns (chars per line) in terminal"
    )

    @field_validator("rows", "cols")
    @classmethod
    def validate_dimensions(cls, v: int) -> int:
        """Validate terminal dimensions are positive integers in valid range.

        Args:
            v: dimension value to validate

        Returns:
            Validated dimension

        Raises:
            ValueError: If dimension is not in range 1-1000
        """
        if not isinstance(v, int):
            raise ValueError("Terminal dimensions must be integers")
        if v < 1 or v > 1000:
            raise ValueError("Terminal dimensions must be between 1 and 1000")
        return v


class TerminalClose(SessionMessage):
    """Terminal session close notification.

    Sent bidirectionally when either side wants to close the terminal session:
    - Client -> Server: User closed the terminal window or logged out
    - Server -> Desktop: PTY process exited or crashed

    After receiving TerminalClose, the recipient should clean up resources
    (close PTY, close WebSocket, etc.). The reason field helps with debugging
    and logging.

    Fields:
        type: Message type discriminator "terminal.close"
        session_id: UUID identifying the terminal session (inherited)
        reason: Human-readable explanation for closure

    Example JSON:
        {
            "type": "terminal.close",
            "session_id": "123e4567-e89b-12d3-a456-426614174000",
            "reason": "User disconnected"
        }

    Common reasons:
        - "User disconnected" - Client closed window/tab
        - "Process exited" - PTY process terminated normally
        - "Process crashed" - PTY process terminated with error
        - "Timeout" - Session idle timeout
        - "Authentication failed" - Security validation failed
    """

    type: Literal["terminal.close"] = "terminal.close"
    reason: str = Field(..., description="Human-readable closure reason")


# ==============================================================================
# Message Type Registration
# ==============================================================================

# Register all terminal message types in the global registry for deserialization
MESSAGE_TYPES["terminal.output"] = TerminalOutput
MESSAGE_TYPES["terminal.input"] = TerminalInput
MESSAGE_TYPES["terminal.resize"] = TerminalResize
MESSAGE_TYPES["terminal.close"] = TerminalClose
