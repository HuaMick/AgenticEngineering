# Story-Writer UAT-First Restructure

## Objective

Restructure the `build-story-writer` agent so that its output is **UAT-testable from day one**. Today, stories are written as behavioral specs (when/then steps) that downstream agents can use for exploration and orchestration, but the test-uat agent often struggles to validate them because:

1. **Stories lack explicit UAT hooks** — the `steps` field describes observable behavior but not how a blind test-uat agent should *verify* each step (expected CLI output, file-system artifacts, database state).
2. **Testing metadata is post-hoc** — `test_status`, `last_tested`, `test_notes` are populated *after* implementation, but UAT needs success criteria defined *before* implementation.
3. **No verification commands in stories** — test-uat must independently discover how to validate each `then` clause, leading to inconsistent validation and false passes/fails.
4. **Category codebase_scope is exploration-only** — categories help planner-explore but don't carry UAT-relevant context (e.g., which CLI commands to smoke-test, which files to check exist).

This epic restructures the story-writer output format and process to embed UAT verification metadata directly into stories at generation time, ensuring test-uat agents can validate every story step without guesswork.

## Affected Stories

- **US-STR-001**: Story Discovery and Coverage — story format changes affect `find`, `health`, `coverage` commands
- **US-GDN-074**: User Story UAT — UAT process directly impacted by story format changes
- **US-GDN-081**: Test Phase Planning Architecture — planner-test reads stories to create UAT tasks
- **US-PLN-046**: Orchestration Workflow — planning pipeline spawns story-writer and parses output

## Phases Overview

### P1: Story Schema Extension (Build)
Add UAT verification fields to the story schema and update the story-writer process guidance. New fields per story step:
- `verify`: How to verify the `then` clause (CLI command, file check, API call)
- `verify_type`: Enum (`cli_output`, `file_exists`, `db_state`, `api_response`, `manual`)

### P2: Story Service Updates (Build)
Update `agenticguidance.services.story` to parse, validate, and expose the new verification fields. Update the `StoryService` model, YAML loading, and any downstream consumers.

### P3: Story-Writer Agent Guidance Update (Guidance)
Rewrite `build-story-writer/process.yml` to instruct the agent to produce verification metadata for every `then` clause. Add examples showing good vs. bad verification steps.

### P4: Pipeline Integration (Build)
Update `planner_loop.py` parsing and `planner-test` to consume verification fields when creating UAT tickets. Ensure test-uat can extract verification commands from story definitions.

### P5: Test & Validation (Test)
Unit and integration tests for schema changes, service layer, and pipeline integration. Includes test-fix-loop pattern.

### P6: UAT (User Acceptance Testing)
Validate the full journey: seed an epic → story-writer generates stories with verification metadata → planner-test creates UAT tickets with verification commands → test-uat can execute verification steps.

## Dependencies and Prerequisites

- Story service (`agenticguidance.services.story`) must remain backward compatible — existing stories without `verify` fields must still load
- Planning pipeline (`planner_loop.py`) must not break on stories missing the new fields
- Existing 27+ stories across the repository must continue to pass `agentic stories find` and `agentic stories health`

## Success Criteria

1. **Schema**: Stories have optional `verify` and `verify_type` fields per step
2. **Story-Writer**: Agent generates verification metadata for every `then` clause
3. **Backward Compatibility**: Existing stories without verify fields load without error
4. **Pipeline**: planner-test reads verify fields to create more targeted UAT tickets
5. **test-uat**: Agent can extract verification commands directly from story definitions
6. **No regression**: All existing tests pass (`AgenticGuidance` + `AgenticCLI` suites)

## Impacted Artifacts

| Artifact | Type | Impact |
|---|---|---|
| `modules/AgenticGuidance/assets/definitions/user-stories.yml` | Definition | Schema extension |
| `modules/AgenticGuidance/agents/build/build-story-writer/process.yml` | Agent guidance | Verification step instructions |
| `modules/AgenticGuidance/agents/build/build-story-writer/manifest.yml` | Agent manifest | Output schema update |
| `modules/AgenticGuidance/src/agenticguidance/services/story.py` | Service | Model + parsing |
| `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` | Workflow | Story parsing |
| `modules/AgenticGuidance/agents/planner/planner-test/process.yml` | Agent guidance | Verification-aware UAT ticket creation |
| `modules/AgenticGuidance/agents/test/test-uat/process.yml` | Agent guidance | Verification command extraction |
| `docs/userstories/Stories/*.yml` | Story files | Existing stories unchanged (backward compat) |

## Open Questions

1. Should `verify` be a single string or a list (to support multi-assertion steps)?
   - **Recommendation**: Single string initially (verification command), list in future iteration
2. Should existing stories be backfilled with verify fields, or only new stories?
   - **Recommendation**: New stories only; existing stories gain verify fields when re-generated
3. Should verify_type include `composite` for steps requiring multiple check types?
   - **Recommendation**: Start with simple enum, extend later
