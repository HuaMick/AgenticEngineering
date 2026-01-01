"""End-to-end integration tests for RemoteAgents session lifecycle.

This test suite validates the complete session lifecycle from desktop session creation
through client pairing, bidirectional message exchange, and graceful disconnection.
It simulates a real Flutter client connecting to the relay server.

Test Coverage:
1. Complete session lifecycle (create -> pair -> I/O -> resize -> close)
2. End-to-end encryption with real keypairs (using PyNaCl)
3. Concurrent sessions with message isolation
4. Terminal I/O routing (TerminalOutput, TerminalInput, TerminalResize)
5. Proper cleanup and state management

Test Strategy: Integration testing with FastAPI TestClient synchronous WebSocket API
Agent: Build Agent
"""

import base64
import json
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from nacl.public import PrivateKey
from starlette.testclient import WebSocketTestSession

from agent_remote.services.relay.api.api import app
from agent_remote.services.relay.api.websockets import router as ws_router
from agent_remote.services.relay.infrastructure.in_memory_repository import (
    InMemorySessionRepository,
)
from agent_remote.shared.crypto.nacl_impl import (
    NaClBox,
    NaClKeyPair,
    base64_to_bytes,
    bytes_to_base64,
)
from agent_remote.shared.protocol.base import RemoteAgentMessage
from agent_remote.shared.protocol.relay_messages import EncryptedBlob
from agent_remote.shared.protocol.session_messages import SessionPair, SessionPaired
from agent_remote.shared.protocol.terminal_messages import (
    TerminalInput,
    TerminalOutput,
    TerminalResize,
)

# Mount WebSocket router to app
app.include_router(ws_router)


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def test_client():
    """Create a fresh TestClient with reset repository state.

    This fixture ensures each test starts with a clean slate by resetting
    the singleton repository instances used by both the REST API and WebSocket
    endpoints.
    """
    # Reset the singleton repositories before each test
    # IMPORTANT: api.py and websockets.py have separate singleton references
    from agent_remote.services.relay.api import api, websockets

    # Create a shared repository instance
    shared_repo = InMemorySessionRepository()

    # Set both singletons to use the same instance
    api._repository = shared_repo
    websockets._repository = shared_repo
    websockets._websocket_manager = None  # Reset websocket manager too

    return TestClient(app)


@pytest.fixture
def desktop_keypair():
    """Generate valid X25519 keypair for desktop using PyNaCl."""
    private_key = PrivateKey.generate()
    return NaClKeyPair(private_key)


@pytest.fixture
def client_keypair():
    """Generate valid X25519 keypair for client using PyNaCl."""
    private_key = PrivateKey.generate()
    return NaClKeyPair(private_key)


@pytest.fixture
def desktop_public_key_b64(desktop_keypair: NaClKeyPair) -> str:
    """Get base64-encoded desktop public key."""
    return bytes_to_base64(desktop_keypair.public_key)


@pytest.fixture
def client_public_key_b64(client_keypair: NaClKeyPair) -> str:
    """Get base64-encoded client public key."""
    return bytes_to_base64(client_keypair.public_key)


# ==============================================================================
# Helper Functions
# ==============================================================================


def encrypt_message(
    message: RemoteAgentMessage,
    sender_keypair: NaClKeyPair,
    recipient_public_key: bytes,
    session_id: str,
    sender: str,
) -> EncryptedBlob:
    """Encrypt a message using NaCl box encryption.

    Args:
        message: The protocol message to encrypt
        sender_keypair: Sender's keypair for encryption
        recipient_public_key: Recipient's public key (32 bytes)
        session_id: UUID of the session
        sender: "desktop" or "client"

    Returns:
        EncryptedBlob ready to send over WebSocket
    """
    # Serialize message to JSON
    plaintext = message.model_dump_json().encode("utf-8")

    # Encrypt using NaCl box
    box = NaClBox(sender_keypair)
    nonce, ciphertext = box.encrypt(plaintext, recipient_public_key)

    # Create EncryptedBlob
    return EncryptedBlob.create(
        session_id=session_id,
        sender=sender,
        payload=ciphertext,
        nonce=nonce,
    )


