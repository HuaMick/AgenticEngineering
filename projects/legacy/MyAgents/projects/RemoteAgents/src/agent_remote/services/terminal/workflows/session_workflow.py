"""SessionWorkflow orchestrates complete remote session lifecycle.

Manages:
1. Session creation via relay API
2. PTY spawning via TerminalWorkflow
3. Relay client connection for I/O transport
4. Bidirectional I/O piping (PTY <-> Relay)
"""

import asyncio
import base64
import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from nacl.public import PrivateKey as NaClPrivateKey

from agent_remote.services.terminal.domains.pty_manager import TerminalDimensions
from agent_remote.services.terminal.infrastructure.in_memory_repository import InMemoryPTYRepository
from agent_remote.services.terminal.infrastructure.pty_spawner import PTYSpawner
from agent_remote.services.terminal.infrastructure.relay_client import (
    RelayClient,
    RelayClientConfig,
    RelayClientError,
)
from agent_remote.services.terminal.workflows.terminal_workflow import TerminalWorkflow

logger = logging.getLogger(__name__)


@dataclass
class KeyPair:
    """Simple key pair for E2E encryption."""
    public_key: bytes
    private_key: bytes

    @property
    def public_key_base64(self) -> str:
        """Get base64-encoded public key for transmission."""
        return base64.b64encode(self.public_key).decode('ascii')


def generate_keypair() -> KeyPair:
    """Generate a new NaCl key pair."""
    private_key = NaClPrivateKey.generate()
    return KeyPair(
        public_key=bytes(private_key.public_key),
        private_key=bytes(private_key),
    )


class SessionWorkflowError(Exception):
    """Error in session workflow operations."""
    pass


