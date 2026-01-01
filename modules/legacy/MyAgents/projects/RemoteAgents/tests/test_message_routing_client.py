"""Integration tests for message routing from client to desktop through relay workflow.

This test suite validates the complete message routing pipeline:
1. Session creation and peer pairing (desktop + client)
2. Client sends EncryptedBlob message via WebSocket
3. Desktop receives identical message
4. Bidirectional communication (both peers send/receive simultaneously)
5. Message integrity and order preservation
6. Large message handling (payload > 1MB)

Test Strategy: technical-spike (integration testing)
Agent: Test Agent 3
Target Files:
- /home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_workflow.py
- /home/code/myagents/RemoteAgents/src/agent_remote/services/relay/api/websockets.py
"""

import asyncio
import base64
import json
import time
from typing import Any, List, Optional
from unittest.mock import AsyncMock, Mock, MagicMock

import pytest

from agent_remote.services.relay.domains.session_manager.value_objects import (
    PairingCode,
    PeerRole,
    SessionId,
    SessionState,
)
from agent_remote.services.relay.infrastructure.in_memory_repository import (
    InMemorySessionRepository,
)
from agent_remote.services.relay.workflows.relay_workflow import (
    RelayWorkflow,
    SessionNotFoundException,
    PeerNotConnectedException,
)
from agent_remote.shared.protocol.relay_messages import EncryptedBlob
from agent_remote.shared.protocol.base import bytes_to_base64


# ==============================================================================
# Mock WebSocket Implementation
# ==============================================================================


class MockWebSocket:
    """Mock WebSocket connection for testing message routing.

    This mock captures sent messages and allows simulating message reception
    without requiring actual WebSocket connections.
    """

    def __init__(self, name: str):
        """Initialize mock WebSocket.

        Args:
            name: Identifier for this WebSocket (e.g., "desktop", "client")
        """
        self.name = name
        self.sent_messages: List[dict] = []
        self.is_connected = True
        self.client = ("127.0.0.1", 12345)

    async def send_json(self, data: dict) -> None:
        """Mock send_json method that captures sent messages.

        Args:
            data: Dictionary to send as JSON
        """
        if not self.is_connected:
            raise RuntimeError(f"WebSocket {self.name} is not connected")
        self.sent_messages.append(data)

    async def send(self, data: str) -> None:
        """Mock send method for fallback JSON sending.

        Args:
            data: JSON string to send
        """
        if not self.is_connected:
            raise RuntimeError(f"WebSocket {self.name} is not connected")
        self.sent_messages.append(json.loads(data))

    async def receive_text(self) -> str:
        """Mock receive_text method (not used in these tests)."""
        await asyncio.sleep(0)
        return "{}"

    def disconnect(self) -> None:
        """Simulate WebSocket disconnection."""
        self.is_connected = False

    def get_sent_messages(self) -> List[dict]:
        """Get all messages sent through this WebSocket.

        Returns:
            List of message dictionaries in order sent
        """
        return self.sent_messages.copy()

    def clear_sent_messages(self) -> None:
        """Clear the sent messages buffer."""
        self.sent_messages.clear()


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def repository():
    """Create fresh InMemorySessionRepository for each test."""
    return InMemorySessionRepository()


@pytest.fixture
def workflow(repository):
    """Create RelayWorkflow with injected repository."""
    return RelayWorkflow(repository=repository)


@pytest.fixture
def desktop_ws():
    """Create mock desktop WebSocket."""
    return MockWebSocket(name="desktop")


@pytest.fixture
def client_ws():
    """Create mock client WebSocket."""
    return MockWebSocket(name="client")


@pytest.fixture
def desktop_public_key():
    """Generate mock desktop public key (32 bytes base64-encoded)."""
    key_bytes = b"DESKTOP_PUBLIC_KEY_32_BYTES!1234"
    assert len(key_bytes) == 32
    return bytes_to_base64(key_bytes)


