#!/usr/bin/env python3
"""Test Agent 3: Status commands and connection info display.

Tests:
1. RemoteWorkflow.get_status() method
2. RemoteWorkflow.get_connection_info() method
3. RemoteWorkflow.format_pairing_code() method
4. RelayServiceWorkflow.get_status() method
5. RelayServiceWorkflow.get_relay_info() method
6. Verify pairing code format (6 chars, formatted as ABC-123)
7. Verify WebSocket URL format correctness
8. Verify active session count display
"""

import sys
import os
from pathlib import Path
import tempfile
import json

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent_remote.services.terminal.workflows.remote_workflow import RemoteWorkflow
from agent_remote.services.relay.workflows.relay_service_workflow import RelayServiceWorkflow

# Test results collector
test_results = []

def log_test(test_name, passed, message=""):
    """Log test result."""
    result = {
        "test_name": test_name,
        "status": "PASS" if passed else "FAIL",
        "message": message
    }
    test_results.append(result)
    status_symbol = "[PASS]" if passed else "[FAIL]"
    print(f"{status_symbol} {test_name}")
    if message:
        print(f"    {message}")

def test_remote_get_status():
    """Test RemoteWorkflow.get_status() method."""
    print("\n=== Testing RemoteWorkflow.get_status() ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow = RemoteWorkflow(home_config_dir=Path(tmpdir))

        # Test 1: Status when service not running
        status = workflow.get_status()

        # Verify status dict structure
        required_keys = ["running", "port", "websocket_url", "connection_info"]
        missing_keys = [key for key in required_keys if key not in status]

        if missing_keys:
            log_test(
                "RemoteWorkflow.get_status() - keys present",
                False,
                f"Missing keys: {missing_keys}"
            )
        else:
            log_test(
                "RemoteWorkflow.get_status() - keys present",
                True,
                f"All required keys present: {list(status.keys())}"
            )

        # Verify running status is False when not running
        if status.get("running") is False:
            log_test(
                "RemoteWorkflow.get_status() - running=False when stopped",
                True
            )
        else:
            log_test(
                "RemoteWorkflow.get_status() - running=False when stopped",
                False,
                f"Expected running=False, got running={status.get('running')}"
            )

        # Verify websocket_url is None when not running
        if status.get("websocket_url") is None:
            log_test(
                "RemoteWorkflow.get_status() - websocket_url=None when stopped",
                True
            )
        else:
            log_test(
                "RemoteWorkflow.get_status() - websocket_url=None when stopped",
                False,
                f"Expected websocket_url=None, got {status.get('websocket_url')}"
            )

def test_remote_get_connection_info():
    """Test RemoteWorkflow.get_connection_info() method."""
    print("\n=== Testing RemoteWorkflow.get_connection_info() ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow = RemoteWorkflow(home_config_dir=Path(tmpdir))

        # Test when service not running
        conn_info = workflow.get_connection_info()

        # Verify connection_info dict structure
        required_keys = ["session_id", "pairing_code", "websocket_url", "relay_url", "status"]
        missing_keys = [key for key in required_keys if key not in conn_info]

        if missing_keys:
            log_test(
                "RemoteWorkflow.get_connection_info() - keys present",
                False,
                f"Missing keys: {missing_keys}"
            )
        else:
            log_test(
                "RemoteWorkflow.get_connection_info() - keys present",
                True,
                f"All required keys present: {list(conn_info.keys())}"
            )

        # Verify status is DISCONNECTED when not running
        if conn_info.get("status") == "DISCONNECTED":
            log_test(
                "RemoteWorkflow.get_connection_info() - status=DISCONNECTED when stopped",
                True
            )
        else:
            log_test(
                "RemoteWorkflow.get_connection_info() - status=DISCONNECTED when stopped",
                False,
                f"Expected status=DISCONNECTED, got {conn_info.get('status')}"
            )

        # Verify pairing_code is None when not running
        if conn_info.get("pairing_code") is None:
            log_test(
                "RemoteWorkflow.get_connection_info() - pairing_code=None when stopped",
                True
            )
        else:
            log_test(
                "RemoteWorkflow.get_connection_info() - pairing_code=None when stopped",
                False,
                f"Expected pairing_code=None, got {conn_info.get('pairing_code')}"
            )

        # Test when service "running" (simulated with state file)
        state = {
            "pid": 12345,
            "port": 8080,
            "host": "0.0.0.0",
            "relay_url": "ws://localhost:8080",
            "started_at": "2024-01-01T00:00:00Z"
        }
        workflow._save_state(state)

        # Call get_connection_info() again - should generate pairing code
        conn_info = workflow.get_connection_info()

        # Verify pairing code is generated (even though service isn't actually running)
        # The code checks running status, so pairing_code should still be None
        # Let's test the actual state where service would be "running"

        # Actually, let's just test the pairing code generation function directly
        pairing_code = workflow._generate_pairing_code()

        # Verify pairing code length
        if len(pairing_code) == 6:
            log_test(
                "RemoteWorkflow._generate_pairing_code() - length=6",
                True,
                f"Generated code: {pairing_code}"
            )
        else:
            log_test(
                "RemoteWorkflow._generate_pairing_code() - length=6",
                False,
                f"Expected length 6, got {len(pairing_code)}: {pairing_code}"
            )

        # Verify pairing code is alphanumeric uppercase
        if pairing_code.isupper() and pairing_code.isalnum():
            log_test(
                "RemoteWorkflow._generate_pairing_code() - uppercase alphanumeric",
                True,
                f"Generated code: {pairing_code}"
            )
        else:
            log_test(
                "RemoteWorkflow._generate_pairing_code() - uppercase alphanumeric",
                False,
                f"Code should be uppercase alphanumeric: {pairing_code}"
            )

def test_pairing_code_format():
    """Test pairing code formatting (ABC-123)."""
    print("\n=== Testing Pairing Code Format ===")

    # Test format_pairing_code static method
    test_code = "ABC123"
    formatted = RemoteWorkflow.format_pairing_code(test_code)

    expected = "ABC-123"
    if formatted == expected:
        log_test(
            "RemoteWorkflow.format_pairing_code() - ABC123 -> ABC-123",
            True,
            f"Formatted: {formatted}"
        )
    else:
        log_test(
            "RemoteWorkflow.format_pairing_code() - ABC123 -> ABC-123",
            False,
            f"Expected {expected}, got {formatted}"
        )

    # Test with different code
    test_code2 = "XYZ999"
    formatted2 = RemoteWorkflow.format_pairing_code(test_code2)
    expected2 = "XYZ-999"

    if formatted2 == expected2:
        log_test(
            "RemoteWorkflow.format_pairing_code() - XYZ999 -> XYZ-999",
            True,
            f"Formatted: {formatted2}"
        )
    else:
        log_test(
            "RemoteWorkflow.format_pairing_code() - XYZ999 -> XYZ-999",
            False,
            f"Expected {expected2}, got {formatted2}"
        )

    # Test with wrong length (should return as-is)
    test_code3 = "AB12"
    formatted3 = RemoteWorkflow.format_pairing_code(test_code3)

    if formatted3 == test_code3:
        log_test(
            "RemoteWorkflow.format_pairing_code() - wrong length unchanged",
            True,
            f"Input: {test_code3}, Output: {formatted3}"
        )
    else:
        log_test(
            "RemoteWorkflow.format_pairing_code() - wrong length unchanged",
            False,
            f"Expected {test_code3}, got {formatted3}"
        )

def test_websocket_url_format():
    """Test WebSocket URL format correctness."""
    print("\n=== Testing WebSocket URL Format ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow = RemoteWorkflow(home_config_dir=Path(tmpdir))

        # Get connection info
        conn_info = workflow.get_connection_info()

        # Verify WebSocket URL format
        ws_url = conn_info.get("websocket_url")

        # Check if URL starts with ws://
        if ws_url and ws_url.startswith("ws://"):
            log_test(
                "RemoteWorkflow WebSocket URL - starts with ws://",
                True,
                f"URL: {ws_url}"
            )
        else:
            log_test(
                "RemoteWorkflow WebSocket URL - starts with ws://",
                False,
                f"Expected ws:// prefix, got: {ws_url}"
            )

        # Check if URL contains /ws/desktop path
        if ws_url and "/ws/desktop" in ws_url:
            log_test(
                "RemoteWorkflow WebSocket URL - contains /ws/desktop",
                True,
                f"URL: {ws_url}"
            )
        else:
            log_test(
                "RemoteWorkflow WebSocket URL - contains /ws/desktop",
                False,
                f"Expected /ws/desktop in URL, got: {ws_url}"
            )

        # Verify relay_url format (http://)
        relay_url = conn_info.get("relay_url")

        if relay_url and relay_url.startswith("http://"):
            log_test(
                "RemoteWorkflow relay URL - starts with http://",
                True,
                f"URL: {relay_url}"
            )
        else:
            log_test(
                "RemoteWorkflow relay URL - starts with http://",
                False,
                f"Expected http:// prefix, got: {relay_url}"
            )

def test_relay_get_status():
    """Test RelayServiceWorkflow.get_status() method."""
    print("\n=== Testing RelayServiceWorkflow.get_status() ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow = RelayServiceWorkflow(home_config_dir=Path(tmpdir))

        # Test status when service not running
        status = workflow.get_status()

        # Verify status dict structure
        required_keys = ["running", "host", "port", "ws_url", "desktop_endpoint",
                        "client_endpoint", "active_sessions", "healthy", "relay_info"]
        missing_keys = [key for key in required_keys if key not in status]

        if missing_keys:
            log_test(
                "RelayServiceWorkflow.get_status() - keys present",
                False,
                f"Missing keys: {missing_keys}"
            )
        else:
            log_test(
                "RelayServiceWorkflow.get_status() - keys present",
                True,
                f"All required keys present: {list(status.keys())}"
            )

        # Verify running status is False when not running
        if status.get("running") is False:
            log_test(
                "RelayServiceWorkflow.get_status() - running=False when stopped",
                True
            )
        else:
            log_test(
                "RelayServiceWorkflow.get_status() - running=False when stopped",
                False,
                f"Expected running=False, got running={status.get('running')}"
            )

        # Verify active_sessions is 0 when not running
        if status.get("active_sessions") == 0:
            log_test(
                "RelayServiceWorkflow.get_status() - active_sessions=0 when stopped",
                True
            )
        else:
            log_test(
                "RelayServiceWorkflow.get_status() - active_sessions=0 when stopped",
                False,
                f"Expected active_sessions=0, got {status.get('active_sessions')}"
            )

        # Verify healthy is False when not running
        if status.get("healthy") is False:
            log_test(
                "RelayServiceWorkflow.get_status() - healthy=False when stopped",
                True
            )
        else:
            log_test(
                "RelayServiceWorkflow.get_status() - healthy=False when stopped",
                False,
                f"Expected healthy=False, got healthy={status.get('healthy')}"
            )

def test_relay_get_relay_info():
    """Test RelayServiceWorkflow.get_relay_info() method."""
    print("\n=== Testing RelayServiceWorkflow.get_relay_info() ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow = RelayServiceWorkflow(home_config_dir=Path(tmpdir))

        # Test relay info when service not running
        relay_info = workflow.get_relay_info()

        # Verify relay_info dict structure
        required_keys = ["relay_url", "websocket_endpoints", "active_sessions", "health"]
        missing_keys = [key for key in required_keys if key not in relay_info]

        if missing_keys:
            log_test(
                "RelayServiceWorkflow.get_relay_info() - keys present",
                False,
                f"Missing keys: {missing_keys}"
            )
        else:
            log_test(
                "RelayServiceWorkflow.get_relay_info() - keys present",
                True,
                f"All required keys present: {list(relay_info.keys())}"
            )

        # Verify health is UNHEALTHY when not running
        if relay_info.get("health") == "UNHEALTHY":
            log_test(
                "RelayServiceWorkflow.get_relay_info() - health=UNHEALTHY when stopped",
                True
            )
        else:
            log_test(
                "RelayServiceWorkflow.get_relay_info() - health=UNHEALTHY when stopped",
                False,
                f"Expected health=UNHEALTHY, got {relay_info.get('health')}"
            )

        # Verify active_sessions is 0 when not running
        if relay_info.get("active_sessions") == 0:
            log_test(
                "RelayServiceWorkflow.get_relay_info() - active_sessions=0 when stopped",
                True
            )
        else:
            log_test(
                "RelayServiceWorkflow.get_relay_info() - active_sessions=0 when stopped",
                False,
                f"Expected active_sessions=0, got {relay_info.get('active_sessions')}"
            )

        # Verify websocket_endpoints structure
        endpoints = relay_info.get("websocket_endpoints")
        if endpoints and isinstance(endpoints, dict):
            required_endpoint_keys = ["desktop", "client"]
            missing_endpoint_keys = [key for key in required_endpoint_keys if key not in endpoints]

            if missing_endpoint_keys:
                log_test(
                    "RelayServiceWorkflow.get_relay_info() - websocket_endpoints keys",
                    False,
                    f"Missing endpoint keys: {missing_endpoint_keys}"
                )
            else:
                log_test(
                    "RelayServiceWorkflow.get_relay_info() - websocket_endpoints keys",
                    True,
                    f"Endpoint keys present: {list(endpoints.keys())}"
                )
        else:
            log_test(
                "RelayServiceWorkflow.get_relay_info() - websocket_endpoints is dict",
                False,
                f"Expected dict, got {type(endpoints)}"
            )

def test_relay_websocket_urls():
    """Test relay WebSocket URL format correctness."""
    print("\n=== Testing Relay WebSocket URL Formats ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        workflow = RelayServiceWorkflow(home_config_dir=Path(tmpdir))

        # Get relay info
        relay_info = workflow.get_relay_info()
        endpoints = relay_info.get("websocket_endpoints", {})

        # Test desktop endpoint format
        desktop_url = endpoints.get("desktop")
        if desktop_url and desktop_url.startswith("ws://"):
            log_test(
                "Relay desktop endpoint - starts with ws://",
                True,
                f"URL: {desktop_url}"
            )
        else:
            log_test(
                "Relay desktop endpoint - starts with ws://",
                False,
                f"Expected ws:// prefix, got: {desktop_url}"
            )

        if desktop_url and "/ws/desktop/{session_id}" in desktop_url:
            log_test(
                "Relay desktop endpoint - contains /ws/desktop/{session_id}",
                True,
                f"URL: {desktop_url}"
            )
        else:
            log_test(
                "Relay desktop endpoint - contains /ws/desktop/{session_id}",
                False,
                f"Expected /ws/desktop/{{session_id}} in URL, got: {desktop_url}"
            )

        # Test client endpoint format
        client_url = endpoints.get("client")
        if client_url and client_url.startswith("ws://"):
            log_test(
                "Relay client endpoint - starts with ws://",
                True,
                f"URL: {client_url}"
            )
        else:
            log_test(
                "Relay client endpoint - starts with ws://",
                False,
                f"Expected ws:// prefix, got: {client_url}"
            )

        if client_url and "/ws/client/{pairing_code}" in client_url:
            log_test(
                "Relay client endpoint - contains /ws/client/{pairing_code}",
                True,
                f"URL: {client_url}"
            )
        else:
            log_test(
                "Relay client endpoint - contains /ws/client/{pairing_code}",
                False,
                f"Expected /ws/client/{{pairing_code}} in URL, got: {client_url}"
            )

def print_summary():
    """Print test summary."""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    total = len(test_results)
    passed = sum(1 for r in test_results if r["status"] == "PASS")
    failed = total - passed

    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\nFailed Tests:")
        for result in test_results:
            if result["status"] == "FAIL":
                print(f"  - {result['test_name']}")
                if result["message"]:
                    print(f"    {result['message']}")

    print("\n" + "=" * 60)

    return failed == 0

if __name__ == "__main__":
    print("Test Agent 3: Status Commands and Connection Info Display")
    print("=" * 60)

    # Run all tests
    test_remote_get_status()
    test_remote_get_connection_info()
    test_pairing_code_format()
    test_websocket_url_format()
    test_relay_get_status()
    test_relay_get_relay_info()
    test_relay_websocket_urls()

    # Print summary
    all_passed = print_summary()

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)
