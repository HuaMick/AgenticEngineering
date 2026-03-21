# Epic: Planner-Design Agent & Story-Test Alignment

## Problem

Two interconnected gaps in the orchestration planning system:

1. **No design intermediary** — After story discovery, individual planners are spawned with just an `objective` string. No structured step maps stories → solution architecture → phase skeleton. Planners work blind to each other.

2. **No persistent test-to-story linkage** — 95% of 544 user stories are untested. The `affected_stories` mechanism is ephemeral (per-epic lifecycle). Once an epic completes, there is no persistent record that test X validates story Y. The `test_status` field decays immediately and is disconnected from CI.

## Solution (Revised after 5 independent architecture reviews)

### 1. Pytest Story Markers (Primary Linkage Mechanism)
- Register `@pytest.mark.story("US-XXX-NNN")` marker convention in both test modules
- Conftest collection plugin validates markers reference valid story IDs
- Co-located with test code — cannot drift, natively queryable, zero infrastructure
- Test-builder agent guidance updated to mandate markers on story-linked tests

### 2. New `planner-design` Agent
A dedicated agent between story discovery and planner spawning:
- Receives `affected_stories` as required input (not discovered mid-process)
- Maps stories to phases (traceability matrix)
- Defines solution architecture skeleton with cross-phase contracts
- Outputs structured inputs for downstream planners

### 3. Enhanced `planner-audit` and `planner-test` Guidance
- planner-audit: new story traceability audit step (tickets↔stories bidirectional check)
- planner-test: UAT task template requires `story_id` as mandatory field

### 4. Story Coverage Feedback Loop (Research-Validated)
Based on research into NVIDIA HEPH, CoverUp, and Meta TestGen-LLM patterns:
- `STORY_COVERAGE_INCOMPLETE` feedback trigger in orchestration-executor
- After test phase, check pytest marker coverage against affected stories
- If incomplete, re-run test-builder with uncovered story IDs as context (max 3 iterations)
- Exit condition: all affected stories have `@pytest.mark.story` markers in test files
- Validation gate enhanced to scan markers (not just YAML test_status which decays)

### 5. CLI Coverage Reporting and Fence Checks
- `agentic stories report --coverage`: cross-references pytest markers against story inventory
- Fence 4 in `_check_fences()`: post-execution WARN for uncovered stories
- `story_ids` field on Ticket dataclass for planning-level traceability

## What We Explicitly Don't Do (Per Review Consensus)
- **Don't move story YAML content to TinyDB** — stories are authored reference docs, not transactional state
- **Don't write test scaffolds during planning** — violates planner/builder separation
- **Don't build a separate TinyDB linkage table** — markers are co-located and can't drift

## Future Phases (After This Epic)
- Extract test metadata (test_status, last_tested) to TinyDB
- Create StoryService/StoryRepository abstraction
- Story content migration (only if warranted)

## Scope

- P1: Pytest marker registration + conftest collection plugin (3 tickets)
- P2: planner-design agent + guidance updates for test-builder/planner-test/planner-audit/orchestration-planning + story coverage feedback loop (9 tickets)
- P3: Ticket.story_ids field + CLI --story-ids flag + coverage reporting + Fence 4 + PlannerLoopRunner update (5 tickets)
- P4: Tests for all of the above (5 tickets)
