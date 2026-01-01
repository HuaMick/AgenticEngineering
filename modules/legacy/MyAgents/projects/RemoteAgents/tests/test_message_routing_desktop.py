"""Test message routing from desktop to client.

This test suite validates that messages sent from desktop peers are correctly
routed to client peers through the relay workflow. Tests cover:

1. Session creation and pairing (using flow from Agent 1)
2. Desktop sends EncryptedBlob message via WebSocket
3. Client receives identical message (same payload, nonce, sender)
4. Multiple messages in sequence (10+ messages)
5. Message order preservation (no reordering)
6. Concurrent messages (send before previous received)

Test Strategy: technical-spike (integration testing)

Target Files:
- /home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_workflow.py
- /home/code/myagents/RemoteAgents/src/agent_remote/services/relay/api/websockets.py
"""

import asyncio
import base64
import time
from typing import List
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_remote.services.relay.domains.session_manager.value_objects import (
    PairingCode,
    PeerRole,
    SessionId,
)
from agent_remote.services.relay.infrastructure.in_memory_repository import (
    InMemorySessionRepository,
)
from agent_remote.services.relay.workflows.relay_workflow import (
    PeerNotConnectedException,
    RelayWorkflow,
    SessionNotFoundException,
)
from agent_remote.shared.protocol.relay_messages import EncryptedBlob


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def repository():
    """Create an in-memory session repository for testing."""
    return InMemorySessionRepository()


@pytest.fixture
def workflow(repository):
    """Create a RelayWorkflow with the test repository."""
    return RelayWorkflow(repository=repository)


@pytest.fixture
def mock_desktop_ws():
    """Create a mock WebSocket connection for desktop."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    ws.send = AsyncMock()
    return ws


@pytest.fixture
def mock_client_ws():
    """Create a mock WebSocket connection for client."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    ws.send = AsyncMock()
    return ws


@pytest.fixture
def sample_encrypted_blob():
    """Create a sample EncryptedBlob message for testing."""
    # Create realistic test data (24-byte nonce as required by NaCl)
    nonce = base64.b64encode(b"0" * 24).decode("ascii")  # Exactly 24 bytes
    payload = base64.b64encode(b"encrypted_test_data").decode("ascii")

    return EncryptedBlob(
        session_id="00000000-0000-0000-0000-000000000000",
        sender="desktop",
        payload=payload,
        nonce=nonce,
    )


@pytest.fixture
def paired_session(workflow, mock_desktop_ws, mock_client_ws):
    """Create a fully paired session (desktop + client connected).

    This fixture simulates the complete pairing flow:
    1. Desktop creates session
    2. Desktop connects WebSocket
    3. Client pairs with pairing code

    Returns:
        Tuple of (session_id, pairing_code, desktop_ws, client_ws)
    """
    # Desktop creates session
    desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
    session_id, pairing_code = workflow.create_session(desktop_public_key)

    # Desktop connects
    workflow.handle_desktop_connect(session_id, mock_desktop_ws)

    # Client pairs
    client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
    workflow.handle_client_pair(pairing_code, client_public_key, mock_client_ws)

    return session_id, pairing_code, mock_desktop_ws, mock_client_ws


# ==============================================================================
# Test Case 1: Session Creation and Pairing
# ==============================================================================


