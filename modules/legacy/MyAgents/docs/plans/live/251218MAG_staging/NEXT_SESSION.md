# Next Session: P1 Reference Layer Rollout

## Context (Quick Read)

**What we did**: Eliminated duplication in agent guidance system using teacher agents
- Phase 1 ✅: Fixed exact duplications (278 lines), deleted unused files (4), created boundary docs (2)
- Phase 2 ✅: Split mega-files into atomic files (14 files), created reference layers (7 layers)
- P1 Pilot ✅: Validated reference layers with 2 agents (test-builder, build-python)

**Current status**: Foundation complete, ready for full rollout

## What's Left: P1 Full Rollout

**Goal**: Migrate remaining 29 agents to use reference layers
- **Done**: 2/31 agents (test-builder, build-python)
- **Pending**: 29/31 agents
- **Estimated savings**: 718 more lines of duplication eliminated

## Reference Layer System

**7 layers created** in `assets/inputs/`:
1. `core-system.yml` - 5 files, used by 27 agents
2. `core-guidelines.yml` - 8 files, used by 22 agents
3. `cleaner-shared.yml` - 8 files, used by 6 agents
4. `deploy-shared.yml` - 2 files, used by 8 agents
5. `planner-shared.yml` - 4 files, used by 8 agents
6. `test-shared.yml` - 6 files, used by 10 agents
7. `explore-shared.yml` - 1 file, used by 5 agents

**Pilot Results**: ✅ VALIDATED
- Both agents successfully accessed all layered inputs
- Transitive loading works correctly
- Zero broken references
- Significant line reduction (20-50 lines per agent)

## Agent-to-Layer Mapping

### Build Category (2 agents)
- build-flutter: core-system, core-guidelines ⏳
- build-python: core-system, core-guidelines ✅ PILOT

### Test Category (8 agents)
- test-builder: core-system, core-guidelines, planner-shared, test-shared ✅ PILOT
- test-audit: core-system, core-guidelines, test-shared ⏳
- test-final-output: core-system, core-guidelines, test-shared ⏳
- test-runner: core-system, core-guidelines, test-shared ⏳
- test-service: core-system, core-guidelines, test-shared ⏳
- test-user-simulator: core-system, core-guidelines ⏳
- test-flutter-builder: core-guidelines, cleaner-shared, test-shared ⏳
- test-flutter-runner: test-shared ⏳

### Cleaner Category (3 agents)
- cleaner-core: core-system, cleaner-shared, deploy-shared ⏳
- cleaner-execute: core-system, cleaner-shared, deploy-shared ⏳
- cleaner-identify: core-system, cleaner-shared, deploy-shared ⏳

### Deploy Category (3 agents)
- deploy-cicd: core-system, core-guidelines, deploy-shared ⏳
- deploy-packaging: core-system, core-guidelines, deploy-shared ⏳
- deploy-worktree: core-system, core-guidelines, deploy-shared ⏳

### Explore Category (5 agents)
- explore-architecture: core-system, core-guidelines, explore-shared ⏳
- explore-dependency: core-system, core-guidelines, explore-shared ⏳
- explore-feature: core-system, core-guidelines, explore-shared ⏳
- explore-synthesis: core-system, core-guidelines, explore-shared ⏳
- explore-test: core-system, core-guidelines, explore-shared ⏳

### Planner Category (5 agents)
- planner-agent-exam: core-system, planner-shared ⏳
- planner-build: core-system, planner-shared ⏳
- planner-cleaning: core-system, planner-shared ⏳
- planner-teach: core-system, core-guidelines, cleaner-shared, deploy-shared, planner-shared, test-shared ⏳
- planner-test: core-system, core-guidelines, planner-shared, test-shared ⏳

### Teacher Category (2 agents)
- teacher-process: core-system, core-guidelines, cleaner-shared, planner-shared, test-shared ⏳
- teacher-update-assets: core-system, core-guidelines, deploy-shared, planner-shared ⏳

### Documentation Category (1 agent)
- documentation-core: core-system, core-guidelines ⏳

## Recommended Approach

**Option 1: Automated (Recommended)**
Use teacher agents to migrate all 29 agents automatically:
- Spawn teacher-update-assets agent per category
- Each agent updates inputs.yml for agents in its category
- Verify after each category
- Estimated time: 2-4 hours

**Option 2: Manual**
Update each agent's inputs.yml manually following pilot pattern:
- Add `layers:` section with appropriate layer references
- Remove duplicated file references from `core_inputs:`
- Keep agent-specific files
- Estimated time: 1-2 days

**Option 3: Phased**
Rollout by category over 4 weeks (safer for production):
- Week 1: Test category
- Week 2: Build + Deploy
- Week 3: Planner + Teacher
- Week 4: Explore + Cleaner + Documentation

## Files to Reference

**Summary**: `docs/plans/live/251218MAG_staging/PHASE_1_2_SUMMARY.md`
**Layer files**: `assets/inputs/*.yml`
**Pilot examples**:
- `agents/test/test-builder/inputs.yml`
- `agents/build/build-python/inputs.yml`

## Success Criteria (P1 Full Rollout)

- [ ] All 31 agents migrated to use reference layers
- [ ] Each agent references appropriate layers per mapping above
- [ ] Agent-specific inputs preserved
- [ ] All agents can access required inputs
- [ ] 788 lines of duplication eliminated total (70 done, 718 remaining)
- [ ] Zero broken references
- [ ] "1 concept per file" principle maintained

## Quick Start (Next Session)

```bash
# 1. Review summary
cat docs/plans/live/251218MAG_staging/PHASE_1_2_SUMMARY.md

# 2. Review pilot examples
cat agents/test/test-builder/inputs.yml
cat agents/build/build-python/inputs.yml

# 3. Review layer files
ls -la assets/inputs/

# 4. Choose approach and execute
# Option 1: Spawn teacher agents (automated)
# Option 2: Manual updates category by category
# Option 3: Phased rollout over 4 weeks
```

---

**Status**: Ready for rollout
**Blockers**: None
**Risks**: Low (pilot validated, backwards compatible)
**Context window**: Reset recommended (current session at 117K/200K tokens)
