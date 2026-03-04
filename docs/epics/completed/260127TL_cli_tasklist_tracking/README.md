# 260127TL - CLI Tasklist Tracking for Agent Compliance

## Problem

Agents can claim tasks are completed without actually verifying or committing to completion. There's no enforcement mechanism that forces agents to explicitly acknowledge task completion via a tracked action.

## Solution

Add CLI commands that force agents to explicitly tick off tasks as completed by running CLI commands. This creates an auditable trail and enables the Ralph Loop to verify actual completion before respawning.

### Workflow

```
PLANNING PHASE
    │
    ▼
Planner creates orchestration.mmd with phases/tasks
    │
    ▼
REVIEW PHASE
    │
    ▼
Reviewer approves plan
    │
    ▼
Reviewer reads orchestration.mmd, extracts tasks
    │
    ▼
Reviewer runs: agentic tasklist init --tasks '<JSON>'  ◄── GATE
    │           (populates .tasklist/status.json)
    ▼
ORCHESTRATION PHASE
    │
    ▼
Agent runs: agentic tasklist update <id> in-progress  ◄── START TASK
    │
    ▼
Agent works on task
    │
    ▼
Agent runs: agentic tasklist update <id> completed  ◄── ENFORCEMENT
    │
    ▼
RALPH LOOP checks: agentic tasklist show --status pending
    │
    ├── Has results → Respawn agent with pending task list
    │
    └── Empty       → Plan complete, archive
```

### Key Principles

1. **Agent Does Parsing** - Agent reads MMD, extracts tasks, passes to CLI
2. **CLI Just Stores Data** - CLI doesn't know about MMD format, just stores/queries tasks
3. **Explicit Status Updates** - Agents must run `update <id> <status>` to change state
4. **Compliance or Lie** - If agent claims completion without update, it's detectable deception
5. **Ralph Loop Integration** - Loop checks `show --status pending`, respawns until empty

## Scope

- Module: `modules/AgenticGuidance` (new service)
- CLI: `modules/AgenticCLI` (new orchestrate command group)
- First target: orchestration.mmd files (expand to other agents later)

## Deliverables

1. `OrchestrationTasklistService` in AgenticGuidance
   - Parse orchestration.mmd for tasks/phases
   - Track tick status in `.tasklist/status.json`
   - Validate completion state

2. CLI Commands (`agentic tasklist`)
   - `init --tasks JSON` - **REVIEWER GATE** - Initialize tasklist from agent-provided data
   - `show [--status S] [--limit N]` - Show/filter tasks
   - `update <id> <status>` - **ENFORCEMENT** - Update task status

   Status values: `pending`, `in-progress`, `completed`, `blocked`, `deferred`

3. Ralph Loop Integration
   - Completion detection: all tasks must be ticked
   - Fresh context per iteration with tasklist state from files

## Related Plans

- `260127AG_ralph_loop_compliance` - Ralph Loop investigation (parallel work)

## Files

- `live/plan_live_build.yml` - Implementation plan
- `live/orchestration_tasklist_tracking.mmd` - Execution flowchart