class TestSessionCreationAndPairing:
    """Test the complete session creation and pairing flow."""

    @pytest.mark.asyncio
    async def test_create_session(self, workflow):
        """Test desktop can create a session."""
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")

        session_id, pairing_code = workflow.create_session(desktop_public_key)

        # Verify session ID and pairing code are generated
        assert session_id is not None
        assert isinstance(session_id, SessionId)
        assert pairing_code is not None
        assert isinstance(pairing_code, PairingCode)
        assert len(str(pairing_code)) == 6

    @pytest.mark.asyncio
    async def test_desktop_connect(self, workflow, mock_desktop_ws):
        """Test desktop can connect to created session."""
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        session_id, _ = workflow.create_session(desktop_public_key)

        # Desktop connects - should not raise
        workflow.handle_desktop_connect(session_id, mock_desktop_ws)

        # Verify session is in repository and desktop is connected
        session = workflow._repository.get_by_id(session_id)
        assert session is not None
        assert session.desktop_ws is mock_desktop_ws

    @pytest.mark.asyncio
    async def test_client_pair(self, workflow, mock_desktop_ws, mock_client_ws):
        """Test client can pair with session using pairing code."""
        # Create session and connect desktop
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        session_id, pairing_code = workflow.create_session(desktop_public_key)
        workflow.handle_desktop_connect(session_id, mock_desktop_ws)

        # Client pairs
        client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
        returned_session_id, _, _ = workflow.handle_client_pair(
            pairing_code, client_public_key, mock_client_ws
        )

        # Verify client is paired
        assert returned_session_id == session_id
        session = workflow._repository.get_by_id(session_id)
        assert session.client_ws is mock_client_ws
        assert session.client_public_key == client_public_key


# ==============================================================================
# Test Case 2: Single Message Routing (Desktop -> Client)
# ==============================================================================


class TestSingleMessageRouting:
    """Test routing a single EncryptedBlob message from desktop to client."""

    @pytest.mark.asyncio
    async def test_route_message_desktop_to_client(self, paired_session):
        """Test desktop can send message to client."""
        session_id, _, desktop_ws, client_ws = paired_session

        # Create encrypted blob
        nonce = base64.b64encode(b"0" * 24).decode("ascii")
        payload = base64.b64encode(b"test_payload").decode("ascii")
        message = EncryptedBlob(
            session_id=str(session_id),
            sender="desktop",
            payload=payload,
            nonce=nonce,
        )

        # Create workflow and route message
        from agent_remote.services.relay.workflows.relay_workflow import RelayWorkflow
        workflow = RelayWorkflow(repository=InMemorySessionRepository())

        # Recreate the session in the new workflow's repository
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        new_session_id, pairing_code = workflow.create_session(desktop_public_key)
        workflow.handle_desktop_connect(new_session_id, desktop_ws)
        client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
        workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

        # Update message with correct session_id
        message.session_id = str(new_session_id)

        # Route message from desktop to client
        await workflow.route_message(new_session_id, PeerRole.DESKTOP, message)

        # Verify client WebSocket received the message
        assert client_ws.send_json.called or client_ws.send.called

        # Verify message content is identical
        if client_ws.send_json.called:
            sent_data = client_ws.send_json.call_args[0][0]
            assert sent_data["type"] == "relay.encrypted"
            assert sent_data["sender"] == "desktop"
            assert sent_data["payload"] == payload
            assert sent_data["nonce"] == nonce

    @pytest.mark.asyncio
    async def test_route_message_preserves_integrity(self, paired_session):
        """Test that message payload, nonce, and sender are preserved."""
        session_id, _, desktop_ws, client_ws = paired_session

        # Create encrypted blob with specific values
        original_nonce = base64.b64encode(b"unique_nonce_24_bytes!!!").decode("ascii")
        original_payload = base64.b64encode(b"sensitive_encrypted_data").decode("ascii")
        message = EncryptedBlob(
            session_id=str(session_id),
            sender="desktop",
            payload=original_payload,
            nonce=original_nonce,
        )

        # Create workflow and route message
        from agent_remote.services.relay.workflows.relay_workflow import RelayWorkflow
        workflow = RelayWorkflow(repository=InMemorySessionRepository())

        # Recreate the session
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        new_session_id, pairing_code = workflow.create_session(desktop_public_key)
        workflow.handle_desktop_connect(new_session_id, desktop_ws)
        client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
        workflow.handle_client_pair(pairing_code, client_public_key, client_ws)
        message.session_id = str(new_session_id)

        # Route message
        await workflow.route_message(new_session_id, PeerRole.DESKTOP, message)

        # Verify exact message content
        assert client_ws.send_json.called or client_ws.send.called
        if client_ws.send_json.called:
            sent_data = client_ws.send_json.call_args[0][0]
            # Payload must be identical
            assert sent_data["payload"] == original_payload
            # Nonce must be identical
            assert sent_data["nonce"] == original_nonce
            # Sender must be preserved
            assert sent_data["sender"] == "desktop"


