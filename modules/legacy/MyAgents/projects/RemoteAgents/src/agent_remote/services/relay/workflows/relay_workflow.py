"""RelayWorkflow orchestrates session lifecycle and message routing.

This workflow coordinates session creation, pairing, and message routing between
desktop and client peers. It uses SessionRepository for persistence and delegates
domain logic to the Session entity.

Workflow Pattern (DDD):
- Orchestrates domain entities (Session) and repositories (SessionRepository)
- Wraps domain exceptions with workflow context for better error handling
- Coordinates cross-entity operations (session creation, message routing)
- No business logic - delegates to domain entities

Lifecycle:
1. create_session(): Desktop creates session, gets pairing code
2. handle_desktop_connect(): Desktop connects WebSocket
3. handle_client_pair(): Client pairs with code and public key
4. route_message(): Route encrypted messages between peers
5. close_session(): Clean up session on disconnect/timeout
"""

from typing import Any, Optional, Tuple

from agent_remote.services.relay.domains.session_manager.entities import (
    InvalidPairingCodeException,
    InvalidStateTransitionException,
    Session,
    SessionAlreadyPairedException,
    SessionDomainException,
    SessionExpiredException,
)
from agent_remote.services.relay.domains.session_manager.repository import (
    SessionRepository,
)
from agent_remote.services.relay.domains.session_manager.value_objects import (
    PairingCode,
    PeerRole,
    SessionId,
)
from agent_remote.shared.protocol.relay_messages import EncryptedBlob


# ==============================================================================
# Workflow Exceptions
# ==============================================================================


class RelayWorkflowException(Exception):
    """Base exception for all RelayWorkflow errors.

    Wraps domain exceptions with workflow context to provide better
    error messages and structured error handling at the service layer.
    """
    pass


class SessionNotFoundException(RelayWorkflowException):
    """Raised when a session cannot be found in the repository.

    This indicates either:
    - Session ID is invalid
    - Session was already closed and removed
    - Session expired and was cleaned up
    """

    def __init__(self, session_id: str, context: str = ""):
        self.session_id = session_id
        self.context = context
        message = f"Session '{session_id}' not found"
        if context:
            message += f": {context}"
        super().__init__(message)


class PairingCodeNotFoundException(RelayWorkflowException):
    """Raised when a pairing code cannot be found in the repository.

    This indicates either:
    - Pairing code is invalid
    - Session with that code was already closed
    - Session expired and was cleaned up
    """

    def __init__(self, pairing_code: str):
        self.pairing_code = pairing_code
        super().__init__(
            f"No session found with pairing code '{pairing_code}'. "
            "Code may be invalid or session may have expired."
        )


class PeerNotConnectedException(RelayWorkflowException):
    """Raised when attempting to send message to disconnected peer.

    This indicates the recipient peer's WebSocket is not connected,
    preventing message delivery.
    """

    def __init__(self, session_id: str, peer_role: PeerRole):
        self.session_id = session_id
        self.peer_role = peer_role
        super().__init__(
            f"Cannot route message: {peer_role.value} peer is not connected "
            f"in session '{session_id}'"
        )


class SessionWorkflowException(RelayWorkflowException):
    """Wraps domain exceptions with workflow context.

    Provides additional context about what workflow operation was being
    performed when the domain exception occurred.
    """

    def __init__(self, operation: str, session_id: str, cause: SessionDomainException):
        self.operation = operation
        self.session_id = session_id
        self.cause = cause
        super().__init__(
            f"Failed to {operation} for session '{session_id}': {str(cause)}"
        )


# ==============================================================================
# RelayWorkflow
# ==============================================================================