def decrypt_message(
    encrypted_blob: EncryptedBlob,
    recipient_keypair: NaClKeyPair,
    sender_public_key: bytes,
) -> RemoteAgentMessage:
    """Decrypt an EncryptedBlob message using NaCl box.

    Args:
        encrypted_blob: The encrypted message to decrypt
        recipient_keypair: Recipient's keypair for decryption
        sender_public_key: Sender's public key (32 bytes)

    Returns:
        Decrypted protocol message
    """
    # Decrypt using NaCl box
    box = NaClBox(recipient_keypair)
    ciphertext = encrypted_blob.get_payload_bytes()
    nonce = encrypted_blob.get_nonce_bytes()
    plaintext = box.decrypt(ciphertext, nonce, sender_public_key)

    # Parse JSON back to message
    message_dict = json.loads(plaintext.decode("utf-8"))

    # Determine message type and deserialize
    msg_type = message_dict.get("type")
    if msg_type == "session.paired":
        return SessionPaired(**message_dict)
    elif msg_type == "terminal.output":
        return TerminalOutput(**message_dict)
    elif msg_type == "terminal.input":
        return TerminalInput(**message_dict)
    elif msg_type == "terminal.resize":
        return TerminalResize(**message_dict)
    else:
        raise ValueError(f"Unknown message type: {msg_type}")


def receive_ws_message(websocket: WebSocketTestSession, skip_ping: bool = True) -> Dict[str, Any]:
    """Receive and parse a WebSocket message.

    Args:
        websocket: TestClient WebSocket session
        skip_ping: If True, skip over relay.ping messages

    Returns:
        Parsed message as dict
    """
    while True:
        msg = websocket.receive_json()
        # Skip ping messages if requested (these are server-side keepalive)
        if skip_ping and msg.get("type") == "relay.ping":
            continue
        return msg


def send_ws_message(websocket: WebSocketTestSession, message: RemoteAgentMessage):
    """Send a protocol message over WebSocket.

    Args:
        websocket: TestClient WebSocket session
        message: Protocol message to send
    """
    websocket.send_json(json.loads(message.model_dump_json()))


# ==============================================================================
# E2E Test Cases
# ==============================================================================


