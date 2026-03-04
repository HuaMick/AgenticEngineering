# Migration Guide: 260203AV -> CLI-First Strategy

**Date**: 2026-02-03
**Status**: Architecture Change - Voice-First to CLI-First

## Summary

This plan (260203AV_agenticvoice_async) has been **superseded** by a new CLI-First strategy that reorganizes the human-in-the-loop (HITL) architecture:

- **Old Strategy**: Voice-first with PersonaPlex as core interface
- **New Strategy**: CLI-first with PersonaPlex as optional consumer

## New Plan Structure

The functionality from 260203AV has been decomposed into 5 new plans:

| Plan ID | Name | Priority | Replaces |
|---------|------|----------|----------|
| 260203QF | Question Foundation | High | Phase 1-2 (data models, queue) |
| 260203QC | Question CLI | High | PRIMARY INTERFACE (new) |
| 260203QG | Question Guidance | Medium | Agent integration (new) |
| 260203QT | Question Tmux | Medium | Remote session support (new) |
| 260203VP | Voice PersonaPlex | Low | Phase 3-7 (voice as OPTIONAL) |

## Dependency Chain

```
260203QF (Foundation)
    |
    +---> 260203QC (CLI - PRIMARY)
    |         |
    |         +---> 260203QG (Guidance)
    |         |         |
    |         |         +---> 260203QT (Tmux)
    |         |
    |         +---> 260203VP (Voice - OPTIONAL)
    +---> 260203VP (Voice - OPTIONAL)
```

## Content Migration

### KEEP and Migrate to 260203VP

From 260203AV, the following content should be migrated to 260203VP:

1. **PersonaPlex WebSocket Integration** (Phase 3):
   - WebSocket client patterns
   - TTS/STT API calls
   - Voice parameters and configuration

2. **Parakeet TDT Integration** (Phase 4):
   - Transcription pipeline
   - Confidence scoring
   - Quality validation

3. **Configuration System** (Phase 7):
   - YAML configuration patterns
   - Environment variable expansion
   - Validation logic

4. **Documentation Patterns**:
   - Architecture diagrams (adapt for CLI-first)
   - User documentation structure

### DISCARD (Replaced by New Plans)

The following content from 260203AV is replaced by new infrastructure:

1. **Question Queue Implementation** (Phase 2):
   - REPLACED BY: 260203QF (QuestionQueue service)
   - Old: Custom queue monitoring and file watcher
   - New: Shared QuestionQueue service used by CLI and voice

2. **Answer Writing Logic** (Phase 2):
   - REPLACED BY: 260203QC (CLI answer command)
   - Old: Direct file writing in voice module
   - New: Use QuestionQueue service (same as CLI)

3. **Daemon-First Architecture** (Phase 6):
   - REPLACED BY: 260203VP (voice as optional consumer)
   - Old: Daemon was core infrastructure
   - New: Daemon is optional, CLI is core

4. **CLI Integration as Secondary** (Phase 6):
   - REPLACED BY: 260203QC (CLI as primary)
   - Old: CLI was secondary to voice daemon
   - New: CLI is primary, voice is optional

## Architecture Comparison

### Old Architecture (260203AV)

```
AgenticGuidance
    |
    v
QuestionQueue (in AgenticVoice module)
    |
    v
PersonaPlex Daemon (CORE)
    |
    +---> Voice I/O (primary)
    +---> CLI (secondary)
```

### New Architecture (CLI-First)

```
AgenticGuidance
    |
    v
QuestionQueue Service (260203QF - shared)
    |
    +---> CLI Commands (260203QC - PRIMARY)
    |         |
    |         +---> Tmux Integration (260203QT - optional)
    |
    +---> PersonaPlex Daemon (260203VP - OPTIONAL)
```

## Implementation Status

| Plan | Status | Next Action |
|------|--------|-------------|
| 260203QF | Active | Expand plan_build.yml with detailed tasks |
| 260203QC | Active | Expand plan_build.yml with detailed tasks |
| 260203QG | Active | Expand plan_build.yml with detailed tasks |
| 260203QT | Active | Expand plan_build.yml with detailed tasks |
| 260203VP | Active | Migrate PersonaPlex patterns from 260203AV |
| 260203AV | Superseded | Archive after migration complete |

## Action Items

1. Review 260203AV content for PersonaPlex/Parakeet patterns
2. Migrate relevant patterns to 260203VP
3. Update 260203VP plan with migrated content
4. Archive 260203AV to docs/plans/deferred/ or docs/plans/completed/
5. Update references from 260203AV to new plan IDs

## Rationale for Change

The CLI-First strategy provides several advantages:

1. **Lower Barrier to Entry**: Text-mode CLI is easier to test and debug
2. **Optional Voice**: PersonaPlex becomes enhancement, not requirement
3. **Better Separation**: Foundation (queue) separate from interfaces (CLI, voice)
4. **Parallel Development**: CLI and voice can be developed independently
5. **Testability**: CLI easier to test than voice interactions
6. **Remote Workflows**: Tmux integration enables remote HITL sessions

## Questions

If you have questions about this migration, see:
- New plan README.md files in docs/plans/live/260203*
- Architecture comparison above
- Dependency chain diagram
