"""Relay protocol messages for encrypted transport and WebSocket management.

This module defines the relay layer messages that handle:
- Encrypted message transport (EncryptedBlob wraps all terminal/session messages)
- WebSocket keepalive (Ping/Pong)
- Error reporting

The relay layer is the encrypted transport layer. All terminal and session messages
are wrapped in EncryptedBlob when transmitted through the relay. The relay never
sees the plaintext content of these messages.

Message types:
- EncryptedBlob: Encrypted payload with NaCl nonce, carries terminal/session messages
- Ping/Pong: WebSocket keepalive to prevent connection timeouts
- Error: Structured error reporting with namespaced error codes

Encryption details:
- Uses NaCl box (libsodium) for authenticated encryption
- Nonce must be exactly 24 bytes (crypto_box_NONCEBYTES requirement)
- Payload contains the encrypted terminal or session message
- Sender identifies whether message came from desktop or client

Error codes:
- Use namespaced format: SESSION_EXPIRED, INVALID_KEY, PAIRING_FAILED, etc.
- Enables structured error handling and debugging
- Optional details dict for additional context
"""

from typing import Literal, Optional

from pydantic import Field, field_validator

from agent_remote.shared.protocol.base import (
    MESSAGE_TYPES,
    RemoteAgentMessage,
    SessionMessage,
    TimestampedMessage,
    base64_to_bytes,
    bytes_to_base64,
)


# ==============================================================================
# Error Code Constants
# ==============================================================================

# Session errors
ERROR_SESSION_EXPIRED = "SESSION_EXPIRED"
ERROR_SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
ERROR_SESSION_ALREADY_EXISTS = "SESSION_ALREADY_EXISTS"

# Pairing errors
ERROR_PAIRING_FAILED = "PAIRING_FAILED"
ERROR_PAIRING_CODE_INVALID = "PAIRING_CODE_INVALID"
ERROR_PAIRING_CODE_EXPIRED = "PAIRING_CODE_EXPIRED"

# Cryptography errors
ERROR_CRYPTO_ERROR = "CRYPTO_ERROR"
ERROR_INVALID_KEY = "INVALID_KEY"
ERROR_DECRYPTION_FAILED = "DECRYPTION_FAILED"
ERROR_INVALID_NONCE = "INVALID_NONCE"

# Protocol errors
ERROR_INVALID_MESSAGE = "INVALID_MESSAGE"
ERROR_UNSUPPORTED_MESSAGE_TYPE = "UNSUPPORTED_MESSAGE_TYPE"
ERROR_VALIDATION_FAILED = "VALIDATION_FAILED"

# Connection errors
ERROR_CONNECTION_LOST = "CONNECTION_LOST"
ERROR_TIMEOUT = "TIMEOUT"

# General errors
ERROR_INTERNAL_ERROR = "INTERNAL_ERROR"
ERROR_UNAUTHORIZED = "UNAUTHORIZED"


# ==============================================================================
# Relay Messages
# ==============================================================================


class EncryptedBlob(SessionMessage):
    """Encrypted payload for secure message transport through relay.

    This is the only message type that crosses the untrusted network. All terminal
    and session messages are encrypted and wrapped in this envelope before being
    sent through the relay service.

    The relay service cannot decrypt these messages - only the desktop and client
    endpoints have the encryption keys established during pairing.

    Encryption:
    - Uses NaCl box (libsodium crypto_box) for authenticated encryption
    - Nonce must be exactly 24 bytes (crypto_box_NONCEBYTES)
    - Each message must use a unique random nonce (never reuse nonces!)
    - Payload contains the encrypted terminal or session message

    Sender:
    - "desktop": Message originated from desktop agent
    - "client": Message originated from web client
    - Enables relay to route messages correctly without decryption

    Example:
        >>> from nacl.public import Box
        >>> # Desktop encrypting message for client
        >>> plaintext = terminal_output.to_json().encode()
        >>> nonce = nacl.utils.random(Box.NONCE_SIZE)  # 24 bytes
        >>> ciphertext = box.encrypt(plaintext, nonce).ciphertext
        >>> blob = EncryptedBlob(
        ...     session_id=session_id,
        ...     sender="desktop",
        ...     payload=ciphertext,
        ...     nonce=nonce
        ... )
    """

    type: Literal["relay.encrypted"] = "relay.encrypted"
    sender: Literal["desktop", "client"] = Field(
        ..., description="Identifies message origin (desktop or client)"
    )
    payload: str = Field(
        ..., description="Base64-encoded encrypted message (terminal or session)"
    )
    nonce: str = Field(
        ..., description="Base64-encoded 24-byte NaCl nonce for decryption"
    )

    @field_validator("nonce")
    @classmethod
    def validate_nonce_length(cls, v: str) -> str:
        """Validate nonce is exactly 24 bytes when decoded.

        NaCl crypto_box requires exactly 24-byte nonces (crypto_box_NONCEBYTES).
        This is a cryptographic requirement - shorter or longer nonces will fail.

        Args:
            v: Base64-encoded nonce string

        Returns:
            Validated nonce string

        Raises:
            ValueError: If decoded nonce is not exactly 24 bytes
        """
        try:
            nonce_bytes = base64_to_bytes(v)
        except Exception as e:
            raise ValueError(f"nonce must be valid base64: {e}")

        if len(nonce_bytes) != 24:
            raise ValueError(
                f"nonce must be exactly 24 bytes, got {len(nonce_bytes)} bytes. "
                "NaCl crypto_box requires 24-byte nonces (crypto_box_NONCEBYTES)."
            )
        return v

    def get_payload_bytes(self) -> bytes:
        """Decode payload from base64 to bytes.

        Returns:
            Raw encrypted payload bytes
        """
        return base64_to_bytes(self.payload)

    def get_nonce_bytes(self) -> bytes:
        """Decode nonce from base64 to bytes.

        Returns:
            24-byte nonce for NaCl decryption
        """
        return base64_to_bytes(self.nonce)

    @classmethod
    def create(
        cls, session_id: str, sender: Literal["desktop", "client"], payload: bytes, nonce: bytes
    ) -> "EncryptedBlob":
        """Create EncryptedBlob from raw bytes.

        Helper method to create EncryptedBlob with automatic base64 encoding
        of payload and nonce.

        Args:
            session_id: UUID identifying the session
            sender: Message origin ("desktop" or "client")
            payload: Raw encrypted message bytes
            nonce: 24-byte NaCl nonce

        Returns:
            EncryptedBlob instance with base64-encoded fields

        Raises:
            ValueError: If nonce is not exactly 24 bytes

        Example:
            >>> blob = EncryptedBlob.create(
            ...     session_id=session_id,
            ...     sender="desktop",
            ...     payload=ciphertext,
            ...     nonce=random_nonce
            ... )
        """
        return cls(
            session_id=session_id,
            sender=sender,
            payload=bytes_to_base64(payload),
            nonce=bytes_to_base64(nonce),
        )