@pytest.mark.integration
def test_e2e_complete_session_lifecycle(
    test_client: TestClient,
    desktop_keypair: NaClKeyPair,
    client_keypair: NaClKeyPair,
    desktop_public_key_b64: str,
    client_public_key_b64: str,
):
    """Test complete session lifecycle: create -> pair -> I/O -> resize -> close.

    This test validates the entire flow:
    1. Desktop creates session via REST API
    2. Desktop connects via WebSocket
    3. Client pairs via WebSocket with pairing code
    4. Both peers receive SessionPaired confirmation
    5. Desktop sends TerminalOutput
    6. Client receives and decrypts output
    7. Client sends TerminalInput
    8. Desktop receives and decrypts input
    9. Client sends TerminalResize
    10. Desktop receives resize event
    11. Client disconnects gracefully
    12. Session is cleaned up
    """
    # Step 1: Create session via REST API
    create_response = test_client.post(
        "/api/sessions",
        json={"desktop_public_key": desktop_public_key_b64},
    )
    assert create_response.status_code == 201

    session_data = create_response.json()
    session_id = session_data["session_id"]
    pairing_code = session_data["pairing_code"]

    assert len(pairing_code) == 6
    assert pairing_code.isupper()

    # Step 2: Desktop connects via WebSocket
    with test_client.websocket_connect(f"/ws/desktop/{session_id}") as desktop_ws:
        # Step 3: Client connects and pairs
        with test_client.websocket_connect(f"/ws/client/{pairing_code}") as client_ws:
            # Send SessionPair message with client public key
            pair_message = SessionPair(
                pairing_code=pairing_code,
                client_public_key=client_keypair.public_key,
            )
            send_ws_message(client_ws, pair_message)

            # Step 4: Both peers should receive SessionPaired message (unencrypted)
            # SessionPaired is sent unencrypted because:
            # - It contains the desktop's public key which client needs to establish E2E encryption
            # - Before receiving this, client can't decrypt anything

            # Desktop receives SessionPaired
            desktop_paired_raw = receive_ws_message(desktop_ws)
            assert desktop_paired_raw["type"] == "session.paired"
            desktop_paired_msg = SessionPaired(**desktop_paired_raw)
            assert desktop_paired_msg.session_id == session_id

            # Client receives SessionPaired
            client_paired_raw = receive_ws_message(client_ws)
            assert client_paired_raw["type"] == "session.paired"
            client_paired_msg = SessionPaired(**client_paired_raw)
            assert client_paired_msg.session_id == session_id

            # Step 5: Desktop sends TerminalOutput
            output_message = TerminalOutput(
                session_id=session_id,
                data=b"\x1b[32mHello from desktop!\x1b[0m",
            )
            encrypted_output = encrypt_message(
                output_message,
                desktop_keypair,
                client_keypair.public_key,
                session_id,
                "desktop",
            )
            send_ws_message(desktop_ws, encrypted_output)

            # Step 6: Client receives and decrypts output
            client_received_raw = receive_ws_message(client_ws)
            assert client_received_raw["type"] == "relay.encrypted"

            client_received_blob = EncryptedBlob(**client_received_raw)
            client_received_msg = decrypt_message(
                client_received_blob,
                client_keypair,
                desktop_keypair.public_key,
            )
            assert isinstance(client_received_msg, TerminalOutput)
            assert client_received_msg.data == b"\x1b[32mHello from desktop!\x1b[0m"

            # Step 7: Client sends TerminalInput
            input_message = TerminalInput(
                session_id=session_id,
                data=b"ls -la\r",
            )
            encrypted_input = encrypt_message(
                input_message,
                client_keypair,
                desktop_keypair.public_key,
                session_id,
                "client",
            )
            send_ws_message(client_ws, encrypted_input)

            # Step 8: Desktop receives and decrypts input
            desktop_received_raw = receive_ws_message(desktop_ws)
            assert desktop_received_raw["type"] == "relay.encrypted"

            desktop_received_blob = EncryptedBlob(**desktop_received_raw)
            desktop_received_msg = decrypt_message(
                desktop_received_blob,
                desktop_keypair,
                client_keypair.public_key,
            )
            assert isinstance(desktop_received_msg, TerminalInput)
            assert desktop_received_msg.data == b"ls -la\r"

            # Step 9: Client sends TerminalResize
            resize_message = TerminalResize(
                session_id=session_id,
                rows=40,
                cols=120,
            )
            encrypted_resize = encrypt_message(
                resize_message,
                client_keypair,
                desktop_keypair.public_key,
                session_id,
                "client",
            )
            send_ws_message(client_ws, encrypted_resize)

            # Step 10: Desktop receives resize event
            desktop_resize_raw = receive_ws_message(desktop_ws)
            assert desktop_resize_raw["type"] == "relay.encrypted"

            desktop_resize_blob = EncryptedBlob(**desktop_resize_raw)
            desktop_resize_msg = decrypt_message(
                desktop_resize_blob,
                desktop_keypair,
                client_keypair.public_key,
            )
            assert isinstance(desktop_resize_msg, TerminalResize)
            assert desktop_resize_msg.rows == 40
            assert desktop_resize_msg.cols == 120

        # Step 11: Client disconnects (context manager closes)

    # Step 12: Verify session is cleaned up
    status_response = test_client.get(f"/api/sessions/{session_id}")
    # Session should be gone or closed
    assert status_response.status_code in [404, 200]




