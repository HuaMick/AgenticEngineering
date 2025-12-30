"""WebSocket endpoints for real-time message routing between desktop and client.

This module provides WebSocket endpoints for the relay service:
- GET /ws/desktop/{session_id}: Desktop CLI connects with session ID
- GET /ws/client/{pairing_code}: Web client connects with pairing code

Message flow:
1. Desktop creates session via REST API and gets session_id + pairing_code
2. Desktop connects to /ws/desktop/{session_id}
3. Client connects to /ws/client/{pairing_code} with first message containing client_public_key
4. Messages route bidirectionally as EncryptedBlob through RelayWorkflow
5. Disconnects trigger session cleanup

Error handling:
- Invalid session_id/pairing_code returns Error message before closing
- WebSocketDisconnect triggers workflow.close_session()
- Validation failures send Error via websocket_manager.close()
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from agent_remote.services.relay.domains.session_manager.value_objects import (
    PairingCode,
    PeerRole,
    SessionId,
)
from agent_remote.services.relay.infrastructure.websocket_manager import (
    WebSocketManager,
)
from agent_remote.services.relay.workflows.relay_workflow import (
    PairingCodeNotFoundException,
    RelayWorkflow,
    SessionNotFoundException,
    SessionWorkflowException,
)
from agent_remote.shared.protocol.base import bytes_to_base64, base64_to_bytes
from agent_remote.shared.protocol.relay_messages import (
    ERROR_INVALID_MESSAGE,
    ERROR_PAIRING_CODE_INVALID,
    ERROR_SESSION_NOT_FOUND,
    ERROR_VALIDATION_FAILED,
    EncryptedBlob,
    Error,
)
from agent_remote.shared.protocol.session_messages import SessionPair, SessionPaired

# Import shared repository from api.py to ensure single instance
from agent_remote.services.relay.api.api import get_repository

logger = logging.getLogger(__name__)


# ==============================================================================
# Dependency Injection
# ==============================================================================

# Singleton instance for WebSocketManager (repository is shared via get_repository import above)
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create the singleton WebSocketManager instance.

    Returns:
        WebSocketManager instance for WebSocket lifecycle management
    """
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager


def get_workflow() -> RelayWorkflow:
    """Create RelayWorkflow instance with injected repository.

    Returns:
        RelayWorkflow instance for orchestrating session operations

    Note:
        Uses get_repository() from api module to ensure the same repository
        instance is shared between REST API and WebSocket endpoints.
    """
    return RelayWorkflow(repository=get_repository())


# ==============================================================================
# WebSocket Router
# ==============================================================================

router = APIRouter()


# ==============================================================================
# Desktop WebSocket Endpoint
# ==============================================================================


