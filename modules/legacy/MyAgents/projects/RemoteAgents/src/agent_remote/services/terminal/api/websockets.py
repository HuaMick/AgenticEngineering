"""WebSocket endpoint for terminal PTY sessions.

This module provides the WebSocket endpoint for the terminal service:
- GET /ws/terminal/{session_id}: Connect to a PTY session for terminal I/O

Message flow:
1. Client connects to /ws/terminal/{session_id}
2. Server creates PTY session via TerminalWorkflow
3. Bidirectional message routing:
   - Client -> Server: TerminalInput (keystrokes) and TerminalResize (window size)
   - Server -> Client: TerminalOutput (PTY output)
4. Either side can send TerminalClose to terminate
5. WebSocket disconnect triggers PTY cleanup

Error handling:
- Invalid session_id returns Error message before closing
- WebSocketDisconnect triggers workflow.stop_session()
- PTY process exit triggers TerminalClose to client
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from agent_remote.services.terminal.domains.pty_manager import TerminalDimensions
from agent_remote.services.terminal.infrastructure.in_memory_repository import (
    InMemoryPTYRepository,
)
from agent_remote.services.terminal.infrastructure.pty_spawner import PTYSpawner
from agent_remote.services.terminal.workflows.terminal_workflow import (
    SessionNotFoundError,
    TerminalWorkflow,
    TerminalWorkflowError,
)
from agent_remote.shared.protocol.base import RemoteAgentMessage
from agent_remote.shared.protocol.relay_messages import (
    ERROR_INVALID_MESSAGE,
    ERROR_SESSION_NOT_FOUND,
    ERROR_VALIDATION_FAILED,
    Error,
)
from agent_remote.shared.protocol.terminal_messages import (
    TerminalClose,
    TerminalInput,
    TerminalOutput,
    TerminalResize,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# Dependency Injection
# ==============================================================================

# Singleton instances for workflow components
_repository: Optional[InMemoryPTYRepository] = None
_spawner: Optional[PTYSpawner] = None
_workflow: Optional[TerminalWorkflow] = None


def get_repository() -> InMemoryPTYRepository:
    """Get or create the singleton PTY repository instance.

    Returns:
        InMemoryPTYRepository instance for PTY session storage
    """
    global _repository
    if _repository is None:
        _repository = InMemoryPTYRepository()
    return _repository


def get_spawner() -> PTYSpawner:
    """Get or create the singleton PTY spawner instance.

    Returns:
        PTYSpawner instance for PTY process management
    """
    global _spawner
    if _spawner is None:
        _spawner = PTYSpawner()
    return _spawner


def get_workflow() -> TerminalWorkflow:
    """Get or create the singleton TerminalWorkflow instance.

    Returns:
        TerminalWorkflow instance for orchestrating PTY sessions
    """
    global _workflow
    if _workflow is None:
        _workflow = TerminalWorkflow(
            repository=get_repository(),
            spawner=get_spawner(),
            output_callback=None,  # Will be set per-session in WebSocket handler
        )
    return _workflow


# ==============================================================================
# WebSocket Router
# ==============================================================================

router = APIRouter()


# ==============================================================================
# WebSocket Message Helpers
# ==============================================================================


async def send_message(websocket: WebSocket, message: RemoteAgentMessage) -> None:
    """Send a protocol message via WebSocket.

    Args:
        websocket: WebSocket connection
        message: Protocol message to send
    """
    await websocket.send_json(message.model_dump())


async def receive_message(websocket: WebSocket) -> RemoteAgentMessage:
    """Receive and parse a protocol message from WebSocket.

    Args:
        websocket: WebSocket connection

    Returns:
        Parsed protocol message

    Raises:
        WebSocketDisconnect: If client disconnects
        ValueError: If message format is invalid
    """
    data = await websocket.receive_json()

    # Parse message using protocol registry
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError("Invalid message format: missing 'type' field")

    # Import MESSAGE_TYPES registry to parse message
    from agent_remote.shared.protocol.base import MESSAGE_TYPES

    msg_type = data.get("type")
    if msg_type not in MESSAGE_TYPES:
        raise ValueError(f"Unknown message type: {msg_type}")

    # Parse message using registered type
    message_class = MESSAGE_TYPES[msg_type]
    return message_class.model_validate(data)


# ==============================================================================
# Terminal WebSocket Endpoint
# ==============================================================================


@router.websocket("/ws/terminal/{session_id}")
async def terminal_websocket(
    websocket: WebSocket,
    session_id: str,
    workflow: TerminalWorkflow = Depends(get_workflow),
):
    """WebSocket endpoint for terminal PTY sessions.

    Terminal flow:
    1. Client connects with session_id
    2. Server creates PTY session with shell
    3. Client receives initial shell prompt (TerminalOutput)
    4. Bidirectional I/O:
       - Client sends TerminalInput (keystrokes)
       - Server sends TerminalOutput (PTY output)
       - Client sends TerminalResize (window size changes)
    5. Either side sends TerminalClose to end session
    6. Disconnect triggers PTY cleanup

    Args:
        websocket: FastAPI WebSocket connection
        session_id: UUID identifying the terminal session (from URL path)
        workflow: TerminalWorkflow instance (injected)

    Message protocol:
        - Receives: TerminalInput (keystrokes), TerminalResize (window size)
        - Sends: TerminalOutput (PTY output), TerminalClose (session end)
        - Sends: Error messages on validation/workflow failures
    """
    # Accept WebSocket connection
    try:
        await websocket.accept()
        logger.info(f"Terminal WebSocket accepted for session {session_id}")
    except Exception as e:
        logger.error(f"Failed to accept terminal WebSocket: {e}")
        return

    # Output callback to send PTY output to client
    output_queue: asyncio.Queue[bytes] = asyncio.Queue()

    def output_callback(sid: str, data: bytes) -> None:
        """Called by TerminalWorkflow when PTY produces output."""
        if sid == session_id:
            output_queue.put_nowait(data)

    # Set output callback on workflow
    workflow._output_callback = output_callback

    # Start PTY session with default shell
    try:
        # Default terminal dimensions (will be updated by client's first TerminalResize)
        dimensions = TerminalDimensions(rows=24, cols=80)

        # Start shell session
        # TODO: Make shell command configurable via environment variable
        session = await workflow.start_session(
            session_id=session_id,
            command=["/bin/bash"],  # Default shell
            dimensions=dimensions,
        )
        logger.info(f"Started PTY session '{session_id}' with PID {session.pid}")
    except TerminalWorkflowError as e:
        logger.error(f"Failed to start PTY session: {e}")
        await send_message(
            websocket,
            Error(
                code=ERROR_VALIDATION_FAILED,
                message=f"Failed to start terminal session: {str(e)}",
            ),
        )
        await websocket.close()
        return

    # Create background task to send PTY output to client
    async def output_sender():
        """Background task that sends PTY output to WebSocket."""
        try:
            while True:
                data = await output_queue.get()
                output_msg = TerminalOutput(session_id=session_id, data=data)
                await send_message(websocket, output_msg)
        except asyncio.CancelledError:
            logger.debug(f"Output sender cancelled for session '{session_id}'")
            raise
        except Exception as e:
            logger.error(f"Error sending output for session '{session_id}': {e}")

    output_task = asyncio.create_task(output_sender())

    try:
        # Message handling loop
        while True:
            # Receive message from client
            try:
                message = await receive_message(websocket)
                logger.debug(f"Terminal message received: type={message.type}")
            except WebSocketDisconnect:
                logger.info(f"Terminal WebSocket disconnected for session {session_id}")
                break
            except Exception as e:
                logger.error(f"Error receiving terminal message: {e}")
                await send_message(
                    websocket,
                    Error(
                        code=ERROR_INVALID_MESSAGE,
                        message=f"Failed to receive message: {str(e)}",
                    ),
                )
                break

            # Handle message based on type
            try:
                if isinstance(message, TerminalInput):
                    # Send input to PTY
                    await workflow.send_input(session_id, message.data)
                    logger.debug(f"Sent {len(message.data)} bytes to PTY session '{session_id}'")

                elif isinstance(message, TerminalResize):
                    # Resize PTY window
                    dimensions = TerminalDimensions(rows=message.rows, cols=message.cols)
                    await workflow.resize_terminal(session_id, dimensions)
                    logger.debug(f"Resized PTY session '{session_id}' to {dimensions}")

                elif isinstance(message, TerminalClose):
                    # Client requested close
                    logger.info(f"Client requested close for session '{session_id}': {message.reason}")
                    break

                else:
                    # Unexpected message type
                    logger.warning(f"Unexpected message type: {message.type}")
                    await send_message(
                        websocket,
                        Error(
                            code=ERROR_INVALID_MESSAGE,
                            message=f"Unexpected message type: {message.type}",
                        ),
                    )

            except SessionNotFoundError as e:
                logger.error(f"Session not found: {e}")
                await send_message(
                    websocket,
                    Error(
                        code=ERROR_SESSION_NOT_FOUND,
                        message=str(e),
                    ),
                )
                break
            except TerminalWorkflowError as e:
                logger.error(f"Workflow error: {e}")
                await send_message(
                    websocket,
                    Error(
                        code=ERROR_VALIDATION_FAILED,
                        message=f"Terminal workflow error: {str(e)}",
                    ),
                )
                break
            except Exception as e:
                logger.error(f"Unexpected error handling message: {e}")
                await send_message(
                    websocket,
                    Error(
                        code=ERROR_INVALID_MESSAGE,
                        message=f"Unexpected error: {str(e)}",
                    ),
                )
                break

    except Exception as e:
        logger.error(f"Unexpected error in terminal WebSocket loop: {e}")
    finally:
        # Cancel output sender task
        output_task.cancel()
        try:
            await output_task
        except asyncio.CancelledError:
            pass

        # Stop PTY session and clean up
        try:
            exit_code = await workflow.stop_session(session_id)
            logger.info(f"Stopped PTY session '{session_id}' with exit code {exit_code}")

            # Notify client that session ended
            try:
                close_msg = TerminalClose(
                    session_id=session_id,
                    reason=f"PTY process exited with code {exit_code}",
                )
                await send_message(websocket, close_msg)
            except Exception as e:
                logger.debug(f"Could not send close message (client may have disconnected): {e}")
        except Exception as e:
            logger.error(f"Error stopping PTY session on disconnect: {e}")

        # Close WebSocket
        try:
            await websocket.close()
        except Exception as e:
            logger.debug(f"Error closing WebSocket (may already be closed): {e}")


# ==============================================================================
# Export router
# ==============================================================================

__all__ = ["router"]
