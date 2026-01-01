"""Session protocol messages for RemoteAgents pairing flow.

This module defines the message types used in the session lifecycle:
1. Desktop creates session -> SessionCreate
2. Relay responds with session ID and pairing code -> SessionCreated
3. Client connects with pairing code -> SessionPair
4. Relay confirms pairing with desktop public key -> SessionPaired
5. Either party closes session -> SessionClose

All public keys are X25519 keys (32 bytes) used for E2E encryption.
Pairing codes are 6-character uppercase alphanumeric codes.

Example pairing flow:
    Desktop -> Relay: SessionCreate(desktop_public_key=<32 bytes>)
    Relay -> Desktop: SessionCreated(session_id="uuid", pairing_code="ABC123")
    Client -> Relay: SessionPair(pairing_code="ABC123", client_public_key=<32 bytes>)
    Relay -> Client: SessionPaired(session_id="uuid", desktop_public_key=<32 bytes>)
    Relay -> Desktop: SessionPaired(session_id="uuid", desktop_public_key=<32 bytes>)
    [Session active for terminal communication]
    Desktop/Client -> Relay: SessionClose(session_id="uuid")
"""

import re
from typing import Literal, Optional, Union

from pydantic import Field, field_validator, field_serializer

from agent_remote.shared.protocol.base import (
    MESSAGE_TYPES,
    RemoteAgentMessage,
    SessionMessage,
    bytes_to_base64,
    base64_to_bytes,
)


# ==============================================================================
# Session Lifecycle Messages
# ==============================================================================

class SessionCreate(RemoteAgentMessage):
    """Desktop initiates session creation with its public key.

    Desktop sends this message to the relay to request a new session.
    The relay will respond with SessionCreated containing the session ID
    and a pairing code that the client can use to connect.

    Fields:
        type: Always "session.create"
        desktop_public_key: X25519 public key (32 bytes) for E2E encryption
    """

    type: Literal["session.create"] = "session.create"
    desktop_public_key: bytes = Field(
        ...,
        description="Desktop's X25519 public key (32 bytes) for E2E encryption"
    )

    @field_validator("desktop_public_key", mode="before")
    @classmethod
    def validate_desktop_public_key(cls, v: Union[bytes, str]) -> bytes:
        """Validate and convert public key to bytes.

        Handles both direct bytes input (construction) and base64 string input
        (JSON deserialization). Validates that the result is exactly 32 bytes.

        Args:
            v: Public key as bytes or base64 string

        Returns:
            Validated public key bytes

        Raises:
            ValueError: If public key is not exactly 32 bytes
        """
        # Convert base64 string to bytes if necessary
        if isinstance(v, str):
            v = base64_to_bytes(v)

        if not isinstance(v, bytes):
            raise ValueError(f"desktop_public_key must be bytes or base64 string, got {type(v)}")

        if len(v) != 32:
            raise ValueError(
                f"desktop_public_key must be exactly 32 bytes (X25519 format), "
                f"got {len(v)} bytes"
            )
        return v

    @field_serializer("desktop_public_key")
    def serialize_desktop_public_key(self, v: bytes) -> str:
        """Serialize public key to base64 for JSON transport."""
        return bytes_to_base64(v)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """Register message type in global registry."""
        MESSAGE_TYPES["session.create"] = cls


