# Next Session Execution Checklist
# Plan: 260104AE_agenticguidance
# Generated: 2026-01-06

## Pre-Flight Checks

- [ ] Verify worktree exists: `/home/code/AgenticEngineering-agenticguidance`
- [ ] Verify on correct branch: `agenticguidance`
- [ ] Review session summary: `audit/260106_session3_summary.yml`

## Priority 1: Decision Items (BLOCKING)

### DECISION-001: Legacy-only Agents
**Agents**: planner-phases, planner-teach
**Location**: `modules/legacy/MyAgents/projects/MyAgentsGuidance/agents/planner/`

Choose ONE: 
- [ ] **Option A**: Migrate with full updates
  - Create `modules/AgenticGuidance/agents/planner/planner-phases/`
  - Create `modules/AgenticGuidance/agents/planner/planner-teach/`
  - Add PATH RESOLUTION SEMANTICS header
  - Add required_inputs section
  - Add layer references
  - Update agent-categories.yml

- [X] **Option B**: Deprecate
  - Create `DEPRECATED.md` in legacy folders
  - Remove any dangling references
  - Document that functionality absorbed by orchestration-planning

- [ ] **Option C**: Merge into orchestration-planning
  - Extract phase decomposition logic
  - Add to orchestration-planning process
  - Deprecate original agents

**Recommendation**: Evaluate if orchestration-planning already handles phase decomposition

### DECISION-002: NOT_MIGRATED Test Agents
**Agents**: test-user-simulator, test-service, test-builder
**Referenced by**: planner-test manifest

Choose ONE:
- [ ] **Option A**: Add fallback paths (RECOMMENDED - LOW effort)
  - Update planner-test/manifest.yml with fallback_path fields
  - Point to legacy locations

- [X] **Option B**: Migrate agents (HIGH effort)
  - Create agents in `modules/AgenticGuidance/agents/test/`
  - Full guidance updates

- [ ] **Option C**: Remove strategies
  - Remove test strategies that require unmigrated agents
  - Update planner-test guidance

## Priority 2: Teach Plan Execution

Execute phases from `live/plan_live_teach.yml`:

### CRITICAL Phases
- [ ] **Phase 1**: Fragment Reference Resolution (`teach_frag_001`)
  - Update `assets/definitions/fragment-references.yml`
  - Add dot-notation support
  - Add concrete examples

- [ ] **Phase 2**: Process File Format Standardization (`teach_proc_001`)
  - Update `agent-context-files.yml` to allow `.mmd` format
  - Update `agent-role-scope-matrix.md` with `.mmd` links
  - Document the .mmd-first pattern for orchestration

### HIGH Phases
- [ ] **Phase 3**: Output Schema Documentation (`teach_out_001`)
- [ ] **Phase 4**: Required Input Validation (`teach_inp_001`)
- [ ] **Phase 5**: Version Alignment (`teach_ver_001`)
- [ ] **Phase 6**: CLI Command Centralization (`teach_cli_001`)
- [ ] **Phase 7**: Spawns Declaration (`teach_spn_001`)
- [ ] **Phase 8**: REPO_ROOT Variable Definition (`teach_repo_001`)

## Priority 3: Friction Remediation Phase 2

Execute tasks from main plan (`live/plan_agenticguidance.yml`):

### CRITICAL Tasks
- [ ] `rem2_001`: Resolve legacy-only planner agents (see DECISION-001)
- [ ] `rem2_002`: Fix fragment reference resolution (see Phase 1)
- [ ] `rem2_003`: Standardize process file format (see Phase 2)
- [ ] `rem2_004`: Address NOT_MIGRATED test agents (see DECISION-002)

### HIGH Tasks
- [ ] `rem2_005`: Align version numbers
- [ ] `rem2_006`: Populate output schemas
- [ ] `rem2_007`: Centralize CLI command documentation
- [ ] `rem2_008`: Add spawns declarations
- [ ] `rem2_009`: Explicit required input validation
- [ ] `rem2_010`: Define REPO_ROOT variable
- [ ] `rem2_011`: Clarify path resolution prefixes

## Priority 4: Resume Main Plan

After completing above:
- [ ] CLI Offloading phase (4 tasks)
- [ ] Entrypoint & Schema phase (2 tasks)
- [ ] MMD Implementation phase (3 tasks)
- [ ] Orchestration Remodel & De-linearization phase (1 task)
- [ ] Asset & Example Alignment phase (4 tasks)

## Quick Reference

| File | Purpose |
|------|---------|
| `live/plan_agenticguidance.yml` | Main plan with all phases |
| `live/plan_live_teach.yml` | Teaching phases (8 phases) |
| `live/plan_live_orchestration_remodel.yml` | Remodel phases (4 phases) |
| `audit/260106_session2_self_review_results.yml` | Friction findings |
| `audit/260106_session3_summary.yml` | Session summary |

## Estimated Scope

- Decision items: 2 (blocking)
- Teach phases: 8 (2 CRITICAL, 6 HIGH)
- Remediation tasks: 11 (4 CRITICAL, 7 HIGH)
- Main plan tasks: 13 (deferred)

Total blocking items: 4 CRITICAL (depends on decisions)