@pytest.fixture
def client_public_key():
    """Generate mock client public key (32 bytes base64-encoded)."""
    key_bytes = b"CLIENT_PUBLIC_KEY_32_BYTES!12345"
    assert len(key_bytes) == 32
    return bytes_to_base64(key_bytes)


@pytest.fixture
def encrypted_payload():
    """Generate mock encrypted payload."""
    return bytes_to_base64(b"Mock encrypted message content")


@pytest.fixture
def nonce_24bytes():
    """Generate mock 24-byte nonce for EncryptedBlob."""
    nonce = b"24_BYTE_NONCE_FOR_TEST!1"
    assert len(nonce) == 24
    return bytes_to_base64(nonce)


# ==============================================================================
# Test 1: Session Creation and Peer Pairing
# ==============================================================================


@pytest.mark.asyncio
async def test_create_session_and_pair_both_peers(
    workflow: RelayWorkflow,
    desktop_ws: MockWebSocket,
    client_ws: MockWebSocket,
    desktop_public_key: str,
    client_public_key: str,
):
    """Test scenario 1: Create session and pair both peers.

    Validates:
    - Desktop can create a session
    - Desktop can connect with session_id
    - Client can pair with pairing_code
    - Session state transitions correctly
    - Both peers are connected after pairing
    """
    # Step 1: Desktop creates session
    session_id, pairing_code = workflow.create_session(
        desktop_public_key=desktop_public_key
    )

    # Verify session_id and pairing_code are returned
    assert session_id is not None
    assert isinstance(session_id, SessionId)
    assert pairing_code is not None
    assert isinstance(pairing_code, PairingCode)

    # Step 2: Desktop connects WebSocket
    workflow.handle_desktop_connect(session_id=session_id, ws_connection=desktop_ws)

    # Step 3: Client pairs with pairing code
    returned_session_id, desktop_public_key_returned, desktop_ws_returned = workflow.handle_client_pair(
        pairing_code=pairing_code,
        client_public_key=client_public_key,
        ws_connection=client_ws,
    )

    # Verify client received correct session_id
    assert returned_session_id == session_id
    # Verify desktop info is returned for SessionPaired message
    assert desktop_public_key_returned is not None
    assert desktop_ws_returned == desktop_ws

    # Verify both peers are connected (check via repository)
    session = workflow._repository.get_by_id(session_id)
    assert session is not None
    assert session.state == SessionState.PAIRED
    assert session.desktop_ws == desktop_ws
    assert session.client_ws == client_ws


# ==============================================================================
# Test 2: Client Sends Message to Desktop
# ==============================================================================


@pytest.mark.asyncio
async def test_client_sends_encrypted_blob_to_desktop(
    workflow: RelayWorkflow,
    desktop_ws: MockWebSocket,
    client_ws: MockWebSocket,
    desktop_public_key: str,
    client_public_key: str,
    encrypted_payload: str,
    nonce_24bytes: str,
):
    """Test scenario 2: Client sends EncryptedBlob message to desktop.

    Validates:
    - Client can send message via route_message with sender=CLIENT
    - Desktop receives identical message on its WebSocket
    - Message contains correct session_id, sender, payload, nonce
    - Message type is relay.encrypted
    """
    # Setup: Create and pair session
    session_id, pairing_code = workflow.create_session(desktop_public_key)
    workflow.handle_desktop_connect(session_id, desktop_ws)
    workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

    # Create EncryptedBlob message from client
    client_message = EncryptedBlob(
        session_id=str(session_id),
        sender="client",
        payload=encrypted_payload,
        nonce=nonce_24bytes,
    )

    # Client sends message to desktop via workflow
    await workflow.route_message(
        session_id=session_id,
        sender=PeerRole.CLIENT,
        message=client_message,
    )

    # Verify desktop received the message
    desktop_messages = desktop_ws.get_sent_messages()
    assert len(desktop_messages) == 1

    # Verify message content is identical
    received_msg = desktop_messages[0]
    assert received_msg["type"] == "relay.encrypted"
    assert received_msg["session_id"] == str(session_id)
    assert received_msg["sender"] == "client"
    assert received_msg["payload"] == encrypted_payload
    assert received_msg["nonce"] == nonce_24bytes


