#!/usr/bin/env python3
"""Test script for Remote Terminal service start/stop lifecycle.

This script tests the following:
1. Run 'start_service()' and verify process spawns
2. Verify PID file created at ~/.config/myagents/remote.state
3. Verify terminal service listening on WebSocket port
4. Run 'stop_service()' and verify graceful shutdown
5. Verify PID file cleaned up and process terminated
"""

import sys
import time
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent_remote.services.terminal.workflows.remote_workflow import RemoteWorkflow


def test_remote_lifecycle():
    """Test the complete Remote Terminal service lifecycle."""
    print("=" * 70)
    print("Remote Terminal Service Lifecycle Test")
    print("=" * 70)
    print()

    # Initialize workflow
    workflow = RemoteWorkflow(home_config_dir=None)
    state_file = workflow.state_file

    print(f"State file location: {state_file}")
    print(f"Log directory: {workflow.log_dir}")
    print()

    # Test 1: Ensure service is not already running
    print("Test 1: Checking initial state...")
    if workflow.is_running():
        print("FAIL: Service is already running. Stopping it first...")
        success, msg = workflow.stop_service(force=True)
        if not success:
            print(f"FAIL: Could not stop existing service: {msg}")
            return False
        time.sleep(2)  # Wait for cleanup

    if state_file.exists():
        print(f"WARN: State file exists at {state_file}, removing...")
        state_file.unlink()

    print("PASS: Service is not running, state is clean")
    print()

    # Test 2: Start the service in background
    print("Test 2: Starting Remote Terminal service...")
    test_port = 9090  # Use a different port for testing
    success, message = workflow.start_service(port=test_port, background=True)

    if not success:
        print(f"FAIL: Could not start service")
        print(f"Message: {message}")
        return False

    print(f"PASS: Service start initiated")
    print(f"Message: {message}")
    print()

    # Test 3: Verify PID file was created
    print("Test 3: Verifying PID file creation...")
    if not state_file.exists():
        print(f"FAIL: State file not created at {state_file}")
        return False

    print(f"PASS: State file created at {state_file}")

    # Read and display state
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
        print(f"State contents:")
        for key, value in state.items():
            print(f"  {key}: {value}")

        if "pid" not in state:
            print("FAIL: PID not found in state file")
            return False

        pid = state["pid"]
        print(f"PASS: PID {pid} recorded in state file")
    except Exception as e:
        print(f"FAIL: Could not read state file: {e}")
        return False
    print()

    # Test 4: Verify process is running
    print("Test 4: Verifying process is running...")
    if not workflow.is_running():
        print("FAIL: Service reports as not running after start")
        return False

    print(f"PASS: Service is running")
    print()

    # Test 5: Verify port is listening
    print(f"Test 5: Verifying WebSocket port {test_port} is listening...")
    if not workflow._is_port_in_use(test_port):
        print(f"FAIL: Port {test_port} is not in use")
        # This might be expected if the service takes time to start
        print("INFO: Waiting 5 more seconds for service to bind port...")
        time.sleep(5)
        if not workflow._is_port_in_use(test_port):
            print(f"FAIL: Port {test_port} still not in use after waiting")
            # Get recent errors
            recent_errors = workflow._get_recent_errors(num_lines=30)
            if recent_errors:
                print("\nRecent errors from logs:")
                print(recent_errors)
            return False

    print(f"PASS: Port {test_port} is listening")
    print()

    # Test 6: Get status
    print("Test 6: Getting service status...")
    status = workflow.get_status()
    print("Status:")
    for key, value in status.items():
        if key != "connection_info":
            print(f"  {key}: {value}")

    if not status.get("running"):
        print("FAIL: Status reports service not running")
        return False

    print("PASS: Status shows service running")
    print()

    # Test 7: Stop the service gracefully
    print("Test 7: Stopping service gracefully...")
    success, message = workflow.stop_service(force=False)

    if not success:
        print(f"FAIL: Could not stop service gracefully")
        print(f"Message: {message}")
        return False

    print(f"PASS: Service stopped gracefully")
    print(f"Message: {message}")
    print()

    # Test 8: Verify process terminated
    print("Test 8: Verifying process is terminated...")
    time.sleep(1)  # Give it a moment

    if workflow.is_running():
        print("FAIL: Service still reports as running after stop")
        return False

    print("PASS: Process is terminated")
    print()

    # Test 9: Verify PID file is cleaned up
    print("Test 9: Verifying PID file cleanup...")
    if state_file.exists():
        print(f"FAIL: State file still exists at {state_file}")
        return False

    print("PASS: PID file cleaned up")
    print()

    # All tests passed
    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
    return True


if __name__ == "__main__":
    try:
        success = test_remote_lifecycle()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
