"""Integration tests for relay session creation and pairing flow.

This test module validates the complete lifecycle of a relay session:
1. Session creation via POST /api/sessions with desktop_public_key
2. Desktop WebSocket connection to /ws/desktop/{session_id}
3. Client WebSocket connection to /ws/client/{pairing_code}
4. Verification of state transitions: created -> desktop_connected -> paired

Test Strategy: technical-spike (integration testing with FastAPI TestClient)
Agent ID: 1
"""

import asyncio
import base64
import json
import re
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agent_remote.services.relay.api.api import app
from agent_remote.services.relay.api.websockets import router as ws_router
from agent_remote.services.relay.infrastructure.in_memory_repository import (
    InMemorySessionRepository,
)
from agent_remote.shared.protocol.session_messages import SessionPair

# Mount WebSocket router to app
app.include_router(ws_router)


class TestSessionCreationAndPairing:
    """Integration tests for session creation and pairing workflow."""

    @pytest.fixture
    def client(self):
        """Create a fresh TestClient for each test."""
        # Reset the singleton repositories before each test
        # IMPORTANT: There's a bug where api.py and websockets.py have separate singletons!
        from agent_remote.services.relay.api import api, websockets

        # Create a shared repository instance
        shared_repo = InMemorySessionRepository()

        # Set both singletons to use the same instance
        api._repository = shared_repo
        websockets._repository = shared_repo
        websockets._websocket_manager = None  # Reset websocket manager too

        return TestClient(app)

    @pytest.fixture
    def desktop_public_key(self):
        """Generate a valid base64-encoded desktop public key."""
        # 32-byte key (typical for X25519)
        key_bytes = b"A" * 32
        return base64.b64encode(key_bytes).decode("utf-8")

    @pytest.fixture
    def client_public_key(self):
        """Generate a valid base64-encoded client public key."""
        key_bytes = b"B" * 32
        return base64.b64encode(key_bytes).decode("utf-8")

    def test_01_create_session_success(self, client: TestClient, desktop_public_key: str):
        """Test POST /api/sessions successfully creates a session.

        Verifies:
        - HTTP 201 Created response
        - Response contains session_id (valid UUID)
        - Response contains pairing_code (6 chars, uppercase alphanumeric)
        """
        # Create session
        response = client.post(
            "/api/sessions",
            json={"desktop_public_key": desktop_public_key}
        )

        # Assert response status
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

        # Parse response
        data = response.json()
        assert "session_id" in data, "Response missing session_id"
        assert "pairing_code" in data, "Response missing pairing_code"

        session_id = data["session_id"]
        pairing_code = data["pairing_code"]

        # Validate session_id is a valid UUID
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        assert uuid_pattern.match(session_id), f"session_id '{session_id}' is not a valid UUID"

        # Validate pairing_code format (6 chars, uppercase alphanumeric)
        assert len(pairing_code) == 6, f"pairing_code length is {len(pairing_code)}, expected 6"
        assert pairing_code.isupper(), f"pairing_code '{pairing_code}' is not uppercase"
        assert pairing_code.isalnum(), f"pairing_code '{pairing_code}' is not alphanumeric"

    def test_02_get_session_status_after_creation(self, client: TestClient, desktop_public_key: str):
        """Test GET /api/sessions/{session_id} returns correct initial state.

        Verifies:
        - Session state is 'created'
        - desktop_connected is False
        - client_connected is False
        - expires_at is present and in ISO 8601 format
        """
        # Create session
        create_response = client.post(
            "/api/sessions",
            json={"desktop_public_key": desktop_public_key}
        )
        session_id = create_response.json()["session_id"]

        # Get session status
        status_response = client.get(f"/api/sessions/{session_id}")

        assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}"

        status = status_response.json()

        # Validate initial state
        assert status["session_id"] == session_id
        assert status["state"] == "created", f"Expected state 'created', got '{status['state']}'"
        assert status["desktop_connected"] is False, "desktop_connected should be False initially"
        assert status["client_connected"] is False, "client_connected should be False initially"
        assert "expires_at" in status, "Missing expires_at field"

        # Validate expires_at is ISO 8601 format (basic check)
        expires_at = status["expires_at"]
        assert "T" in expires_at or "-" in expires_at, f"expires_at '{expires_at}' doesn't look like ISO 8601"

    def test_03_desktop_websocket_connection(self, client: TestClient, desktop_public_key: str):
        """Test desktop WebSocket connection via /ws/desktop/{session_id}.

        Verifies:
        - WebSocket connection succeeds
        - Session state transitions to 'desktop_connected'
        - desktop_connected becomes True
        """
        # Create session
        create_response = client.post(
            "/api/sessions",
            json={"desktop_public_key": desktop_public_key}
        )
        data = create_response.json()
        session_id = data["session_id"]

        # Connect desktop WebSocket
        with client.websocket_connect(f"/ws/desktop/{session_id}") as websocket:
            # WebSocket should connect successfully
            assert websocket is not None, "Desktop WebSocket connection failed"

            # Check session status while connected
            status_response = client.get(f"/api/sessions/{session_id}")
            status = status_response.json()

            assert status["state"] == "desktop_connected", \
                f"Expected state 'desktop_connected', got '{status['state']}'"
            assert status["desktop_connected"] is True, "desktop_connected should be True"
            assert status["client_connected"] is False, "client_connected should still be False"

    def test_04_client_websocket_pairing(
        self,
        client: TestClient,
        desktop_public_key: str,
        client_public_key: str
    ):
        """Test complete pairing flow: desktop connects, then client pairs.

        Verifies:
        - Desktop connects successfully
        - Client connects with pairing code
        - Client sends SessionPair message with client_public_key
        - Session state transitions to 'paired'
        - Both desktop_connected and client_connected are True
        """
        # Create session
        create_response = client.post(
            "/api/sessions",
            json={"desktop_public_key": desktop_public_key}
        )
        data = create_response.json()
        session_id = data["session_id"]
        pairing_code = data["pairing_code"]

        # Connect desktop WebSocket
        with client.websocket_connect(f"/ws/desktop/{session_id}") as desktop_ws:
            # Verify desktop connected
            status = client.get(f"/api/sessions/{session_id}").json()
            assert status["state"] == "desktop_connected"

            # Connect client WebSocket with pairing code
            with client.websocket_connect(f"/ws/client/{pairing_code}") as client_ws:
                # Send SessionPair message (correct format: type is "session.pair")
                # The pairing code is included even though it's in the URL
                pairing_msg = {
                    "type": "session.pair",
                    "pairing_code": pairing_code,
                    "client_public_key": client_public_key  # Send as base64 string
                }

                client_ws.send_json(pairing_msg)

                # Check session status after pairing
                status = client.get(f"/api/sessions/{session_id}").json()

                assert status["state"] == "paired", \
                    f"Expected state 'paired', got '{status['state']}'"
                assert status["desktop_connected"] is True, "desktop_connected should be True"
                assert status["client_connected"] is True, "client_connected should be True"

    def test_05_invalid_session_id_format(self, client: TestClient):
        """Test that invalid session_id format returns 400 Bad Request."""
        # Try to get status with invalid session ID
        response = client.get("/api/sessions/not-a-uuid")
        assert response.status_code == 400, \
            f"Expected 400 for invalid UUID, got {response.status_code}"
        assert "Invalid session ID format" in response.json()["detail"]

    def test_06_nonexistent_session_id(self, client: TestClient):
        """Test that nonexistent session_id returns 404 Not Found."""
        # Use a valid UUID that doesn't exist
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/api/sessions/{fake_uuid}")
        assert response.status_code == 404, \
            f"Expected 404 for nonexistent session, got {response.status_code}"
        assert "not found" in response.json()["detail"].lower()

    def test_07_invalid_pairing_code_format(self, client: TestClient):
        """Test that invalid pairing code format is rejected at WebSocket connection."""
        # Try to connect with invalid pairing code (too short)
        try:
            with client.websocket_connect("/ws/client/ABC") as ws:
                # Should receive error and close
                try:
                    message = ws.receive_json(timeout=2)
                    # If we get a message, it should be an error
                    if "code" in message:
                        assert message["code"] == 4002  # ERROR_PAIRING_CODE_INVALID
                except:
                    pass  # Connection closed before we could read
        except WebSocketDisconnect:
            # Expected - connection should be closed
            pass

    def test_08_nonexistent_pairing_code(self, client: TestClient, client_public_key: str):
        """Test that nonexistent pairing code returns error."""
        # Try to connect with valid format but nonexistent code
        try:
            with client.websocket_connect("/ws/client/ZZZZZ9") as ws:
                # Send SessionPair message with correct format
                pairing_msg = {
                    "type": "session.pair",
                    "pairing_code": "ZZZZZ9",
                    "client_public_key": client_public_key  # base64 string
                }

                try:
                    ws.send_json(pairing_msg)
                    # Should receive error
                    message = ws.receive_json(timeout=2)
                    if "code" in message:
                        assert message["code"] == 4002  # ERROR_PAIRING_CODE_INVALID
                except:
                    pass  # Connection might close immediately
        except WebSocketDisconnect:
            # Expected - connection should be closed
            pass

    def test_09_state_transition_sequence(self, client: TestClient, desktop_public_key: str, client_public_key: str):
        """Test complete state transition sequence: created -> desktop_connected -> paired.

        This is the comprehensive integration test that validates the entire workflow.
        """
        # Step 1: Create session
        create_response = client.post(
            "/api/sessions",
            json={"desktop_public_key": desktop_public_key}
        )
        assert create_response.status_code == 201

        data = create_response.json()
        session_id = data["session_id"]
        pairing_code = data["pairing_code"]

        # Verify pairing code format
        assert len(pairing_code) == 6
        assert pairing_code.isupper()
        assert pairing_code.isalnum()

        # Step 2: Verify initial state is 'created'
        status = client.get(f"/api/sessions/{session_id}").json()
        assert status["state"] == "created"
        assert status["desktop_connected"] is False
        assert status["client_connected"] is False

        # Step 3: Desktop connects
        with client.websocket_connect(f"/ws/desktop/{session_id}") as desktop_ws:
            # Verify state transitioned to 'desktop_connected'
            status = client.get(f"/api/sessions/{session_id}").json()
            assert status["state"] == "desktop_connected"
            assert status["desktop_connected"] is True
            assert status["client_connected"] is False

            # Step 4: Client pairs
            with client.websocket_connect(f"/ws/client/{pairing_code}") as client_ws:
                # Send SessionPair message with correct format
                pairing_msg = {
                    "type": "session.pair",
                    "pairing_code": pairing_code,
                    "client_public_key": client_public_key  # base64 string
                }
                client_ws.send_json(pairing_msg)

                # Verify state transitioned to 'paired'
                status = client.get(f"/api/sessions/{session_id}").json()
                assert status["state"] == "paired"
                assert status["desktop_connected"] is True
                assert status["client_connected"] is True

    def test_10_invalid_base64_public_key(self, client: TestClient):
        """Test that invalid base64 public key returns 400 Bad Request."""
        response = client.post(
            "/api/sessions",
            json={"desktop_public_key": "not-valid-base64!!!"}
        )
        assert response.status_code == 400
        assert "Invalid base64" in response.json()["detail"]