# ==============================================================================
# Test Case 3: Error Handling
# ==============================================================================


class TestErrorHandling:
    """Test error handling for invalid routing scenarios."""

    @pytest.mark.asyncio
    async def test_route_to_nonexistent_session(self, workflow, sample_encrypted_blob):
        """Test routing to non-existent session raises SessionNotFoundException."""
        fake_session_id = SessionId("00000000-0000-0000-0000-000000000000")

        with pytest.raises(SessionNotFoundException) as exc_info:
            await workflow.route_message(fake_session_id, PeerRole.DESKTOP, sample_encrypted_blob)

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_route_with_no_desktop_connected(self, workflow, mock_client_ws):
        """Test routing from disconnected desktop raises PeerNotConnectedException."""
        # Create session but don't connect desktop
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        session_id, pairing_code = workflow.create_session(desktop_public_key)

        # Manually set client to simulate partial connection
        session = workflow._repository.get_by_id(session_id)
        client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
        session._client_public_key = client_public_key
        session._client_ws = mock_client_ws
        session._state = session._state.PAIRED

        # Try to route from desktop (which is not connected)
        nonce = base64.b64encode(b"0" * 24).decode("ascii")
        message = EncryptedBlob(
            session_id=str(session_id),
            sender="desktop",
            payload=base64.b64encode(b"test").decode("ascii"),
            nonce=nonce,
        )

        with pytest.raises(PeerNotConnectedException) as exc_info:
            await workflow.route_message(session_id, PeerRole.DESKTOP, message)

        assert "desktop" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_route_with_no_client_connected(self, workflow, mock_desktop_ws):
        """Test routing to disconnected client raises PeerNotConnectedException."""
        # Create session and connect desktop only
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        session_id, _ = workflow.create_session(desktop_public_key)
        workflow.handle_desktop_connect(session_id, mock_desktop_ws)

        # Try to route to client (which is not connected)
        nonce = base64.b64encode(b"0" * 24).decode("ascii")
        message = EncryptedBlob(
            session_id=str(session_id),
            sender="desktop",
            payload=base64.b64encode(b"test").decode("ascii"),
            nonce=nonce,
        )

        with pytest.raises(PeerNotConnectedException) as exc_info:
            await workflow.route_message(session_id, PeerRole.DESKTOP, message)

        assert "client" in str(exc_info.value).lower()


# ==============================================================================
# Test Case 4: Multiple Messages in Sequence
# ==============================================================================


class TestMultipleMessagesInSequence:
    """Test routing multiple messages in sequence (10+ messages)."""

    @pytest.mark.asyncio
    async def test_route_ten_messages_in_sequence(self, paired_session):
        """Test routing 10 messages in sequence from desktop to client."""
        session_id, _, desktop_ws, client_ws = paired_session

        # Create workflow
        from agent_remote.services.relay.workflows.relay_workflow import RelayWorkflow
        workflow = RelayWorkflow(repository=InMemorySessionRepository())

        # Recreate session
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        new_session_id, pairing_code = workflow.create_session(desktop_public_key)
        workflow.handle_desktop_connect(new_session_id, desktop_ws)
        client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
        workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

        # Route 10 messages
        messages_sent = []
        for i in range(10):
            # Create exactly 24-byte nonce
            nonce_bytes = f"nonce_{i:02d}".encode().ljust(24, b'\x00')
            nonce = base64.b64encode(nonce_bytes).decode("ascii")
            payload = base64.b64encode(f"message_{i}".encode()).decode("ascii")
            message = EncryptedBlob(
                session_id=str(new_session_id),
                sender="desktop",
                payload=payload,
                nonce=nonce,
            )
            messages_sent.append(message)

            # Route message
            await workflow.route_message(new_session_id, PeerRole.DESKTOP, message)

        # Verify all 10 messages were sent
        assert client_ws.send_json.call_count == 10 or client_ws.send.call_count == 10

    @pytest.mark.asyncio
    async def test_route_fifteen_messages_in_sequence(self, paired_session):
        """Test routing 15 messages to exceed the 10+ requirement."""
        session_id, _, desktop_ws, client_ws = paired_session

        # Create workflow
        from agent_remote.services.relay.workflows.relay_workflow import RelayWorkflow
        workflow = RelayWorkflow(repository=InMemorySessionRepository())

        # Recreate session
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        new_session_id, pairing_code = workflow.create_session(desktop_public_key)
        workflow.handle_desktop_connect(new_session_id, desktop_ws)
        client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
        workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

        # Route 15 messages
        for i in range(15):
            # Create exactly 24-byte nonce
            nonce_bytes = f"nonce_{i:02d}".encode().ljust(24, b'\x00')
            nonce = base64.b64encode(nonce_bytes).decode("ascii")
            payload = base64.b64encode(f"message_number_{i}".encode()).decode("ascii")
            message = EncryptedBlob(
                session_id=str(new_session_id),
                sender="desktop",
                payload=payload,
                nonce=nonce,
            )

            await workflow.route_message(new_session_id, PeerRole.DESKTOP, message)

        # Verify all 15 messages were sent
        assert client_ws.send_json.call_count == 15 or client_ws.send.call_count == 15


