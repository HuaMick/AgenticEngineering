# Agent Remote

Remote terminal access for AI coding agents. Enables controlling Claude Code terminal sessions from a web browser.

## Overview

Agent Remote provides:
- **Relay Service**: WebSocket relay server for encrypted communication
- **Terminal Service**: PTY wrapper to control Claude Code CLI remotely
- **E2E Encryption**: All communication is end-to-end encrypted using NaCl
- **Shared Contracts**: Protocol message types and crypto interfaces for cross-platform compatibility

## Architecture

```
Browser (Flutter Web)
    │
    │ WSS (E2E encrypted)
    ▼
Relay Server (FastAPI)
    │
    │ WSS (E2E encrypted)
    ▼
Desktop CLI (PTY wrapper around Claude Code)
```

## Critical Path

This package is a **critical path blocker** for:
- `relay-service` - Uses protocol messages and crypto interfaces
- `terminal-service` - Uses protocol messages and crypto interfaces
- `crypto-impl` - Implements crypto interfaces
- `cli-integration` - Uses protocol messages

## Installation

```bash
# For development (sibling to MyAgents)
cd /home/code/myagents
git clone <repo> RemoteAgents
cd RemoteAgents
uv sync

# Install in editable mode for development
pip install -e .
```

## Quick Start: Using Protocol Messages

```python
from agent_remote.shared.protocol import (
    TerminalOutput,
    TerminalInput,
    SessionCreate,
    deserialize_message,
    generate_session_id,
)

# Create a terminal output message
output = TerminalOutput(
    session_id=generate_session_id(),
    data=b"Hello World\n"
)

# Serialize to JSON
json_str = output.to_json()
# {"type": "terminal.output", "session_id": "...", "timestamp": 1733299200.123, "data": "SGVsbG8gV29ybGQK"}

# Deserialize from JSON (auto-detects message type)
msg = deserialize_message(json_str)
assert isinstance(msg, TerminalOutput)
```

## Running the Relay Service

```bash
# Start relay server (default: 0.0.0.0:8080)
.venv/bin/python -m agent_remote.services.relay.api.server

# Or with uvicorn directly
uvicorn agent_remote.services.relay.api.server:app --host 0.0.0.0 --port 8080

# Environment variables
export RELAY_HOST=0.0.0.0      # Host to bind (default: 0.0.0.0)
export RELAY_PORT=8080         # Port to listen (default: 8080)
export CLEANUP_INTERVAL=60     # Session cleanup interval (default: 60s)
export LOG_LEVEL=INFO          # Logging level (default: INFO)
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions` | Create session, get pairing code |
| GET | `/api/sessions/{id}` | Get session status |
| DELETE | `/api/sessions/{id}` | Close session |
| GET | `/health` | Health check |

### WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `/ws/desktop/{session_id}` | Desktop CLI connection |
| `/ws/client/{pairing_code}` | Web client pairing |

## Usage (CLI)

```bash
# Start relay server
agent-remote relay start

# Start remote terminal session (from MyAgents CLI)
myagents remote start
```

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Run test vectors only
pytest tests/shared/test_vectors.py -v

# Lint
uv run ruff check .

# Type check
uv run mypy src/
```

## Project Structure

```
src/agent_remote/
├── services/
│   ├── relay/                      # WebSocket relay server (DDD architecture)
│   │   ├── domains/                # Domain Layer (pure business logic)
│   │   │   └── session_manager/    # Session lifecycle management
│   │   │       ├── entities.py     # Session entity with state machine
│   │   │       ├── value_objects.py # SessionId, PairingCode, etc.
│   │   │       └── repository.py   # Repository Protocol (interface)
│   │   │
│   │   ├── workflows/              # Application Layer (orchestration)
│   │   │   └── relay_workflow.py   # Session creation, pairing, routing
│   │   │
│   │   ├── infrastructure/         # Infrastructure Layer (implementations)
│   │   │   ├── in_memory_repository.py  # Thread-safe dict storage
│   │   │   └── websocket_manager.py     # WebSocket lifecycle, keepalive
│   │   │
│   │   ├── api/                    # Interface Layer (FastAPI)
│   │   │   ├── api.py              # REST endpoints
│   │   │   ├── websockets.py       # WebSocket endpoints
│   │   │   └── server.py           # Main entrypoint with lifespan
│   │   │
│   │   └── workers/                # Background Tasks
│   │       └── cleanup_worker.py   # Session expiry cleanup
│   │
│   └── terminal/        # PTY wrapper for Claude Code
│       ├── domains/     # PTY management, crypto, I/O buffering
│       └── workflows/   # Terminal session orchestration
│
└── shared/              # Shared contracts (critical path!)
    ├── crypto/          # Crypto interface types (no implementation)
    │   └── types.py     # KeyPair, CryptoBox, CryptoProvider protocols
    │
    └── protocol/        # Protocol message definitions
        ├── base.py           # Base classes, utilities, type registry
        ├── terminal_messages.py  # TerminalOutput, TerminalInput, etc.
        ├── session_messages.py   # SessionCreate, SessionPaired, etc.
        └── relay_messages.py     # EncryptedBlob, Ping, Pong, Error

tests/shared/
├── test_vectors.py      # Pytest tests for protocol validation
├── fixtures/
│   ├── protocol_vectors.json  # Protocol message test vectors
│   └── crypto_vectors.json    # Crypto test vectors
└── README.md            # Test vector documentation

docs/
├── protocol.md          # Protocol specification (all 13 message types)
└── crypto.md            # Crypto specification (NaCl box)
```

## Protocol Messages

| Category | Messages |
|----------|----------|
| Session | `SessionCreate`, `SessionCreated`, `SessionPair`, `SessionPaired`, `SessionClose` |
| Terminal | `TerminalOutput`, `TerminalInput`, `TerminalResize`, `TerminalClose` |
| Relay | `EncryptedBlob`, `Ping`, `Pong`, `Error` |

See [docs/protocol.md](docs/protocol.md) for full specification.

## Crypto Interfaces

Defines Protocol classes for crypto operations (implementation-agnostic):
- `KeyPair` - X25519 public/private key pair
- `CryptoBox` - NaCl box encrypt/decrypt operations
- `CryptoProvider` - Factory for key generation

See [docs/crypto.md](docs/crypto.md) for full specification.

## Test Vectors

Cross-platform test vectors enable independent development:
- Python: `pytest tests/shared/test_vectors.py -v`
- Flutter: Load `tests/shared/fixtures/*.json` and validate

See [tests/shared/README.md](tests/shared/README.md) for usage.

## License

Apache-2.0