# ==============================================================================
# Test 3: Desktop Sends Message to Client
# ==============================================================================


@pytest.mark.asyncio
async def test_desktop_sends_encrypted_blob_to_client(
    workflow: RelayWorkflow,
    desktop_ws: MockWebSocket,
    client_ws: MockWebSocket,
    desktop_public_key: str,
    client_public_key: str,
    encrypted_payload: str,
    nonce_24bytes: str,
):
    """Test scenario 3: Desktop sends EncryptedBlob message to client.

    Validates:
    - Desktop can send message via route_message with sender=DESKTOP
    - Client receives identical message on its WebSocket
    - Reverse direction routing works correctly
    """
    # Setup: Create and pair session
    session_id, pairing_code = workflow.create_session(desktop_public_key)
    workflow.handle_desktop_connect(session_id, desktop_ws)
    workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

    # Create EncryptedBlob message from desktop
    desktop_message = EncryptedBlob(
        session_id=str(session_id),
        sender="desktop",
        payload=encrypted_payload,
        nonce=nonce_24bytes,
    )

    # Desktop sends message to client via workflow
    await workflow.route_message(
        session_id=session_id,
        sender=PeerRole.DESKTOP,
        message=desktop_message,
    )

    # Verify client received the message
    client_messages = client_ws.get_sent_messages()
    assert len(client_messages) == 1

    # Verify message content is identical
    received_msg = client_messages[0]
    assert received_msg["type"] == "relay.encrypted"
    assert received_msg["session_id"] == str(session_id)
    assert received_msg["sender"] == "desktop"
    assert received_msg["payload"] == encrypted_payload
    assert received_msg["nonce"] == nonce_24bytes


# ==============================================================================
# Test 4: Bidirectional Communication
# ==============================================================================


@pytest.mark.asyncio
async def test_bidirectional_communication_simultaneous(
    workflow: RelayWorkflow,
    desktop_ws: MockWebSocket,
    client_ws: MockWebSocket,
    desktop_public_key: str,
    client_public_key: str,
):
    """Test scenario 4: Both peers send and receive simultaneously.

    Validates:
    - Both peers can send messages independently
    - Messages don't interfere with each other
    - Each peer receives only messages intended for them
    - Message order is preserved per direction
    """
    # Setup: Create and pair session
    session_id, pairing_code = workflow.create_session(desktop_public_key)
    workflow.handle_desktop_connect(session_id, desktop_ws)
    workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

    # Send multiple messages in both directions
    num_messages = 5

    for i in range(num_messages):
        # Client sends to desktop (pad to exactly 24 bytes)
        client_nonce = f"NONCE_CLIENT_{i:02d}_24_BYTES"
        assert len(client_nonce.encode()) == 24
        client_msg = EncryptedBlob(
            session_id=str(session_id),
            sender="client",
            payload=bytes_to_base64(f"Client message {i}".encode()),
            nonce=bytes_to_base64(client_nonce.encode()),
        )
        await workflow.route_message(session_id, PeerRole.CLIENT, client_msg)

        # Desktop sends to client (pad to exactly 24 bytes)
        desktop_nonce = f"NONCE_DESKTOP_{i:02d}_24BYTES"
        assert len(desktop_nonce.encode()) == 24
        desktop_msg = EncryptedBlob(
            session_id=str(session_id),
            sender="desktop",
            payload=bytes_to_base64(f"Desktop message {i}".encode()),
            nonce=bytes_to_base64(desktop_nonce.encode()),
        )
        await workflow.route_message(session_id, PeerRole.DESKTOP, desktop_msg)

    # Verify desktop received all client messages
    desktop_messages = desktop_ws.get_sent_messages()
    assert len(desktop_messages) == num_messages

    for i, msg in enumerate(desktop_messages):
        assert msg["type"] == "relay.encrypted"
        assert msg["sender"] == "client"
        expected_payload = bytes_to_base64(f"Client message {i}".encode())
        assert msg["payload"] == expected_payload

    # Verify client received all desktop messages
    client_messages = client_ws.get_sent_messages()
    assert len(client_messages) == num_messages

    for i, msg in enumerate(client_messages):
        assert msg["type"] == "relay.encrypted"
        assert msg["sender"] == "desktop"
        expected_payload = bytes_to_base64(f"Desktop message {i}".encode())
        assert msg["payload"] == expected_payload