class Ping(TimestampedMessage):
    """WebSocket keepalive ping message.

    Sent periodically to prevent WebSocket connection timeouts. The relay service
    or client should respond with a Pong message.

    The timestamp enables round-trip time (RTT) measurement:
    - Sender records timestamp when sending Ping
    - Receiver responds with Pong containing same timestamp
    - Sender calculates RTT = current_time - ping.timestamp

    Example:
        >>> ping = Ping()
        >>> # Send ping, wait for pong
        >>> rtt = time.time() - pong.timestamp
    """

    type: Literal["relay.ping"] = "relay.ping"


class Pong(TimestampedMessage):
    """WebSocket keepalive pong response.

    Sent in response to a Ping message. Should echo the timestamp from the
    original Ping to enable RTT calculation.

    Example:
        >>> def handle_ping(ping: Ping):
        ...     pong = Pong(timestamp=ping.timestamp)
        ...     send_message(pong)
    """

    type: Literal["relay.pong"] = "relay.pong"


class Error(RemoteAgentMessage):
    """Structured error message with namespaced error codes.

    Provides standardized error reporting across the relay protocol. Error codes
    use namespaced constants (ERROR_SESSION_EXPIRED, ERROR_INVALID_KEY, etc.) for
    structured handling.

    Fields:
    - code: Namespaced error code constant (e.g., "SESSION_EXPIRED")
    - message: Human-readable error description
    - details: Optional dict with additional context (stack traces, invalid values, etc.)

    Error codes are defined as constants in this module:
    - Session: ERROR_SESSION_EXPIRED, ERROR_SESSION_NOT_FOUND, etc.
    - Pairing: ERROR_PAIRING_FAILED, ERROR_PAIRING_CODE_INVALID, etc.
    - Crypto: ERROR_CRYPTO_ERROR, ERROR_INVALID_KEY, ERROR_DECRYPTION_FAILED, etc.
    - Protocol: ERROR_INVALID_MESSAGE, ERROR_UNSUPPORTED_MESSAGE_TYPE, etc.
    - Connection: ERROR_CONNECTION_LOST, ERROR_TIMEOUT
    - General: ERROR_INTERNAL_ERROR, ERROR_UNAUTHORIZED

    Example:
        >>> error = Error(
        ...     code=ERROR_SESSION_EXPIRED,
        ...     message="Session abc123 expired after 1 hour of inactivity",
        ...     details={"session_id": "abc123", "expired_at": "2025-12-04T10:00:00Z"}
        ... )
    """

    type: Literal["relay.error"] = "relay.error"
    code: str = Field(..., description="Namespaced error code (e.g., SESSION_EXPIRED)")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[dict] = Field(
        default=None, description="Optional additional context (stack traces, values, etc.)"
    )


# ==============================================================================
# Register Message Types
# ==============================================================================

MESSAGE_TYPES["relay.encrypted"] = EncryptedBlob
MESSAGE_TYPES["relay.ping"] = Ping
MESSAGE_TYPES["relay.pong"] = Pong
MESSAGE_TYPES["relay.error"] = Error
