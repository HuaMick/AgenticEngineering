# Test Agent 1: Remote Terminal Service Start/Stop Lifecycle

## Test Date
2025-12-06

## Test Scope
Testing the Remote Terminal service start/stop lifecycle as defined in the live plan:
1. Run 'myagents remote start' and verify process spawns
2. Verify PID file created at ~/.config/myagents/remote.state
3. Verify terminal service listening on WebSocket port
4. Run 'myagents remote stop' and verify graceful shutdown
5. Verify PID file cleaned up and process terminated

## Test Status: FAIL

## Summary
The Remote Terminal service lifecycle tests **FAILED** due to critical implementation issues in the RemoteWorkflow class. The workflow class exists and has the correct method signatures, but contains incorrect implementation that prevents the service from starting.

## Test Results

### Test 1: Service start command
**Status**: FAIL

**Test Method**: Direct Python API testing via RemoteWorkflow.start_service()

**Expected Behavior**:
- start_service() should spawn a terminal service process
- The process should provide PTY sessions via WebSocket

**Actual Behavior**:
- start_service() attempts to execute: `python -m agent_remote.services.relay.api.server`
- This is the RELAY service, not the terminal service
- Error: `[Errno 2] No such file or directory: 'python'`

**Root Cause**:
1. Incorrect module path in command (line 89 of remote_workflow.py)
2. Hardcoded 'python' instead of sys.executable (line 87)

### Test 2: Missing terminal server implementation
**Status**: FAIL

**Test Method**: File system inspection

**Expected Behavior**:
- Terminal service should have an api/server.py module that can be run
- Similar to relay service structure: agent_remote.services.relay.api.server

**Actual Behavior**:
- No terminal service server implementation exists
- Terminal service directory structure:
  ```
  agent_remote/services/terminal/
  ├── domains/
  │   ├── pty_manager/
  │   ├── crypto/
  │   └── io_buffer/
  └── workflows/
      └── remote_workflow.py
  ```
- Missing: `api/` directory and `server.py` module

**Root Cause**:
- Terminal service API layer not implemented yet
- RemoteWorkflow assumes a server exists but it doesn't

### Test 3: PID file creation
**Status**: NOT TESTED

**Reason**: Cannot test because service fails to start (prerequisite failure)

### Test 4: Process verification
**Status**: NOT TESTED

**Reason**: Cannot test because service fails to start (prerequisite failure)

### Test 5: Port listening verification
**Status**: NOT TESTED

**Reason**: Cannot test because service fails to start (prerequisite failure)

### Test 6: Service stop/cleanup
**Status**: NOT TESTED

**Reason**: Cannot test because service never successfully starts (prerequisite failure)

## Failures Identified

### Failure 1: Incorrect service module reference
- **File**: /home/code/myagents/RemoteAgents/src/agent_remote/services/terminal/workflows/remote_workflow.py
- **Line**: 89
- **Issue**: Points to relay server instead of terminal server
- **Current Code**:
  ```python
  command = [
      "python",
      "-m",
      "agent_remote.services.relay.api.server"
  ]
  ```
- **Should Be**:
  ```python
  command = [
      sys.executable,
      "-m",
      "agent_remote.services.terminal.api.server"  # If it existed
  ]
  ```

### Failure 2: Missing terminal server implementation
- **Location**: /home/code/myagents/RemoteAgents/src/agent_remote/services/terminal/
- **Missing Components**:
  - api/ directory
  - api/server.py (main server entrypoint)
  - api/websockets.py (WebSocket endpoints for PTY sessions)
  - api/__init__.py
- **Impact**: Cannot start terminal service even if workflow is fixed

### Failure 3: Hardcoded Python executable
- **File**: /home/code/myagents/RemoteAgents/src/agent_remote/services/terminal/workflows/remote_workflow.py
- **Line**: 87
- **Issue**: Uses 'python' instead of sys.executable
- **Impact**: Fails in detached subprocess context (FileNotFoundError)
- **Fix Required**: Import sys and use sys.executable

## Files Involved
1. /home/code/myagents/RemoteAgents/src/agent_remote/services/terminal/workflows/remote_workflow.py
2. /home/code/myagents/MyAgents-remote/src/myagents/frontend/cli/myagents_cli.py (CLI integration)
3. /home/code/myagents/RemoteAgents/src/agent_remote/services/terminal/ (missing api module)

## Recommendations

### Immediate Fixes Required
1. **Create terminal service server module**:
   - Implement agent_remote.services.terminal.api.server
   - Model after relay service structure
   - Provide WebSocket endpoints for PTY sessions

2. **Fix RemoteWorkflow command**:
   - Change module path from relay to terminal server
   - Use sys.executable instead of 'python'

3. **Implement terminal service API**:
   - Create api/server.py with FastAPI application
   - Create WebSocket endpoints for PTY connections
   - Integrate with existing pty_manager domain

### Architecture Clarification Needed
The live plan mentions "terminal service" and "relay service" as separate services, but the current implementation appears confused:
- Should the terminal service be a standalone WebSocket server?
- Or should it connect TO the relay service as a client?
- The RemoteWorkflow seems to assume standalone, but no server exists

## Test Artifacts
- Test script: /home/code/myagents/RemoteAgents/test_remote_lifecycle.py
- Test output: See above
- Updated live plan: /home/code/myagents/docs/plans/live/251203_remoteagents_cli-integration.yml

## Conclusion
**FAIL**: Remote Terminal service cannot start due to:
1. Incorrect module reference (points to relay instead of terminal)
2. Missing terminal server implementation
3. Hardcoded Python executable path

All three issues must be fixed before the service can be tested. The workflow class structure is correct (methods, state file handling, etc.) but the implementation is incomplete.
