# AgenticVoice Async Implementation Plan

**Plan ID**: 260203AV
**Status**: Active
**Created**: 2026-02-03
**Worktree**: `/home/code/AgenticEngineering` (main branch)

## Objective

Implement AgenticVoice module as an async voice interface for the agentic planning system.

## Architecture (User-Approved)

```
┌─────────────────────────────────────────────────────────────┐
│  AgenticGuidance (Claude-powered)                            │
│  - Runs autonomously on tasks                                │
│  - Hits blockers / needs clarification                       │
│  - Generates open questions -> questions/pending/*.yml       │
└──────────────────────┬──────────────────────────────────────┘
                       │ questions queue
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  AgenticVoice (PersonaPlex + Parakeet)                       │
│  - Monitors question queue                                   │
│  - Pings user: "Hey, I have a question about X"              │
│  - Conducts voice Q&A to gather answers                      │
│  - Transcribes answers (Parakeet for transcription)          │
└──────────────────────┬──────────────────────────────────────┘
                       │ answers -> questions/answered/*.yml
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  AgenticGuidance (continues)                                 │
│  - Receives structured answers                               │
│  - Resumes work with Claude intelligence                     │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

1. **PersonaPlex for voice interaction**: Full-duplex, natural conversation via **WebSocket** (using Python SDK).
2. **Parakeet TDT for transcription**: Runs in parallel for answer capture.
3. **Async workflow**: Agent works, generates questions, voice module pings user.
4. **Question/Answer contract**: YAML files in **plan-scoped** `questions/` folder (e.g., `docs/plans/live/{plan}/questions/`).
5. **Daemon with CLI control**: Service runs as a background daemon for continuous monitoring.
6. **NO real-time Claude intelligence in voice loop**: Claude called by agentic system.

## This Plan REPLACES

This plan **replaces** the deferred 260126AV plan (docs/plans/deferred/260126AV_agenticvoice/).

**Why the old plan was deferred**:
- Required non-existent AgenticGuidance services (PlanService, ContextService, TaskService)
- Was architected as a thin presentation layer over services that didn't exist
- Blocked on service implementation

**Why this new plan works**:
- Standalone module, no dependencies on non-existent services
- Async architecture decouples voice interaction from agent execution
- Simple YAML file contract for question-answer workflow
- Leverages PersonaPlex + Parakeet (user-approved technology stack)

## Session History

### Session 1: 2026-02-03
- Initial planning completed.
- Created plan_build.yml with 7 phases, 18 tasks.
- Created orchestration_agenticvoice_async.mmd.
- **Answered 3 open questions**: WebSocket for PersonaPlex, Plan-scoped questions folder, and Daemon deployment mode.

## Status

### Overall
- **Status**: Active (planning complete, ready for implementation)
- **Blocker**: None (all open questions answered)

### Open Questions (Answered)
1. **QUESTION-001** (high): Which PersonaPlex API should we use?
   - **Answer**: WebSocket connection (via Python SDK if available).
   - Impact: Low latency and full-duplex communication.

2. **QUESTION-002** (medium): Where should the questions/ folder be located?
   - **Answer**: Plan-scoped (e.g., `docs/plans/live/260203AV_agenticvoice_async/questions/`).
   - Impact: Ensures questions are tied directly to the relevant build plan.

3. **QUESTION-003** (medium): Should AgenticVoice run as daemon or on-demand?
   - **Answer**: Daemon with CLI control.
   - Impact: Allows background monitoring with CLI for lifecycle management.

### Phases

| Phase | Status | Tasks | Description |
|-------|--------|-------|-------------|
| Phase 1: Module Structure Setup | Pending | 2/2 | Create module structure and data models |
| Phase 2: Question Queue Monitor | Pending | 2/2 | Implement queue monitoring and file watcher |
| Phase 3: PersonaPlex Integration | Pending | 3/3 | Voice I/O via PersonaPlex |
| Phase 4: Parakeet Integration | Pending | 2/2 | High-quality transcription pipeline |
| Phase 5: Answer Synthesis | Pending | 2/2 | Synthesize answers and notify system |
| Phase 6: CLI Integration | Pending | 2/2 | CLI commands and daemon management |
| Phase 7: Config & Documentation | Pending | 2/2 | Configuration and user docs |

## Next Steps

1. **User**: Answer open questions (QUESTION-001, QUESTION-002, QUESTION-003)
2. **Orchestrator**: Update plan with answers
3. **Orchestrator**: Spawn build-python agents for Phase 1
4. **Builder**: Implement tasks sequentially through phases
5. **Tester**: Integration testing (Phase 8)
6. **Auditor**: Final audit (Phase 9)

## Implementation Notes

### Technology Stack
- **Python**: >=3.11
- **Voice I/O**: PersonaPlex (API TBD in QUESTION-001)
- **Transcription**: Parakeet TDT
- **File Format**: YAML for questions/answers
- **CLI Framework**: Typer (following AgenticCLI patterns)
- **Daemon**: python-daemon or custom implementation

### Folder Structure
```
modules/AgenticVoice/
├── pyproject.toml
├── README.md
├── config.example.yml
├── docs/
│   ├── QUICKSTART.md
│   └── ARCHITECTURE.md
├── src/agenticvoice/
│   ├── __init__.py
│   ├── models.py          # Question/Answer dataclasses
│   ├── queue.py           # Queue monitor and answer writer
│   ├── personaplex.py     # PersonaPlex client (TTS/STT)
│   ├── parakeet.py        # Parakeet transcription
│   ├── workflow.py        # Answer synthesis workflow
│   ├── daemon.py          # Daemon lifecycle management
│   └── config.py          # Configuration loader
└── tests/
    ├── test_models.py
    ├── test_queue.py
    ├── test_personaplex.py
    ├── test_parakeet.py
    ├── test_workflow.py
    └── integration/
        └── test_e2e_voice_loop.py
```

### Question/Answer File Format

**Question File** (questions/pending/{timestamp}_{question_id}.yml):
```yaml
id: "q_001"
question_text: "Should we use REST or WebSocket for the API?"
context:
  module: "agenticvoice"
  task: "persona_001"
severity: "high"
asked_by: "planner-build"
created_at: "2026-02-03T12:00:00Z"
status: "pending"
```

**Answer File** (questions/answered/{question_id}_answer.yml):
```yaml
question_id: "q_001"
answer_text: "Use the REST API for simplicity"
answered_by: "HUMAN"
answered_at: "2026-02-03T12:05:00Z"
confidence: 0.95
```

## Success Criteria

- AgenticVoice module installable and functional
- Question queue monitoring works reliably
- PersonaPlex integration speaks questions and captures answers
- Parakeet provides high-quality transcription
- Answers written to questions/answered/ atomically
- CLI commands (start/stop/status/logs) work correctly
- Daemon runs reliably in background
- Configuration loaded from YAML with validation
- Documentation enables first-time users to set up
- User can ask questions via AgenticGuidance, receive answers via voice

## Related Files

- Plan: [plan_build.yml](live/plan_build.yml)
- Orchestration: [orchestration_agenticvoice_async.mmd](live/orchestration_agenticvoice_async.mmd)
- Old Plan (deferred): [../../../deferred/260126AV_agenticvoice/](../../../deferred/260126AV_agenticvoice/)