# ==============================================================================
# Test 5: No Message Loss or Duplication
# ==============================================================================


@pytest.mark.asyncio
async def test_no_message_loss_or_duplication(
    workflow: RelayWorkflow,
    desktop_ws: MockWebSocket,
    client_ws: MockWebSocket,
    desktop_public_key: str,
    client_public_key: str,
):
    """Test scenario 5: Verify no message loss or duplication.

    Validates:
    - All sent messages are received exactly once
    - No messages are duplicated
    - No messages are lost
    - Message sequence numbers are preserved
    """
    # Setup: Create and pair session
    session_id, pairing_code = workflow.create_session(desktop_public_key)
    workflow.handle_desktop_connect(session_id, desktop_ws)
    workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

    # Send 10 messages from client to desktop
    num_messages = 10
    sent_payloads = []

    for i in range(num_messages):
        payload = bytes_to_base64(f"Message sequence {i:03d}".encode())
        sent_payloads.append(payload)

        # Pad nonce to exactly 24 bytes
        nonce_str = f"NONCE_{i:03d}_24_BYTES!!XYZW"
        assert len(nonce_str.encode()) == 24
        msg = EncryptedBlob(
            session_id=str(session_id),
            sender="client",
            payload=payload,
            nonce=bytes_to_base64(nonce_str.encode()),
        )
        await workflow.route_message(session_id, PeerRole.CLIENT, msg)

    # Verify all messages received in correct order
    desktop_messages = desktop_ws.get_sent_messages()
    assert len(desktop_messages) == num_messages, "Message count mismatch"

    received_payloads = [msg["payload"] for msg in desktop_messages]
    assert received_payloads == sent_payloads, "Messages lost or reordered"

    # Verify no duplicates
    assert len(received_payloads) == len(set(received_payloads)), "Duplicate messages detected"


# ==============================================================================
# Test 6: Large Message Handling (> 1MB)
# ==============================================================================


@pytest.mark.asyncio
async def test_large_message_handling_over_1mb(
    workflow: RelayWorkflow,
    desktop_ws: MockWebSocket,
    client_ws: MockWebSocket,
    desktop_public_key: str,
    client_public_key: str,
    nonce_24bytes: str,
):
    """Test scenario 6: Test large messages (payload > 1MB).

    Validates:
    - Large messages (>1MB) can be routed successfully
    - Message integrity is preserved for large payloads
    - No truncation or corruption occurs
    """
    # Setup: Create and pair session
    session_id, pairing_code = workflow.create_session(desktop_public_key)
    workflow.handle_desktop_connect(session_id, desktop_ws)
    workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

    # Create large payload (1.5 MB)
    large_payload_bytes = b"X" * (1024 * 1024 * 1 + 512 * 1024)  # 1.5 MB
    large_payload = bytes_to_base64(large_payload_bytes)

    # Verify payload is actually large
    payload_size_mb = len(large_payload) / (1024 * 1024)
    assert payload_size_mb > 1.0, f"Payload is only {payload_size_mb:.2f} MB"

    # Client sends large message to desktop
    large_msg = EncryptedBlob(
        session_id=str(session_id),
        sender="client",
        payload=large_payload,
        nonce=nonce_24bytes,
    )

    # Route the large message
    await workflow.route_message(session_id, PeerRole.CLIENT, large_msg)

    # Verify desktop received the complete message
    desktop_messages = desktop_ws.get_sent_messages()
    assert len(desktop_messages) == 1

    received_msg = desktop_messages[0]
    assert received_msg["type"] == "relay.encrypted"
    assert received_msg["payload"] == large_payload, "Large payload was corrupted"
    assert len(received_msg["payload"]) == len(large_payload), "Payload was truncated"


