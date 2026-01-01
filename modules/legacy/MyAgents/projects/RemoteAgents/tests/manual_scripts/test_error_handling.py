#!/usr/bin/env python3
"""
Test Agent 4: Error Handling and Edge Cases

This script tests error handling in the RemoteAgents CLI integration:
1. Double-start prevention
2. Port conflict handling
3. Stop when not running
4. Stale PID file handling (crashed service scenario)
5. Error message clarity
"""

import sys
import os
import json
import socket
import time
import signal
from pathlib import Path

# Add RemoteAgents to path
sys.path.insert(0, '/home/code/myagents/RemoteAgents/src')

from agent_remote.services.terminal.workflows.remote_workflow import RemoteWorkflow
from agent_remote.services.relay.workflows.relay_service_workflow import RelayServiceWorkflow


class TestResults:
    """Track test results"""
    def __init__(self):
        self.tests = []
        self.failures = []

    def add_test(self, name, passed, message):
        self.tests.append({
            'name': name,
            'passed': passed,
            'message': message
        })
        if not passed:
            self.failures.append({
                'test_name': name,
                'failure_description': message
            })

    def summary(self):
        total = len(self.tests)
        passed = sum(1 for t in self.tests if t['passed'])
        failed = total - passed
        return f"Tests: {total}, Passed: {passed}, Failed: {failed}"


def cleanup_state_files():
    """Clean up any existing state files before testing"""
    home_config = Path.home() / ".config" / "myagents"
    remote_state = home_config / "remote.state"
    relay_state = home_config / "relay.state"

    if remote_state.exists():
        remote_state.unlink()
    if relay_state.exists():
        relay_state.unlink()


def test_remote_double_start(results: TestResults):
    """Test 1: Double-start prevention for remote service"""
    print("\n=== Test 1: Remote Double-Start Prevention ===")

    cleanup_state_files()
    workflow = RemoteWorkflow()

    # Start service first time
    success1, msg1 = workflow.start_service(port=9001, background=True)
    print(f"First start: {success1}, Message: {msg1}")

    if not success1:
        results.add_test(
            "remote_double_start",
            False,
            f"First start failed: {msg1}"
        )
        return

    # Give it time to start
    time.sleep(4)

    # Try to start again (should fail with clear message)
    success2, msg2 = workflow.start_service(port=9001, background=True)
    print(f"Second start: {success2}, Message: {msg2}")

    # Clean up
    workflow.stop_service(force=True)
    time.sleep(2)

    # Validate results
    if success2:
        results.add_test(
            "remote_double_start",
            False,
            "Second start should have failed but succeeded"
        )
    elif "already running" not in msg2.lower():
        results.add_test(
            "remote_double_start",
            False,
            f"Error message not clear about 'already running'. Got: {msg2}"
        )
    else:
        results.add_test(
            "remote_double_start",
            True,
            "Double-start correctly prevented with clear message"
        )


def test_relay_double_start(results: TestResults):
    """Test 2: Double-start prevention for relay service"""
    print("\n=== Test 2: Relay Double-Start Prevention ===")

    cleanup_state_files()
    workflow = RelayServiceWorkflow()

    # Start service first time
    success1, msg1 = workflow.start_relay(host="0.0.0.0", port=9002, background=True)
    print(f"First start: {success1}, Message: {msg1}")

    if not success1:
        results.add_test(
            "relay_double_start",
            False,
            f"First start failed: {msg1}"
        )
        return

    # Give it time to start
    time.sleep(4)

    # Try to start again (should fail with clear message)
    success2, msg2 = workflow.start_relay(host="0.0.0.0", port=9002, background=True)
    print(f"Second start: {success2}, Message: {msg2}")

    # Clean up
    workflow.stop_relay(force=True)
    time.sleep(2)

    # Validate results
    if success2:
        results.add_test(
            "relay_double_start",
            False,
            "Second start should have failed but succeeded"
        )
    elif "already running" not in msg2.lower():
        results.add_test(
            "relay_double_start",
            False,
            f"Error message not clear about 'already running'. Got: {msg2}"
        )
    else:
        results.add_test(
            "relay_double_start",
            True,
            "Double-start correctly prevented with clear message"
        )


