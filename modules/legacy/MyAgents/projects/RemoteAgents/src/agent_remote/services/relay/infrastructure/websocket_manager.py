"""WebSocket connection lifecycle and message management.

This module provides the WebSocketManager class that handles:
- WebSocket connection acceptance and lifecycle
- Message serialization and deserialization using protocol messages
- Ping/pong keepalive to detect disconnected clients
- Graceful error handling and connection closure

The WebSocketManager wraps FastAPI's WebSocket with relay-specific logic:
- Messages are sent/received as JSON text frames
- Ping/pong keepalive runs as background task
- Connections are closed gracefully with Error messages
- WebSocketDisconnect exceptions are handled without crashing

Keepalive behavior:
- Ping sent every 30 seconds (configurable)
- Pong expected within 5 seconds
- Connection closed if Pong timeout (detects disconnected clients within 35s)
"""

import asyncio
import logging
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from agent_remote.shared.protocol.base import RemoteAgentMessage, deserialize_message
from agent_remote.shared.protocol.relay_messages import (
    ERROR_CONNECTION_LOST,
    ERROR_TIMEOUT,
    Error,
    Ping,
    Pong,
)

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connection lifecycle and message transport.
    
    This class handles:
    - Connection acceptance and setup
    - Message serialization/deserialization using protocol
    - Ping/pong keepalive with timeout detection
    - Graceful connection closure with error messages
    
    Example:
        >>> manager = WebSocketManager()
        >>> await manager.accept(websocket)
        >>> # Start keepalive in background
        >>> keepalive_task = manager.start_keepalive(websocket)
        >>> try:
        ...     while True:
        ...         msg = await manager.receive_message(websocket)
        ...         # Process message
        ...         await manager.send_message(websocket, response)
        ... except WebSocketDisconnect:
        ...     logger.info("Client disconnected")
        ... finally:
        ...     keepalive_task.cancel()
    """
    
    def __init__(self):
        """Initialize WebSocketManager."""
        self._keepalive_tasks: dict[WebSocket, asyncio.Task] = {}
        self._pong_events: dict[WebSocket, asyncio.Event] = {}
    
    async def accept(self, websocket: WebSocket) -> None:
        """Accept WebSocket connection.
        
        Args:
            websocket: FastAPI WebSocket instance to accept
            
        Raises:
            RuntimeError: If connection cannot be accepted
        """
        try:
            await websocket.accept()
            logger.info(f"WebSocket connection accepted from {websocket.client}")
        except Exception as e:
            logger.error(f"Failed to accept WebSocket connection: {e}")
            raise RuntimeError(f"Failed to accept WebSocket: {e}")
    
    async def send_message(
        self, websocket: WebSocket, message: RemoteAgentMessage
    ) -> None:
        """Send message over WebSocket.
        
        Serializes the message to JSON and sends as text frame.
        Handles WebSocketDisconnect gracefully.
        
        Args:
            websocket: WebSocket to send message on
            message: RemoteAgentMessage to serialize and send
            
        Raises:
            WebSocketDisconnect: If connection is closed during send
        """
        try:
            json_str = message.to_json()
            await websocket.send_text(json_str)
            logger.debug(f"Sent message type={message.type}")
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected during send")
            raise
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    async def receive_message(self, websocket: WebSocket) -> RemoteAgentMessage:
        """Receive and deserialize message from WebSocket.
        
        Receives JSON text frame and deserializes using MESSAGE_TYPES registry.
        
        Args:
            websocket: WebSocket to receive message from
            
        Returns:
            Deserialized RemoteAgentMessage instance
            
        Raises:
            WebSocketDisconnect: If connection closed during receive
            ValueError: If message cannot be deserialized
        """
        try:
            json_str = await websocket.receive_text()
            logger.debug(f"Received message: {json_str[:100]}...")
            
            message = deserialize_message(json_str)
            logger.debug(f"Deserialized message type={message.type}")
            
            # Handle Pong responses for keepalive
            if isinstance(message, Pong):
                if websocket in self._pong_events:
                    self._pong_events[websocket].set()
                    logger.debug("Pong received, keepalive satisfied")
            
            return message
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected during receive")
            raise
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            raise ValueError(f"Failed to deserialize message: {e}")
    
    async def close(
        self, websocket: WebSocket, reason: str, code: str = ERROR_CONNECTION_LOST
    ) -> None:
        """Close WebSocket connection gracefully.
        
        Sends an Error message with the reason before closing the connection.
        Cancels any keepalive tasks associated with this connection.
        
        Args:
            websocket: WebSocket to close
            reason: Human-readable reason for closure
            code: Error code constant (default: ERROR_CONNECTION_LOST)
        """
        try:
            # Cancel keepalive task if exists
            if websocket in self._keepalive_tasks:
                task = self._keepalive_tasks.pop(websocket)
                task.cancel()
                logger.debug("Keepalive task cancelled")
            
            # Clean up pong event
            if websocket in self._pong_events:
                del self._pong_events[websocket]
            
            # Send error message before closing
            try:
                error_msg = Error(code=code, message=reason)
                await self.send_message(websocket, error_msg)
            except Exception as e:
                logger.warning(f"Failed to send error message before close: {e}")
            
            # Close connection
            await websocket.close()
            logger.info(f"WebSocket closed: {reason}")
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
    
    def start_keepalive(
        self, websocket: WebSocket, interval: int = 30, pong_timeout: int = 5
    ) -> asyncio.Task:
        """Start keepalive background task.
        
        Sends Ping messages at regular intervals and expects Pong responses.
        If no Pong is received within pong_timeout seconds, closes the connection.
        
        This detects disconnected clients that fail to respond to pings.
        With default settings (30s interval, 5s timeout), disconnected clients
        are detected within 35 seconds.
        
        Args:
            websocket: WebSocket to send keepalive pings on
            interval: Seconds between ping messages (default: 30)
            pong_timeout: Seconds to wait for pong response (default: 5)
            
        Returns:
            asyncio.Task running the keepalive loop
            
        Example:
            >>> task = manager.start_keepalive(websocket)
            >>> # Later, when cleaning up:
            >>> task.cancel()
        """
        # Create pong event for this connection
        self._pong_events[websocket] = asyncio.Event()
        
        async def keepalive_loop():
            """Background task that sends pings and waits for pongs."""
            try:
                while True:
                    # Wait for interval
                    await asyncio.sleep(interval)
                    
                    # Send ping
                    try:
                        ping = Ping()
                        await self.send_message(websocket, ping)
                        logger.debug(f"Sent ping, waiting {pong_timeout}s for pong")
                    except WebSocketDisconnect:
                        logger.info("WebSocket disconnected during ping")
                        break
                    except Exception as e:
                        logger.error(f"Error sending ping: {e}")
                        break
                    
                    # Wait for pong with timeout
                    pong_event = self._pong_events.get(websocket)
                    if pong_event is None:
                        logger.warning("Pong event not found, stopping keepalive")
                        break
                    
                    try:
                        await asyncio.wait_for(pong_event.wait(), timeout=pong_timeout)
                        pong_event.clear()  # Reset for next ping
                        logger.debug("Pong received within timeout")
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"Pong timeout after {pong_timeout}s, closing connection"
                        )
                        await self.close(
                            websocket,
                            reason=f"Keepalive timeout: no pong after {pong_timeout}s",
                            code=ERROR_TIMEOUT,
                        )
                        break
            except asyncio.CancelledError:
                logger.debug("Keepalive task cancelled")
            except Exception as e:
                logger.error(f"Unexpected error in keepalive loop: {e}")
        
        # Start background task
        task = asyncio.create_task(keepalive_loop())
        self._keepalive_tasks[websocket] = task
        logger.info(f"Keepalive started: interval={interval}s, pong_timeout={pong_timeout}s")
        return task
