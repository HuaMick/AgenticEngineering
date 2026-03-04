# UAT Fence Hardening Plan

## Objective

Harden the three mandatory UAT fences (story-first planning, UAT mandatory, story anchoring) so they are **enforced**, not just documented. Agents currently bypass UAT via unchecked decision points; the executor validation gate warns instead of blocking; and the output contract between test-user-simulator and the executor is broken.

## Scope

- **Phase 1**: Unify escape hatch rules into a single source of truth
- **Phase 2**: Harden planning and executor gates (blocking, not advisory)
- **Phase 3**: Fix output contract between test-user-simulator and story schema
- **Phase 4**: Add story coverage validation and CLI `--check-fences` command

## Stories

US-ORCH-035 through US-ORCH-042 in `docs/userstories/Orchestration/05_uat_fences.yml`

## Phase Dependencies

```
Phase 1 (unified rules) -> Phase 2 (gates reference unified rules) -> Phase 3 (schema + contract) -> Phase 4 (coverage + CLI)
```

## Files Modified

| Phase | Files |
|-------|-------|
| 1 | planning-standard.yml, orchestration-planning/process.mmd, planner-test/process.yml, planner-reviewer/process.yml, planner-build/process.yml |
| 2 | orchestration-planning/process.mmd, orchestration-executor/process.yml, orchestration-executor/inputs.yml |
| 3 | user-stories.yml (definitions), test-user-simulator/process.yml, test-user-simulator/inputs.yml |
| 4 | orchestration-executor/process.yml, plan.py (CLI), test_plan_validate_fences.py (new) |

## Verification

1. `agentic plan validate docs/plans/live/260208UF_uat_fence_hardening --check-fences` passes
2. No inline escape hatch definitions remain outside `planning-standard.yml`
3. All 8 stories (US-ORCH-035 through US-ORCH-042) exist
4. Build plan flow in process.mmd has no path skipping UAT without rationale
5. Executor validation gate blocks on missing stories, untested stories, missing UAT subgraph
