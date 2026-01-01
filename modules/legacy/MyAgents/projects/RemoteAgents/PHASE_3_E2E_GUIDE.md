# Phase 3: E2E Relay Integration & UAT Guide

**Status**: Ready for Next Session
**Priority**: High
**Estimated Effort**: 2-3 hours
**Type**: Testing & Validation (all code exists)

## Overview

Phase 3 validates the complete E2E flow: Desktop CLI ↔ Relay Service ↔ Terminal Service ↔ PTY

**Key Point**: All implementation code already exists! This phase is about TESTING, not coding.

## What Exists

### Completed Components

| Component | Location | Lines | Status |
|-----------|----------|-------|--------|
| Terminal Service | `src/agent_remote/services/terminal/api/` | 574 | ✅ Phase 1-2 |
| RelayClient | `src/agent_remote/services/terminal/infrastructure/relay_client.py` | 655 | ✅ Exists |
| SessionWorkflow | `src/agent_remote/services/terminal/workflows/session_workflow.py` | 352 | ✅ Exists |
| Relay Service | RemoteAgents main branch | - | ✅ Merged |

### Architecture

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐         ┌─────┐
│  Web Client │◄────────│Relay Service│────────►│Terminal     │────────►│ PTY │
│  (Browser)  │ Pairing │ (Port 8080) │ Session │Service      │  spawn  │Shell│
└─────────────┘  Code   └─────────────┘   ID    │(Port 8081)  │         └─────┘
       │                       ▲                  │             │
       │                       │                  │  Existing   │
       │                ┌──────┴────────┐        │  Code       │
       └────pairing────►│SessionWorkflow│        │  (Phase 1-2)│
          code          │(Desktop CLI)  │        └─────────────┘
                        └───────────────┘
```

## Prerequisites

1. **Relay Service** running on port 8080
   - Source: RemoteAgents main branch
   - Status: Completed and merged in earlier phase

2. **Terminal Service** running on port 8081
   - Source: RemoteAgents-pty worktree (this branch)
   - Status: Completed in Phases 1-2

3. **Desktop CLI** components
   - SessionWorkflow for orchestration
   - RelayClient for relay communication
   - TerminalWorkflow for PTY management

## Quick Start

### Terminal 1: Start Relay Service
```bash
cd /home/code/myagents/RemoteAgents
uvicorn agent_remote.services.relay.api.server:app --host 0.0.0.0 --port 8080
```

Expected output:
```
INFO - Starting Agent Remote Relay Service
INFO - Relay service startup complete
INFO - Uvicorn running on http://0.0.0.0:8080
```

### Terminal 2: Start Terminal Service
```bash
cd /home/code/myagents/RemoteAgents-pty
TERMINAL_PORT=8081 uvicorn agent_remote.services.terminal.api.server:app --host 0.0.0.0
```

Expected output:
```
INFO - Starting Agent Remote Terminal Service
INFO - Terminal Shell: /bin/bash
INFO - Workflow initialized: TerminalWorkflow
INFO - Terminal service startup complete
INFO - Uvicorn running on http://0.0.0.0:8081
```

### Terminal 3: Run E2E Test
```bash
cd /home/code/myagents/RemoteAgents-pty
.venv/bin/python tests/e2e/test_full_flow.py
```

## Task List

### Phase 3 Tasks (10 items)

- [ ] **Task 1**: Start relay service in test environment
  - Command: `uvicorn agent_remote.services.relay.api.server:app --port 8080`
  - Validation: Health check at http://localhost:8080/health

- [ ] **Task 2**: Start terminal service on port 8081
  - Command: `TERMINAL_PORT=8081 uvicorn agent_remote.services.terminal.api.server:app`
  - Validation: Health check at http://localhost:8081/health

- [ ] **Task 3**: Test desktop CLI session creation
  - Use: `SessionWorkflow.create_session()`
  - Validates: POST /api/sessions returns session_id + pairing_code
  - File: `src/agent_remote/services/terminal/workflows/session_workflow.py`

- [ ] **Task 4**: Test RelayClient connection to relay service
  - Validates: WebSocket connects to `ws://localhost:8080/ws/desktop/{session_id}`
  - File: `src/agent_remote/services/terminal/infrastructure/relay_client.py`