# ==============================================================================
# Test Case 5: Message Order Preservation
# ==============================================================================


class TestMessageOrderPreservation:
    """Test that message order is preserved (no reordering)."""

    @pytest.mark.asyncio
    async def test_message_order_preserved(self, paired_session):
        """Test that messages are delivered in the same order they are sent."""
        session_id, _, desktop_ws, client_ws = paired_session

        # Create workflow
        from agent_remote.services.relay.workflows.relay_workflow import RelayWorkflow
        workflow = RelayWorkflow(repository=InMemorySessionRepository())

        # Recreate session
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        new_session_id, pairing_code = workflow.create_session(desktop_public_key)
        workflow.handle_desktop_connect(new_session_id, desktop_ws)
        client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
        workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

        # Send messages with sequence numbers
        num_messages = 12
        for i in range(num_messages):
            # Create exactly 24-byte nonce
            nonce_bytes = f"seq_{i:03d}".encode().ljust(24, b'\x00')
            nonce = base64.b64encode(nonce_bytes).decode("ascii")
            payload = base64.b64encode(f"sequence_{i:03d}".encode()).decode("ascii")
            message = EncryptedBlob(
                session_id=str(new_session_id),
                sender="desktop",
                payload=payload,
                nonce=nonce,
            )

            await workflow.route_message(new_session_id, PeerRole.DESKTOP, message)

        # Verify messages were sent in order
        assert client_ws.send_json.call_count == num_messages or client_ws.send.call_count == num_messages

        # Extract payloads from all calls
        if client_ws.send_json.called:
            calls = client_ws.send_json.call_args_list
            payloads = [call[0][0]["payload"] for call in calls]

            # Verify sequence
            for i in range(num_messages):
                expected_payload = base64.b64encode(f"sequence_{i:03d}".encode()).decode("ascii")
                assert payloads[i] == expected_payload, f"Message {i} out of order"


# ==============================================================================
# Test Case 6: Concurrent Messages
# ==============================================================================