class SessionCreated(SessionMessage):
    """Relay confirms session creation with session ID and pairing code.

    Relay sends this message to the desktop after receiving SessionCreate.
    Contains the session ID that will be used for all future communication
    and a pairing code that the client needs to connect.

    Fields:
        type: Always "session.created"
        session_id: UUID identifying the session (validated by SessionMessage)
        pairing_code: 6-character uppercase alphanumeric code for client pairing
    """

    type: Literal["session.created"] = "session.created"
    pairing_code: str = Field(
        ...,
        description="6-character uppercase alphanumeric pairing code"
    )

    @field_validator("pairing_code")
    @classmethod
    def validate_pairing_code(cls, v: str) -> str:
        """Validate pairing code is 6 uppercase alphanumeric characters.

        Format: Exactly 6 characters from [A-Z0-9]
        Examples: "ABC123", "XYZ789", "A1B2C3"

        Args:
            v: Pairing code to validate

        Returns:
            Validated pairing code

        Raises:
            ValueError: If pairing code doesn't match required format
        """
        pattern = r"^[A-Z0-9]{6}$"
        if not re.match(pattern, v):
            raise ValueError(
                f"pairing_code must be exactly 6 uppercase alphanumeric characters "
                f"(A-Z, 0-9), got: {v!r}"
            )
        return v

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """Register message type in global registry."""
        MESSAGE_TYPES["session.created"] = cls


class SessionPair(RemoteAgentMessage):
    """Client requests to pair with session using pairing code.

    Client sends this message to the relay with the pairing code (obtained
    from the desktop user) and its own public key for E2E encryption.
    The relay will validate the pairing code and respond with SessionPaired.

    Fields:
        type: Always "session.pair"
        pairing_code: 6-character uppercase alphanumeric code from desktop
        client_public_key: X25519 public key (32 bytes) for E2E encryption
    """

    type: Literal["session.pair"] = "session.pair"
    pairing_code: str = Field(
        ...,
        description="6-character uppercase alphanumeric pairing code"
    )
    client_public_key: bytes = Field(
        ...,
        description="Client's X25519 public key (32 bytes) for E2E encryption"
    )

    @field_validator("pairing_code")
    @classmethod
    def validate_pairing_code(cls, v: str) -> str:
        """Validate pairing code is 6 uppercase alphanumeric characters.

        Format: Exactly 6 characters from [A-Z0-9]
        Examples: "ABC123", "XYZ789", "A1B2C3"

        Args:
            v: Pairing code to validate

        Returns:
            Validated pairing code

        Raises:
            ValueError: If pairing code doesn't match required format
        """
        pattern = r"^[A-Z0-9]{6}$"
        if not re.match(pattern, v):
            raise ValueError(
                f"pairing_code must be exactly 6 uppercase alphanumeric characters "
                f"(A-Z, 0-9), got: {v!r}"
            )
        return v

    @field_validator("client_public_key", mode="before")
    @classmethod
    def validate_client_public_key(cls, v: Union[bytes, str]) -> bytes:
        """Validate and convert public key to bytes.

        Handles both direct bytes input (construction) and base64 string input
        (JSON deserialization). Validates that the result is exactly 32 bytes.

        Args:
            v: Public key as bytes or base64 string

        Returns:
            Validated public key bytes

        Raises:
            ValueError: If public key is not exactly 32 bytes
        """
        # Convert base64 string to bytes if necessary
        if isinstance(v, str):
            v = base64_to_bytes(v)

        if not isinstance(v, bytes):
            raise ValueError(f"client_public_key must be bytes or base64 string, got {type(v)}")

        if len(v) != 32:
            raise ValueError(
                f"client_public_key must be exactly 32 bytes (X25519 format), "
                f"got {len(v)} bytes"
            )
        return v

    @field_serializer("client_public_key")
    def serialize_client_public_key(self, v: bytes) -> str:
        """Serialize public key to base64 for JSON transport."""
        return bytes_to_base64(v)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """Register message type in global registry."""
        MESSAGE_TYPES["session.pair"] = cls