- [ ] **Task 5**: Test E2E encrypted I/O flow
  - Send: Terminal input → Relay → Desktop → PTY
  - Receive: PTY output → Desktop → Relay → Client
  - Validates: E2E encryption with NaCl box

- [ ] **Task 6**: Test client pairing flow
  - Simulate web client connecting with pairing code
  - Validates: SessionPair + SessionPaired messages

- [ ] **Task 7**: Test window resize propagation
  - Send: TerminalResize → Relay → Desktop → PTY
  - Validates: SIGWINCH signal sent to PTY

- [ ] **Task 8**: Test session cleanup across services
  - Close session and verify cleanup in all 3 services
  - Validates: No orphaned PTY processes

- [ ] **Task 9**: Write E2E integration test suite
  - Create: `tests/services/terminal/e2e/test_relay_integration.py`
  - Automate all E2E validation scenarios

- [ ] **Task 10**: Run UAT validation for all user stories
  - Validate: US-E2E-001 through US-E2E-005
  - Document results in UAT report

## User Stories

### Phase 1-2 Stories (Completed) ✅

- ✅ US-PTY-001: Create PTY session via WebSocket
- ✅ US-PTY-002: Send input to PTY session
- ✅ US-PTY-003: Receive output from PTY session
- ✅ US-PTY-004: Resize terminal window
- ✅ US-PTY-005: Close PTY session gracefully

### Phase 3 Stories (Pending) ⏳

#### US-E2E-001: Desktop creates session via relay API
**Description**: Desktop CLI creates session through relay, gets session_id and pairing_code

**Acceptance Criteria**:
- SessionWorkflow.create_session() succeeds
- POST /api/sessions returns 200 OK
- Response contains valid session_id (UUID)
- Response contains valid pairing_code (6 chars)
- Desktop keypair generated for E2E encryption

**Test Approach**:
1. Start relay service on port 8080
2. Run `SessionWorkflow.create_session(relay_url="http://localhost:8080")`
3. Verify response contains session_id and pairing_code
4. Verify keypair generated (public_key, private_key)

---

#### US-E2E-002: Desktop connects to relay and starts PTY
**Description**: Desktop connects to relay via WebSocket and spawns local PTY

**Acceptance Criteria**:
- RelayClient connects to `ws://relay:8080/ws/desktop/{session_id}`
- WebSocket handshake succeeds
- PTY session created via TerminalWorkflow
- PTY process spawns with shell
- PTY output callback registered

**Test Approach**:
1. Create session (US-E2E-001)
2. Run `SessionWorkflow.start()`
3. Verify `RelayClient.is_connected == True`
4. Verify PTY session exists in repository
5. Verify PTY process is running (check PID)

---

#### US-E2E-003: Web client pairs and establishes encryption
**Description**: Client connects with pairing code, E2E encryption established

**Acceptance Criteria**:
- Client connects to `ws://relay:8080/ws/client/{pairing_code}`
- Client sends SessionPair with client_public_key
- Relay validates pairing code
- Relay sends SessionPaired to both sides
- Desktop receives client_public_key
- Both sides can encrypt/decrypt

**Test Approach**:
1. Desktop creates session and starts (US-E2E-001, US-E2E-002)
2. Simulate web client connection with pairing code
3. Verify SessionPaired messages received
4. Verify desktop has client_public_key set
5. Test encrypt/decrypt roundtrip

---

#### US-E2E-004: Terminal I/O flows through encrypted relay
**Description**: Terminal data flows bidirectionally through encrypted relay