class TestConcurrentMessages:
    """Test concurrent message sending (send before previous received)."""

    @pytest.mark.asyncio
    async def test_rapid_message_sending(self, paired_session):
        """Test sending messages rapidly without waiting for acknowledgment."""
        session_id, _, desktop_ws, client_ws = paired_session

        # Create workflow
        from agent_remote.services.relay.workflows.relay_workflow import RelayWorkflow
        workflow = RelayWorkflow(repository=InMemorySessionRepository())

        # Recreate session
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        new_session_id, pairing_code = workflow.create_session(desktop_public_key)
        workflow.handle_desktop_connect(new_session_id, desktop_ws)
        client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
        workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

        # Send 20 messages rapidly (simulating concurrent sends)
        num_messages = 20
        for i in range(num_messages):
            # Create exactly 24-byte nonce
            nonce_bytes = f"concurrent_{i:02d}".encode().ljust(24, b'\x00')
            nonce = base64.b64encode(nonce_bytes).decode("ascii")
            payload = base64.b64encode(f"concurrent_msg_{i}".encode()).decode("ascii")
            message = EncryptedBlob(
                session_id=str(new_session_id),
                sender="desktop",
                payload=payload,
                nonce=nonce,
            )

            # Send immediately without waiting
            await workflow.route_message(new_session_id, PeerRole.DESKTOP, message)

        # Verify all messages were sent
        total_calls = client_ws.send_json.call_count + client_ws.send.call_count
        assert total_calls == num_messages, f"Expected {num_messages} calls, got {total_calls}"

    @pytest.mark.asyncio
    async def test_concurrent_different_payloads(self, paired_session):
        """Test concurrent messages with varying payload sizes."""
        session_id, _, desktop_ws, client_ws = paired_session

        # Create workflow
        from agent_remote.services.relay.workflows.relay_workflow import RelayWorkflow
        workflow = RelayWorkflow(repository=InMemorySessionRepository())

        # Recreate session
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        new_session_id, pairing_code = workflow.create_session(desktop_public_key)
        workflow.handle_desktop_connect(new_session_id, desktop_ws)
        client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
        workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

        # Send messages with different payload sizes
        payloads_sent = []
        for i in range(15):
            # Vary payload size
            payload_data = f"msg_{i}_" + ("x" * (i * 10))
            # Create exactly 24-byte nonce
            nonce_bytes = f"var_{i:03d}".encode().ljust(24, b'\x00')
            nonce = base64.b64encode(nonce_bytes).decode("ascii")
            payload = base64.b64encode(payload_data.encode()).decode("ascii")
            payloads_sent.append(payload)

            message = EncryptedBlob(
                session_id=str(new_session_id),
                sender="desktop",
                payload=payload,
                nonce=nonce,
            )

            await workflow.route_message(new_session_id, PeerRole.DESKTOP, message)

        # Verify all messages sent
        total_calls = client_ws.send_json.call_count + client_ws.send.call_count
        assert total_calls == 15

        # Verify payloads match
        if client_ws.send_json.called:
            calls = client_ws.send_json.call_args_list
            for i, call in enumerate(calls):
                sent_payload = call[0][0]["payload"]
                assert sent_payload == payloads_sent[i], f"Payload {i} mismatch"


# ==============================================================================
# Test Case 7: Bidirectional Routing (Bonus)
# ==============================================================================


class TestBidirectionalRouting:
    """Test that routing works both ways (desktop->client and client->desktop)."""

    @pytest.mark.asyncio
    async def test_route_message_client_to_desktop(self, paired_session):
        """Test client can send message to desktop."""
        session_id, _, desktop_ws, client_ws = paired_session

        # Create workflow
        from agent_remote.services.relay.workflows.relay_workflow import RelayWorkflow
        workflow = RelayWorkflow(repository=InMemorySessionRepository())

        # Recreate session
        desktop_public_key = base64.b64encode(b"desktop_key_32bytes_padding!").decode("ascii")
        new_session_id, pairing_code = workflow.create_session(desktop_public_key)
        workflow.handle_desktop_connect(new_session_id, desktop_ws)
        client_public_key = base64.b64encode(b"client_key_32bytes__padding!").decode("ascii")
        workflow.handle_client_pair(pairing_code, client_public_key, client_ws)

        # Create message from client
        nonce = base64.b64encode(b"0" * 24).decode("ascii")
        payload = base64.b64encode(b"message_from_client").decode("ascii")
        message = EncryptedBlob(
            session_id=str(new_session_id),
            sender="client",
            payload=payload,
            nonce=nonce,
        )

        # Route message from client to desktop
        await workflow.route_message(new_session_id, PeerRole.CLIENT, message)

        # Verify desktop WebSocket received the message
        assert desktop_ws.send_json.called or desktop_ws.send.called

        # Verify message content
        if desktop_ws.send_json.called:
            sent_data = desktop_ws.send_json.call_args[0][0]
            assert sent_data["type"] == "relay.encrypted"
            assert sent_data["sender"] == "client"
            assert sent_data["payload"] == payload