def test_port_conflict_remote(results: TestResults):
    """Test 3: Port already in use for remote service"""
    print("\n=== Test 3: Remote Port Conflict Handling ===")

    cleanup_state_files()
    workflow = RemoteWorkflow()
    test_port = 9003

    # Bind to port manually
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", test_port))
        sock.listen(1)
        print(f"Manually bound to port {test_port}")

        # Try to start service on same port
        success, msg = workflow.start_service(port=test_port, background=True)
        print(f"Start result: {success}, Message: {msg}")

        # Validate
        if success:
            results.add_test(
                "remote_port_conflict",
                False,
                "Service started despite port being in use"
            )
            workflow.stop_service(force=True)
        elif "already in use" not in msg.lower() and "port" not in msg.lower():
            results.add_test(
                "remote_port_conflict",
                False,
                f"Error message not clear about port conflict. Got: {msg}"
            )
        else:
            results.add_test(
                "remote_port_conflict",
                True,
                "Port conflict correctly detected with clear message"
            )
    finally:
        sock.close()


def test_port_conflict_relay(results: TestResults):
    """Test 4: Port already in use for relay service"""
    print("\n=== Test 4: Relay Port Conflict Handling ===")

    cleanup_state_files()
    workflow = RelayServiceWorkflow()
    test_port = 9004

    # Bind to port manually
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", test_port))
        sock.listen(1)
        print(f"Manually bound to port {test_port}")

        # Try to start service on same port
        success, msg = workflow.start_relay(host="0.0.0.0", port=test_port, background=True)
        print(f"Start result: {success}, Message: {msg}")

        # Validate
        if success:
            results.add_test(
                "relay_port_conflict",
                False,
                "Service started despite port being in use"
            )
            workflow.stop_relay(force=True)
        elif "already in use" not in msg.lower() and "port" not in msg.lower():
            results.add_test(
                "relay_port_conflict",
                False,
                f"Error message not clear about port conflict. Got: {msg}"
            )
        else:
            results.add_test(
                "relay_port_conflict",
                True,
                "Port conflict correctly detected with clear message"
            )
    finally:
        sock.close()


def test_stop_not_running_remote(results: TestResults):
    """Test 5: Stop remote service when not running"""
    print("\n=== Test 5: Stop Remote When Not Running ===")

    cleanup_state_files()
    workflow = RemoteWorkflow()

    # Ensure not running
    if workflow.is_running():
        workflow.stop_service(force=True)
        time.sleep(2)

    # Try to stop when not running
    success, msg = workflow.stop_service()
    print(f"Stop result: {success}, Message: {msg}")

    # Validate - should fail gracefully with clear message
    if success:
        results.add_test(
            "remote_stop_not_running",
            False,
            "Stop succeeded when service wasn't running (should indicate not running)"
        )
    elif "not running" not in msg.lower():
        results.add_test(
            "remote_stop_not_running",
            False,
            f"Error message not clear about service not running. Got: {msg}"
        )
    else:
        results.add_test(
            "remote_stop_not_running",
            True,
            "Stop correctly indicated service not running with clear message"
        )


def test_stop_not_running_relay(results: TestResults):
    """Test 6: Stop relay service when not running"""
    print("\n=== Test 6: Stop Relay When Not Running ===")

    cleanup_state_files()
    workflow = RelayServiceWorkflow()

    # Ensure not running
    if workflow.is_running():
        workflow.stop_relay(force=True)
        time.sleep(2)

    # Try to stop when not running
    success, msg = workflow.stop_relay()
    print(f"Stop result: {success}, Message: {msg}")

    # Validate - should fail gracefully with clear message
    if success:
        results.add_test(
            "relay_stop_not_running",
            False,
            "Stop succeeded when service wasn't running (should indicate not running)"
        )
    elif "not running" not in msg.lower():
        results.add_test(
            "relay_stop_not_running",
            False,
            f"Error message not clear about service not running. Got: {msg}"
        )
    else:
        results.add_test(
            "relay_stop_not_running",
            True,
            "Stop correctly indicated service not running with clear message"
        )


