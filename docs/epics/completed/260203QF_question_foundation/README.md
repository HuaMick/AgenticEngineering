# Question Foundation - Data Models and Queue Service

**Plan ID**: 260203QF
**Status**: Active
**Created**: 2026-02-03
**Worktree**: `/home/code/AgenticEngineering` (main branch)

## Objective

Implement the foundational data models and queue service for the Question/Answer workflow. This establishes the core infrastructure that enables both CLI-based and voice-based human-in-the-loop (HITL) interactions.

## Scope

This plan implements the **foundation layer** for the CLI-First HITL strategy:

1. **Data Models**: Question and Answer dataclasses with YAML serialization
2. **Queue Service**: Question queue management (create, read, list, answer)
3. **File System Contract**: YAML-based question/answer storage in plan-scoped folders

## Architecture Context

This plan is part of the **Text-Mode CLI-First strategy** where:
- CLI commands are the primary interface for question management
- Voice (PersonaPlex) is an optional consumer that reads from the same queue
- Questions are stored in plan-scoped folders: `docs/plans/live/{plan_id}/questions/`

```
┌─────────────────────────────────────────────────────────────┐
│  AgenticGuidance (Claude-powered agents)                     │
│  - Hits blockers / needs clarification                       │
│  - Generates questions -> questions/pending/*.yml            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  QuestionQueue Service (THIS PLAN)                           │
│  - Data models: Question, Answer                             │
│  - Queue operations: create, list, answer                    │
│  - File-based storage in plan-scoped folders                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓ (consumed by)
          ┌────────────────────────┐
          │  CLI (260203QC)         │ Text-mode interface
          └────────────────────────┘
          ┌────────────────────────┐
          │  PersonaPlex (260203VP) │ Voice interface (optional)
          └────────────────────────┘
```

## Key Design Decisions

1. **Plan-scoped storage**: Questions stored in `docs/plans/live/{plan_id}/questions/pending/` and `questions/answered/`
2. **YAML contract**: Simple, human-readable format for question/answer exchange
3. **No dependencies**: Foundation layer has no dependencies on CLI or voice modules
4. **Thread-safe**: Queue operations use file locks for atomic updates

## Dependencies

**Depends on**: None (foundation layer)

**Required by**:
- 260203QC (Question CLI) - Uses QuestionQueue for CLI operations
- 260203QG (Question Guidance) - Uses data models to generate questions
- 260203VP (Voice PersonaPlex) - Uses QuestionQueue to read/answer questions

## Implementation Phases

### Phase 1: Data Models (3 tasks)
- QF_001: Create Question dataclass with all fields and enums
- QF_002: Create Answer dataclass with all fields and enums
- QF_003: Implement YAML serialization helpers (to_yaml/from_yaml)

### Phase 2: Queue Service (5 tasks)
- QF_004: Create QuestionQueue service class with initialization
- QF_005: Implement create_question method
- QF_006: Implement list_pending_questions method
- QF_007: Implement get_question method
- QF_008: Implement answer_question method

### Phase 3: File System Layer (3 tasks)
- QF_009: Add atomic file write operation (temp file + rename)
- QF_010: Add file locking for concurrent access (FileLock integration)
- QF_011: Add error handling and logging throughout service

### Phase 4: Unit Tests (4 tasks)
- QF_012: Create data model tests (models/question.py)
- QF_013: Create queue service tests (services/question.py)
- QF_014: Create integration tests (complete workflow)
- QF_015: Run test suite and verify >90% coverage

**Total**: 15 tasks across 4 phases

## Success Criteria

- Question and Answer dataclasses defined with full type hints
- YAML serialization/deserialization working correctly
- QuestionQueue service can create, list, and answer questions
- File operations are atomic and thread-safe
- Unit tests achieve >90% coverage for models and services
- Integration tests verify complete question/answer workflow
- No dependencies on CLI or voice modules
- All tests pass in test suite
- Error handling is comprehensive with actionable messages
- Logging provides visibility into operations

## Related Files

- Plan: [plan_build.yml](plan_build.yml) - Detailed build plan with 15 tasks
- Orchestration: [orchestration_question_foundation.mmd](orchestration_question_foundation.mmd) - Visual execution flow
- Target Module: `modules/AgenticGuidance/src/agenticguidance/services/question.py`
- Target Models: `modules/AgenticGuidance/src/agenticguidance/models/question.py`

## Plan Status

**Planning**: Complete
**Implementation**: Ready to begin

## Next Steps

1. Spawn builder agent for Phase 1 (Data Models) - Tasks QF_001 through QF_003
2. After Phase 1 complete, spawn builder for Phase 2 (Queue Service) - Tasks QF_004 through QF_008
3. After Phase 2 complete, spawn builder for Phase 3 (File System) - Tasks QF_009 through QF_011
4. After Phase 3 complete, spawn test-builder for Phase 4 (Unit Tests) - Tasks QF_012 through QF_015
5. Hand off to 260203QC for CLI integration
