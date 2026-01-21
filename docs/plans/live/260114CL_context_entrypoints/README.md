# Plan: 260114CL_context_entrypoints

## Status: ACTIVE (Ready for Implementation)

**Updated**: 2026-01-21
**Priority**: HIGH
**Estimated Effort**: 8-12 weeks

## Overview

Implements JIT (Just-In-Time) Pull-based context architecture for agents. Evolves from current "Push" model (pre-loading large static markdown files) to a "Pull" model where agents fetch exactly what they need via CLI.

## Key Deliverables

1. **CLI Context Commands**: `agentic context bootstrap|role|task|inputs`
2. **CLI Plan Tools**: `agentic plan task status|update|current`
3. **Main-First Plan Resolution**: Resolve plans from main worktree into feature worktree sessions
4. **Thin-Client Agent Migration**: All agents use minimal bootstrap instructions

## Plan Files

| File | Description | Status |
|------|-------------|--------|
| `plan.yml` | Master plan metadata | Active |
| `specification.md` | Technical specification | Reference |
| `live/plan_live_build.yml` | Build implementation plan (5 phases, 20+ tasks) | Active |
| `live/plan_live_test.yml` | Test validation plan (7 phases) | Active |

## Phases Summary

### Build Plan (plan_live_build.yml)

| Phase | Description | Tasks | Status |
|-------|-------------|-------|--------|
| Phase 1 | CLI Context Command Infrastructure | 6 tasks | Pending |
| Phase 2 | CLI Plan Status Tools | 3 tasks | Pending |
| Phase 3 | Thin-Client Agent Migration | 5 tasks | Pending |
| Phase 4 | Integration & Testing | 4 tasks | Pending |
| Phase 5 | Cleanup & Documentation | 3 tasks | Pending |

### Test Plan (plan_live_test.yml)

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1-7 | Environment setup through documentation validation | Pending |

## Next Session Entry Point

To continue implementation:

```bash
# Start with Phase 1, Task 01.1: Create cmd_context module and parser
# Target files:
# - modules/AgenticCLI/src/agenticcli/cli.py
# - modules/AgenticCLI/src/agenticcli/commands/context.py (new)
```

### Phase 1 Tasks (CLI Context Command Infrastructure)

| Task ID | Name | Description |
|---------|------|-------------|
| 01.1 | Create cmd_context module and parser | New command group with subcommands |
| 01.2 | Implement Main-First Plan Hunter | Find active plan in main worktree |
| 01.3 | Implement context bootstrap command | Primary Seed Context entrypoint |
| 01.4 | Implement context role command | Role-specific process/guidelines |
| 01.5 | Implement context task command | Active task from Main-First plan |
| 01.6 | Implement context inputs command | JIT manifest of relevant files |

## Dependencies

- None - this plan is foundational

## Success Criteria

- Agents can identify task objective via `agentic context bootstrap`
- CLI plan task commands are operational
- Agents can update task status without holding plan in context
- Main-First planning folders resolved in feature worktree sessions
- All agents migrated to Pull model

## Folder Structure

```
260114CL_context_entrypoints/
├── README.md           # This file
├── plan.yml            # Master plan metadata
├── specification.md    # Technical specification
├── analysis/           # Analysis documents
├── audit/              # Audit reports
├── completed/          # Completed plans
└── live/               # Active plans
    ├── plan_live_build.yml   # Build implementation
    └── plan_live_test.yml    # Test validation
```