# ==============================================================================
# Test 7: Error Cases - Peer Not Connected
# ==============================================================================


@pytest.mark.asyncio
async def test_error_client_not_connected(
    workflow: RelayWorkflow,
    desktop_ws: MockWebSocket,
    desktop_public_key: str,
    encrypted_payload: str,
    nonce_24bytes: str,
):
    """Test error case: Desktop sends message when client not connected.

    Validates:
    - PeerNotConnectedException raised when recipient not connected
    - Error message indicates which peer is disconnected
    """
    # Setup: Create session with only desktop connected
    session_id, pairing_code = workflow.create_session(desktop_public_key)
    workflow.handle_desktop_connect(session_id, desktop_ws)
    # Note: Client never pairs

    # Create message from desktop to client
    msg = EncryptedBlob(
        session_id=str(session_id),
        sender="desktop",
        payload=encrypted_payload,
        nonce=nonce_24bytes,
    )

    # Attempt to route message should raise exception
    with pytest.raises(PeerNotConnectedException) as exc_info:
        await workflow.route_message(session_id, PeerRole.DESKTOP, msg)

    # Verify exception details
    assert exc_info.value.session_id == str(session_id)
    assert exc_info.value.peer_role == PeerRole.CLIENT
    assert "not connected" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_error_desktop_not_connected(
    workflow: RelayWorkflow,
    desktop_public_key: str,
    client_public_key: str,
    client_ws: MockWebSocket,
    encrypted_payload: str,
    nonce_24bytes: str,
):
    """Test error case: Client sends message when desktop not connected.

    Validates:
    - PeerNotConnectedException raised when desktop disconnected
    - Works correctly even if session is paired
    """
    # Setup: Create session, connect desktop, pair client, then simulate desktop disconnect
    session_id, pairing_code = workflow.create_session(desktop_public_key)

    # Create temporary desktop_ws for pairing
    temp_desktop_ws = MockWebSocket("temp_desktop")
    workflow.handle_desktop_connect(session_id, temp_desktop_ws)
    workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

    # Simulate desktop disconnect by setting desktop_ws to None
    session = workflow._repository.get_by_id(session_id)
    session._desktop_ws = None

    # Create message from client to desktop
    msg = EncryptedBlob(
        session_id=str(session_id),
        sender="client",
        payload=encrypted_payload,
        nonce=nonce_24bytes,
    )

    # Attempt to route message should raise exception
    with pytest.raises(PeerNotConnectedException) as exc_info:
        await workflow.route_message(session_id, PeerRole.CLIENT, msg)

    # Verify exception details
    assert exc_info.value.session_id == str(session_id)
    assert exc_info.value.peer_role == PeerRole.DESKTOP


# ==============================================================================
# Test 8: Error Cases - Invalid Session
# ==============================================================================


@pytest.mark.asyncio
async def test_error_invalid_session_id(
    workflow: RelayWorkflow,
    encrypted_payload: str,
    nonce_24bytes: str,
):
    """Test error case: Route message to non-existent session.

    Validates:
    - SessionNotFoundException raised for invalid session_id
    - Exception contains helpful error context
    """
    # Create fake session_id that doesn't exist
    fake_session_id = SessionId("00000000-0000-0000-0000-000000000000")

    # Create message
    msg = EncryptedBlob(
        session_id=str(fake_session_id),
        sender="client",
        payload=encrypted_payload,
        nonce=nonce_24bytes,
    )

    # Attempt to route message should raise exception
    with pytest.raises(SessionNotFoundException) as exc_info:
        await workflow.route_message(fake_session_id, PeerRole.CLIENT, msg)

    # Verify exception details
    assert exc_info.value.session_id == str(fake_session_id)
    assert "not found" in str(exc_info.value).lower()


# ==============================================================================
# Test 9: Message Integrity - Payload and Nonce Preservation
# ==============================================================================


