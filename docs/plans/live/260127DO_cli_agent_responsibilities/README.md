# 260127DO - CLI vs Agent Responsibilities Documentation

## Objective

Document the architectural distinction between CLI (deterministic executor) and Agent (thinking/decision maker) responsibilities across README files and planner guidance.

## Key Concepts

This plan documents three core architectural learnings:

| Component | Responsibility | Decision Making |
|-----------|---------------|-----------------|
| **CLI** | Programmable, deterministic tool | None - executes established patterns |
| **Agent** | Tactical decision making | Handles ambiguity and novel situations |
| **Pattern** | Established process | When something becomes established, offload deterministic parts to CLI |

## Phases

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Update Module README Files | pending |
| Phase 2 | Create Architecture Definition | pending |
| Phase 3 | Update Planner Guidance | pending |
| Phase 4 | Self-Review Validation | pending |

## Files to Update

### Module READMEs
- `modules/AgenticCLI/README.md` - Add CLI vs Agent Architecture section
- `modules/AgenticGuidance/README.md` - Add Agent Responsibilities section

### New Definitions
- `modules/AgenticGuidance/assets/definitions/cli-agent-architecture.yml` - Formal architecture definition

### Planner Guidance
- `modules/AgenticGuidance/assets/inputs/planner-shared.yml` - README discovery guidance
- `modules/AgenticGuidance/agents/planner/planner-build/process.yml` - CLI vs Agent decision criteria

## The Handoff Pattern

```
Novel Situation          Established Pattern
     |                         |
     v                         v
[Agent Handles]  ---->  [Offload to CLI]
 (thinking)              (deterministic)

Example:
1. Agent manually creates plan folders (requires judgment)
2. Pattern becomes established (naming convention, structure)
3. CLI command created: `agentic plan init`
4. Agent now calls CLI (no thinking needed for folder creation)
```

## Success Criteria

- [ ] AgenticCLI README documents CLI as deterministic executor
- [ ] AgenticGuidance README documents Agent responsibility boundary
- [ ] New cli-agent-architecture.yml definition exists
- [ ] Planner guidance includes README discovery pattern
- [ ] Self-review validates documentation clarity

## Plan Files

- `plan_teach.yml` - Main implementation plan (7 tasks across 4 phases)
- `plan_test.yml` - Test plan (template)
- `plan_audit_clean.yml` - Audit and cleanup plan (template)

---

Created: 2026-01-27
Branch: cli-agent-docs
Worktree: /home/code/AgenticEngineering-cli-agent-docs
