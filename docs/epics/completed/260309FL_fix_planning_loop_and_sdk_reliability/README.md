# Epic: Fix Planning Loop + SDK Reliability

## Problem
Planning loop gets stuck in infinite loop. Two root causes identified:

### Root Cause 1: Missing planner-orchestration step (FIXED)
`_process_plan()` in `planner_loop.py` never spawns `planner-orchestration` agent.
Without this step, no TinyDB phase records with `agent` routing are created.
`discover_plans_needing_orchestration()` keeps finding the epic → infinite loop.

### Root Cause 2: determine_plan_type returns None for fresh epics (FIXED)
When no tickets exist in TinyDB (first-time planning), `determine_plan_type()` returned None,
causing `_process_plan()` to fail immediately. Fixed to default to "build".

### Root Cause 3: Agent guidance references YAML files (FIXED)
Multiple `.claude/agents/planner-*.md` files and `planner-sdk` manifest/process still
declared YAML file outputs. Fixed to reference TinyDB via CLI commands.

### Issue 4: SDK agent failures (RESOLVED by epic 260309TM)
During planning test, SDK agents fail with "Fatal error in message reader: Command failed
with exit code 1". Happens after first few agents succeed. Root cause confirmed: SDK
`query()` cannot be called more than once per process (zombie subprocess bug). Resolved
by epic 260309TM_sdk_in_tmux_spawn_unification — each agent now runs in its own tmux
pane via `sdk_pane_runner.py`, eliminating sequential `query()` calls in a single process.

## Changes Made

### planner_loop.py
- Added `spawn_orchestration_agent()` method to `PlannerLoopWorkflow`
- Added step 6 (orchestration) to `_process_plan()` after review cycle
- Changed `determine_plan_type()` to default to "build" when no tickets exist
- Fixed misleading log message "No plan YAML found" → "Could not determine plan type"

### test_planner_loop.py
- Updated `_make_runner()` to mock `spawn_orchestration_agent`
- Updated `test_processes_single_plan` to verify 6-step workflow with orchestration
- Updated `test_validate_result_called_in_process_plan` to check planner-orchestration
- Fixed `test_no_plan_file` and `test_nonexistent_folder` for new default-to-build behavior

### Agent guidance files (background agents)
- `.claude/agents/planner-build.md` - TinyDB outputs, no YAML
- `.claude/agents/planner-guidance.md` - TinyDB outputs, no YAML
- `.claude/agents/planner-test.md` - TinyDB outputs, no YAML
- `.claude/agents/planner-orchestration.md` - TinyDB ticket reading
- `planner-sdk/manifest.yml` - TinyDB outputs, no YAML
- `planner-sdk/process.yml` - TinyDB outputs, no YAML

## Test Results
- `test_planner_loop.py`: 64 passed
- `test_orchestration_workflow.py`: 17 passed
- `test_plan_orchestration.py` + `test_ralph_commands.py`: 78 passed

## Planning Test
- Epic: 260307TA_test_audit_user_story_coverage
- Result: Loop terminated at max_iterations=10 (NO infinite loop)
- First iteration: explore → story → planner → reviewer all succeeded
- Subsequent iterations: SDK failed with exit code 1
- Error: "Fatal error in message reader: Command failed with exit code 1"

## Remaining Work
- [ ] Investigate SDK "Fatal error in message reader" failures
- [ ] Check LangSmith traces for the failed sessions
- [ ] Consider adding early-stop when all retry attempts exhaust for same epic
- [ ] Update stale docstrings referencing plan_build.yml (low priority)
