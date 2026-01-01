"""WebSocket client for relay service connection.

This module provides the RelayClient infrastructure component that:
- Connects to relay service via WebSocket (wss:// or ws://)
- Handles E2E encryption/decryption using NaCl box
- Implements reconnect logic with exponential backoff
- Routes messages between terminal workflow and relay

The client operates as the "desktop" side of the relay protocol:
1. Connects to /ws/desktop/{session_id}
2. Sends encrypted terminal output to client via EncryptedBlob
3. Receives encrypted terminal input from client via EncryptedBlob
4. Handles keepalive (Ping/Pong) and errors

Encryption:
- Uses NaCl box (Curve25519-XSalsa20-Poly1305)
- Desktop generates keypair during session creation
- Client public key is received via relay after pairing
- All terminal messages are encrypted before transmission
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Optional

import websockets
from nacl.exceptions import CryptoError
from nacl.public import Box, PrivateKey, PublicKey
from nacl.utils import random as nacl_random
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidStatus,
    WebSocketException,
)

from agent_remote.shared.protocol.base import (
    base64_to_bytes,
    bytes_to_base64,
    deserialize_message,
)
from agent_remote.shared.protocol.relay_messages import (
    ERROR_CONNECTION_LOST,
    ERROR_CRYPTO_ERROR,
    ERROR_DECRYPTION_FAILED,
    EncryptedBlob,
    Error,
    Ping,
    Pong,
)
from agent_remote.shared.protocol.terminal_messages import (
    TerminalClose,
    TerminalInput,
    TerminalOutput,
    TerminalResize,
)

logger = logging.getLogger(__name__)


# Type aliases for callbacks
OutputHandler = Callable[[bytes], Awaitable[None]]  # Terminal output data
ResizeHandler = Callable[[int, int], Awaitable[None]]  # (rows, cols)
CloseHandler = Callable[[str], Awaitable[None]]  # reason
ErrorHandler = Callable[[str, str], Awaitable[None]]  # (code, message)


class ConnectionState(Enum):
    """State of the relay client connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


@dataclass
class RelayClientConfig:
    """Configuration for RelayClient.

    Attributes:
        relay_ws_url: WebSocket URL for relay (e.g., "wss://relay.example.com")
        session_id: UUID identifying the session
        private_key: Desktop's NaCl private key (32 bytes)
        max_reconnect_attempts: Maximum reconnection attempts (0 = infinite)
        initial_reconnect_delay: Initial delay before reconnect (seconds)
        max_reconnect_delay: Maximum delay between reconnects (seconds)
        keepalive_interval: Interval between keepalive pings (seconds)
        connection_timeout: Timeout for connection establishment (seconds)
    """

    relay_ws_url: str
    session_id: str
    private_key: bytes
    max_reconnect_attempts: int = 10
    initial_reconnect_delay: float = 1.0
    max_reconnect_delay: float = 30.0
    keepalive_interval: float = 30.0
    connection_timeout: float = 10.0


class RelayClientError(Exception):
    """Error in relay client operations."""

    pass


class RelayConnectionError(RelayClientError):
    """Failed to connect to relay service."""

    pass


class RelayEncryptionError(RelayClientError):
    """Encryption or decryption failure."""

    pass