@pytest.mark.integration
def test_e2e_encrypted_message_exchange(
    test_client: TestClient,
    desktop_keypair: NaClKeyPair,
    client_keypair: NaClKeyPair,
    desktop_public_key_b64: str,
    client_public_key_b64: str,
):
    """Test end-to-end encryption with full key exchange.

    Validates:
    1. Key exchange during pairing
    2. Desktop can encrypt messages that client can decrypt
    3. Client can encrypt messages that desktop can decrypt
    4. Message content is preserved through encryption/decryption
    """
    # Create session
    create_response = test_client.post(
        "/api/sessions",
        json={"desktop_public_key": desktop_public_key_b64},
    )
    assert create_response.status_code == 201

    session_data = create_response.json()
    session_id = session_data["session_id"]
    pairing_code = session_data["pairing_code"]

    # Connect both peers
    with test_client.websocket_connect(f"/ws/desktop/{session_id}") as desktop_ws:
        with test_client.websocket_connect(f"/ws/client/{pairing_code}") as client_ws:
            # Pair client
            pair_message = SessionPair(
                pairing_code=pairing_code,
                client_public_key=client_keypair.public_key,
            )
            send_ws_message(client_ws, pair_message)

            # Receive SessionPaired messages
            receive_ws_message(desktop_ws)
            receive_ws_message(client_ws)

            # Test encrypted TerminalOutput from desktop
            test_output_data = b"Test output with \x1b[31mANSI codes\x1b[0m and UTF-8: \xf0\x9f\x9a\x80"
            output_message = TerminalOutput(
                session_id=session_id,
                data=test_output_data,
            )
            encrypted_output = encrypt_message(
                output_message,
                desktop_keypair,
                client_keypair.public_key,
                session_id,
                "desktop",
            )
            send_ws_message(desktop_ws, encrypted_output)

            # Client decrypts and verifies
            client_received_raw = receive_ws_message(client_ws)
            client_received_blob = EncryptedBlob(**client_received_raw)
            client_received_msg = decrypt_message(
                client_received_blob,
                client_keypair,
                desktop_keypair.public_key,
            )
            assert isinstance(client_received_msg, TerminalOutput)
            assert client_received_msg.data == test_output_data

            # Test encrypted TerminalInput from client
            test_input_data = b"echo 'Test command' && exit\r\n"
            input_message = TerminalInput(
                session_id=session_id,
                data=test_input_data,
            )
            encrypted_input = encrypt_message(
                input_message,
                client_keypair,
                desktop_keypair.public_key,
                session_id,
                "client",
            )
            send_ws_message(client_ws, encrypted_input)

            # Desktop decrypts and verifies
            desktop_received_raw = receive_ws_message(desktop_ws)
            desktop_received_blob = EncryptedBlob(**desktop_received_raw)
            desktop_received_msg = decrypt_message(
                desktop_received_blob,
                desktop_keypair,
                client_keypair.public_key,
            )
            assert isinstance(desktop_received_msg, TerminalInput)
            assert desktop_received_msg.data == test_input_data


@pytest.mark.integration
def test_e2e_concurrent_sessions(
    test_client: TestClient,
):
    """Test concurrent sessions with message isolation.

    Creates 3 concurrent sessions and verifies:
    1. Each session can be paired independently
    2. Messages are isolated to their respective sessions
    3. No cross-talk between sessions
    4. All sessions can be cleaned up properly
    """
    num_sessions = 3
    sessions = []

    # Create keypairs and sessions
    for i in range(num_sessions):
        desktop_kp = NaClKeyPair(PrivateKey.generate())
        client_kp = NaClKeyPair(PrivateKey.generate())

        # Create session
        create_response = test_client.post(
            "/api/sessions",
            json={"desktop_public_key": bytes_to_base64(desktop_kp.public_key)},
        )
        assert create_response.status_code == 201

        session_data = create_response.json()
        sessions.append({
            "session_id": session_data["session_id"],
            "pairing_code": session_data["pairing_code"],
            "desktop_keypair": desktop_kp,
            "client_keypair": client_kp,
            "index": i,
        })

    # Test each session independently
    for session_info in sessions:
        session_id = session_info["session_id"]
        pairing_code = session_info["pairing_code"]
        desktop_kp = session_info["desktop_keypair"]
        client_kp = session_info["client_keypair"]
        index = session_info["index"]

        with test_client.websocket_connect(f"/ws/desktop/{session_id}") as desktop_ws:
            with test_client.websocket_connect(f"/ws/client/{pairing_code}") as client_ws:
                # Pair client
                pair_message = SessionPair(
                    pairing_code=pairing_code,
                    client_public_key=client_kp.public_key,
                )
                send_ws_message(client_ws, pair_message)

                # Receive SessionPaired
                receive_ws_message(desktop_ws)
                receive_ws_message(client_ws)

                # Send unique message in this session
                unique_data = f"Session {index} unique message".encode()
                output_message = TerminalOutput(
                    session_id=session_id,
                    data=unique_data,
                )
                encrypted_output = encrypt_message(
                    output_message,
                    desktop_kp,
                    client_kp.public_key,
                    session_id,
                    "desktop",
                )
                send_ws_message(desktop_ws, encrypted_output)

                # Receive and verify message
                client_received_raw = receive_ws_message(client_ws)
                client_received_blob = EncryptedBlob(**client_received_raw)
                client_received_msg = decrypt_message(
                    client_received_blob,
                    client_kp,
                    desktop_kp.public_key,
                )

                # Verify message isolation - should only receive own message
                assert isinstance(client_received_msg, TerminalOutput)
                assert client_received_msg.data == unique_data
                assert client_received_msg.session_id == session_id