@router.websocket("/ws/desktop/{session_id}")
async def desktop_websocket(
    websocket: WebSocket,
    session_id: str,
    workflow: RelayWorkflow = Depends(get_workflow),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
):
    """WebSocket endpoint for desktop CLI connection.

    Desktop flow:
    1. Desktop creates session via REST API, receives session_id and pairing_code
    2. Desktop connects to this endpoint with session_id
    3. WebSocket is registered with session via workflow.handle_desktop_connect()
    4. Desktop enters message loop, routing EncryptedBlob messages to client
    5. On disconnect, workflow.close_session() is called to clean up

    Args:
        websocket: FastAPI WebSocket connection
        session_id: UUID identifying the session (from URL path)
        workflow: RelayWorkflow instance (injected)
        websocket_manager: WebSocketManager instance (injected)

    Message protocol:
        - Receives: EncryptedBlob messages from desktop
        - Sends: EncryptedBlob messages from client (via workflow routing)
        - Sends: Error messages on validation/routing failures
    """
    # Validate session_id format before accepting WebSocket
    try:
        session_id_obj = SessionId(session_id)
    except ValueError as e:
        logger.warning(f"Invalid session ID format: {session_id} - {e}")
        await websocket_manager.accept(websocket)
        await websocket_manager.close(
            websocket,
            reason=f"Invalid session ID format: {str(e)}",
            code=ERROR_VALIDATION_FAILED,
        )
        return

    # Accept WebSocket connection
    try:
        await websocket_manager.accept(websocket)
        logger.info(f"Desktop WebSocket accepted for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to accept desktop WebSocket: {e}")
        return

    # Connect desktop to session via workflow
    try:
        workflow.handle_desktop_connect(session_id_obj, websocket)
        logger.info(f"Desktop connected to session {session_id}")
    except SessionNotFoundException as e:
        logger.warning(f"Session not found for desktop connection: {e}")
        await websocket_manager.close(
            websocket,
            reason=str(e),
            code=ERROR_SESSION_NOT_FOUND,
        )
        return
    except SessionWorkflowException as e:
        logger.error(f"Failed to connect desktop to session: {e}")
        await websocket_manager.close(
            websocket,
            reason=str(e),
            code=ERROR_VALIDATION_FAILED,
        )
        return

    # Start keepalive background task
    keepalive_task = websocket_manager.start_keepalive(websocket)

    try:
        # Message routing loop
        while True:
            # Receive message from desktop
            try:
                message = await websocket_manager.receive_message(websocket)
                logger.debug(f"Desktop message received: type={message.type}")
            except WebSocketDisconnect:
                logger.info(f"Desktop WebSocket disconnected for session {session_id}")
                break
            except Exception as e:
                logger.error(f"Error receiving desktop message: {e}")
                await websocket_manager.close(
                    websocket,
                    reason=f"Failed to receive message: {str(e)}",
                    code=ERROR_INVALID_MESSAGE,
                )
                break

            # Validate message is EncryptedBlob
            if not isinstance(message, EncryptedBlob):
                logger.warning(
                    f"Desktop sent non-EncryptedBlob message: type={message.type}"
                )
                await websocket_manager.close(
                    websocket,
                    reason=f"Expected EncryptedBlob, got {message.type}",
                    code=ERROR_INVALID_MESSAGE,
                )
                break

            # Route message to client via workflow
            try:
                await workflow.route_message(
                    session_id=session_id_obj,
                    sender=PeerRole.DESKTOP,
                    message=message,
                )
                logger.debug(f"Message routed from desktop to client in session {session_id}")
            except Exception as e:
                logger.error(f"Failed to route desktop message: {e}")
                # Don't close connection on routing failures - client might not be connected yet
                # Send error back to desktop
                try:
                    error_msg = Error(
                        code=ERROR_INVALID_MESSAGE,
                        message=f"Failed to route message: {str(e)}",
                    )
                    await websocket_manager.send_message(websocket, error_msg)
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
                    break

    except Exception as e:
        logger.error(f"Unexpected error in desktop WebSocket loop: {e}")
    finally:
        # Cancel keepalive task
        keepalive_task.cancel()

        # Close session and clean up
        try:
            workflow.close_session(session_id_obj, "desktop_disconnect")
            logger.info(f"Session {session_id} closed due to desktop disconnect")
        except Exception as e:
            logger.error(f"Error closing session on desktop disconnect: {e}")


# ==============================================================================
# Client WebSocket Endpoint
# ==============================================================================


