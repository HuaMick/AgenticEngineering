# Planning Loop CLI Command

**Plan ID**: 260208PL
**Status**: Active
**Created**: 2026-02-08

## Objective

Create a CLI command that automates the full planning loop: creating plan folders, spawning planner agents, generating orchestration, and optionally executing the plan.

## Proposed Command

```bash
# Full automation: create plan and spawn planner agent
agentic plan new "Add phone notifications feature" --execute

# Breakdown:
# 1. Creates plan folder with proper naming (YYMMDDXX_description)
# 2. Spawns planner agent session to populate plan files
# 3. (Optional) Generates orchestration MMD
# 4. (Optional) Spawns builder agents to execute tasks
```

## User Flow

```
User: agentic plan new "Add feature X" --execute
       ↓
CLI: Creates 260208XX_add_feature_x folder
       ↓
CLI: Spawns planner session with objective
       ↓
Planner: Writes README.md, plan_build.yml
       ↓
CLI: Generates orchestration_*.mmd
       ↓
CLI: Spawns builder sessions for each phase
       ↓
Builders: Execute tasks, update status
       ↓
CLI: Archives plan when complete
```

## Implementation Phases

| Phase | Description |
|-------|-------------|
| Phase 1 | `agentic plan new` command scaffold |
| Phase 2 | Planner agent prompt template |
| Phase 3 | Orchestration auto-generation |
| Phase 4 | Builder agent spawning (`--execute`) |
| Phase 5 | Progress monitoring and completion |

## Dependencies

- `agentic session spawn` - ✅ Exists
- `agentic plan init` - ⚠️ Needs fix (260208CF)
- `agentic plan orchestration generate` - ✅ Exists

## Success Criteria

- [ ] `agentic plan new "objective"` creates populated plan folder
- [ ] Planner agent writes proper plan files
- [ ] `--execute` flag spawns builder agents
- [ ] Progress visible via `agentic plan status`
- [ ] Auto-archives on completion
