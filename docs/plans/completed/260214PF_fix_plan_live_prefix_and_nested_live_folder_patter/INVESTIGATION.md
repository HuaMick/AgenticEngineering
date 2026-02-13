# Investigation: Outdated plan_live_ Pattern in Guidance Files

## Problem Statement

The plan folder `260214US_add_user_story_generation_phase_to_planner_agents` was created with a MIXED structure:

**Correct files (at root):**
- `plan_teach.yml`
- `plan_test.yml`
- `plan_audit_clean.yml`

**Incorrect files (nested in live/ subfolder):**
- `live/plan_live_build.yml`
- `live/plan_live_test.yml`

This violates the canonical plan folder structure defined in `plans.yml`.

## Root Cause

The orchestration-planning and planner agents are using **outdated guidance** that references:
1. Nested `live/` subdirectories within plan folders
2. `plan_live_*` filename prefix

### Evidence from Code

**orchestration-planning/process.mmd (line 68):**
```
%% - plan_live_*.yml: Phase plan files (build, test, teach, cleanup as needed)
```

**planner-test/process.yml (line 18):**
```yaml
path_template: "docs/plans/live/{planning_folder}/live/plan_test.yml"
```

**planner-build/process.yml (line 35):**
```yaml
path_template: "docs/plans/live/{plan_folder_name}/live/plan_live_build.yml"
```

**planner-guidance/process.yml (lines 27, 37):**
```yaml
path_template: "docs/plans/live/{plan_folder_name}/live/plan_live_teach.yml"
path_template: "docs/plans/live/{plan_folder_name}/live/plan_live_audit_clean.yml"
```

**planner-cleaning/process.yml (line 42):**
```yaml
location: "docs/plans/live/YYMMDDXX_description/live/plan_live_*.yml"
```

## Canonical Structure (from plans.yml)

**plans.yml lines 33-51 (FLAT STRUCTURE REQUIREMENT):**
```yaml
  Standard folder structure:
    YYMMDDXX_description/
    ├── README.md              # Plan overview and status
    ├── orchestration_*.mmd    # Process diagram(s)
    ├── plan_*.yml             # Phase files (directly in root)
    └── reference/             # Optional: reference materials

  Optional subfolders for artifacts (NOT for plan files):
  - reference/: Reference materials and research (optional)
  - analysis/: Iteration logs and analysis artifacts (optional)
  - audit/: Audit reports and findings (optional)
```

**plans.yml lines 200-216 (file_taxonomy FENCE):**
```yaml
file_taxonomy:
  CRITICAL: Plan files (plan_*.yml) MUST be in the plan folder root, NOT in subdirectories.

  Correct structure:
    YYMMDDXX_description/
    ├── README.md
    ├── orchestration_*.mmd
    ├── plan_build.yml       # <-- Directly in folder root
    ├── plan_teach.yml       # <-- Directly in folder root
    └── reference/           # Optional subfolder for reference materials

  WRONG structure (do NOT use):
    YYMMDDXX_description/
    ├── live/
    │   └── plan_*.yml       # WRONG: nested in subdirectory
    └── completed/
        └── plan_*.yml       # WRONG: nested in subdirectory
```

## Impact

1. **CLI Incompatibility**: The CLI expects flat structure. Commands like `agentic plan task start` may not find files in nested folders.

2. **Auto-Archival Failures**: The auto-archival logic looks for plan files at root, not in subfolders.

3. **Inconsistency**: Different plan folders have different structures, causing confusion.

4. **Maintenance Burden**: Agents receive conflicting guidance about where to write plan files.

## Verification of CLI Behavior

The `agentic plan init` command correctly creates the flat structure:

```bash
$ agentic plan init 260214PF_fix_plan_live_prefix_outdated_pattern --description "Fix plan_live_ prefix and nested live/ folder pattern in guidance"

$ ls -la docs/plans/live/260214PF_fix_plan_live_prefix_and_nested_live_folder_patter/
total 24
-rw-r--r-- 1 mick mick 1515 Feb 14 07:41 plan_audit_clean.yml
-rw-r--r-- 1 mick mick   95 Feb 14 07:41 plan_completed.yml
-rw-r--r-- 1 mick mick 2521 Feb 14 07:41 plan_teach.yml
-rw-r--r-- 1 mick mick 1629 Feb 14 07:41 plan_test.yml
```

**No nested folders. Plan files at root. No `plan_live_` prefix.**

## Comparison with Completed Plans

All recent completed plans use the correct flat structure:

```bash
$ ls docs/plans/completed/260214WS_workspace_auto_sync/
README.md
audit/
completed/
live/
orchestration_workspace_auto_sync.mmd
plan_build.yml  <-- At root
questions/
```

```bash
$ ls docs/plans/completed/260214PL_orchestrate_planning_loop/
orchestration_orchestrate_planning_loop.mmd
plan_build.yml  <-- At root
questions/
review_20260214.yml
```

```bash
$ ls docs/plans/completed/260214TU_tmux_orchestration_ui/
orchestration_tmux_orchestration_ui.mmd
plan_build.yml  <-- At root
questions/
```

## Legacy Contamination

The outdated pattern exists in legacy code (`modules/legacy/MyAgents/...`) which is expected. However, it has leaked into the active guidance in `modules/AgenticGuidance/`:

**Active guidance files with outdated pattern:**
1. `modules/AgenticGuidance/agents/orchestration/orchestration-planning/process.mmd`
2. `modules/AgenticGuidance/agents/planner/planner-test/process.yml`
3. `modules/AgenticGuidance/agents/planner/planner-build/process.yml`
4. `modules/AgenticGuidance/agents/planner/planner-guidance/process.yml`
5. `modules/AgenticGuidance/agents/planner/planner-cleaning/process.yml`
6. `modules/AgenticGuidance/agents/planner/planner-audit/process.yml`
7. `modules/AgenticGuidance/agents/planner/planner-guidance-testing/process.yml`

## Search Results Summary

```bash
# Search for plan_live_ pattern
$ rg "plan_live_" --files-with-matches | wc -l
249  # Mostly legacy, 7 in active guidance

# Search for live/plan_ pattern
$ rg "live/plan_" --files-with-matches | wc -l
195  # Mostly legacy, 5 in active guidance
```

## Why This Happened

The migration from MyAgents to AgenticGuidance was incomplete. The planner agents were migrated but retained references to the old nested structure pattern from the legacy codebase.

The CLI was built correctly (following the canonical plans.yml definition), but the planner agents were not updated to match.

## Prevention Strategy

1. **Update all planner guidance**: Fix path_templates to use flat structure
2. **Add fence to plans.yml**: Explicitly prohibit nested folders for plan files
3. **Update planner-reviewer checklist**: Add validation for flat structure
4. **Validate existing plans**: Scan for violations and document them

## Related Files

**Canonical definitions:**
- `modules/AgenticGuidance/assets/definitions/plans.yml` (lines 33-51, 200-216)

**Files requiring updates:**
- `modules/AgenticGuidance/agents/orchestration/orchestration-planning/process.mmd`
- `modules/AgenticGuidance/agents/planner/planner-test/process.yml`
- `modules/AgenticGuidance/agents/planner/planner-build/process.yml`
- `modules/AgenticGuidance/agents/planner/planner-guidance/process.yml`
- `modules/AgenticGuidance/agents/planner/planner-cleaning/process.yml`
- `modules/AgenticGuidance/agents/planner/planner-audit/process.yml`
- `modules/AgenticGuidance/agents/planner/planner-guidance-testing/process.yml`

**Affected plan folders:**
- `docs/plans/live/260214US_add_user_story_generation_phase_to_planner_agents/`
