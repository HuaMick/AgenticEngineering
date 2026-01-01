"""Base protocol infrastructure for RemoteAgents messaging.

This module provides the foundational classes and utilities for all protocol messages:
- RemoteAgentMessage: Base class for all messages with type discriminator and JSON serialization
- TimestampedMessage: Adds automatic timestamp field for message ordering
- SessionMessage: Adds session_id field with UUID validation
- Utility functions for bytes encoding, session/pairing code generation
- Type registry for safe message deserialization without eval()

All protocol messages inherit from these base classes to ensure consistent:
- Type discrimination for routing (via 'type' field)
- JSON serialization/deserialization (via to_json()/from_json())
- Validation (via Pydantic validators)
- Timestamp ordering (via auto-populated timestamp)
- Session tracking (via UUID-validated session_id)

Example usage:
    class MyMessage(SessionMessage, TimestampedMessage):
        type: Literal["my.message"] = "my.message"
        data: str

    msg = MyMessage(session_id="uuid-here", data="hello")
    json_str = msg.to_json()
    msg2 = deserialize_message(json_str)  # Returns MyMessage instance
"""

import base64
import json
import random
import string
import time
from typing import Any, Dict, Type
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RemoteAgentMessage(BaseModel):
    """Base class for all RemoteAgents protocol messages.

    Provides:
    - type: String discriminator for message routing (must be set by subclasses)
    - to_json(): Serialize message to JSON string
    - from_json(): Deserialize message from JSON string (class method)

    All protocol messages must inherit from this class and define a 'type' field
    with a unique string value (e.g., "terminal.output", "session.create").

    The type field is used by the deserialization infrastructure to dispatch
    incoming messages to the correct concrete class.

    Example:
        class TerminalOutput(RemoteAgentMessage):
            type: Literal["terminal.output"] = "terminal.output"
            data: bytes
    """

    type: str = Field(..., description="Message type discriminator for routing")

    def to_json(self) -> str:
        """Serialize message to JSON string.

        Uses Pydantic's model_dump() to convert to dict, then json.dumps().
        Handles bytes fields by converting them to base64 strings.

        Returns:
            JSON string representation of the message
        """
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "RemoteAgentMessage":
        """Deserialize message from JSON string.

        Uses Pydantic's model_validate_json() to parse and validate.

        Args:
            json_str: JSON string containing message data

        Returns:
            Message instance of the appropriate type

        Raises:
            ValidationError: If JSON doesn't match message schema
        """
        return cls.model_validate_json(json_str)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class TimestampedMessage(RemoteAgentMessage):
    """Base class for messages that require timestamp ordering.

    Adds:
    - timestamp: Unix epoch timestamp in seconds (float), auto-populated on creation

    The timestamp is automatically set to time.time() when the message is created
    if not explicitly provided. This enables message ordering and timeout detection.

    Example:
        class Ping(TimestampedMessage):
            type: Literal["relay.ping"] = "relay.ping"

        msg = Ping()  # timestamp auto-populated
        assert msg.timestamp > 0
    """

    timestamp: float = Field(
        default_factory=time.time,
        description="Unix epoch timestamp in seconds (auto-populated)",
    )


class SessionMessage(RemoteAgentMessage):
    """Base class for messages that belong to a specific session.

    Adds:
    - session_id: UUID string identifying the session, validated for correct format

    The session_id must be a valid UUID string. This is validated by Pydantic
    to ensure only well-formed session IDs are accepted.

    Sessions are established during the pairing flow and identify a connected
    desktop-client pair. All terminal messages and most protocol messages
    require a session_id.

    Example:
        class TerminalOutput(SessionMessage, TimestampedMessage):
            type: Literal["terminal.output"] = "terminal.output"
            data: bytes

        msg = TerminalOutput(
            session_id=generate_session_id(),
            data=b"hello"
        )
    """

    session_id: str = Field(..., description="UUID identifying the session")

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Validate session_id is a valid UUID string.

        Args:
            v: session_id value to validate

        Returns:
            Validated session_id string

        Raises:
            ValueError: If session_id is not a valid UUID
        """
        try:
            # Validate UUID format by attempting to parse
            UUID(v)
            return v
        except ValueError as e:
            raise ValueError(f"session_id must be a valid UUID string: {e}")


# ==============================================================================
# Utility Functions
# ==============================================================================

def bytes_to_base64(data: bytes) -> str:
    """Convert bytes to base64-encoded string for JSON transport.

    Args:
        data: Raw bytes to encode

    Returns:
        Base64-encoded string representation

    Example:
        >>> bytes_to_base64(b"hello")
        'aGVsbG8='
    """
    return base64.b64encode(data).decode("ascii")


def base64_to_bytes(data: str) -> bytes:
    """Convert base64-encoded string back to bytes.

    Args:
        data: Base64-encoded string

    Returns:
        Decoded bytes

    Raises:
        ValueError: If string is not valid base64

    Example:
        >>> base64_to_bytes('aGVsbG8=')
        b'hello'
    """
    return base64.b64decode(data.encode("ascii"))


def generate_session_id() -> str:
    """Generate a new session ID as UUID4 string.

    Returns:
        UUID4 string suitable for use as session_id

    Example:
        >>> session_id = generate_session_id()
        >>> UUID(session_id)  # Valid UUID
    """
    return str(uuid4())


def generate_pairing_code() -> str:
    """Generate a 6-character random alphanumeric uppercase pairing code.

    Pairing codes are used in the session pairing flow. The relay service
    issues a pairing code when a desktop creates a session, and the web client
    uses this code to connect.

    Format: 6 characters, uppercase letters and digits only (A-Z, 0-9)
    Example: "ABC123", "XYZ789"

    Returns:
        6-character uppercase alphanumeric string

    Example:
        >>> code = generate_pairing_code()
        >>> len(code)
        6
        >>> code.isupper()
        True
        >>> all(c in string.ascii_uppercase + string.digits for c in code)
        True
    """
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(6))


# ==============================================================================
# Type Registry Infrastructure
# ==============================================================================

# Global registry mapping type strings to message classes
# Populated by message definitions as they are imported
MESSAGE_TYPES: Dict[str, Type[RemoteAgentMessage]] = {}


def deserialize_message(json_str: str) -> RemoteAgentMessage:
    """Deserialize a JSON message to the appropriate concrete type.

    This function uses the 'type' field in the JSON to dispatch to the correct
    message class from the MESSAGE_TYPES registry. This enables safe deserialization
    without eval() or other dangerous operations.

    Message classes must be registered in MESSAGE_TYPES before they can be
    deserialized. This is typically done when message modules are imported.

    Args:
        json_str: JSON string containing message with 'type' field

    Returns:
        Message instance of the appropriate concrete type

    Raises:
        ValueError: If type field is missing or unknown
        KeyError: If message type not registered in MESSAGE_TYPES
        ValidationError: If JSON doesn't match message schema

    Example:
        >>> json_str = '{"type": "terminal.output", "session_id": "...", "data": "..."}'
        >>> msg = deserialize_message(json_str)
        >>> isinstance(msg, TerminalOutput)
        True
    """
    # Parse JSON to extract type field
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    # Extract and validate type field
    if "type" not in data:
        raise ValueError("Message missing required 'type' field")

    msg_type = data["type"]

    # Lookup message class in registry
    if msg_type not in MESSAGE_TYPES:
        raise KeyError(
            f"Unknown message type '{msg_type}'. "
            f"Known types: {list(MESSAGE_TYPES.keys())}"
        )

    # Deserialize using appropriate message class
    message_class = MESSAGE_TYPES[msg_type]
    return message_class.from_json(json_str)
