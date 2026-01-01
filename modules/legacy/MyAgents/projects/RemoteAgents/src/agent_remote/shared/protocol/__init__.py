"""Protocol message definitions for RemoteAgents communication.

This module exports all protocol message types and infrastructure:

Base Infrastructure:
- RemoteAgentMessage: Base class for all messages
- TimestampedMessage: Messages with auto-populated timestamps
- SessionMessage: Messages with session_id validation
- Utility functions: bytes_to_base64, base64_to_bytes, generate_session_id, generate_pairing_code
- Type registry: MESSAGE_TYPES, deserialize_message

Session Messages (pairing flow):
- SessionCreate: Desktop creates session with public key
- SessionCreated: Relay responds with session ID and pairing code
- SessionPair: Client pairs with pairing code and public key
- SessionPaired: Relay confirms pairing with desktop public key
- SessionClose: Either party closes the session

Terminal Messages (PTY communication):
- TerminalOutput: Server -> Client PTY output data
- TerminalInput: Client -> Server PTY input (keystrokes)
- TerminalResize: Client -> Server terminal dimension changes
- TerminalClose: Bidirectional session termination request

Relay Messages (encrypted transport):
- EncryptedBlob: Encrypted payload wrapper for terminal/session messages
- Ping/Pong: WebSocket keepalive messages
- Error: Structured error reporting with namespaced error codes
- ERROR_* constants: Namespaced error codes for structured handling
"""

from agent_remote.shared.protocol.base import (
    MESSAGE_TYPES,
    RemoteAgentMessage,
    SessionMessage,
    TimestampedMessage,
    base64_to_bytes,
    bytes_to_base64,
    deserialize_message,
    generate_pairing_code,
    generate_session_id,
)

# Import session messages to register them in MESSAGE_TYPES
from agent_remote.shared.protocol.session_messages import (
    SessionClose,
    SessionCreate,
    SessionCreated,
    SessionPair,
    SessionPaired,
)

# Import terminal messages to register them in MESSAGE_TYPES
from agent_remote.shared.protocol.terminal_messages import (
    TerminalClose,
    TerminalInput,
    TerminalOutput,
    TerminalResize,
)

# Import relay messages to register them in MESSAGE_TYPES
from agent_remote.shared.protocol.relay_messages import (
    ERROR_CONNECTION_LOST,
    ERROR_CRYPTO_ERROR,
    ERROR_DECRYPTION_FAILED,
    ERROR_INTERNAL_ERROR,
    ERROR_INVALID_KEY,
    ERROR_INVALID_MESSAGE,
    ERROR_INVALID_NONCE,
    ERROR_PAIRING_CODE_EXPIRED,
    ERROR_PAIRING_CODE_INVALID,
    ERROR_PAIRING_FAILED,
    ERROR_SESSION_ALREADY_EXISTS,
    ERROR_SESSION_EXPIRED,
    ERROR_SESSION_NOT_FOUND,
    ERROR_TIMEOUT,
    ERROR_UNAUTHORIZED,
    ERROR_UNSUPPORTED_MESSAGE_TYPE,
    ERROR_VALIDATION_FAILED,
    EncryptedBlob,
    Error,
    Ping,
    Pong,
)

__all__ = [
    # Base classes
    "RemoteAgentMessage",
    "TimestampedMessage",
    "SessionMessage",
    # Utility functions
    "bytes_to_base64",
    "base64_to_bytes",
    "generate_session_id",
    "generate_pairing_code",
    # Type registry
    "MESSAGE_TYPES",
    "deserialize_message",
    # Session messages
    "SessionCreate",
    "SessionCreated",
    "SessionPair",
    "SessionPaired",
    "SessionClose",
    # Terminal messages
    "TerminalOutput",
    "TerminalInput",
    "TerminalResize",
    "TerminalClose",
    # Relay messages
    "EncryptedBlob",
    "Ping",
    "Pong",
    "Error",
    # Error code constants
    "ERROR_SESSION_EXPIRED",
    "ERROR_SESSION_NOT_FOUND",
    "ERROR_SESSION_ALREADY_EXISTS",
    "ERROR_PAIRING_FAILED",
    "ERROR_PAIRING_CODE_INVALID",
    "ERROR_PAIRING_CODE_EXPIRED",
    "ERROR_CRYPTO_ERROR",
    "ERROR_INVALID_KEY",
    "ERROR_DECRYPTION_FAILED",
    "ERROR_INVALID_NONCE",
    "ERROR_INVALID_MESSAGE",
    "ERROR_UNSUPPORTED_MESSAGE_TYPE",
    "ERROR_VALIDATION_FAILED",
    "ERROR_CONNECTION_LOST",
    "ERROR_TIMEOUT",
    "ERROR_INTERNAL_ERROR",
    "ERROR_UNAUTHORIZED",
]
