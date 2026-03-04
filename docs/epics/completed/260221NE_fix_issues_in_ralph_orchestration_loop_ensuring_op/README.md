# Fix Issues in Ralph Orchestration Loop

## Objective

Fix multiple identified issues in the Ralph orchestration loop that prevent it from
operating reliably as a self-directing plan orchestration system. The key issues are:

1. **Question Gate Not Implemented** - The process.yml MANDATES checking `agentic question list --plan <folder>` before processing any plan, but RalphLoopService has no question-checking logic. Plans with open blocking questions are executed regardless.

2. **Open Questions Not Routed to Human** - When agents encounter ambiguities during execution, questions created via `agentic question ask` are stored in plan question folders but the ralph loop has no mechanism to surface them, block affected plans, or notify the human operator.

3. **Completion Promise Not Enforced** - The completion_promise text is defined in inputs.yml but `check_all_complete()` returns a bare boolean without emitting the promise text. The agent loop lacks a clear signal for when to emit the promise.

4. **CLI `-j` Flag Inconsistency in RalphLoopService** - `_get_plan_status_from_cli()` uses `[..., "-j"]` but the CLI convention is `agentic --json plan status` (root-level `--json` flag). This causes the CLI call to fail silently.

5. **Plans with No Tasks Treated as Completed** - `_determine_action_required()` returns "completed" when `total_tasks == 0`, but a plan with 0 tasks may simply not have been fully created yet (e.g., just a README.md and empty plan_build.yml).

## Phases Overview

| Phase | Name | Tasks | Description |
|-------|------|-------|-------------|
| P1 | Question Gate Integration | 3 | Add question-checking to RalphLoopService and block plans with pending blocking questions |
| P2 | Open Question Routing | 2 | Surface open questions in ralph status/next output, add question summary to loop reports |
| P3 | Loop Robustness Fixes | 3 | Fix CLI flag, empty plan handling, completion promise enforcement |
| P4 | Testing | 2 | Unit tests for question gate, integration tests for loop fixes |
| P5 | UAT | 1 | User acceptance testing against affected stories |

## Dependencies and Prerequisites

- **260219NS_fix_nested_session_spawn**: Fixes CLAUDECODE env var leakage in subprocess spawns (including ralph.py). This plan is independent of that fix - both can proceed in parallel since they touch different aspects of ralph.
- **Question service**: Already implemented (`agenticguidance.services.question`)
- **Question CLI**: Already implemented (`agenticcli.commands.question`)

## Success Criteria

- `RalphLoopService.discover_plans()` checks for pending blocking questions and marks plans as "blocked" when they have unresolved blocking questions
- `ralph next --json` output includes `blocking_questions` count when a plan is blocked by questions
- `ralph status` output includes a question summary section showing total pending questions across all plans
- Plans with 0 tasks and no orchestration MMD are classified as "needs_planning" not "completed"
- The `-j` flag in `_get_plan_status_from_cli()` is fixed to use the correct `--json` root-level convention
- `check_all_complete()` returns additional context (not just bool) including whether promise can be emitted
- All new functionality is covered by unit tests
- Existing tests continue to pass (no regressions)

## Open Questions

- **OQ-1**: Should the ralph loop auto-start a question dashboard/watcher when it starts? Currently question monitoring requires a separate `agentic question watch-daemon` invocation.
- **OQ-2**: When all remaining plans are blocked by questions, should the loop emit the completion promise or a distinct "blocked_by_questions" status?
- **OQ-3**: Should the loop iteration limit be paused/not-counted when the loop is waiting for human answers?
