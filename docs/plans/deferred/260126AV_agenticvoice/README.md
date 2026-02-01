# AgenticVoice Module Plan

**Plan ID**: 260126AV
**Status**: Deferred
**Worktree**: `/home/code/AgenticEngineering-agenticvoice`
**Branch**: `agenticvoice`

## Objective

Create AgenticVoice module for voice-based planning and phone control.

## Dependency

**DEFERRED**: This plan is deferred because required AgenticGuidance services are not yet implemented:
- PlanService (plan.py has PlanMovementWorkflow only)
- ContextService (not implemented)
- TaskService (not implemented)
- ConfigService (partial - TieredConfigLoader only)
- StateService (partial - StateRegistry only)

The blocker plan 260123AE_agenticguidance completed on 2026-01-26, but the services it created are insufficient for AgenticVoice requirements.

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
- Define core Python interfaces (protocols) and types

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

## Acceptance Criteria

### Core Requirements
- [ ] WebSocket server accepts voice connections and streams audio
- [ ] STT converts speech to text with acceptable latency (<500ms)
- [ ] TTS generates natural-sounding voice output
- [ ] Voice commands successfully route to AgenticGuidance services
- [ ] Service responses are converted to spoken output

### Quality Requirements
- [ ] Module follows AgenticEngineering project structure
- [ ] pyproject.toml correctly declares agenticguidance dependency
- [ ] All public interfaces documented with docstrings
- [ ] Error handling provides user-friendly voice feedback

### Optional (Phase 4)
- [ ] PersonaPlex integration enables persona-aware responses
- [ ] Multiple voice personas configurable
- [ ] Conversation context maintained across interactions

## Status

- Created: 2026-01-26
- Reviewed: 2026-01-27 (deferral validated)
- Status: Deferred (awaiting AgenticGuidance service implementation)