class SessionPaired(SessionMessage):
    """Relay confirms successful pairing with public keys.

    Relay sends this message to both the desktop and client after successful
    pairing. Contains the session ID and public keys for E2E encryption.

    When sent to Client:
        - desktop_public_key is provided so client can establish E2E encryption
        - client_public_key is omitted (client already knows its own key)

    When sent to Desktop:
        - desktop_public_key is provided (for consistency)
        - client_public_key is provided so desktop knows who paired

    Fields:
        type: Always "session.paired"
        session_id: UUID identifying the session (validated by SessionMessage)
        desktop_public_key: Desktop's X25519 public key (32 bytes) for E2E encryption
        client_public_key: Client's X25519 public key (optional, sent to desktop only)
    """

    type: Literal["session.paired"] = "session.paired"
    desktop_public_key: bytes = Field(
        ...,
        description="Desktop's X25519 public key (32 bytes) for E2E encryption"
    )
    client_public_key: Optional[bytes] = Field(
        default=None,
        description="Client's X25519 public key (32 bytes) - sent to desktop only"
    )

    @field_validator("desktop_public_key", mode="before")
    @classmethod
    def validate_desktop_public_key(cls, v: Union[bytes, str]) -> bytes:
        """Validate and convert public key to bytes.

        Handles both direct bytes input (construction) and base64 string input
        (JSON deserialization). Validates that the result is exactly 32 bytes.

        Args:
            v: Public key as bytes or base64 string

        Returns:
            Validated public key bytes

        Raises:
            ValueError: If public key is not exactly 32 bytes
        """
        # Convert base64 string to bytes if necessary
        if isinstance(v, str):
            v = base64_to_bytes(v)

        if not isinstance(v, bytes):
            raise ValueError(f"desktop_public_key must be bytes or base64 string, got {type(v)}")

        if len(v) != 32:
            raise ValueError(
                f"desktop_public_key must be exactly 32 bytes (X25519 format), "
                f"got {len(v)} bytes"
            )
        return v

    @field_serializer("desktop_public_key")
    def serialize_desktop_public_key(self, v: bytes) -> str:
        """Serialize public key to base64 for JSON transport."""
        return bytes_to_base64(v)

    @field_validator("client_public_key", mode="before")
    @classmethod
    def validate_client_public_key(cls, v: Union[bytes, str, None]) -> Optional[bytes]:
        """Validate and convert public key to bytes if provided.

        Handles both direct bytes input (construction) and base64 string input
        (JSON deserialization). Validates that the result is exactly 32 bytes.

        Args:
            v: Public key as bytes or base64 string, or None

        Returns:
            Validated public key bytes or None

        Raises:
            ValueError: If public key is not exactly 32 bytes
        """
        if v is None:
            return None

        # Convert base64 string to bytes if necessary
        if isinstance(v, str):
            v = base64_to_bytes(v)

        if not isinstance(v, bytes):
            raise ValueError(f"client_public_key must be bytes or base64 string, got {type(v)}")

        if len(v) != 32:
            raise ValueError(
                f"client_public_key must be exactly 32 bytes (X25519 format), "
                f"got {len(v)} bytes"
            )
        return v

    @field_serializer("client_public_key")
    def serialize_client_public_key(self, v: Optional[bytes]) -> Optional[str]:
        """Serialize public key to base64 for JSON transport."""
        if v is None:
            return None
        return bytes_to_base64(v)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """Register message type in global registry."""
        MESSAGE_TYPES["session.paired"] = cls


class SessionClose(SessionMessage):
    """Either desktop or client requests to close the session.

    Either party can send this message to close the session gracefully.
    The relay will forward the close to the other party and clean up resources.

    Fields:
        type: Always "session.close"
        session_id: UUID identifying the session to close (validated by SessionMessage)
    """

    type: Literal["session.close"] = "session.close"

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """Register message type in global registry."""
        MESSAGE_TYPES["session.close"] = cls


# ==============================================================================
# Auto-register message types on module import
# ==============================================================================

# Force class initialization to register all message types
# This ensures MESSAGE_TYPES is populated when this module is imported
SessionCreate.__pydantic_init_subclass__()
SessionCreated.__pydantic_init_subclass__()
SessionPair.__pydantic_init_subclass__()
SessionPaired.__pydantic_init_subclass__()
SessionClose.__pydantic_init_subclass__()
