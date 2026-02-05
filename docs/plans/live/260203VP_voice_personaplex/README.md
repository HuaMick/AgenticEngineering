# Voice PersonaPlex - Optional Voice Interface for HITL

**Plan ID**: 260203VP
**Status**: Active
**Created**: 2026-02-03
**Worktree**: `/home/code/AgenticEngineering` (main branch)

## Objective

Implement PersonaPlex integration as an **optional voice interface** for the human-in-the-loop (HITL) workflow. This provides an alternative to the CLI for answering agent questions.

## Scope

This plan implements **voice-based HITL** as a consumer of the CLI-First infrastructure:

1. **PersonaPlex Client**: WebSocket connection for TTS/STT
2. **Question Monitoring**: Daemon watches questions/pending/ folder
3. **Voice Q&A**: Speak questions via TTS, capture answers via STT
4. **Answer Writing**: Write answers using the same QuestionQueue service
5. **CLI Integration**: Use CLI commands internally for answer submission

## Architecture Context

PersonaPlex is now a **consumer** of the CLI-First infrastructure, not the core:
- Voice daemon reads from questions/pending/ (same as CLI)
- Voice daemon writes via QuestionQueue service (same as CLI)
- CLI remains the primary interface; voice is an optional alternative
- Both interfaces coexist without conflict

```
┌─────────────────────────────────────────────────────────────┐
│  AgenticGuidance                                             │
│  - Generates questions -> questions/pending/*.yml            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  QuestionQueue Service (260203QF)                            │
└────────────┬────────────────────────────────────────────────┘
             │
             ├──────────────────┬─────────────────────────────┐
             ↓                  ↓                             ↓
  ┌──────────────────┐ ┌─────────────────┐ ┌────────────────────────┐
  │  CLI (PRIMARY)   │ │  Tmux (OPTIONAL)│ │  PersonaPlex (OPTIONAL)│
  │  (260203QC)      │ │  (260203QT)     │ │  (THIS PLAN)           │
  │                  │ │                 │ │                        │
  │  Text-mode       │ │  Remote session │ │  Voice-mode            │
  │  interface       │ │  notifications  │ │  interface             │
  └──────────────────┘ └─────────────────┘ └────────────────────────┘
```

## Key Design Decisions

1. **CLI-First**: Voice is a consumer, not the core infrastructure
2. **Daemon mode**: Background service monitors question queue
3. **WebSocket API**: PersonaPlex connection for low latency
4. **Parakeet TDT**: High-quality transcription for final answers
5. **CLI invocation**: Internally uses `agentic question answer` for consistency

## Dependencies

**Depends on**:
- 260203QF (Question Foundation) - QuestionQueue service and data models
- 260203QC (Question CLI) - May invoke CLI commands internally for answer submission
- 260203QG (Question Guidance) - Agents generate questions using updated patterns

**Required by**:
- None (optional enhancement for voice-based workflows)

**Related to**:
- 260203QT (Question Tmux) - Alternative HITL interface (Tmux instead of voice)

## Implementation Phases

1. **Phase 1: PersonaPlex Client** - WebSocket connection and TTS/STT
2. **Phase 2: Question Monitoring** - Daemon watches questions/pending/ folder
3. **Phase 3: Voice Workflow** - Speak questions, capture answers
4. **Phase 4: Parakeet Integration** - High-quality transcription pipeline
5. **Phase 5: Answer Submission** - Write answers via QuestionQueue
6. **Phase 6: Daemon Management** - CLI commands for start/stop/status

## Success Criteria

- PersonaPlex client connects via WebSocket
- Voice daemon monitors questions/pending/ folder
- Questions spoken via PersonaPlex TTS with context
- User answers captured via PersonaPlex STT
- Parakeet TDT provides high-quality transcription
- Answers written via QuestionQueue service (same as CLI)
- `agentic voice start` / `stop` / `status` commands work
- Voice and CLI can coexist without conflicts
- Voice interface is truly optional (system works without it)
- Integration tests validate voice workflow end-to-end

## Migration from 260203AV

This plan **replaces** the voice-first approach in 260203AV_agenticvoice_async:
- Old approach: Voice was the core interface
- New approach: CLI is core, voice is optional consumer
- Reuse: PersonaPlex + Parakeet integration patterns
- Discard: Daemon-first architecture, custom notification mechanisms

Content to migrate from 260203AV:
- PersonaPlex WebSocket patterns (Phase 3 of old plan)
- Parakeet TDT integration (Phase 4 of old plan)
- Configuration system (Phase 7 of old plan)

Content to discard:
- Question queue monitoring (now uses 260203QF)
- Answer writing logic (now uses 260203QC patterns)
- Custom daemon management (now follows CLI patterns)

## Related Files

- Plan: [plan_build.yml](live/plan_build.yml) (to be created)
- Old Plan (to be archived): `/home/code/AgenticEngineering/docs/plans/live/260203AV_agenticvoice_async/`
- Module: `modules/AgenticVoice/` (to be created with new scope)

## Next Steps

1. Review and archive 260203AV_agenticvoice_async plan
2. Create `plan_build.yml` with implementation tasks focused on voice as consumer
3. Migrate PersonaPlex and Parakeet integration patterns
4. Implement voice daemon as optional service
5. Create integration tests with CLI and QuestionQueue
6. Document voice workflow as optional feature