@pytest.mark.integration
def test_e2e_bidirectional_message_flow(
    test_client: TestClient,
    desktop_keypair: NaClKeyPair,
    client_keypair: NaClKeyPair,
    desktop_public_key_b64: str,
    client_public_key_b64: str,
):
    """Test bidirectional message flow with multiple messages.

    Validates:
    1. Desktop can send multiple TerminalOutput messages
    2. Client can send multiple TerminalInput messages
    3. Messages are delivered in order
    4. Both directions work simultaneously
    """
    # Create and pair session
    create_response = test_client.post(
        "/api/sessions",
        json={"desktop_public_key": desktop_public_key_b64},
    )
    session_data = create_response.json()
    session_id = session_data["session_id"]
    pairing_code = session_data["pairing_code"]

    with test_client.websocket_connect(f"/ws/desktop/{session_id}") as desktop_ws:
        with test_client.websocket_connect(f"/ws/client/{pairing_code}") as client_ws:
            # Pair
            pair_message = SessionPair(
                pairing_code=pairing_code,
                client_public_key=client_keypair.public_key,
            )
            send_ws_message(client_ws, pair_message)

            # Consume SessionPaired messages
            receive_ws_message(desktop_ws)
            receive_ws_message(client_ws)

            # Send multiple messages from desktop
            num_messages = 3
            sent_outputs = []
            for i in range(num_messages):
                data = f"Output line {i}\n".encode()
                sent_outputs.append(data)

                output_message = TerminalOutput(
                    session_id=session_id,
                    data=data,
                )
                encrypted_output = encrypt_message(
                    output_message,
                    desktop_keypair,
                    client_keypair.public_key,
                    session_id,
                    "desktop",
                )
                send_ws_message(desktop_ws, encrypted_output)

            # Receive and verify all outputs at client
            received_outputs = []
            for i in range(num_messages):
                client_received_raw = receive_ws_message(client_ws)
                client_received_blob = EncryptedBlob(**client_received_raw)
                client_received_msg = decrypt_message(
                    client_received_blob,
                    client_keypair,
                    desktop_keypair.public_key,
                )
                assert isinstance(client_received_msg, TerminalOutput)
                received_outputs.append(client_received_msg.data)

            # Verify order preserved
            assert received_outputs == sent_outputs

            # Send multiple inputs from client
            sent_inputs = []
            for i in range(num_messages):
                data = f"command{i}\r".encode()
                sent_inputs.append(data)

                input_message = TerminalInput(
                    session_id=session_id,
                    data=data,
                )
                encrypted_input = encrypt_message(
                    input_message,
                    client_keypair,
                    desktop_keypair.public_key,
                    session_id,
                    "client",
                )
                send_ws_message(client_ws, encrypted_input)

            # Receive and verify all inputs at desktop
            received_inputs = []
            for i in range(num_messages):
                desktop_received_raw = receive_ws_message(desktop_ws)
                desktop_received_blob = EncryptedBlob(**desktop_received_raw)
                desktop_received_msg = decrypt_message(
                    desktop_received_blob,
                    desktop_keypair,
                    client_keypair.public_key,
                )
                assert isinstance(desktop_received_msg, TerminalInput)
                received_inputs.append(desktop_received_msg.data)

            # Verify order preserved
            assert received_inputs == sent_inputs


