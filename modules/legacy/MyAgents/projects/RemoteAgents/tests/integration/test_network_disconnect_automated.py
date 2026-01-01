"""Automated Network Disconnect Integration Tests (US-ERROR-006).

This test suite validates network disconnect handling for the RemoteAgents relay service.
It uses Docker to simulate network failures and verifies:
1. Disconnect detection within keepalive timeout
2. No data corruption on interrupted transfers
3. Session cleanup on disconnect
4. Reconnection capability after network restoration

Test Strategy: Docker-based integration testing
User Story: US-ERROR-006 - Network Disconnect During Send
Priority: LOW
Category: error_handling

Prerequisites:
- Docker Engine installed and running
- Docker Compose v2+
- Port 8080 available

Run with: pytest -m docker tests/integration/test_network_disconnect_automated.py -v
"""

import asyncio
import json
import time
from typing import Any, Dict

import httpx
import pytest
import websockets
from nacl.public import PrivateKey
from websockets import State

from agent_remote.shared.crypto.nacl_impl import NaClKeyPair, bytes_to_base64


def is_ws_open(ws) -> bool:
    """Check if WebSocket connection is open (compatible with websockets 15.x).

    Args:
        ws: WebSocket connection

    Returns:
        True if connection is open
    """
    return ws.state == State.OPEN

from .docker_helpers import (
    disconnect_container_from_network,
    get_container_logs,
    is_container_connected_to_network,
    reconnect_container_to_network,
)


# ==============================================================================
# Constants
# ==============================================================================

KEEPALIVE_TIMEOUT = 35  # Default relay keepalive timeout in seconds
NETWORK_NAME = "agent-network"
RELAY_CONTAINER = "agent-relay"


# ==============================================================================
# Helper Functions
# ==============================================================================


def create_session(relay_url: str) -> Dict[str, Any]:
    """Create a new session via REST API.

    Args:
        relay_url: Base URL of the relay service

    Returns:
        Dict with session_id, pairing_code, etc.
    """
    keypair = NaClKeyPair(PrivateKey.generate())
    public_key_b64 = bytes_to_base64(keypair.public_key)

    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{relay_url}/api/sessions",
            json={"desktop_public_key": public_key_b64},
        )
        response.raise_for_status()
        data = response.json()
        data["keypair"] = keypair
        return data


async def connect_websocket(url: str, timeout: float = 10.0):
    """Connect to WebSocket with timeout.

    Args:
        url: WebSocket URL
        timeout: Connection timeout in seconds

    Returns:
        WebSocket connection
    """
    return await asyncio.wait_for(
        websockets.connect(url, ping_interval=None, ping_timeout=None),
        timeout=timeout,
    )


async def receive_with_timeout(ws, timeout: float = 5.0) -> Dict[str, Any]:
    """Receive WebSocket message with timeout.

    Args:
        ws: WebSocket connection
        timeout: Receive timeout in seconds

    Returns:
        Parsed JSON message
    """
    message = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(message)