class RelayWorkflow:
    """Orchestrates relay session lifecycle and message routing.

    This workflow coordinates the complete lifecycle of relay sessions:
    1. Session creation with pairing code generation
    2. Desktop and client connection management
    3. Message routing between connected peers
    4. Session cleanup on disconnect or expiry

    The workflow is stateless - all state is managed by the SessionRepository.
    Domain logic is delegated to the Session entity.

    Dependencies:
    - SessionRepository: Persistence layer for sessions (injected)

    Example:
        >>> repository = InMemorySessionRepository()
        >>> workflow = RelayWorkflow(repository)
        >>>
        >>> # Desktop creates session
        >>> session_id, pairing_code = workflow.create_session(desktop_key)
        >>>
        >>> # Desktop connects
        >>> workflow.handle_desktop_connect(session_id, desktop_ws)
        >>>
        >>> # Client pairs
        >>> client_session_id = workflow.handle_client_pair(
        ...     pairing_code, client_key, client_ws
        ... )
        >>>
        >>> # Route messages
        >>> workflow.route_message(session_id, PeerRole.DESKTOP, encrypted_blob)
    """

    def __init__(self, repository: SessionRepository):
        """Initialize RelayWorkflow with repository.

        Args:
            repository: SessionRepository implementation for persistence
        """
        self._repository = repository

    def create_session(self, desktop_public_key: str) -> Tuple[SessionId, PairingCode]:
        """Create a new relay session for desktop.

        Creates a new session with generated session ID and pairing code.
        The session is stored in the repository in CREATED state.

        Args:
            desktop_public_key: Desktop's public key for E2E encryption

        Returns:
            Tuple of (session_id, pairing_code) for desktop to use

        Raises:
            ValueError: If session already exists (unlikely due to UUID collision)

        Example:
            >>> session_id, pairing_code = workflow.create_session(
            ...     desktop_public_key="base64_encoded_key..."
            ... )
            >>> print(f"Pairing code: {pairing_code}")
            >>> print(f"Session ID: {session_id}")
        """
        # Create session entity using factory method
        session = Session.create(desktop_public_key=desktop_public_key)

        # Store in repository
        self._repository.add(session)

        # Return session ID and pairing code for response
        return session.session_id, session.pairing_code

    def handle_desktop_connect(
        self, session_id: SessionId, ws_connection: Any
    ) -> None:
        """Connect desktop's WebSocket to session.

        Retrieves the session and connects the desktop's WebSocket,
        transitioning the session to DESKTOP_CONNECTED state.

        Args:
            session_id: Unique session identifier
            ws_connection: Desktop's WebSocket connection (opaque)

        Raises:
            SessionNotFoundException: If session not found in repository
            SessionWorkflowException: If session state transition fails

        Example:
            >>> workflow.handle_desktop_connect(
            ...     session_id=SessionId("123e4567-..."),
            ...     ws_connection=desktop_websocket
            ... )
        """
        # Retrieve session from repository
        session = self._repository.get_by_id(session_id)
        if session is None:
            raise SessionNotFoundException(
                session_id=str(session_id),
                context="Desktop attempted to connect to non-existent session"
            )

        # Connect desktop WebSocket (delegates to domain entity)
        try:
            session.connect_desktop(ws_connection)
        except SessionDomainException as e:
            raise SessionWorkflowException(
                operation="connect desktop",
                session_id=str(session_id),
                cause=e
            )

        # Note: Repository update not needed for in-memory implementation
        # as session is mutable object. For persistent repositories,
        # add: self._repository.update(session)

    def handle_client_pair(
        self, pairing_code: PairingCode, client_public_key: str, ws_connection: Any
    ) -> Tuple[SessionId, str, Any]:
        """Pair client with session using pairing code.

        Retrieves session by pairing code, validates expiry, and pairs
        the client with the session. Transitions to PAIRED state.

        Args:
            pairing_code: 6-char pairing code from user input
            client_public_key: Client's public key for E2E encryption
            ws_connection: Client's WebSocket connection (opaque)

        Returns:
            Tuple of (session_id, desktop_public_key, desktop_ws) for sending SessionPaired

        Raises:
            PairingCodeNotFoundException: If pairing code not found
            SessionWorkflowException: If pairing fails (expired, invalid state, etc.)

        Example:
            >>> session_id, desktop_key, desktop_ws = workflow.handle_client_pair(
            ...     pairing_code=PairingCode("ABC123"),
            ...     client_public_key="base64_encoded_key...",
            ...     ws_connection=client_websocket
            ... )
        """
        # Retrieve session by pairing code
        session = self._repository.get_by_pairing_code(pairing_code)
        if session is None:
            raise PairingCodeNotFoundException(pairing_code=str(pairing_code))

        # Store desktop_ws before pairing (needed for sending SessionPaired)
        desktop_public_key = session.desktop_public_key
        desktop_ws = session.desktop_ws

        # Validate not expired and pair client (delegates to domain entity)
        try:
            session.pair_client(
                pairing_code=str(pairing_code),
                client_public_key=client_public_key,
                ws_connection=ws_connection
            )
        except SessionExpiredException as e:
            # Re-raise with more context
            raise SessionWorkflowException(
                operation="pair client",
                session_id=str(session.session_id),
                cause=e
            )
        except SessionDomainException as e:
            raise SessionWorkflowException(
                operation="pair client",
                session_id=str(session.session_id),
                cause=e
            )

        # Note: Repository update not needed for in-memory implementation
        # For persistent repositories, add: self._repository.update(session)

        # Return session ID, desktop public key, and desktop WebSocket for sending SessionPaired
        return session.session_id, desktop_public_key, desktop_ws

    async def route_message(
        self, session_id: SessionId, sender: PeerRole, message: EncryptedBlob
    ) -> None:
        """Route encrypted message from sender to recipient peer.

        Validates sender is connected, determines recipient, and sends
        the encrypted message to the recipient's WebSocket.

        Message routing:
        - sender=DESKTOP -> recipient=CLIENT
        - sender=CLIENT -> recipient=DESKTOP

        Args:
            session_id: Unique session identifier
            sender: Role of the peer sending the message (DESKTOP or CLIENT)
            message: Encrypted message to route

        Raises:
            SessionNotFoundException: If session not found
            PeerNotConnectedException: If sender or recipient not connected

        Example:
            >>> await workflow.route_message(
            ...     session_id=SessionId("123e4567-..."),
            ...     sender=PeerRole.DESKTOP,
            ...     message=encrypted_blob
            ... )
        """
        # Retrieve session
        session = self._repository.get_by_id(session_id)
        if session is None:
            raise SessionNotFoundException(
                session_id=str(session_id),
                context="Attempted to route message through non-existent session"
            )

        # Validate sender is connected and get sender/recipient WebSockets
        if sender == PeerRole.DESKTOP:
            sender_ws = session.desktop_ws
            recipient_ws = session.client_ws
            recipient_role = PeerRole.CLIENT
        else:  # sender == PeerRole.CLIENT
            sender_ws = session.client_ws
            recipient_ws = session.desktop_ws
            recipient_role = PeerRole.DESKTOP

        # Validate sender has WebSocket connection
        if sender_ws is None:
            raise PeerNotConnectedException(
                session_id=str(session_id),
                peer_role=sender
            )

        # Validate recipient has WebSocket connection
        if recipient_ws is None:
            raise PeerNotConnectedException(
                session_id=str(session_id),
                peer_role=recipient_role
            )

        # Send message to recipient WebSocket (async)
        # FastAPI WebSocket send_json is an async method
        try:
            await recipient_ws.send_json(message.model_dump())
        except AttributeError:
            # Fallback for different WebSocket implementations
            await recipient_ws.send(message.to_json())

    def close_session(self, session_id: SessionId, reason: str) -> None:
        """Close session and remove from repository.

        Closes the session (clearing WebSocket references) and removes
        it from the repository. This is idempotent - closing a non-existent
        session is not an error.

        Args:
            session_id: Unique session identifier
            reason: Human-readable reason for closure

        Example:
            >>> workflow.close_session(
            ...     session_id=SessionId("123e4567-..."),
            ...     reason="Client disconnected"
            ... )
        """
        # Retrieve session (optional - idempotent operation)
        session = self._repository.get_by_id(session_id)

        # If session exists, close it
        if session is not None:
            session.close(reason)

        # Remove from repository (idempotent per repository contract)
        self._repository.remove(session_id)
