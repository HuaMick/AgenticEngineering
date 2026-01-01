#!/usr/bin/env python3
"""Sequential test script for Relay Service start/stop lifecycle.

This script tests the lifecycle sequentially (start -> verify -> stop -> cleanup)
to avoid state file conflicts between tests.
"""

import sys
import time
import json
import os
import signal
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent_remote.services.relay.workflows.relay_service_workflow import RelayServiceWorkflow


def main():
    """Run sequential lifecycle test."""
    print("=" * 70)
    print("RELAY SERVICE LIFECYCLE TEST (Sequential)")
    print("=" * 70)

    workflow = RelayServiceWorkflow()
    test_port = 9999
    test_host = "0.0.0.0"

    failures = []

    # Clean up any existing state
    if workflow.state_file.exists():
        workflow.state_file.unlink()
        print("Cleaned up existing state file")

    # STEP 1: Start relay service
    print("\n" + "=" * 70)
    print("STEP 1: Start relay service and verify uvicorn process spawns")
    print("=" * 70)

    success, message = workflow.start_relay(host=test_host, port=test_port, background=True)
    print(f"Start result: {success}")
    print(f"Message:\n{message}")

    if not success:
        failures.append({
            "test_name": "Start relay service",
            "component": "RelayServiceWorkflow.start_relay",
            "failure_description": "Failed to start relay service",
            "expected_behavior": "Relay should start successfully on port 9999",
            "actual_behavior": f"Start failed with message: {message}",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print("✗ FAILED: Could not start relay service")
        return failures

    if not workflow.is_running():
        failures.append({
            "test_name": "Verify process running",
            "component": "RelayServiceWorkflow.is_running",
            "failure_description": "Process not detected as running after start",
            "expected_behavior": "is_running() should return True after successful start",
            "actual_behavior": "is_running() returned False",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print("✗ FAILED: Process not running")
        return failures

    print("✓ PASSED: Relay service started and process is running")

    # STEP 2: Verify PID file
    print("\n" + "=" * 70)
    print("STEP 2: Verify PID file created at ~/.config/myagents/relay.state")
    print("=" * 70)

    if not workflow.state_file.exists():
        failures.append({
            "test_name": "PID file creation",
            "component": "RelayServiceWorkflow._save_state",
            "failure_description": f"State file not created at {workflow.state_file}",
            "expected_behavior": "State file should be created on service start",
            "actual_behavior": "State file does not exist",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print(f"✗ FAILED: State file does not exist at {workflow.state_file}")
        # Try to stop before returning
        workflow.stop_relay(force=True)
        return failures

    print(f"✓ State file exists at: {workflow.state_file}")

    state = workflow._load_state()
    if not state:
        failures.append({
            "test_name": "PID file contents",
            "component": "RelayServiceWorkflow._save_state",
            "failure_description": "State file exists but is empty or invalid JSON",
            "expected_behavior": "State file should contain valid JSON with process info",
            "actual_behavior": "State file is empty or invalid",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print("✗ FAILED: State file is empty or invalid")
        workflow.stop_relay(force=True)
        return failures

    print(f"State file contents: {json.dumps(state, indent=2)}")

    required_fields = ["pid", "host", "port", "started_at"]
    missing_fields = [f for f in required_fields if f not in state]
    if missing_fields:
        failures.append({
            "test_name": "PID file required fields",
            "component": "RelayServiceWorkflow._save_state",
            "failure_description": f"State file missing required fields: {missing_fields}",
            "expected_behavior": f"State file should contain: {required_fields}",
            "actual_behavior": f"Missing fields: {missing_fields}",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print(f"✗ FAILED: Missing required fields: {missing_fields}")
        workflow.stop_relay(force=True)
        return failures

    print(f"✓ PASSED: State file contains all required fields")

    # Verify PID is correct
    saved_pid = state["pid"]
    try:
        os.kill(saved_pid, 0)
        print(f"✓ PID {saved_pid} is valid and process exists")
    except ProcessLookupError:
        failures.append({
            "test_name": "PID validity",
            "component": "RelayServiceWorkflow.start_relay",
            "failure_description": f"PID {saved_pid} in state file does not correspond to running process",
            "expected_behavior": "PID in state file should be a running process",
            "actual_behavior": f"Process with PID {saved_pid} not found",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print(f"✗ FAILED: PID {saved_pid} does not exist")
        return failures

    # STEP 3: Verify health endpoint
    print("\n" + "=" * 70)
    print("STEP 3: Verify relay endpoints available via health check")
    print("=" * 70)

    print("Waiting 3 seconds for server to fully initialize...")
    time.sleep(3)

    status = workflow.get_status()
    print(f"Status:\n{json.dumps(status, indent=2)}")

    if not status.get("running"):
        failures.append({
            "test_name": "Service running status",
            "component": "RelayServiceWorkflow.get_status",
            "failure_description": "get_status() reports service not running",
            "expected_behavior": "get_status() should report running=True",
            "actual_behavior": f"running={status.get('running')}",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print("✗ FAILED: Service not detected as running")
        workflow.stop_relay(force=True)
        return failures

    print("✓ Service reported as running")

    if not status.get("healthy"):
        failures.append({
            "test_name": "Health endpoint check",
            "component": "RelayServiceWorkflow._get_health_info",
            "failure_description": "Health endpoint not responding or unhealthy",
            "expected_behavior": "Health endpoint should respond with healthy status",
            "actual_behavior": f"healthy={status.get('healthy')}",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py",
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/api/server.py"
            ]
        })
        print("✗ FAILED: Health endpoint not healthy")
        workflow.stop_relay(force=True)
        return failures

    print("✓ Health endpoint responded successfully")

    expected_endpoints = ["desktop_endpoint", "client_endpoint"]
    for endpoint in expected_endpoints:
        if endpoint not in status:
            failures.append({
                "test_name": "Endpoint presence",
                "component": "RelayServiceWorkflow.get_status",
                "failure_description": f"Status missing endpoint: {endpoint}",
                "expected_behavior": f"Status should contain {expected_endpoints}",
                "actual_behavior": f"Missing {endpoint}",
                "files_involved": [
                    "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
                ]
            })
            print(f"✗ FAILED: Missing endpoint {endpoint}")
            workflow.stop_relay(force=True)
            return failures

    print(f"✓ PASSED: All expected endpoints present")

    # Verify endpoint formats
    if "/ws/desktop/" not in status["desktop_endpoint"]:
        failures.append({
            "test_name": "Desktop endpoint format",
            "component": "RelayServiceWorkflow.get_status",
            "failure_description": f"Unexpected desktop endpoint format: {status['desktop_endpoint']}",
            "expected_behavior": "Desktop endpoint should contain /ws/desktop/",
            "actual_behavior": f"Got: {status['desktop_endpoint']}",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print(f"✗ FAILED: Desktop endpoint format incorrect")
        workflow.stop_relay(force=True)
        return failures

    if "/ws/client/" not in status["client_endpoint"]:
        failures.append({
            "test_name": "Client endpoint format",
            "component": "RelayServiceWorkflow.get_status",
            "failure_description": f"Unexpected client endpoint format: {status['client_endpoint']}",
            "expected_behavior": "Client endpoint should contain /ws/client/",
            "actual_behavior": f"Got: {status['client_endpoint']}",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print(f"✗ FAILED: Client endpoint format incorrect")
        workflow.stop_relay(force=True)
        return failures

    print("✓ PASSED: Endpoint formats are correct")

    # STEP 4: Graceful shutdown
    print("\n" + "=" * 70)
    print("STEP 4: Stop relay and verify graceful shutdown")
    print("=" * 70)

    state = workflow._load_state()
    pid = state["pid"]
    print(f"Relay PID: {pid}")

    # Try graceful shutdown
    success, message = workflow.stop_relay(force=False)
    print(f"Stop result (graceful): {success}")
    print(f"Message: {message}")

    # If graceful failed, try force (but record it as a failure)
    if not success:
        print("Graceful shutdown failed, trying force shutdown...")
        failures.append({
            "test_name": "Graceful shutdown timeout",
            "component": "RelayServiceWorkflow.stop_relay",
            "failure_description": "Relay server did not stop gracefully within timeout",
            "expected_behavior": "Server should respond to SIGTERM and shut down within 10 seconds",
            "actual_behavior": "Server did not stop after SIGTERM, required force kill",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py",
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/api/server.py"
            ]
        })

        success, message = workflow.stop_relay(force=True)
        print(f"Stop result (force): {success}")
        print(f"Message: {message}")

        if not success:
            failures.append({
                "test_name": "Force shutdown",
                "component": "RelayServiceWorkflow.stop_relay",
                "failure_description": "Failed to stop relay even with force",
                "expected_behavior": "Force shutdown should always succeed",
                "actual_behavior": f"Force shutdown failed: {message}",
                "files_involved": [
                    "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
                ]
            })
            print("✗ FAILED: Could not stop relay even with force")
            return failures

    print("✓ Relay service stopped")

    # Verify process is gone
    if workflow.is_running():
        failures.append({
            "test_name": "Process termination",
            "component": "RelayServiceWorkflow.stop_relay",
            "failure_description": "Process still detected as running after stop",
            "expected_behavior": "is_running() should return False after stop",
            "actual_behavior": "is_running() still returns True",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print("✗ FAILED: Process still running")
        # Force kill it
        workflow.stop_relay(force=True)
        return failures

    print("✓ Process is no longer running")

    # Verify state file cleaned up
    if workflow.state_file.exists():
        failures.append({
            "test_name": "State file cleanup",
            "component": "RelayServiceWorkflow.stop_relay",
            "failure_description": "State file still exists after stop",
            "expected_behavior": "State file should be removed on successful stop",
            "actual_behavior": f"State file still exists at {workflow.state_file}",
            "files_involved": [
                "/home/code/myagents/RemoteAgents/src/agent_remote/services/relay/workflows/relay_service_workflow.py"
            ]
        })
        print(f"✗ FAILED: State file still exists at {workflow.state_file}")
        # Clean it up manually
        workflow.state_file.unlink()
        return failures

    print(f"✓ PASSED: State file cleaned up")

    # Final summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    if failures:
        print(f"RESULT: FAIL ({len(failures)} issue(s) found)")
        print("\nFailures:")
        for failure in failures:
            print(f"\n  - {failure['test_name']}:")
            print(f"    Component: {failure['component']}")
            print(f"    Description: {failure['failure_description']}")
            print(f"    Expected: {failure['expected_behavior']}")
            print(f"    Actual: {failure['actual_behavior']}")
        return failures
    else:
        print("RESULT: PASS")
        print("\nAll tests passed successfully!")
        print("- Relay starts correctly with uvicorn")
        print("- PID file created with correct information")
        print("- Health endpoints (/ws/desktop, /ws/client) accessible")
        print("- Graceful or force shutdown works")
        print("- State file cleanup successful")
        return []


if __name__ == "__main__":
    failures = main()
    sys.exit(0 if not failures else 1)
