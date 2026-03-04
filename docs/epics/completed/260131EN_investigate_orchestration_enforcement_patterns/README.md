# Plan: Investigate Orchestration Enforcement Patterns

**Plan ID:** 260131EN
**Status:** Planning (Investigation)
**Type:** Investigation / Research
**Branch:** `orchestration-enforcement`
**Worktree:** `/home/code/AgenticEngineering-orchestration-enforcement`
**Created:** 2026-01-31

## Problem Statement

Agents frequently fail to follow orchestration patterns consistently during sessions. This manifests as:

1. **Orchestration agents executing tasks directly** instead of spawning appropriate subagents
2. **Skipping mandatory validation steps** (e.g., MMD presence, reviewer approval)
3. **Not maintaining orchestration state** across the session lifecycle
4. **Confusion about role boundaries** between orchestrator and subagent responsibilities
5. **Loss of context** about which phase/task is current when sessions are long-running

## Context

This is a recurring issue that has surfaced in multiple plans:
- 260127AG: Ralph Loop Compliance - orchestrator executed tasks directly
- 260131GA: Test Planning Gap - identified gaps in teacher agent test triggering
- Multiple instances of plans being archived without proper MMD validation
- Subagents occasionally attempting orchestration decisions

## Investigation Scope

This plan investigates **six potential approaches** to enforce orchestration patterns more reliably:

| Proposal | Description | Enforcement Type | Primary Codebase |
|----------|-------------|------------------|------------------|
| P1 | CLI Tasklist Orchestration Tracking | State-based | AgenticGuidance |
| P2 | Preloaded Tasklists at Plan Start | Initialization | AgenticGuidance |
| P3 | Session Spawn Context Injection | Spawn-time | AgenticGuidance |
| P4 | Main Session Detection/Identification | Role identification | AgenticGuidance |
| P5 | Tmux Session Management Patterns | Environment-based | AgenticGuidance |
| P6 | Bootstrap-time Plan Auto-generation | Process-based | AgenticGuidance |

## Plan Structure

```
260131EN_investigate_orchestration_enforcement_patterns/
├── README.md                                    # This file
├── orchestration_orchestration_enforcement.mmd  # Orchestration flowchart
├── friction_analysis.yml                        # Problem documentation
├── plan_teach.yml                               # Investigation tasks with OPEN QUESTIONS
├── plan_test.yml                                # Validation criteria (deferred)
├── plan_audit_clean.yml                         # Cleanup tasks
└── plan_completed.yml                           # Completion tracking
```

## Deliverables

This is an **investigation plan**, not an implementation plan. Expected outputs:

1. **Friction Analysis** - Detailed documentation of the orchestration compliance problem
2. **Proposal Evaluations** - For each of the 6 approaches:
   - Open questions answered
   - Trade-offs documented
   - Implementation complexity assessed (L/M/H)
   - Validation criteria defined
3. **Recommendation Report** - Which approach(es) to pursue, and in what order
4. **Implementation Strategy** - Which codebase(s) require changes:
   - AgenticGuidance (primary - has own CLI backend)
   - AgenticCLI (if needed for CLI command changes)

## Success Criteria

- [ ] All 6 proposals investigated with open questions answered
- [ ] Trade-offs documented for each approach with concrete evidence
- [ ] Clear recommendation on which approach(es) to implement
- [ ] Quick wins identified that could be implemented immediately
- [ ] Dependencies between approaches identified
- [ ] Implementation worktree strategy defined (AgenticGuidance, AgenticCLI, or both)

## Related Plans

| Plan ID | Name | Relevance |
|---------|------|-----------|
| 260127AG | Ralph Loop Compliance | Root cause context |
| 260127TL | CLI Tasklist Tracking | Existing tasklist infrastructure |
| 260130TE | Tmux Remote Terminal | Tmux infrastructure context |
| 260130MA | Multi-Agent Tmux Coordination | Deferred, may inform P5 |
| 260131GA | Test Planning Gap | Consolidated into P6 investigation |

## Investigation Notes

### Current Infrastructure

The CLI already has tasklist functionality:
- `agentic plan task list` - List tasks in a plan
- `agentic plan task current` - Get current task
- `agentic plan task update` - Update task status
- Task tracking files in plan folders

Session management exists:
- `SessionService` in AgenticGuidance
- `agentic session spawn` for starting new sessions
- Session roles (supervisor/worker/observer) partially implemented

### Known Constraints

1. Claude Code sessions have limited state persistence mechanisms
2. Context injection happens at session start, not mid-session
3. Tmux is available but not always the primary interface
4. Plan YAML files are the primary source of truth for task state

## Implementation Worktree Strategy

When investigation completes and proposals are selected for implementation:

| Codebase | Likely Scope | When Needed |
|----------|--------------|-------------|
| **AgenticGuidance** | Process definitions, agent guidance, session management, CLI backend | Primary - most changes expected here |
| **AgenticCLI** | CLI command enhancements (task, session, plan commands) | Only if CLI commands need updating |

**Note:** AgenticGuidance has its own CLI backend (`modules/AgenticGuidance/src/`), so most CLI-related orchestration work can be done there without touching AgenticCLI.

## Next Steps

1. Read `friction_analysis.yml` for detailed problem documentation
2. Review `plan_teach.yml` for investigation tasks and open questions
3. Execute investigation tasks in order of priority (see `orchestration_orchestration_enforcement.mmd`)
4. Document findings in proposal-specific sections