def test_stale_pid_remote(results: TestResults):
    """Test 7: Stale PID file handling for remote service"""
    print("\n=== Test 7: Remote Stale PID File Handling ===")

    cleanup_state_files()
    workflow = RemoteWorkflow()

    # Create fake state file with dead PID
    fake_state = {
        "pid": 99999,  # Non-existent PID
        "port": 9005,
        "host": "0.0.0.0",
        "started_at": "2024-01-01T00:00:00Z"
    }

    workflow.state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(workflow.state_file, 'w') as f:
        json.dump(fake_state, f)

    print(f"Created fake state file with PID {fake_state['pid']}")

    # Check status (should detect stale PID)
    status = workflow.get_status()
    print(f"Status: running={status['running']}")

    # Try to start service (should work, cleaning up stale state)
    success, msg = workflow.start_service(port=9005, background=True)
    print(f"Start result: {success}, Message: {msg}")

    # Clean up
    if success:
        time.sleep(3)
        workflow.stop_service(force=True)

    # Validate
    if not status['running']:
        results.add_test(
            "remote_stale_pid",
            True,
            "Stale PID correctly detected as not running"
        )
    else:
        results.add_test(
            "remote_stale_pid",
            False,
            "Stale PID incorrectly reported as running"
        )


def test_stale_pid_relay(results: TestResults):
    """Test 8: Stale PID file handling for relay service"""
    print("\n=== Test 8: Relay Stale PID File Handling ===")

    cleanup_state_files()
    workflow = RelayServiceWorkflow()

    # Create fake state file with dead PID
    fake_state = {
        "pid": 99998,  # Non-existent PID
        "port": 9006,
        "host": "0.0.0.0",
        "started_at": "2024-01-01T00:00:00Z"
    }

    workflow.state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(workflow.state_file, 'w') as f:
        json.dump(fake_state, f)

    print(f"Created fake state file with PID {fake_state['pid']}")

    # Check status (should detect stale PID)
    status = workflow.get_status()
    print(f"Status: running={status['running']}")

    # Try to start service (should work, cleaning up stale state)
    success, msg = workflow.start_relay(host="0.0.0.0", port=9006, background=True)
    print(f"Start result: {success}, Message: {msg}")

    # Clean up
    if success:
        time.sleep(3)
        workflow.stop_relay(force=True)

    # Validate
    if not status['running']:
        results.add_test(
            "relay_stale_pid",
            True,
            "Stale PID correctly detected as not running"
        )
    else:
        results.add_test(
            "relay_stale_pid",
            False,
            "Stale PID incorrectly reported as running"
        )


def main():
    """Run all error handling tests"""
    print("=" * 60)
    print("Test Agent 4: Error Handling and Edge Cases")
    print("=" * 60)

    results = TestResults()

    try:
        # Run all tests
        test_remote_double_start(results)
        test_relay_double_start(results)
        test_port_conflict_remote(results)
        test_port_conflict_relay(results)
        test_stop_not_running_remote(results)
        test_stop_not_running_relay(results)
        test_stale_pid_remote(results)
        test_stale_pid_relay(results)

        # Final cleanup
        cleanup_state_files()

        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(results.summary())
        print()

        for test in results.tests:
            status = "PASS" if test['passed'] else "FAIL"
            print(f"{status}: {test['name']}")
            if not test['passed']:
                print(f"  -> {test['message']}")

        # Return results
        return results

    except Exception as e:
        print(f"\nERROR: Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        return results


if __name__ == "__main__":
    results = main()

    # Exit with failure code if any tests failed
    sys.exit(0 if len(results.failures) == 0 else 1)
