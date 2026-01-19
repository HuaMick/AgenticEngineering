# Guidance Entrypoint Remediation

## Objective
Address agent confusion regarding where planning should occur (worktree vs main) and ensure the user has a centralized view of all planning state.

## Strategy: Option 2 (Main-First Planning)
This plan implements a policy where:
1.  **Planning initialization** happens in the `main` repo.
2.  **Plan files** stay in `main` (or are committed there frequently) so they are always visible to the user.
3.  **Worktrees** are used strictly for *execution* (implementation, testing).

## Plan Status
- [x] Phase 1: Audit and Analysis (Completed 2026-01-19)
- [x] Phase 2: Policy and Guidance Update (Completed 2026-01-19)
- [ ] Phase 3: CLI Locality Decoupling (Requires separate build plan)
- [x] Phase 4: Verification (Completed 2026-01-19)

## Execution Summary

### Phase 1: Audit and Analysis
- Identified 5 major worktree-locality instruction sets
- Documented in `analysis/audit_worktree_locality.md`
- All 4 target files required updates

### Phase 2: Remediation (Guidance Updates)
Updated the following files with Main-First Planning policy:
- `worktree-and-branching.yml` - Added new "Main-First Planning" rule
- `plans.yml` - Updated definition and added `main_first_policy` section
- `orchestration-planning/process.mmd` - Added Main-First guideline references
- `orchestration-planning/inputs.yml` - Added `planning_policy` section

### Phase 3: Blind Test Validation
- test-guidance-simulator created test planning folder following updated guidance
- **Result**: Guidance is CLEAR and unambiguous
- **Finding**: CLI tool (`agentic plan init`) doesn't yet implement Main-First (creates in worktree)
- This confirms CLI update is needed (separate build plan)

### Phase 4: Final Audit
- All 4 files pass consistency check
- No contradictory statements found
- Cross-references are valid

## Key Decisions
1. **Guidance First**: Guidance documentation is updated BEFORE CLI implementation
2. **CLI Separate**: CLI changes require a dedicated build plan
3. **Main-First Pattern**: Plans created in main, executed in worktrees

## Next Steps
1. Create build plan for CLI locality decoupling (`plan_live_build.yml`)
2. Update `agentic plan init` to support main-worktree creation
3. Consider `--main` flag or auto-detection

## Key Files
- `live/plan_live_teach.yml`: Detailed remediation steps
- `live/plan_live_test.yml`: Blind test validation
- `live/plan_live_audit_clean.yml`: Final audit tasks
- `live/orchestration_guidance_entrypoint.mmd`: Execution flowchart
- `analysis/audit_worktree_locality.md`: Initial audit findings
- `analysis/review_260119_teach_test.yml`: Plan review
