"""Session entity and domain exceptions for SessionManager.

This module defines the core Session entity that models the lifecycle of a relay session:
1. Desktop creates session (CREATED state)
2. Desktop connects with WebSocket (DESKTOP_CONNECTED state)
3. Client pairs with code (PAIRED state)
4. Session closes (CLOSED state)

Domain exceptions provide clear error cases for business rule violations.
All logic is pure domain logic with no infrastructure dependencies.
"""

import time
from typing import Any, Optional

from agent_remote.shared.protocol.base import generate_pairing_code, generate_session_id

from .value_objects import PairingCode, PeerRole, SessionId, SessionState


# ==============================================================================
# Domain Exceptions
# ==============================================================================


class SessionDomainException(Exception):
    """Base exception for all SessionManager domain errors."""
    pass


class SessionExpiredException(SessionDomainException):
    """Raised when attempting to use an expired pairing code."""

    def __init__(self, session_id: str, pairing_code: str):
        self.session_id = session_id
        self.pairing_code = pairing_code
        super().__init__(
            f"Pairing code '{pairing_code}' for session '{session_id}' has expired"
        )


class InvalidPairingCodeException(SessionDomainException):
    """Raised when pairing code does not match session's code."""

    def __init__(self, session_id: str, expected: str, provided: str):
        self.session_id = session_id
        self.expected = expected
        self.provided = provided
        super().__init__(
            f"Invalid pairing code for session '{session_id}': "
            f"expected '{expected}', got '{provided}'"
        )


