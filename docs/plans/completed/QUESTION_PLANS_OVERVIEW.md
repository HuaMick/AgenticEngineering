# Question/Answer HITL Plans Overview

**Strategy**: Text-Mode CLI-First
**Created**: 2026-02-03
**Status**: Active Planning

## Executive Summary

The Question/Answer human-in-the-loop (HITL) workflow has been reorganized into **5 focused plans** following a **CLI-First** strategy. This replaces the previous voice-first approach (260203AV) with a more flexible architecture where CLI is the primary interface and voice is an optional enhancement.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  AgenticGuidance (Claude-powered agents)                     │
│  - Hits blockers / needs clarification                       │
│  - Generates questions -> questions/pending/*.yml            │
│  - Uses guidance from 260203QG                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  QuestionQueue Service (260203QF - FOUNDATION)               │
│  - Data models: Question, Answer                             │
│  - Queue operations: create, list, answer                    │
│  - Plan-scoped storage: questions/pending/, answered/        │
└────────────┬────────────────────────────────────────────────┘
             │
             ├──────────────────┬─────────────────────────────┐
             ↓                  ↓                             ↓
  ┌──────────────────┐ ┌─────────────────┐ ┌────────────────────────┐
  │  CLI (260203QC)  │ │  Tmux (260203QT)│ │  PersonaPlex (260203VP)│
  │  PRIMARY         │ │  OPTIONAL       │ │  OPTIONAL              │
  │                  │ │                 │ │                        │
  │  Text-mode       │ │  Remote session │ │  Voice-mode            │
  │  interface       │ │  notifications  │ │  interface             │
  └──────────────────┘ └─────────────────┘ └────────────────────────┘
```

## Plan Breakdown

### 1. 260203QF - Question Foundation (HIGH PRIORITY)

**Objective**: Implement foundational data models and queue service

**Scope**:
- Question and Answer dataclasses with YAML serialization
- QuestionQueue service with CRUD operations
- Plan-scoped file storage with atomic operations
- No dependencies on CLI or voice (pure foundation)

**Location**: `/home/code/AgenticEngineering/docs/plans/live/260203QF_question_foundation/`

**Dependencies**: None (foundation layer)

**Status**: Ready for detailed planning

---

### 2. 260203QC - Question CLI (HIGH PRIORITY)

**Objective**: Implement CLI commands for question management (PRIMARY INTERFACE)

**Scope**:
- `agentic question list` - Show pending questions
- `agentic question show <id>` - Display question details
- `agentic question answer <id>` - Provide text answer
- `agentic question defer <id>` - Mark as deferred
- `agentic question history` - Show answered questions

**Location**: `/home/code/AgenticEngineering/docs/plans/live/260203QC_question_cli/`

**Dependencies**:
- Requires: 260203QF (QuestionQueue service)

**Status**: Ready for detailed planning (after 260203QF)

---

### 3. 260203QG - Question Guidance (MEDIUM PRIORITY)

**Objective**: Update agent guidance for question generation and handling

**Scope**:
- When to ask questions (blockers vs solvable issues)
- How to generate question YAML (severity, context, format)
- Where to write questions (plan-scoped folders)
- How to check for answers and resume work
- CLI references for human operators

**Location**: `/home/code/AgenticEngineering/docs/plans/live/260203QG_question_guidance/`

**Dependencies**:
- Requires: 260203QF (data model schema)
- Requires: 260203QC (CLI commands to reference)

**Status**: Ready for detailed planning (after 260203QC)

---

### 4. 260203QT - Question Tmux (MEDIUM PRIORITY)

**Objective**: Implement Tmux session support for remote HITL workflows

**Scope**:
- Tmux session detection
- Dedicated notification pane creation
- File watcher for question updates
- CLI command display in notification pane
- Agent integration for Tmux-aware workflows

**Location**: `/home/code/AgenticEngineering/docs/plans/live/260203QT_question_tmux/`

**Dependencies**:
- Requires: 260203QF (QuestionQueue service)
- Requires: 260203QC (CLI commands)
- Requires: 260203QG (Agent patterns)

**Status**: Ready for detailed planning (after 260203QG)

---

### 5. 260203VP - Voice PersonaPlex (LOW PRIORITY - OPTIONAL)

**Objective**: Implement PersonaPlex voice interface as optional HITL consumer

**Scope**:
- PersonaPlex WebSocket client (TTS/STT)
- Voice daemon monitoring questions/pending/
- Parakeet TDT for high-quality transcription
- Answer submission via QuestionQueue service
- CLI commands for daemon management (start/stop/status)

**Location**: `/home/code/AgenticEngineering/docs/plans/live/260203VP_voice_personaplex/`

**Dependencies**:
- Requires: 260203QF (QuestionQueue service)
- May use: 260203QC (CLI patterns)

**Migration**: Replaces 260203AV with new scope (voice as consumer, not core)

**Status**: Ready for detailed planning (can start after 260203QF, independent of CLI)

---

## Dependency Chain

### Sequential Dependencies

```
260203QF (Foundation)
    ↓
260203QC (CLI)
    ↓
260203QG (Guidance)
    ↓
260203QT (Tmux)
```

### Parallel Development (after 260203QF)

```
260203QF (Foundation)
    ├──→ 260203QC (CLI) → 260203QG → 260203QT
    └──→ 260203VP (Voice - independent track)
```

## Implementation Strategy

### Phase 1: Foundation (HIGH PRIORITY)
1. Start with **260203QF** (Question Foundation)
2. Implement data models and queue service
3. Achieve comprehensive test coverage
4. **Blocker for all other plans**

### Phase 2: Primary Interface (HIGH PRIORITY)
1. Start **260203QC** (Question CLI) after 260203QF completes
2. Implement core CLI commands (list, show, answer)
3. Validate with integration tests
4. **Enables human operators to use HITL workflow**

### Phase 3: Agent Integration (MEDIUM PRIORITY)
1. Start **260203QG** (Question Guidance) after 260203QC completes
2. Update agent guidance documents
3. Create examples and templates
4. **Enables agents to generate questions**

### Phase 4: Enhancements (MEDIUM/LOW PRIORITY)
1. **260203QT** (Tmux) - Optional, for remote workflows
2. **260203VP** (Voice) - Optional, for voice-based HITL

Can be developed in parallel or sequentially based on resource availability.

## Migration from 260203AV

The old **260203AV_agenticvoice_async** plan has been superseded by this new structure:

**What Changed**:
- Voice-first approach → CLI-first approach
- Monolithic voice module → Decomposed into 5 focused plans
- PersonaPlex as core → PersonaPlex as optional consumer

**What to Migrate**:
- PersonaPlex WebSocket patterns → 260203VP
- Parakeet TDT integration → 260203VP
- Configuration system → 260203VP

**What to Discard**:
- Custom question queue → Use 260203QF
- Custom answer writer → Use 260203QC
- Daemon-first architecture → Voice is now optional

**See**: `/home/code/AgenticEngineering/docs/plans/live/260203AV_agenticvoice_async/MIGRATION.md`

## Success Criteria (Overall)

### Foundation (260203QF)
- Question/Answer data models working with YAML
- QuestionQueue service operational
- Thread-safe file operations

### CLI (260203QC)
- All CLI commands functional and tested
- Rich formatting for readable output
- Auto-detection of plan context

### Guidance (260203QG)
- Agents can generate well-formed questions
- Resumption patterns documented
- Role-specific guidance complete

### Tmux (260203QT - Optional)
- Tmux sessions auto-create notification panes
- File watcher updates pane on changes
- Graceful fallback when not in Tmux

### Voice (260203VP - Optional)
- PersonaPlex TTS/STT working
- Parakeet transcription accurate
- Voice and CLI coexist without conflicts

## Next Steps

1. **Detailed Planning**:
   - Expand each plan_build.yml with task-level detail
   - Add file-level inputs for context routing
   - Create orchestration MMD files

2. **Implementation Order**:
   - Start 260203QF immediately (foundation)
   - Queue 260203QC for after QF completion
   - Queue 260203QG for after QC completion
   - Consider 260203QT and 260203VP as optional enhancements

3. **Archive Old Plan**:
   - After migrating content to 260203VP, archive 260203AV
   - Move to docs/plans/deferred/ or docs/plans/completed/

## Related Files

- Individual plan README.md files in each plan folder
- Individual plan_build.yml files (high-level objectives)
- MIGRATION.md in 260203AV folder

## Questions or Changes

If this structure needs adjustment, update this overview document and notify all stakeholders.
