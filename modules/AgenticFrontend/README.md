# AgenticFrontend

> **Note**: This project is in early development. The directory structure exists as scaffolding; implementation has not yet begun.

Frontend UI for the AgenticEngineering ecosystem, providing visual interfaces for interacting with Claude Code sessions and agent workflows.

## Vision

AgenticFrontend will serve as the user-facing layer of AgenticEngineering, enabling:

- **Remote terminal access** to Claude Code sessions
- **Workflow visualization** for planning and execution status
- **Session management** across distributed environments

The goal is a minimal, focused UI that complements Claude Code's capabilities without duplicating functionality that belongs in CLI tools or backend services.

## Current State

**Status**: Scaffolding only

The `modules/AgenticFrontend/` directory has been created as a placeholder within the AgenticEngineering project structure. No implementation exists yet.

```
AgenticFrontend/
└── README.md     # This file
```

## Aspirational Architecture

Based on patterns established in the legacy `MyAgentsFrontend` (Flutter), the planned architecture follows a clean separation of concerns:

```
AgenticFrontend
    │
    │ WSS (E2E encrypted)
    ▼
AgenticBackend (relay/orchestration)
    │
    │ WSS (E2E encrypted)
    ▼
Claude Code (terminal sessions)
```

### Planned Features

Drawing from legacy patterns that proved effective:

| Feature | Priority | Legacy Reference |
|---------|----------|-----------------|
| Remote terminal view | High | xterm integration in MyAgentsFrontend |
| E2E encrypted communication | High | NaCl/X25519 encryption layer |
| Session pairing | High | 6-character pairing codes |
| Connection state management | High | Auto-reconnect with exponential backoff |
| Voice-to-text input | Low | Deepgram integration (future) |

### Planned Structure

```
lib/
├── core/                    # Shared infrastructure
│   ├── config/              # Environment configuration
│   ├── crypto/              # E2E encryption (X25519-XSalsa20-Poly1305)
│   ├── networking/          # WebSocket client
│   └── theme/               # UI theming
│
├── features/
│   ├── remote_terminal/     # Terminal display + input
│   ├── pairing/             # Session pairing UI
│   └── workflow/            # Planning visualization (new)
│
└── routing/                 # Navigation
```

## Legacy Reference

The `modules/legacy/MyAgents/projects/MyAgentsFrontend/` directory contains the previous Flutter implementation, providing:

- **Proven patterns**: Pairing flow, WebSocket management, encryption layer
- **User stories**: Detailed acceptance criteria in `modules/AgenticGuidance/userstories/MyAgentsFrontend/`
- **Architecture decisions**: Clean state management (PairingState, PairingController, PairingScreen)
- **CI/CD pipeline**: Cloud Build configuration for testing and deployment

Key lessons from legacy:

1. **Separation of concerns**: State models, controllers, and UI components remain independent
2. **Connection reliability**: Auto-reconnect with exponential backoff (1s base, 60s max)
3. **Security first**: E2E encryption established before any terminal data flows
4. **Progressive implementation**: Core infrastructure (networking, crypto) before features

## Relationship to AgenticEngineering

AgenticFrontend is one of three planned project modules:

| Module | Purpose | Status |
|--------|---------|--------|
| **AgenticBackend** | Python services, relay server, orchestration | Scaffolding |
| **AgenticFrontend** | User interfaces, remote terminal, visualization | Scaffolding |
| **AgenticGuidance** | Definitions, guidelines, constraints | Scaffolding |

The frontend depends on:
- **AgenticBackend**: For relay server connectivity and session management
- **AgenticGuidance**: For consistent patterns and behavioral constraints

## Principles

Aligned with the AgenticEngineering core principles:

### Context Minimization
Keep UI focused. Show only what's needed for the current task. Dense dashboards create noise.

### Less is More
Build minimal viable features first. Resist adding visualization complexity that doesn't serve immediate needs.

### Progressive Automation
Start with manual workflows visualized in the UI. As patterns mature to CLI commands, the UI can delegate to them rather than reimplementing logic.

## Development

No development setup exists yet. When implementation begins:

```bash
# Planned (not yet available)
cd modules/AgenticFrontend
flutter pub get
flutter run -d chrome
```

## Next Steps

1. **Define scope**: Determine initial feature set (likely remote terminal + pairing)
2. **Technology choice**: Confirm Flutter Web or evaluate alternatives
3. **Backend dependency**: AgenticBackend relay server needed before meaningful frontend work
4. **Port core infrastructure**: Adapt crypto/networking from legacy as starting point

## License

Apache-2.0
