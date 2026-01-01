# AgenticBackend

> **Note**: This project is in early development. This document describes the purpose, direction, and aspirations for AgenticBackend within the AgenticEngineering ecosystem.

Backend services for the AgenticEngineering platform. Provides API endpoints, WebSocket communication, and service infrastructure to support Claude Code session orchestration and tooling.

## Purpose

AgenticBackend serves as the server-side infrastructure layer for the AgenticEngineering ecosystem:

- **API Services**: REST endpoints for session management, planning folder operations, and CLI command execution
- **WebSocket Communication**: Real-time communication between clients and Claude Code sessions
- **Workflow Orchestration**: Backend logic for coordinating multi-step operations
- **State Management**: Persistent storage and retrieval of planning folder state

This module works alongside:
- **AgenticFrontend**: Web UI for interacting with Claude Code sessions
- **AgenticGuidance**: Guidance system definitions and constraints

## Current State

**Status**: Empty scaffold awaiting implementation.

The `/home/code/AgenticEngineering/modules/AgenticBackend/` directory currently contains only this README. No services, APIs, or infrastructure have been implemented yet.

## Architectural Direction

Based on patterns established in the legacy `RemoteAgents` project, AgenticBackend will follow Domain-Driven Design (DDD) principles:

```
AgenticBackend/
├── src/
│   ├── services/
│   │   └── {service_name}/
│   │       ├── domains/           # Domain Layer (pure business logic)
│   │       │   └── {domain}/
│   │       │       ├── entities.py
│   │       │       ├── value_objects.py
│   │       │       └── repository.py
│   │       │
│   │       ├── workflows/         # Application Layer (orchestration)
│   │       │   └── {workflow}.py
│   │       │
│   │       ├── infrastructure/    # Infrastructure Layer (implementations)
│   │       │   ├── repository_impl.py
│   │       │   └── external_clients.py
│   │       │
│   │       └── api/               # Interface Layer (FastAPI)
│   │           ├── server.py
│   │           ├── api.py
│   │           └── websockets.py
│   │
│   └── shared/                    # Shared contracts and utilities
│       ├── protocol/              # Message type definitions
│       └── crypto/                # Crypto interfaces (if needed)
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── README.md
```

### Key Patterns from Legacy

The `RemoteAgents` project in the legacy codebase demonstrates several patterns that inform AgenticBackend's direction:

| Pattern | Description | Reference |
|---------|-------------|-----------|
| **DDD Layer Separation** | Domains contain pure business logic; workflows orchestrate domains; infrastructure implements interfaces | `RemoteAgents/src/agent_remote/services/relay/` |
| **Workflow Orchestration** | Single entrypoints with parameters supporting multiple use cases | `legacy/MyAgentsGuidance/assets/definitions/workflows.yml` |
| **Separation of Concerns** | Independent validation from implementation; no conflicting incentives | `legacy/MyAgentsGuidance/assets/definitions/separation-of-concerns.yml` |
| **FastAPI + WebSocket** | REST for management, WebSocket for real-time communication | `RemoteAgents/src/agent_remote/services/relay/api/` |
| **Lifespan Management** | Proper startup/shutdown with background workers | `RemoteAgents/src/agent_remote/services/relay/api/server.py` |

### Aspirational Capabilities

These capabilities are planned but not yet implemented:

| Capability | Purpose | Maturity Target |
|------------|---------|-----------------|
| **Plan State API** | CRUD operations for planning folders | High |
| **CLI Proxy** | Execute CLI commands via API | High |
| **Session Management** | Track Claude Code session state | Medium |
| **Trace Collection** | LangSmith integration for pattern analysis | Medium |
| **Guidance API** | Serve guidance files to agents | High |

## Integration with AgenticEngineering

AgenticBackend fits into the broader ecosystem as described in `/home/code/AgenticEngineering/docs/README.md`:

```
┌─────────────────────────────────────────────────────────┐
│                     Claude Code                          │
│              (reasoning, tool use, code)                 │
└─────────────────────────┬───────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    ┌─────────┐    ┌───────────┐    ┌───────────┐
    │   CLI   │    │  Planning │    │  Guidance │
    │ Commands│    │  Folders  │    │   Files   │
    └────┬────┘    └─────┬─────┘    └─────┬─────┘
         │               │                │
         └───────────────┼────────────────┘
                         ▼
                 ┌───────────────┐
                 │AgenticBackend │  <-- API layer for state & tooling
                 └───────────────┘
```

AgenticBackend provides the API layer that exposes planning folder state, CLI command execution, and guidance files to external clients (including AgenticFrontend).

## Technology Stack (Planned)

Based on legacy patterns and ecosystem requirements:

- **Python 3.11+**: Runtime environment
- **FastAPI**: REST API framework
- **WebSockets**: Real-time communication (via Starlette)
- **uv**: Package management
- **pytest**: Testing framework
- **Docker**: Containerization

## Development

### Prerequisites

```bash
# Python 3.11+ required
python --version

# uv for package management
pip install uv
```

### Setup (Future)

```bash
cd /home/code/AgenticEngineering/modules/AgenticBackend

# Create virtual environment and install dependencies
uv sync

# Run tests
uv run pytest

# Start development server
uv run python -m src.services.{service}.api.server
```

## Principles

AgenticBackend follows the core principles from the AgenticEngineering project:

### Context Minimization
API responses provide only what's needed. Large payloads don't mean include everything.

### Less is More
Minimal sufficient endpoints. Don't add APIs for hypothetical use cases.

### Fix the Source
If an API pattern causes friction, fix the pattern rather than adding workarounds.

### Progressive Automation
Start with simple implementations. Graduate to optimized versions as patterns stabilize.

### Evidence-Based
Use LangSmith traces (when available) to identify actual API friction points.

## Legacy Reference

The `modules/legacy/MyAgents/projects/RemoteAgents/` directory contains a complete implementation of backend services that inform this project's direction:

- **Relay Service**: WebSocket relay for encrypted communication
- **Terminal Service**: PTY wrapper for remote Claude Code control
- **Shared Contracts**: Protocol messages and crypto interfaces

Key documentation:
- `RemoteAgents/docs/api.md` - REST API patterns
- `RemoteAgents/docs/protocol.md` - WebSocket message protocols
- `RemoteAgents/docs/crypto.md` - Encryption specifications

## Contributing

This module is built by Claude Code, for Claude Code. The workflow:

1. Identify a capability needed by the AgenticEngineering ecosystem
2. Check legacy patterns for relevant implementations
3. Implement following DDD structure and established patterns
4. Validate with tests
5. Document API endpoints as they stabilize

## License

See repository root for license information.