class RelayClient:
    """WebSocket client for relay service communication.

    Manages encrypted bidirectional communication between the terminal service
    and web client through the relay service.

    Usage:
        # Create client with config
        config = RelayClientConfig(
            relay_ws_url="wss://relay.example.com",
            session_id=session_id,
            private_key=keypair.private_key,
        )
        client = RelayClient(config)

        # Set handlers for incoming messages
        client.on_input = handle_input
        client.on_resize = handle_resize
        client.on_close = handle_close

        # Connect and run (blocks until disconnected)
        await client.connect()

        # Send terminal output
        await client.send_output(output_data)

        # Stop client
        await client.close()
    """

    def __init__(self, config: RelayClientConfig):
        """Initialize relay client.

        Args:
            config: Client configuration
        """
        self._config = config
        self._state = ConnectionState.DISCONNECTED
        self._ws: Optional[ClientConnection] = None
        self._reconnect_attempts = 0
        self._client_public_key: Optional[bytes] = None
        self._box: Optional[Box] = None

        # Message handlers
        self._on_input: Optional[OutputHandler] = None
        self._on_resize: Optional[ResizeHandler] = None
        self._on_close: Optional[CloseHandler] = None
        self._on_error: Optional[ErrorHandler] = None

        # Background tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._keepalive_task: Optional[asyncio.Task] = None

        # Shutdown flag
        self._shutdown_event = asyncio.Event()

        # Parse private key
        try:
            self._private_key = PrivateKey(config.private_key)
        except Exception as e:
            raise RelayClientError(f"Invalid private key: {e}") from e

        logger.debug(f"RelayClient initialized for session {config.session_id}")

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected to relay."""
        return self._state == ConnectionState.CONNECTED

    @property
    def on_input(self) -> Optional[OutputHandler]:
        """Handler for incoming terminal input from client."""
        return self._on_input

    @on_input.setter
    def on_input(self, handler: OutputHandler) -> None:
        """Set handler for incoming terminal input."""
        self._on_input = handler

    @property
    def on_resize(self) -> Optional[ResizeHandler]:
        """Handler for terminal resize from client."""
        return self._on_resize

    @on_resize.setter
    def on_resize(self, handler: ResizeHandler) -> None:
        """Set handler for terminal resize."""
        self._on_resize = handler

    @property
    def on_close(self) -> Optional[CloseHandler]:
        """Handler for session close from client."""
        return self._on_close

    @on_close.setter
    def on_close(self, handler: CloseHandler) -> None:
        """Set handler for session close."""
        self._on_close = handler

    @property
    def on_error(self) -> Optional[ErrorHandler]:
        """Handler for relay errors."""
        return self._on_error

    @on_error.setter
    def on_error(self, handler: ErrorHandler) -> None:
        """Set handler for relay errors."""
        self._on_error = handler

    def set_client_public_key(self, public_key: bytes) -> None:
        """Set the client's public key for encryption.

        Must be called after the client pairs with the session (public key
        is received via relay API after pairing).

        Args:
            public_key: Client's NaCl public key (32 bytes)

        Raises:
            RelayClientError: If public key is invalid
        """
        try:
            client_key = PublicKey(public_key)
            self._client_public_key = public_key
            # Create encryption box with desktop's private key and client's public key
            self._box = Box(self._private_key, client_key)
            logger.info("Client public key set, encryption box created")
        except Exception as e:
            raise RelayClientError(f"Invalid client public key: {e}") from e

    async def connect(self) -> None:
        """Connect to relay service and start message processing.

        Establishes WebSocket connection to relay service and starts
        background tasks for message receiving and keepalive.

        Blocks until connection is closed (call close() to disconnect).

        Raises:
            RelayConnectionError: If connection fails after all retries
        """
        if self._state == ConnectionState.CLOSED:
            raise RelayClientError("Client has been closed")

        try:
            await self._connect_with_retry()

            # Start background tasks
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())

            # Wait until shutdown
            await self._shutdown_event.wait()

        except asyncio.CancelledError:
            logger.debug("Connect task cancelled")
        finally:
            await self._cleanup()

    async def _connect_with_retry(self) -> None:
        """Connect to relay with exponential backoff retry."""
        delay = self._config.initial_reconnect_delay
        self._reconnect_attempts = 0

        while not self._shutdown_event.is_set():
            try:
                self._state = ConnectionState.CONNECTING
                ws_url = self._build_ws_url()
                logger.info(f"Connecting to relay: {ws_url}")

                self._ws = await asyncio.wait_for(
                    websockets.connect(
                        ws_url,
                        ping_interval=None,  # We handle keepalive ourselves
                        ping_timeout=None,
                        close_timeout=5.0,
                    ),
                    timeout=self._config.connection_timeout,
                )

                self._state = ConnectionState.CONNECTED
                self._reconnect_attempts = 0
                logger.info(f"Connected to relay for session {self._config.session_id}")
                return

            except asyncio.TimeoutError:
                logger.warning("Connection timeout")
            except InvalidStatus as e:
                logger.warning(f"Invalid status: {e.response.status_code}")
                if e.response.status_code in (401, 403, 404):
                    # Session invalid/not found - don't retry
                    raise RelayConnectionError(
                        f"Session not found or invalid: HTTP {e.response.status_code}"
                    ) from e
            except ConnectionRefusedError:
                logger.warning("Connection refused")
            except WebSocketException as e:
                logger.warning(f"WebSocket error: {e}")
            except OSError as e:
                logger.warning(f"Network error: {e}")

            # Check retry limit
            self._reconnect_attempts += 1
            if (
                self._config.max_reconnect_attempts > 0
                and self._reconnect_attempts >= self._config.max_reconnect_attempts
            ):
                raise RelayConnectionError(
                    f"Failed to connect after {self._reconnect_attempts} attempts"
                )

            # Exponential backoff
            self._state = ConnectionState.RECONNECTING
            jitter = delay * 0.1 * (2 * asyncio.get_event_loop().time() % 1 - 0.5)
            actual_delay = min(delay + jitter, self._config.max_reconnect_delay)
            logger.info(f"Reconnecting in {actual_delay:.1f}s (attempt {self._reconnect_attempts})")
            await asyncio.sleep(actual_delay)
            delay = min(delay * 2, self._config.max_reconnect_delay)

    def _build_ws_url(self) -> str:
        """Build WebSocket URL for desktop endpoint."""
        base_url = self._config.relay_ws_url.rstrip("/")
        # Convert http(s) to ws(s) if needed
        if base_url.startswith("http://"):
            base_url = "ws://" + base_url[7:]
        elif base_url.startswith("https://"):
            base_url = "wss://" + base_url[8:]
        elif not base_url.startswith(("ws://", "wss://")):
            base_url = "wss://" + base_url

        return f"{base_url}/ws/desktop/{self._config.session_id}"

    async def _receive_loop(self) -> None:
        """Background task that receives and processes messages."""
        try:
            while not self._shutdown_event.is_set() and self._ws is not None:
                try:
                    raw_message = await self._ws.recv()

                    if isinstance(raw_message, bytes):
                        # Shouldn't receive binary messages from relay
                        logger.warning("Received unexpected binary message")
                        continue

                    await self._handle_message(raw_message)

                except ConnectionClosedOK:
                    logger.info("Connection closed gracefully")
                    break
                except ConnectionClosedError as e:
                    logger.warning(f"Connection closed with error: {e}")
                    await self._handle_disconnect()
                    break
                except ConnectionClosed as e:
                    logger.warning(f"Connection closed: {e}")
                    await self._handle_disconnect()
                    break

        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled")
        except Exception as e:
            logger.error(f"Error in receive loop: {e}", exc_info=True)
            await self._handle_disconnect()

    async def _handle_message(self, raw_message: str) -> None:
        """Process a received message from relay."""
        try:
            message = deserialize_message(raw_message)
            logger.debug(f"Received message: type={message.type}")

            if isinstance(message, EncryptedBlob):
                await self._handle_encrypted_blob(message)
            elif isinstance(message, Ping):
                await self._handle_ping(message)
            elif isinstance(message, Pong):
                # Pong responses are logged but no action needed
                logger.debug("Received pong")
            elif isinstance(message, Error):
                await self._handle_error(message)
            else:
                logger.warning(f"Unexpected message type: {message.type}")

        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)

    async def _handle_encrypted_blob(self, blob: EncryptedBlob) -> None:
        """Decrypt and process an encrypted message from client."""
        if not self._box:
            logger.warning("Received encrypted message but no encryption box set")
            if self._on_error:
                await self._on_error(
                    ERROR_CRYPTO_ERROR,
                    "No encryption box - client public key not set",
                )
            return

        try:
            # Decrypt the payload
            payload_bytes = blob.get_payload_bytes()
            nonce_bytes = blob.get_nonce_bytes()
            plaintext = self._box.decrypt(payload_bytes, nonce_bytes)

            # Deserialize the inner message
            inner_message = deserialize_message(plaintext.decode("utf-8"))
            logger.debug(f"Decrypted message: type={inner_message.type}")

            # Dispatch to appropriate handler
            if isinstance(inner_message, TerminalInput):
                if self._on_input:
                    await self._on_input(inner_message.data)
            elif isinstance(inner_message, TerminalResize):
                if self._on_resize:
                    await self._on_resize(inner_message.rows, inner_message.cols)
            elif isinstance(inner_message, TerminalClose):
                if self._on_close:
                    await self._on_close(inner_message.reason)
            else:
                logger.warning(f"Unexpected inner message type: {inner_message.type}")

        except CryptoError as e:
            logger.error(f"Decryption failed: {e}")
            if self._on_error:
                await self._on_error(ERROR_DECRYPTION_FAILED, str(e))
        except Exception as e:
            logger.error(f"Error processing encrypted message: {e}", exc_info=True)

    async def _handle_ping(self, ping: Ping) -> None:
        """Respond to ping with pong."""
        pong = Pong(timestamp=ping.timestamp)
        await self._send_raw(pong.to_json())
        logger.debug("Sent pong response")

    async def _handle_error(self, error: Error) -> None:
        """Handle error message from relay."""
        logger.error(f"Relay error: [{error.code}] {error.message}")
        if self._on_error:
            await self._on_error(error.code, error.message)

    async def _handle_disconnect(self) -> None:
        """Handle unexpected disconnect - attempt reconnection."""
        if self._shutdown_event.is_set():
            return

        self._state = ConnectionState.DISCONNECTED

        try:
            # Attempt reconnection
            await self._connect_with_retry()

            # Restart receive loop
            if self._receive_task and self._receive_task.done():
                self._receive_task = asyncio.create_task(self._receive_loop())

        except RelayConnectionError as e:
            logger.error(f"Reconnection failed: {e}")
            self._shutdown_event.set()

    async def _keepalive_loop(self) -> None:
        """Background task that sends periodic keepalive pings."""
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(self._config.keepalive_interval)

                if self._state == ConnectionState.CONNECTED and self._ws is not None:
                    try:
                        ping = Ping()
                        await self._send_raw(ping.to_json())
                        logger.debug("Sent keepalive ping")
                    except Exception as e:
                        logger.warning(f"Failed to send keepalive: {e}")

        except asyncio.CancelledError:
            logger.debug("Keepalive loop cancelled")

    async def send_output(self, data: bytes) -> None:
        """Send terminal output to client.

        Encrypts the output data and sends as EncryptedBlob through relay.

        Args:
            data: Terminal output bytes

        Raises:
            RelayClientError: If not connected or encryption fails
        """
        if not self.is_connected:
            raise RelayClientError("Not connected to relay")

        if not self._box or not self._client_public_key:
            raise RelayEncryptionError("Client public key not set")

        # Create terminal output message
        output_msg = TerminalOutput(session_id=self._config.session_id, data=data)

        # Encrypt and send
        await self._send_encrypted(output_msg.to_json())

    async def send_close(self, reason: str) -> None:
        """Send terminal close notification to client.

        Args:
            reason: Reason for closing the session

        Raises:
            RelayClientError: If not connected or encryption fails
        """
        if not self.is_connected:
            return  # Silently ignore if not connected

        if not self._box or not self._client_public_key:
            logger.warning("Cannot send close - client public key not set")
            return

        close_msg = TerminalClose(session_id=self._config.session_id, reason=reason)
        try:
            await self._send_encrypted(close_msg.to_json())
        except Exception as e:
            logger.warning(f"Failed to send close message: {e}")

    async def _send_encrypted(self, plaintext: str) -> None:
        """Encrypt and send a message through the relay.

        Args:
            plaintext: JSON string to encrypt and send

        Raises:
            RelayEncryptionError: If encryption fails
            RelayClientError: If send fails
        """
        if not self._box:
            raise RelayEncryptionError("No encryption box available")

        try:
            # Generate random nonce
            nonce = nacl_random(Box.NONCE_SIZE)

            # Encrypt the plaintext
            ciphertext = self._box.encrypt(plaintext.encode("utf-8"), nonce)
            # Note: nacl box.encrypt returns nonce + ciphertext, we need just ciphertext
            encrypted_data = ciphertext.ciphertext

            # Create encrypted blob
            blob = EncryptedBlob.create(
                session_id=self._config.session_id,
                sender="desktop",
                payload=encrypted_data,
                nonce=nonce,
            )

            await self._send_raw(blob.to_json())

        except CryptoError as e:
            raise RelayEncryptionError(f"Encryption failed: {e}") from e

    async def _send_raw(self, message: str) -> None:
        """Send a raw message to the relay.

        Args:
            message: JSON string to send

        Raises:
            RelayClientError: If not connected or send fails
        """
        if not self._ws:
            raise RelayClientError("WebSocket not connected")

        try:
            await self._ws.send(message)
        except ConnectionClosed as e:
            raise RelayClientError(f"Connection closed: {e}") from e
        except WebSocketException as e:
            raise RelayClientError(f"Send failed: {e}") from e

    async def close(self) -> None:
        """Close the relay client connection.

        Sends close message to client and cleanly shuts down.
        """
        if self._state == ConnectionState.CLOSED:
            return

        logger.info(f"Closing relay client for session {self._config.session_id}")

        # Signal shutdown
        self._shutdown_event.set()
        self._state = ConnectionState.CLOSED

        # Send close message to client
        try:
            await self.send_close("Session ended")
        except Exception:
            pass

        await self._cleanup()

    async def _cleanup(self) -> None:
        """Clean up resources."""
        # Cancel background tasks
        for task in [self._receive_task, self._keepalive_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close WebSocket
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        logger.debug("Relay client cleanup complete")


__all__ = [
    "RelayClient",
    "RelayClientConfig",
    "RelayClientError",
    "RelayConnectionError",
    "RelayEncryptionError",
    "ConnectionState",
]