class SessionWorkflow:
    """Orchestrates complete remote terminal session lifecycle.

    Manages session creation, PTY spawning, relay connection, and I/O transport.
    This is the top-level coordinator used by the CLI entrypoint.
    """

    def __init__(
        self,
        relay_url: str,
        command: list[str],
        dimensions: TerminalDimensions = None,
    ):
        """Initialize session workflow.

        Args:
            relay_url: Base URL for relay service (e.g., "http://localhost:8000")
            command: Command to run in PTY (e.g., ["claude"])
            dimensions: Optional terminal dimensions (defaults to 24x80)
        """
        self._relay_url = relay_url.rstrip('/')
        self._command = command
        self._dimensions = dimensions or TerminalDimensions(rows=24, cols=80)

        # Components (created during start)
        self._session_id: Optional[str] = None
        self._pairing_code: Optional[str] = None
        self._keypair: Optional[KeyPair] = None
        self._terminal_workflow: Optional[TerminalWorkflow] = None
        self._relay_client: Optional[RelayClient] = None
        self._relay_task: Optional[asyncio.Task] = None
        self._running = False
        self._client_public_key: Optional[bytes] = None

    @property
    def session_id(self) -> Optional[str]:
        """Get session ID (available after create_session)."""
        return self._session_id

    @property
    def pairing_code(self) -> Optional[str]:
        """Get pairing code (available after create_session)."""
        return self._pairing_code

    @property
    def is_running(self) -> bool:
        """Check if session is running."""
        return self._running

    async def create_session(self) -> tuple[str, str]:
        """Create session via relay API.

        Generates keypair and registers with relay service.

        Returns:
            Tuple of (session_id, pairing_code)

        Raises:
            SessionWorkflowError: If session creation fails
        """
        try:
            # Generate keypair for E2E encryption
            self._keypair = generate_keypair()

            # Call relay API to create session
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._relay_url}/api/sessions",
                    json={
                        "desktop_public_key": self._keypair.public_key_base64,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

            self._session_id = data["session_id"]
            self._pairing_code = data["pairing_code"]

            logger.info(f"Created session: {self._session_id}")
            logger.info(f"Pairing code: {self._pairing_code}")

            return self._session_id, self._pairing_code

        except httpx.HTTPError as e:
            raise SessionWorkflowError(f"Failed to create session: {e}") from e
        except KeyError as e:
            raise SessionWorkflowError(f"Invalid response from relay: missing {e}") from e

    async def start(self) -> None:
        """Start PTY session and connect to relay.

        Must call create_session() first.

        Raises:
            SessionWorkflowError: If session not created or start fails
        """
        if not self._session_id:
            raise SessionWorkflowError("Must call create_session() first")

        if self._running:
            raise SessionWorkflowError("Session already running")

        # Create terminal workflow with output callback
        repository = InMemoryPTYRepository()
        spawner = PTYSpawner()
        self._terminal_workflow = TerminalWorkflow(
            repository=repository,
            spawner=spawner,
            output_callback=self._on_terminal_output,
        )

        # Start PTY session
        await self._terminal_workflow.start_session(
            session_id=self._session_id,
            command=self._command,
            dimensions=self._dimensions,
        )

        self._running = True
        logger.info(f"Started PTY for session {self._session_id}")

        # Create and configure relay client
        relay_config = RelayClientConfig(
            relay_ws_url=self._relay_url,
            session_id=self._session_id,
            private_key=self._keypair.private_key,
        )
        self._relay_client = RelayClient(relay_config)

        # Set handlers for incoming messages from client
        self._relay_client.on_input = self._on_relay_input
        self._relay_client.on_resize = self._on_relay_resize
        self._relay_client.on_close = self._on_relay_close
        self._relay_client.on_error = self._on_relay_error

        # Start relay connection in background task
        self._relay_task = asyncio.create_task(self._run_relay())
        logger.info(f"Relay client started for session {self._session_id}")

    async def send_input(self, data: bytes) -> None:
        """Send input to PTY.

        Args:
            data: Input bytes to write to PTY stdin
        """
        if not self._running or not self._terminal_workflow:
            raise SessionWorkflowError("Session not running")

        await self._terminal_workflow.send_input(self._session_id, data)

    async def resize(self, rows: int, cols: int) -> None:
        """Resize terminal.

        Args:
            rows: New row count
            cols: New column count
        """
        if not self._running or not self._terminal_workflow:
            raise SessionWorkflowError("Session not running")

        dimensions = TerminalDimensions(rows=rows, cols=cols)
        await self._terminal_workflow.resize_terminal(self._session_id, dimensions)

    async def stop(self) -> int:
        """Stop session and cleanup.

        Returns:
            Exit code from PTY process
        """
        exit_code = 0

        # Stop relay client first
        if self._relay_client:
            try:
                await self._relay_client.close()
            except Exception as e:
                logger.warning(f"Error closing relay client: {e}")

        # Cancel relay task
        if self._relay_task and not self._relay_task.done():
            self._relay_task.cancel()
            try:
                await self._relay_task
            except asyncio.CancelledError:
                pass

        # Stop terminal workflow
        if self._terminal_workflow and self._session_id:
            try:
                exit_code = await self._terminal_workflow.stop_session(self._session_id)
            except Exception as e:
                logger.warning(f"Error stopping terminal: {e}")

        self._running = False
        logger.info(f"Stopped session {self._session_id} with exit code {exit_code}")

        return exit_code

    def set_client_public_key(self, public_key: bytes) -> None:
        """Set the client's public key for E2E encryption.

        Called after the client pairs with the session. The public key is
        received via the relay API or a notification.

        Args:
            public_key: Client's NaCl public key (32 bytes)
        """
        self._client_public_key = public_key
        if self._relay_client:
            self._relay_client.set_client_public_key(public_key)
            logger.info("Client public key set on relay client")

    async def wait_for_exit(self) -> int:
        """Wait for the session to exit.

        Blocks until the PTY process exits or the session is stopped.

        Returns:
            Exit code from PTY process
        """
        if not self._running:
            return 0

        # Wait for relay task to complete (which happens when connection closes)
        if self._relay_task:
            try:
                await self._relay_task
            except asyncio.CancelledError:
                pass

        return await self.stop()

    async def _run_relay(self) -> None:
        """Background task that runs the relay client connection."""
        if not self._relay_client:
            return

        try:
            await self._relay_client.connect()
        except RelayClientError as e:
            logger.error(f"Relay client error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in relay client: {e}", exc_info=True)

    def _on_terminal_output(self, session_id: str, data: bytes) -> None:
        """Called when PTY produces output.

        Forwards output to relay client for transmission to web client.
        """
        if not self._relay_client or not self._relay_client.is_connected:
            logger.debug(f"Terminal output ({len(data)} bytes) - relay not connected")
            return

        # Schedule async send in event loop
        try:
            asyncio.create_task(self._send_output_to_relay(data))
        except RuntimeError:
            # No event loop running
            logger.debug("Cannot send output - no event loop")

    async def _send_output_to_relay(self, data: bytes) -> None:
        """Send terminal output to relay client."""
        if self._relay_client and self._relay_client.is_connected:
            try:
                await self._relay_client.send_output(data)
            except Exception as e:
                logger.warning(f"Failed to send output to relay: {e}")

    async def _on_relay_input(self, data: bytes) -> None:
        """Handle terminal input from web client via relay."""
        if self._terminal_workflow and self._session_id:
            try:
                await self._terminal_workflow.send_input(self._session_id, data)
            except Exception as e:
                logger.warning(f"Failed to forward input to PTY: {e}")

    async def _on_relay_resize(self, rows: int, cols: int) -> None:
        """Handle terminal resize from web client via relay."""
        if self._terminal_workflow and self._session_id:
            try:
                dimensions = TerminalDimensions(rows=rows, cols=cols)
                await self._terminal_workflow.resize_terminal(self._session_id, dimensions)
            except Exception as e:
                logger.warning(f"Failed to resize terminal: {e}")

    async def _on_relay_close(self, reason: str) -> None:
        """Handle session close from web client via relay."""
        logger.info(f"Client requested close: {reason}")
        # Schedule stop in background to avoid blocking the relay handler
        asyncio.create_task(self.stop())

    async def _on_relay_error(self, code: str, message: str) -> None:
        """Handle error from relay."""
        logger.error(f"Relay error [{code}]: {message}")
