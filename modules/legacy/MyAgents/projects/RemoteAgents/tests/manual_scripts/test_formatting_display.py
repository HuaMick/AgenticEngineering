#!/usr/bin/env python3
"""Test formatting display methods for connection info and relay info."""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent_remote.services.terminal.workflows.remote_workflow import RemoteWorkflow
from agent_remote.services.relay.workflows.relay_service_workflow import RelayServiceWorkflow

def test_remote_connection_info_format():
    """Test RemoteWorkflow.format_connection_info() method."""
    print("=" * 60)
    print("Testing RemoteWorkflow.format_connection_info()")
    print("=" * 60)

    # Create sample connection info
    conn_info = {
        "session_id": "test-session-123",
        "pairing_code": "ABC123",
        "websocket_url": "ws://0.0.0.0:8080/ws/desktop/test-session-123",
        "relay_url": "http://0.0.0.0:8080",
        "status": "CONNECTED"
    }

    formatted = RemoteWorkflow.format_connection_info(conn_info)
    print("\nFormatted output (CONNECTED):")
    print(formatted)

    # Test with WAITING status
    conn_info["status"] = "WAITING"
    conn_info["session_id"] = None
    formatted = RemoteWorkflow.format_connection_info(conn_info)
    print("\n\nFormatted output (WAITING):")
    print(formatted)

    # Test with DISCONNECTED status
    conn_info["status"] = "DISCONNECTED"
    conn_info["pairing_code"] = None
    formatted = RemoteWorkflow.format_connection_info(conn_info)
    print("\n\nFormatted output (DISCONNECTED):")
    print(formatted)

def test_relay_info_format():
    """Test RelayServiceWorkflow.format_relay_info() method."""
    print("\n\n" + "=" * 60)
    print("Testing RelayServiceWorkflow.format_relay_info()")
    print("=" * 60)

    # Create sample relay info
    relay_info = {
        "relay_url": "http://0.0.0.0:8080",
        "websocket_endpoints": {
            "desktop": "ws://0.0.0.0:8080/ws/desktop/{session_id}",
            "client": "ws://0.0.0.0:8080/ws/client/{pairing_code}"
        },
        "active_sessions": 3,
        "health": "HEALTHY"
    }

    formatted = RelayServiceWorkflow.format_relay_info(relay_info)
    print("\nFormatted output (HEALTHY, 3 sessions):")
    print(formatted)

    # Test with DEGRADED health
    relay_info["health"] = "DEGRADED"
    relay_info["active_sessions"] = 1
    formatted = RelayServiceWorkflow.format_relay_info(relay_info)
    print("\n\nFormatted output (DEGRADED, 1 session):")
    print(formatted)

    # Test with UNHEALTHY
    relay_info["health"] = "UNHEALTHY"
    relay_info["active_sessions"] = 0
    formatted = RelayServiceWorkflow.format_relay_info(relay_info)
    print("\n\nFormatted output (UNHEALTHY, 0 sessions):")
    print(formatted)

def test_pairing_code_formatting():
    """Test pairing code formatting edge cases."""
    print("\n\n" + "=" * 60)
    print("Testing Pairing Code Formatting")
    print("=" * 60)

    test_cases = [
        ("ABC123", "ABC-123"),
        ("XYZ999", "XYZ-999"),
        ("A1B2C3", "A1B-2C3"),
        ("123456", "123-456"),
        ("ABCDEF", "ABC-DEF"),
        ("AB12", "AB12"),  # Wrong length - should be unchanged
        ("ABCDEFG", "ABCDEFG"),  # Wrong length - should be unchanged
        ("", ""),  # Empty string
    ]

    print("\nTest Cases:")
    print(f"{'Input':<15} {'Expected':<15} {'Actual':<15} {'Status':<10}")
    print("-" * 60)

    all_passed = True
    for input_code, expected in test_cases:
        actual = RemoteWorkflow.format_pairing_code(input_code)
        passed = actual == expected
        status = "PASS" if passed else "FAIL"
        print(f"{input_code:<15} {expected:<15} {actual:<15} {status:<10}")
        if not passed:
            all_passed = False

    return all_passed

if __name__ == "__main__":
    test_remote_connection_info_format()
    test_relay_info_format()
    all_passed = test_pairing_code_formatting()

    print("\n\n" + "=" * 60)
    if all_passed:
        print("All formatting tests PASSED")
    else:
        print("Some formatting tests FAILED")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)
