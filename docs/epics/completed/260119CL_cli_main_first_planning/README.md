# CLI Main-First Planning Implementation

## Objective
Modify `agentic plan init` to ALWAYS create plan folders in the main worktree.
Single happy path - no flags needed.

## Linked Worktree
- **Execution**: `/home/code/AgenticEngineering-agentic-cli` (agentic-cli branch)
- **Related Plan**: `260119AG_guidance_entrypoint_remediation` (guidance updates)

## Plan Status
- [ ] Phase 1: Implement Main Worktree Detection
- [ ] Phase 2: Modify cmd_init() Logic
- [ ] Phase 3: Build Verification

## Target Files
- `modules/AgenticCLI/src/agenticcli/commands/plan.py` - Core logic changes

## Key Changes
1. Plans ALWAYS created in main worktree
2. Feature worktree still created for execution
3. No flags or options - single happy path

## Key Files
- `live/plan_live_build.yml`: Implementation tasks (3 phases, 4 tasks)
- `live/orchestration_cli_main_first.mmd`: Execution flowchart
