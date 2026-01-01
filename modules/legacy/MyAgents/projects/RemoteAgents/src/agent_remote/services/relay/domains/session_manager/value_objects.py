"""Value objects for SessionManager domain.

This module defines immutable value objects that represent core domain concepts:
- SessionId: UUID wrapper with validation
- PairingCode: 6-char alphanumeric code with expiry tracking
- PeerRole: Enum for desktop/client roles
- SessionState: Enum for session lifecycle states

Value objects are immutable and validated, ensuring domain integrity.
"""

import os
import time
from enum import Enum
from typing import Optional
from uuid import UUID


class PeerRole(str, Enum):
    """Role of a peer in a relay session.

    - DESKTOP: The desktop application that creates the session
    - CLIENT: The web client that connects using a pairing code
    """
    DESKTOP = "desktop"
    CLIENT = "client"


class SessionState(str, Enum):
    """State of a relay session in its lifecycle.

    Valid state transitions:
    - CREATED -> DESKTOP_CONNECTED (when desktop connects)
    - DESKTOP_CONNECTED -> PAIRED (when client connects with valid code)
    - Any state -> CLOSED (when session ends)
    """
    CREATED = "created"
    DESKTOP_CONNECTED = "desktop_connected"
    PAIRED = "paired"
    CLOSED = "closed"


class SessionId:
    """Immutable value object representing a session identifier.

    Wraps a UUID with validation to ensure only valid session IDs are used.
    """

    def __init__(self, value: str):
        """Initialize SessionId with validation.

        Args:
            value: UUID string

        Raises:
            ValueError: If value is not a valid UUID
        """
        try:
            self._uuid = UUID(value)
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid session ID format: {e}")
        self._value = str(self._uuid)

    @property
    def value(self) -> str:
        """Get the string representation of the session ID."""
        return self._value

    def __str__(self) -> str:
        """String representation."""
        return self._value

    def __repr__(self) -> str:
        """Developer representation."""
        return f"SessionId('{self._value}')"

    def __eq__(self, other) -> bool:
        """Equality comparison."""
        if isinstance(other, SessionId):
            return self._value == other._value
        return False

    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash(self._value)


class PairingCode:
    """Immutable value object representing a pairing code with expiry.

    Pairing codes are 6-character uppercase alphanumeric strings that expire
    after a configurable duration (default 5 minutes). Used to securely connect
    clients to desktop sessions.

    Format: 6 characters, A-Z and 0-9 only (e.g., "ABC123")

    Configuration:
    - PAIRING_CODE_EXPIRY_SECONDS environment variable controls expiry time
    - Defaults to 300 seconds (5 minutes) if not set
    """

    # Pairing code expiry duration in seconds (configurable via environment variable)
    EXPIRY_DURATION = int(os.environ.get("PAIRING_CODE_EXPIRY_SECONDS", "300"))

    def __init__(self, code: str, created_at: Optional[float] = None):
        """Initialize PairingCode with validation.

        Args:
            code: 6-character uppercase alphanumeric string
            created_at: Unix timestamp when code was created (defaults to now)

        Raises:
            ValueError: If code format is invalid
        """
        # Validate code format
        if not isinstance(code, str):
            raise ValueError("Pairing code must be a string")

        if len(code) != 6:
            raise ValueError("Pairing code must be exactly 6 characters")

        if not code.isalnum():
            raise ValueError("Pairing code must be alphanumeric (A-Z, 0-9)")

        # Check for lowercase letters (isupper() returns False for digit-only strings)
        if code.lower() != code.upper() and not code.isupper():
            raise ValueError("Pairing code must be uppercase")

        self._code = code
        self._created_at = created_at if created_at is not None else time.time()
        self._expires_at = self._created_at + self.EXPIRY_DURATION

    @property
    def code(self) -> str:
        """Get the pairing code string."""
        return self._code

    @property
    def created_at(self) -> float:
        """Get the creation timestamp."""
        return self._created_at

    @property
    def expires_at(self) -> float:
        """Get the expiry timestamp."""
        return self._expires_at

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Check if the pairing code has expired.

        Args:
            current_time: Optional current timestamp (defaults to now)

        Returns:
            True if expired, False otherwise
        """
        check_time = current_time if current_time is not None else time.time()
        return check_time >= self._expires_at

    def __str__(self) -> str:
        """String representation."""
        return self._code

    def __repr__(self) -> str:
        """Developer representation."""
        return f"PairingCode('{self._code}', expires_at={self._expires_at})"

    def __eq__(self, other) -> bool:
        """Equality comparison (compares code only, not timestamps)."""
        if isinstance(other, PairingCode):
            return self._code == other._code
        return False

    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash(self._code)