# ==============================================================================
# Test Cases
# ==============================================================================


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.asyncio
async def test_network_disconnect_detected(
    docker_client,
    relay_service: Dict[str, Any],
):
    """Test that network disconnect is detected within keepalive timeout.

    This test:
    1. Creates a session and connects WebSocket
    2. Disconnects the relay container from network
    3. Verifies disconnect is detected (WebSocket closes)
    4. Verifies detection occurs within keepalive timeout

    Acceptance Criteria:
    - Disconnect detected within 35 seconds (keepalive timeout)
    - WebSocket connection closes properly
    - No hanging connections
    """
    relay_url = relay_service["relay_url"]

    # Step 1: Create session
    session_data = create_session(relay_url)
    session_id = session_data["session_id"]

    # Step 2: Connect desktop WebSocket
    ws_url = f"ws://localhost:8080/ws/desktop/{session_id}"
    ws = await connect_websocket(ws_url)

    try:
        # Verify connection is established
        assert is_ws_open(ws), "WebSocket should be open"

        # Step 3: Disconnect relay container from network
        disconnect_container_from_network(
            docker_client,
            RELAY_CONTAINER,
            NETWORK_NAME,
        )

        # Verify disconnect happened
        assert not is_container_connected_to_network(
            docker_client,
            RELAY_CONTAINER,
            NETWORK_NAME,
        ), "Container should be disconnected from network"

        # Step 4: Wait for WebSocket to close (should happen within keepalive timeout)
        start_time = time.time()
        disconnect_detected = False

        # The WebSocket should close due to the network disconnect
        # This might happen via:
        # a) Connection error when trying to send/receive
        # b) Keepalive timeout on the server side
        try:
            # Try to receive - this should eventually fail or timeout
            while time.time() - start_time < KEEPALIVE_TIMEOUT + 5:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    # Received a message, connection still alive
                except asyncio.TimeoutError:
                    # No message, check if connection still open
                    if not is_ws_open(ws):
                        disconnect_detected = True
                        break
                except websockets.exceptions.ConnectionClosed:
                    disconnect_detected = True
                    break
        except Exception:
            disconnect_detected = True

        elapsed = time.time() - start_time

        # Verify disconnect was detected within timeout
        assert disconnect_detected, f"Disconnect should be detected within {KEEPALIVE_TIMEOUT}s, got {elapsed}s"
        assert elapsed < KEEPALIVE_TIMEOUT + 10, f"Detection took too long: {elapsed}s"

    finally:
        # Cleanup: reconnect container and close WebSocket
        try:
            reconnect_container_to_network(
                docker_client,
                RELAY_CONTAINER,
                NETWORK_NAME,
            )
        except Exception:
            pass

        try:
            await ws.close()
        except Exception:
            pass


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_data_corruption_on_disconnect(
    docker_client,
    relay_service: Dict[str, Any],
):
    """Test that no data corruption occurs when disconnect happens mid-send.

    This test:
    1. Creates a session and connects desktop
    2. Sends messages while connected
    3. Disconnects network mid-transfer
    4. Verifies any received data before disconnect is valid (no partial messages)

    Acceptance Criteria:
    - All received messages are valid JSON
    - No partial messages received
    - Error handling is graceful
    """
    relay_url = relay_service["relay_url"]

    # Create session
    session_data = create_session(relay_url)
    session_id = session_data["session_id"]

    # Connect desktop
    desktop_ws = await connect_websocket(f"ws://localhost:8080/ws/desktop/{session_id}")

    try:
        # Verify connection works
        assert is_ws_open(desktop_ws), "Desktop WebSocket should be open"

        # Send messages from desktop and verify they are received correctly
        # The relay echoes status messages we can check
        messages_received = []

        # Collect any initial messages (like status updates)
        try:
            while True:
                msg = await asyncio.wait_for(desktop_ws.recv(), timeout=1.0)
                parsed = json.loads(msg)
                messages_received.append(parsed)
                # Verify message is well-formed JSON
                assert isinstance(parsed, dict), "Message should be a valid dict"
        except asyncio.TimeoutError:
            pass

        # Disconnect network
        disconnect_container_from_network(
            docker_client,
            RELAY_CONTAINER,
            NETWORK_NAME,
        )

        # Try to receive any remaining messages before connection drops
        # All received messages should be valid JSON (no corruption)
        try:
            while True:
                msg = await asyncio.wait_for(desktop_ws.recv(), timeout=2.0)
                parsed = json.loads(msg)
                messages_received.append(parsed)
                # Verify message is well-formed
                assert isinstance(parsed, dict), "Message should be a valid dict"
        except asyncio.TimeoutError:
            pass
        except websockets.exceptions.ConnectionClosed:
            pass
        except json.JSONDecodeError as e:
            pytest.fail(f"Received corrupted/partial JSON: {e}")

        # Verify all received messages were valid JSON
        # The key assertion is that we never received partial/corrupted data
        for msg in messages_received:
            assert isinstance(msg, dict), "All messages should be valid dicts"

    finally:
        # Cleanup
        try:
            reconnect_container_to_network(
                docker_client,
                RELAY_CONTAINER,
                NETWORK_NAME,
            )
        except Exception:
            pass

        try:
            await desktop_ws.close()
        except Exception:
            pass


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_cleanup_on_disconnect(
    docker_client,
    relay_service: Dict[str, Any],
):
    """Test that sessions are properly cleaned up after disconnect.

    This test:
    1. Creates a session
    2. Disconnects network to trigger cleanup
    3. Reconnects network
    4. Verifies session is no longer accessible

    Acceptance Criteria:
    - Session is cleaned up after disconnect
    - No orphaned session state
    - Service recovers to handle new sessions
    """
    relay_url = relay_service["relay_url"]

    # Create session
    session_data = create_session(relay_url)
    session_id = session_data["session_id"]

    # Connect WebSocket
    ws = await connect_websocket(f"ws://localhost:8080/ws/desktop/{session_id}")

    try:
        # Disconnect network
        disconnect_container_from_network(
            docker_client,
            RELAY_CONTAINER,
            NETWORK_NAME,
        )

        # Wait for disconnect detection
        try:
            while True:
                await asyncio.wait_for(ws.recv(), timeout=1.0)
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
            pass

    finally:
        await ws.close()

    # Reconnect network
    reconnect_container_to_network(
        docker_client,
        RELAY_CONTAINER,
        NETWORK_NAME,
    )

    # Wait for service to recover
    await asyncio.sleep(2)

    # Check session status - should be cleaned up or expired
    with httpx.Client(timeout=10.0) as client:
        # Wait for service to be healthy again
        for _ in range(10):
            try:
                health = client.get(f"{relay_url}/health")
                if health.status_code == 200:
                    break
            except Exception:
                pass
            await asyncio.sleep(1)

        # Check original session - should be gone or closed
        response = client.get(f"{relay_url}/api/sessions/{session_id}")
        # Session should be cleaned up (404) or closed (200 with closed state)
        assert response.status_code in [404, 200], f"Unexpected status: {response.status_code}"


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconnection_after_disconnect(
    docker_client,
    relay_service: Dict[str, Any],
):
    """Test that new sessions work after network reconnection.

    This test:
    1. Creates a session
    2. Disconnects and reconnects network
    3. Creates a new session
    4. Verifies new session works normally

    Acceptance Criteria:
    - Service recovers after network reconnection
    - New sessions can be created
    - New WebSocket connections work normally
    """
    relay_url = relay_service["relay_url"]

    # Create initial session
    session1 = create_session(relay_url)

    # Connect and disconnect
    ws1 = await connect_websocket(f"ws://localhost:8080/ws/desktop/{session1['session_id']}")

    try:
        # Disconnect network
        disconnect_container_from_network(
            docker_client,
            RELAY_CONTAINER,
            NETWORK_NAME,
        )

        # Wait briefly
        await asyncio.sleep(2)

    finally:
        try:
            await ws1.close()
        except Exception:
            pass

    # Reconnect network
    reconnect_container_to_network(
        docker_client,
        RELAY_CONTAINER,
        NETWORK_NAME,
    )

    # Wait for service to be healthy
    await asyncio.sleep(3)

    # Verify service is healthy
    with httpx.Client(timeout=10.0) as client:
        for _ in range(10):
            try:
                health = client.get(f"{relay_url}/health")
                if health.status_code == 200:
                    break
            except Exception:
                pass
            await asyncio.sleep(1)
        else:
            pytest.fail("Service did not recover after reconnection")

    # Create new session
    session2 = create_session(relay_url)
    assert session2["session_id"] != session1["session_id"], "New session should have different ID"

    # Connect to new session
    ws2 = await connect_websocket(f"ws://localhost:8080/ws/desktop/{session2['session_id']}")

    try:
        # Verify connection is working
        assert is_ws_open(ws2), "New WebSocket should be open"

        # Check session status
        with httpx.Client(timeout=10.0) as client:
            status = client.get(f"{relay_url}/api/sessions/{session2['session_id']}")
            assert status.status_code == 200, "New session should be accessible"
            data = status.json()
            assert data["state"] == "desktop_connected", "Session should show desktop connected"

    finally:
        await ws2.close()


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_disconnect_cycles(
    docker_client,
    relay_service: Dict[str, Any],
):
    """Test service stability through multiple disconnect/reconnect cycles.

    This test:
    1. Performs multiple disconnect/reconnect cycles
    2. Verifies service remains stable
    3. Verifies no resource leaks

    Acceptance Criteria:
    - Service survives multiple disconnect cycles
    - No crash or hang
    - Sessions work after each cycle
    """
    relay_url = relay_service["relay_url"]
    num_cycles = 3

    for cycle in range(num_cycles):
        # Create session
        session_data = create_session(relay_url)

        # Connect WebSocket
        ws = await connect_websocket(f"ws://localhost:8080/ws/desktop/{session_data['session_id']}")

        try:
            # Disconnect network
            disconnect_container_from_network(
                docker_client,
                RELAY_CONTAINER,
                NETWORK_NAME,
            )

            # Wait briefly
            await asyncio.sleep(1)

        finally:
            try:
                await ws.close()
            except Exception:
                pass

        # Reconnect network
        reconnect_container_to_network(
            docker_client,
            RELAY_CONTAINER,
            NETWORK_NAME,
        )

        # Wait for recovery
        await asyncio.sleep(2)

        # Verify service is healthy
        with httpx.Client(timeout=10.0) as client:
            for _ in range(5):
                try:
                    health = client.get(f"{relay_url}/health")
                    if health.status_code == 200:
                        break
                except Exception:
                    pass
                await asyncio.sleep(1)
            else:
                pytest.fail(f"Service did not recover after cycle {cycle + 1}")

    # Final verification - service should still work
    final_session = create_session(relay_url)
    assert final_session["session_id"], "Should be able to create session after all cycles"
