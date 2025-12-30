# Infrastructure Workflow Testing Guide

This directory contains tests for cross-cutting infrastructure components including CLI commands and Studio service.

## Test Structure

- `test_cli_integration.py` - CLI command integration tests
- `test_studio_service.py` - LangGraph Studio service endpoint tests

## Testing Guidance

### Studio Service Testing Pattern

When testing Studio service, follow this lifecycle pattern:

1. **Start the server**
   ```bash
   myagents studio start
   ```

2. **Check its status**
   ```bash
   myagents studio status
   ```
   - Verify service reports as RUNNING
   - Verify port is accessible (default: 2024)
   - Verify health endpoint responds: `curl http://127.0.0.1:2024/ok`

3. **Stop the server**
   ```bash
   myagents studio stop
   ```
   - Verify service reports as STOPPED
   - Verify port is no longer accessible
   - Verify health endpoint fails

4. **Try to start it again**
   ```bash
   myagents studio start
   ```
   - Verify it starts successfully after previous stop
   - Verify status is RUNNING again
   - Verify endpoints are accessible

### Test Scenarios

#### Studio Service Endpoints

Test all Studio endpoints in this order:

1. **Health Check** (`/ok`)
   - Verify returns 200 with `{"ok": true}`
   - Should be first endpoint to test

2. **Assistants Search** (`POST /assistants/search`)
   - Verify returns 200 with JSON array
   - Verify array contains at least one assistant
   - Verify assistant objects have required fields

3. **Get Assistant** (`GET /assistants/{id}`)
   - Get ID from search endpoint first
   - Verify returns 200 with assistant details
   - Test with invalid ID to verify error handling (404/422)

4. **Threads** (`POST /threads`, `GET /threads/{id}`)
   - Create thread and verify thread_id returned
   - Get thread details using thread_id
   - Verify thread data structure

5. **Stability Tests**
   - Test delayed validation (wait 10+ seconds, verify still responds)
   - Test under load (10 rapid sequential requests)
   - Verify no errors in logs

#### CLI Integration Tests

Test CLI commands in isolation:

1. **Help Commands**
   - `myagents --help` - Verify shows usage
   - `myagents chat --help` - Verify shows subcommand help
   - `myagents studio status` - Verify shows status info

2. **Preferences**
   - `myagents preferences list` - Verify returns list (even if empty)

3. **Error Handling**
   - Test commands with invalid arguments
   - Verify helpful error messages

## Running Tests

```bash
# Run all infrastructure tests
pytest tests/workflows/infrastructure/ -v

# Run Studio service tests only
pytest tests/workflows/infrastructure/test_studio_service.py -v

# Run CLI integration tests only
pytest tests/workflows/infrastructure/test_cli_integration.py -v

# Run with infrastructure marker
pytest -m infrastructure -v
```

## Prerequisites

- Studio service must be running for Studio tests (tests will skip if not running)
- CLI commands must be installed and available in PATH
- API keys configured via Secret Manager

## Test Markers

All tests use `@pytest.mark.infrastructure` marker for selective execution.

