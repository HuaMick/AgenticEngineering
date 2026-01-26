# AgenticVoice Module Plan

## Objective

Create AgenticVoice module for voice-based planning and phone control.

## Dependency

**BLOCKED**: This plan is blocked until AgenticGuidance services refactor is complete (260123AE_agenticguidance).

## Architecture

AgenticVoice is a thin presentation layer that routes voice commands to AgenticGuidance services:

```
┌─────────────────────────────────────────────────────────────┐
│  AgenticVoice (Presentation Layer)                          │
│  - WebSocket server for real-time voice communication       │
│  - STT/TTS integration                                      │
│  - Voice command parsing                                    │
└─────────────────────┬───────────────────────────────────────┘
                      │ imports from agenticguidance.services
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  AgenticGuidance/services/ (Business Logic Layer)           │
│  - PlanService        (plan management)                     │
│  - ContextService     (context resolution)                  │
│  - TaskService        (task operations)                     │
│  - ConfigService      (configuration)                       │
│  - StateService       (state management)                    │
└─────────────────────────────────────────────────────────────┘
```

## Import Pattern

```python
from agenticguidance.services.plan import PlanService
from agenticguidance.services.context import ContextService
from agenticguidance.services.task import TaskService
```

## Phases

### Phase 1: Module Structure and WebSocket Server
- Set up AgenticVoice module directory structure
- Implement WebSocket server for real-time voice communication
- Define core interfaces and types

### Phase 2: Speech-to-Text and Text-to-Speech Integration
- Integrate speech-to-text (STT) service
- Integrate text-to-speech (TTS) service
- Handle audio streaming and buffering

### Phase 3: Voice Command Routing to AgenticGuidance Services
- Parse voice commands into structured intents
- Route commands to AgenticGuidance/services/*
- Handle responses and convert to voice output

### Phase 4: PersonaPlex Integration (Optional)
- Connect to PersonaPlex for persona-aware voice interactions
- Support multiple voice personas
- Context-aware voice responses

## Status

- Created: 2026-01-26
- Status: Pending (blocked on 260123AE_agenticguidance)