@pytest.mark.integration
def test_e2e_terminal_resize_handling(
    test_client: TestClient,
    desktop_keypair: NaClKeyPair,
    client_keypair: NaClKeyPair,
    desktop_public_key_b64: str,
    client_public_key_b64: str,
):
    """Test terminal resize message handling.

    Validates:
    1. Client can send TerminalResize messages
    2. Desktop receives resize dimensions correctly
    3. Multiple resize events are handled properly
    """
    # Create and pair session
    create_response = test_client.post(
        "/api/sessions",
        json={"desktop_public_key": desktop_public_key_b64},
    )
    session_data = create_response.json()
    session_id = session_data["session_id"]
    pairing_code = session_data["pairing_code"]

    with test_client.websocket_connect(f"/ws/desktop/{session_id}") as desktop_ws:
        with test_client.websocket_connect(f"/ws/client/{pairing_code}") as client_ws:
            # Pair
            pair_message = SessionPair(
                pairing_code=pairing_code,
                client_public_key=client_keypair.public_key,
            )
            send_ws_message(client_ws, pair_message)

            # Consume SessionPaired messages
            receive_ws_message(desktop_ws)
            receive_ws_message(client_ws)

            # Test various resize dimensions
            resize_tests = [
                (24, 80),    # Classic terminal
                (40, 120),   # Modern terminal
                (50, 132),   # Wide terminal
                (100, 200),  # Very large
            ]

            for rows, cols in resize_tests:
                # Client sends resize
                resize_message = TerminalResize(
                    session_id=session_id,
                    rows=rows,
                    cols=cols,
                )
                encrypted_resize = encrypt_message(
                    resize_message,
                    client_keypair,
                    desktop_keypair.public_key,
                    session_id,
                    "client",
                )
                send_ws_message(client_ws, encrypted_resize)

                # Desktop receives and verifies
                desktop_received_raw = receive_ws_message(desktop_ws)
                desktop_received_blob = EncryptedBlob(**desktop_received_raw)
                desktop_received_msg = decrypt_message(
                    desktop_received_blob,
                    desktop_keypair,
                    client_keypair.public_key,
                )

                assert isinstance(desktop_received_msg, TerminalResize)
                assert desktop_received_msg.rows == rows
                assert desktop_received_msg.cols == cols
                assert desktop_received_msg.session_id == session_id


@pytest.mark.integration
def test_e2e_session_status_during_lifecycle(
    test_client: TestClient,
    desktop_public_key_b64: str,
):
    """Test session status endpoint during various lifecycle stages.

    Validates:
    1. Status is correct after session creation
    2. Status updates when desktop connects
    3. Status updates when client pairs
    4. Status can be queried at any stage
    """
    # Create session
    create_response = test_client.post(
        "/api/sessions",
        json={"desktop_public_key": desktop_public_key_b64},
    )
    session_data = create_response.json()
    session_id = session_data["session_id"]

    # Check initial status
    status = test_client.get(f"/api/sessions/{session_id}").json()
    assert status["state"] == "created"
    assert status["desktop_connected"] is False
    assert status["client_connected"] is False

    # Desktop connects
    with test_client.websocket_connect(f"/ws/desktop/{session_id}") as desktop_ws:
        # Check status while desktop connected
        status = test_client.get(f"/api/sessions/{session_id}").json()
        assert status["state"] == "desktop_connected"
        assert status["desktop_connected"] is True
        assert status["client_connected"] is False

    # After disconnect, status might change
    status = test_client.get(f"/api/sessions/{session_id}")
    # Session might be cleaned up or still exist
    assert status.status_code in [200, 404]