@pytest.mark.asyncio
async def test_message_integrity_payload_and_nonce(
    workflow: RelayWorkflow,
    desktop_ws: MockWebSocket,
    client_ws: MockWebSocket,
    desktop_public_key: str,
    client_public_key: str,
):
    """Test message integrity: Verify payload and nonce are preserved exactly.

    Validates:
    - Base64-encoded payload is not modified during routing
    - Nonce is exactly 24 bytes and preserved
    - Session ID is preserved
    - Sender field is preserved
    """
    # Setup: Create and pair session
    session_id, pairing_code = workflow.create_session(desktop_public_key)
    workflow.handle_desktop_connect(session_id, desktop_ws)
    workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

    # Create message with specific payload and nonce
    original_payload = bytes_to_base64(b"Test payload with special chars: \x00\x01\x02\xff")
    original_nonce = bytes_to_base64(b"EXACTLY_24_BYTES_NONCE!!")

    msg = EncryptedBlob(
        session_id=str(session_id),
        sender="client",
        payload=original_payload,
        nonce=original_nonce,
    )

    # Route message
    await workflow.route_message(session_id, PeerRole.CLIENT, msg)

    # Verify received message is identical
    desktop_messages = desktop_ws.get_sent_messages()
    received_msg = desktop_messages[0]

    assert received_msg["session_id"] == str(session_id)
    assert received_msg["sender"] == "client"
    assert received_msg["payload"] == original_payload
    assert received_msg["nonce"] == original_nonce

    # Verify nonce decodes to exactly 24 bytes
    from agent_remote.shared.protocol.base import base64_to_bytes
    nonce_bytes = base64_to_bytes(received_msg["nonce"])
    assert len(nonce_bytes) == 24


# ==============================================================================
# Test 10: Session Cleanup
# ==============================================================================


@pytest.mark.asyncio
async def test_session_cleanup_closes_session(
    workflow: RelayWorkflow,
    desktop_ws: MockWebSocket,
    client_ws: MockWebSocket,
    desktop_public_key: str,
    client_public_key: str,
):
    """Test session cleanup: Verify close_session removes session.

    Validates:
    - close_session removes session from repository
    - Subsequent routing attempts fail with SessionNotFoundException
    - Session state is properly cleaned up
    """
    # Setup: Create and pair session
    session_id, pairing_code = workflow.create_session(desktop_public_key)
    workflow.handle_desktop_connect(session_id, desktop_ws)
    workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

    # Verify session exists
    session = workflow._repository.get_by_id(session_id)
    assert session is not None

    # Close session
    workflow.close_session(session_id, reason="Test cleanup")

    # Verify session is removed
    session = workflow._repository.get_by_id(session_id)
    assert session is None

    # Verify routing fails after close
    msg = EncryptedBlob(
        session_id=str(session_id),
        sender="client",
        payload=bytes_to_base64(b"test"),
        nonce=bytes_to_base64(b"NONCE_24_BYTES_FOR_TEST!"),
    )

    with pytest.raises(SessionNotFoundException):
        await workflow.route_message(session_id, PeerRole.CLIENT, msg)


# ==============================================================================
# Test Summary
# ==============================================================================

# Test coverage:
# 1. test_create_session_and_pair_both_peers - Session lifecycle
# 2. test_client_sends_encrypted_blob_to_desktop - Client->Desktop routing
# 3. test_desktop_sends_encrypted_blob_to_client - Desktop->Client routing
# 4. test_bidirectional_communication_simultaneous - Bidirectional routing
# 5. test_no_message_loss_or_duplication - Message reliability
# 6. test_large_message_handling_over_1mb - Large payload handling
# 7. test_error_client_not_connected - Error: client not connected
# 8. test_error_desktop_not_connected - Error: desktop not connected
# 9. test_error_invalid_session_id - Error: invalid session
# 10. test_message_integrity_payload_and_nonce - Message integrity
# 11. test_session_cleanup_closes_session - Session cleanup

# All tests validate the route_message method and message routing pipeline.