class SessionAlreadyPairedException(SessionDomainException):
    """Raised when client attempts to pair with an already-paired session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(
            f"Session '{session_id}' is already paired with a client"
        )


class InvalidStateTransitionException(SessionDomainException):
    """Raised when attempting an invalid state transition."""

    def __init__(self, session_id: str, current_state: SessionState, action: str):
        self.session_id = session_id
        self.current_state = current_state
        self.action = action
        super().__init__(
            f"Cannot {action} in state {current_state.value} "
            f"for session '{session_id}'"
        )


# ==============================================================================
# Session Entity
# ==============================================================================


class Session:
    """Domain entity representing a relay session.

    A Session models the complete lifecycle of a desktop-client connection:
    - Desktop creates session with public key
    - Session generates pairing code (expires in 5 minutes)
    - Desktop connects WebSocket (transitions to DESKTOP_CONNECTED)
    - Client pairs with pairing code and public key (transitions to PAIRED)
    - Session closes when either peer disconnects or timeout occurs

    Properties:
        session_id: Unique session identifier (UUID)
        pairing_code: 6-char code for client pairing (expires after 5 min)
        desktop_public_key: Desktop's public key for E2E encryption
        client_public_key: Client's public key (set during pairing)
        desktop_ws: Desktop's WebSocket connection (opaque reference)
        client_ws: Client's WebSocket connection (opaque reference)
        state: Current session state in lifecycle
        created_at: Unix timestamp when session was created
        expires_at: Unix timestamp when pairing code expires

    Note: WebSocket references (desktop_ws, client_ws) are stored as opaque
    Any types to avoid infrastructure dependencies in the domain layer.
    The relay service manages the actual WebSocket connections.
    """

    def __init__(
        self,
        session_id: SessionId,
        pairing_code: PairingCode,
        desktop_public_key: str,
        state: SessionState = SessionState.CREATED,
        created_at: Optional[float] = None,
        client_public_key: Optional[str] = None,
        desktop_ws: Optional[Any] = None,
        client_ws: Optional[Any] = None,
    ):
        """Initialize Session entity.

        Args:
            session_id: Unique session identifier
            pairing_code: Pairing code for client connection
            desktop_public_key: Desktop's public key
            state: Initial state (defaults to CREATED)
            created_at: Creation timestamp (defaults to now)
            client_public_key: Client's public key (set during pairing)
            desktop_ws: Desktop WebSocket connection (opaque)
            client_ws: Client WebSocket connection (opaque)
        """
        self._session_id = session_id
        self._pairing_code = pairing_code
        self._desktop_public_key = desktop_public_key
        self._client_public_key = client_public_key
        self._desktop_ws = desktop_ws
        self._client_ws = client_ws
        self._state = state
        self._created_at = created_at if created_at is not None else time.time()
        self._expires_at = pairing_code.expires_at
        self._close_reason: Optional[str] = None

    # Properties
    @property
    def session_id(self) -> SessionId:
        """Get session ID."""
        return self._session_id

    @property
    def pairing_code(self) -> PairingCode:
        """Get pairing code."""
        return self._pairing_code

    @property
    def desktop_public_key(self) -> str:
        """Get desktop's public key."""
        return self._desktop_public_key

    @property
    def client_public_key(self) -> Optional[str]:
        """Get client's public key (None until paired)."""
        return self._client_public_key

    @property
    def desktop_ws(self) -> Optional[Any]:
        """Get desktop WebSocket connection (opaque)."""
        return self._desktop_ws

    @property
    def client_ws(self) -> Optional[Any]:
        """Get client WebSocket connection (opaque)."""
        return self._client_ws

    @property
    def state(self) -> SessionState:
        """Get current session state."""
        return self._state

    @property
    def created_at(self) -> float:
        """Get creation timestamp."""
        return self._created_at

    @property
    def expires_at(self) -> float:
        """Get pairing code expiry timestamp."""
        return self._expires_at

    @property
    def close_reason(self) -> Optional[str]:
        """Get reason for session closure (None if not closed)."""
        return self._close_reason

    # Factory method
    @classmethod
    def create(cls, desktop_public_key: str) -> "Session":
        """Create a new session with generated ID and pairing code.

        This is the primary factory method for creating sessions. It generates
        a unique session ID and pairing code, initializing the session in
        CREATED state.

        Args:
            desktop_public_key: Desktop's public key for E2E encryption

        Returns:
            New Session instance in CREATED state

        Example:
            session = Session.create(desktop_public_key="...pubkey...")
            print(session.pairing_code)  # "ABC123"
            print(session.state)  # SessionState.CREATED
        """
        session_id = SessionId(generate_session_id())
        pairing_code = PairingCode(generate_pairing_code())

        return cls(
            session_id=session_id,
            pairing_code=pairing_code,
            desktop_public_key=desktop_public_key,
            state=SessionState.CREATED,
        )

    # Domain methods
    def connect_desktop(self, ws_connection: Any) -> None:
        """Connect desktop's WebSocket and transition to DESKTOP_CONNECTED state.

        Args:
            ws_connection: Desktop's WebSocket connection (opaque)

        Raises:
            InvalidStateTransitionException: If not in CREATED state
        """
        if self._state != SessionState.CREATED:
            raise InvalidStateTransitionException(
                session_id=str(self._session_id),
                current_state=self._state,
                action="connect desktop",
            )

        self._desktop_ws = ws_connection
        self._state = SessionState.DESKTOP_CONNECTED

    def pair_client(self, pairing_code: str, client_public_key: str, ws_connection: Any) -> None:
        """Pair client with session using pairing code.

        Validates pairing code and expiry, then stores client's public key
        and WebSocket connection. Transitions to PAIRED state.

        Args:
            pairing_code: 6-char pairing code from user
            client_public_key: Client's public key for E2E encryption
            ws_connection: Client's WebSocket connection (opaque)

        Raises:
            InvalidStateTransitionException: If not in DESKTOP_CONNECTED state
            SessionExpiredException: If pairing code has expired
            InvalidPairingCodeException: If pairing code doesn't match
            SessionAlreadyPairedException: If session is already paired
        """
        # Check state
        if self._state == SessionState.PAIRED:
            raise SessionAlreadyPairedException(session_id=str(self._session_id))

        if self._state != SessionState.DESKTOP_CONNECTED:
            raise InvalidStateTransitionException(
                session_id=str(self._session_id),
                current_state=self._state,
                action="pair client",
            )

        # Check expiry
        if self._pairing_code.is_expired():
            raise SessionExpiredException(
                session_id=str(self._session_id),
                pairing_code=str(self._pairing_code),
            )

        # Validate pairing code
        if pairing_code != str(self._pairing_code):
            raise InvalidPairingCodeException(
                session_id=str(self._session_id),
                expected=str(self._pairing_code),
                provided=pairing_code,
            )

        # Pair client
        self._client_public_key = client_public_key
        self._client_ws = ws_connection
        self._state = SessionState.PAIRED

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Check if the session's pairing code has expired.

        Args:
            current_time: Optional current timestamp (defaults to now)

        Returns:
            True if pairing code expired, False otherwise
        """
        return self._pairing_code.is_expired(current_time)

    def close(self, reason: str) -> None:
        """Close the session and clear WebSocket references.

        Transitions to CLOSED state and clears all WebSocket connections.
        Can be called from any state.

        Args:
            reason: Human-readable reason for closure
        """
        self._state = SessionState.CLOSED
        self._close_reason = reason
        self._desktop_ws = None
        self._client_ws = None

    def __repr__(self) -> str:
        """Developer representation."""
        return (
            f"Session("
            f"session_id={self._session_id!r}, "
            f"state={self._state.value}, "
            f"pairing_code={self._pairing_code!r}, "
            f"desktop_connected={self._desktop_ws is not None}, "
            f"client_connected={self._client_ws is not None}"
            f")"
        )
