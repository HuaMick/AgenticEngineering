# Epic: Fix story_ids Field Mismatch Blocking Build Agents

## Objective

Fix the `story_ids` field serialization gap in CLI commands and the incorrect field path references in agent process/inputs files that prevent build agents from receiving story context. Build agents currently cannot access story IDs because:

1. `cmd_task_current` omits `story_ids` from its serialized output
2. `cmd_task_list` omits `story_ids` from its serialized output
3. Agent process.yml and inputs.yml files reference `ticket.inputs.affected_stories` — a path that doesn't exist on the Ticket model (correct field: `ticket.story_ids`)

## Affected Stories

- **US-SET-029**: Ticket Story IDs Field — story_ids defined on model but not serialized everywhere
- **US-STR-011**: Ticket --story-ids CLI Flag — CLI serialization inconsistency
- **US-GDN-023**: Get Active Ticket from Epic — cmd_task_current missing story_ids
- **US-GDN-011**: Process File Structure — process.yml field path correctness
- **US-GDN-014**: Input File Declarations — inputs.yml field path correctness
- **US-PLN-086**: Ticket CRUD Operations — ticket serialization completeness

## Root Cause Analysis

### Bug 1: Missing `story_ids` in CLI serialization

In `modules/AgenticCLI/src/agenticcli/commands/epic.py`:

- **`cmd_task_current` (line ~2447)**: Constructs a dict with `id`, `name`, `description`, `status`, `phase`, `inputs`, `target_files`, `guidance`, `success_criteria`, `agent_type` — but does NOT include `story_ids`. The `repo_task` (TicketData) object has `story_ids` available.

- **`cmd_task_list` (line ~1741)**: Constructs a dict with `id`, `description`, `status`, `phase_id`, `phase_name` — does NOT include `story_ids`. Even verbose mode only adds `guidance` and `success_criteria`.

- **For comparison**: `cmd_task_add` (line ~1893) correctly includes `story_ids` in its JSON output.

### Bug 2: Wrong field path in agent guidance files

Six agent guidance files reference `ticket.inputs.affected_stories` as the source path for story IDs. This path is wrong in two ways:
- The field is `story_ids`, not `affected_stories`
- It's a top-level ticket field, not nested under `inputs`

**Affected files:**
- `agents/build/build-python/process.yml` (line 16)
- `agents/build/build-flutter/process.yml` (line 16)
- `agents/test/test-builder/inputs.yml` (line 95)
- `agents/test/test-audit/inputs.yml` (line 86)
- `agents/test/trace-explorer/process.yml` (line 18)
- `agents/test/trace-explorer/inputs.yml` (line 68)

## Phases Overview

### Phase 1: Fix CLI Serialization
Add `story_ids` field to `cmd_task_current` and `cmd_task_list` output dictionaries in `epic.py`.

### Phase 2: Fix Guidance Field Paths
Update all agent process.yml and inputs.yml files that reference the wrong field path `ticket.inputs.affected_stories` to use `ticket.story_ids`.

### Phase 3: Test
Verify serialization fixes with unit tests and ensure existing tests pass.

### Phase 4: UAT
Validate end-to-end that build agents can receive story_ids through the CLI pipeline.

## Dependencies and Prerequisites

- TinyDB is the sole data store (no YAML/MMD fallback)
- Ticket and TicketData models already have `story_ids` field defined
- `cmd_task_add` already serializes `story_ids` correctly (use as reference)
- No schema migration needed — data already persists in TinyDB correctly

## Success Criteria

1. `agentic agent epic ticket current --epic <epic> -j` output includes `story_ids` field
2. `agentic agent epic ticket list --epic <epic> -j` output includes `story_ids` field
3. All agent process.yml and inputs.yml files reference `ticket.story_ids` (not `ticket.inputs.affected_stories`)
4. All existing tests pass (AgenticCLI + AgenticGuidance)
5. CLI smoke test: `agentic agent epic ticket current` with a ticket that has story_ids returns them
6. UAT validates US-SET-029, US-STR-011, US-GDN-023 acceptance criteria