**Acceptance Criteria**:
- Client sends TerminalInput → Relay (encrypted)
- Relay forwards EncryptedBlob → Desktop
- Desktop decrypts → gets TerminalInput
- Desktop sends to PTY via TerminalWorkflow
- PTY executes command
- Desktop encrypts TerminalOutput → EncryptedBlob
- Relay forwards to client
- Client decrypts output
- ANSI codes preserved

**Test Approach**:
1. Establish paired session (US-E2E-003)
2. Client sends: `echo "Hello E2E"` (encrypted)
3. Desktop receives, decrypts, forwards to PTY
4. PTY executes command
5. Desktop receives output, encrypts, sends
6. Client receives, decrypts, validates output

---

#### US-E2E-005: Session cleanup across all services
**Description**: Clean shutdown with no resource leaks

**Acceptance Criteria**:
- Client disconnect triggers TerminalClose
- Desktop receives close, stops PTY
- PTY process terminated (no orphans)
- Desktop closes relay WebSocket
- Relay removes session
- All connections closed gracefully

**Test Approach**:
1. Establish full E2E session (US-E2E-004)
2. Client sends TerminalClose or disconnects
3. Verify desktop receives close notification
4. Verify PTY terminates (PID gone)
5. Verify relay session removed (404)
6. Check for orphaned processes: `ps aux | grep bash`

## Test Script Template

Create `tests/e2e/test_full_flow.py`:

```python
import asyncio
from agent_remote.services.terminal.workflows.session_workflow import SessionWorkflow
from agent_remote.services.terminal.domains.pty_manager import TerminalDimensions

async def test_e2e_flow():
    # Create workflow
    workflow = SessionWorkflow(
        relay_url="http://localhost:8080",
        command=["bash"],
        dimensions=TerminalDimensions(rows=24, cols=80)
    )

    # US-E2E-001: Create session via relay API
    session_id, pairing_code = await workflow.create_session()
    print(f"✅ Session created: {session_id}")
    print(f"✅ Pairing code: {pairing_code}")

    # US-E2E-002: Start PTY and connect to relay
    await workflow.start()
    print("✅ PTY started and connected to relay")

    # US-E2E-004: Send test input
    await workflow.send_input(b"echo 'E2E Test Success'\n")
    print("✅ Sent test input to PTY")

    # Wait for output
    await asyncio.sleep(2)

    # US-E2E-005: Stop session
    exit_code = await workflow.stop()
    print(f"✅ Session stopped with exit code: {exit_code}")

if __name__ == "__main__":
    asyncio.run(test_e2e_flow())
```

## Validation Checklist

- [ ] Relay service starts on port 8080
- [ ] Terminal service starts on port 8081
- [ ] Desktop creates session (gets session_id and pairing_code)
- [ ] Desktop connects to relay WebSocket
- [ ] PTY process spawns
- [ ] Terminal I/O flows through relay (encrypted)
- [ ] Session cleanup works (no orphaned processes)

## Deliverables

1. **E2E Integration Test Suite**
   - File: `tests/services/terminal/e2e/test_relay_integration.py`
   - Automated E2E validation

2. **UAT Validation Report**
   - Document results for US-E2E-001 through US-E2E-005
   - Performance metrics (latency, throughput)

3. **Setup Documentation**
   - 3-service deployment guide
   - Environment configuration
   - Troubleshooting tips

4. **Security Validation**
   - E2E encryption verification
   - No plaintext terminal data in relay logs

## Success Criteria

Phase 3 is complete when:

✅ All 5 E2E user stories pass
✅ E2E test suite created and passing
✅ UAT report documents validation
✅ No orphaned PTY processes
✅ Encryption verified working
✅ Performance metrics documented

## Notes

- **No new code required** - all components exist
- **Focus on testing** - validate existing implementation
- **Expected effort**: 2-3 hours
- **Primary activity**: Running services, testing flows, documenting results

---

**Ready to execute in next session!** 🚀