@router.websocket("/ws/client/{pairing_code}")
async def client_websocket(
    websocket: WebSocket,
    pairing_code: str,
    workflow: RelayWorkflow = Depends(get_workflow),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
):
    """WebSocket endpoint for web client connection.

    Client flow:
    1. User enters pairing_code in web client
    2. Client connects to this endpoint with pairing_code
    3. Client sends first message as SessionPair containing client_public_key
    4. workflow.handle_client_pair() pairs client and returns session_id
    5. Client enters message loop, routing EncryptedBlob messages to desktop
    6. On disconnect, workflow.close_session() is called to clean up

    Args:
        websocket: FastAPI WebSocket connection
        pairing_code: 6-character alphanumeric code (from URL path)
        workflow: RelayWorkflow instance (injected)
        websocket_manager: WebSocketManager instance (injected)

    Message protocol:
        - Receives: First message must be SessionPair with client_public_key
        - Receives: Subsequent messages must be EncryptedBlob messages from client
        - Sends: EncryptedBlob messages from desktop (via workflow routing)
        - Sends: Error messages on validation/routing failures
    """
    # Validate pairing_code format before accepting WebSocket
    try:
        pairing_code_obj = PairingCode(pairing_code)
    except ValueError as e:
        logger.warning(f"Invalid pairing code format: {pairing_code} - {e}")
        await websocket_manager.accept(websocket)
        await websocket_manager.close(
            websocket,
            reason=f"Invalid pairing code format: {str(e)}",
            code=ERROR_PAIRING_CODE_INVALID,
        )
        return

    # Accept WebSocket connection
    try:
        await websocket_manager.accept(websocket)
        logger.info(f"Client WebSocket accepted for pairing code {pairing_code}")
    except Exception as e:
        logger.error(f"Failed to accept client WebSocket: {e}")
        return

    # Receive first message containing client_public_key (SessionPair message)
    session_id_obj: Optional[SessionId] = None
    try:
        first_message = await websocket_manager.receive_message(websocket)
        logger.debug(f"Client first message received: type={first_message.type}")

        # Validate message is SessionPair
        if not isinstance(first_message, SessionPair):
            raise ValueError(
                f"First message must be SessionPair, got {first_message.type}"
            )

        # Extract client_public_key from SessionPair message
        # Convert bytes to base64 string for workflow
        client_public_key = bytes_to_base64(first_message.client_public_key)
        logger.info(f"Client public key received: {client_public_key[:20]}...")

    except WebSocketDisconnect:
        logger.info(f"Client WebSocket disconnected before pairing for code {pairing_code}")
        return
    except Exception as e:
        logger.error(f"Error receiving client SessionPair message: {e}")
        await websocket_manager.close(
            websocket,
            reason=f"Failed to receive SessionPair message: {str(e)}",
            code=ERROR_INVALID_MESSAGE,
        )
        return

    # Pair client with session via workflow
    desktop_ws = None
    try:
        session_id_obj, desktop_public_key, desktop_ws = workflow.handle_client_pair(
            pairing_code=pairing_code_obj,
            client_public_key=client_public_key,
            ws_connection=websocket,
        )
        logger.info(f"Client paired with session {session_id_obj} using code {pairing_code}")
    except PairingCodeNotFoundException as e:
        logger.warning(f"Pairing code not found: {e}")
        await websocket_manager.close(
            websocket,
            reason=str(e),
            code=ERROR_PAIRING_CODE_INVALID,
        )
        return
    except SessionWorkflowException as e:
        logger.error(f"Failed to pair client: {e}")
        await websocket_manager.close(
            websocket,
            reason=str(e),
            code=ERROR_VALIDATION_FAILED,
        )
        return

    # Send SessionPaired message to both client and desktop
    # This confirms pairing and provides the public keys for E2E encryption
    try:
        # Convert desktop_public_key from base64 string to bytes for SessionPaired
        desktop_key_bytes = base64_to_bytes(desktop_public_key)

        # Client receives desktop's public key so it can establish E2E encryption
        client_session_paired_msg = SessionPaired(
            session_id=str(session_id_obj),
            desktop_public_key=desktop_key_bytes,
        )

        # Send to client (the current websocket)
        await websocket_manager.send_message(websocket, client_session_paired_msg)
        logger.info(f"Sent SessionPaired to client for session {session_id_obj}")

        # Send to desktop if connected
        # Desktop receives client's public key so it knows who paired
        if desktop_ws is not None:
            # Convert client_public_key from base64 string to bytes
            client_key_bytes = base64_to_bytes(client_public_key)
            desktop_session_paired_msg = SessionPaired(
                session_id=str(session_id_obj),
                desktop_public_key=desktop_key_bytes,
                client_public_key=client_key_bytes,
            )
            await desktop_ws.send_json(desktop_session_paired_msg.model_dump())
            logger.info(f"Sent SessionPaired to desktop for session {session_id_obj}")
        else:
            logger.warning(f"Desktop not connected when pairing session {session_id_obj}")
    except Exception as e:
        logger.error(f"Failed to send SessionPaired messages: {e}")
        # Continue anyway - the session is paired, just notification failed

    # Start keepalive background task
    keepalive_task = websocket_manager.start_keepalive(websocket)

    try:
        # Message routing loop
        while True:
            # Receive message from client
            try:
                message = await websocket_manager.receive_message(websocket)
                logger.debug(f"Client message received: type={message.type}")
            except WebSocketDisconnect:
                logger.info(f"Client WebSocket disconnected for session {session_id_obj}")
                break
            except Exception as e:
                logger.error(f"Error receiving client message: {e}")
                await websocket_manager.close(
                    websocket,
                    reason=f"Failed to receive message: {str(e)}",
                    code=ERROR_INVALID_MESSAGE,
                )
                break

            # Validate message is EncryptedBlob
            if not isinstance(message, EncryptedBlob):
                logger.warning(
                    f"Client sent non-EncryptedBlob message: type={message.type}"
                )
                await websocket_manager.close(
                    websocket,
                    reason=f"Expected EncryptedBlob, got {message.type}",
                    code=ERROR_INVALID_MESSAGE,
                )
                break

            # Route message to desktop via workflow
            try:
                await workflow.route_message(
                    session_id=session_id_obj,
                    sender=PeerRole.CLIENT,
                    message=message,
                )
                logger.debug(
                    f"Message routed from client to desktop in session {session_id_obj}"
                )
            except Exception as e:
                logger.error(f"Failed to route client message: {e}")
                # Don't close connection on routing failures - desktop might be disconnected
                # Send error back to client
                try:
                    error_msg = Error(
                        code=ERROR_INVALID_MESSAGE,
                        message=f"Failed to route message: {str(e)}",
                    )
                    await websocket_manager.send_message(websocket, error_msg)
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
                    break

    except Exception as e:
        logger.error(f"Unexpected error in client WebSocket loop: {e}")
    finally:
        # Cancel keepalive task
        keepalive_task.cancel()

        # Close session and clean up (if session was paired)
        if session_id_obj is not None:
            try:
                workflow.close_session(session_id_obj, "client_disconnect")
                logger.info(f"Session {session_id_obj} closed due to client disconnect")
            except Exception as e:
                logger.error(f"Error closing session on client disconnect: {e}")


# ==============================================================================
# Export router
# ==============================================================================

__all__ = ["router"]
