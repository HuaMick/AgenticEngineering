# Epic: Decouple Stories from Epic Folders

## Objective

Stories are permanent system behaviors and must not be lost when epics are archived.
Currently, `stories.yml` files live inside epic folders (`docs/epics/live/<epic>/stories.yml`).
When epics complete and archive to `docs/epics/completed/`, these stories become buried in
historical folders — invisible to discovery tooling and unavailable for cross-epic reference.

This epic moves story storage from `docs/epics/live/<epic>/stories.yml` to
`docs/stories/<epic>/stories.yml`, a durable location outside the epic lifecycle. All
producers (build-story-writer), consumers (planner_loop, stories commands), and agent
guidance are updated. Existing stories.yml files are migrated to the new location.

## Affected User Stories

- **US-STR-001**: Find User Stories Across Projects
- **US-STR-009**: Story Coverage Report via Pytest Markers
- **US-STR-014**: Planner-Audit Story Traceability Audit Step
- **US-PLN-006**: Archive Completed Epics
- **US-PLN-091**: Planning Pipeline Story Generation

## Phases Overview

### Phase 1: Story Path Infrastructure
Create `docs/stories/` directory and a shared utility function for story path resolution.
Single source of truth eliminates hardcoded paths scattered across modules.

### Phase 2: Update Code Paths
Update all producers and consumers to use the new story location:
- planner_loop.py (folder creation, file readiness gate, parse method)
- stories.py cmd_audit (story reading for gap detection)
- build-story-writer process.yml (write target path + completion signal)
- Agent guidance files (planner-explore, epic-creator references)

### Phase 3: Migration and Backward Compatibility
Migrate existing stories.yml files from `docs/epics/{live,completed}/` to `docs/stories/`.
Add backward-compat fallback: read from new location first, old location as fallback for
epics that may not have been migrated (e.g., in-flight epics on other branches).

### Phase 4: Test Updates
Update test fixtures that create stories.yml in epic folders. Add new test verifying
stories persist after epic archival. Ensure test_stories_audit, test_planner_loop, and
test_planner_loop_e2e all pass with the new path.

### Phase 5: UAT
Validate the complete story lifecycle: write → read → audit → archive → stories persist.

## Dependencies and Prerequisites

- TinyDB is the sole data store for epic/ticket metadata (no YAML ticket files)
- `docs/userstories/` contains manually-authored system-wide stories (separate concern)
- `docs/stories/` (new) will hold epic-generated planning stories
- build-story-writer agent reads process.yml instructions for write path
- planner_loop reads stories.yml via `_parse_story_categories()` with retry logic
- cmd_audit reads stories.yml for bidirectional gap detection

## Impacted Artifacts

| Artifact | Type | Impact |
|----------|------|--------|
| `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` | Python | Change stories path (3 locations) |
| `modules/AgenticCLI/src/agenticcli/commands/stories.py` | Python | Change cmd_audit story path |
| `modules/AgenticGuidance/agents/build/build-story-writer/process.yml` | Guidance | Update write target path |
| `modules/AgenticGuidance/agents/planner/planner-explore/process.yml` | Guidance | Update stories.yml reference |
| `modules/AgenticGuidance/agents/planner/epic-creator/process.yml` | Guidance | Update stories.yml reference |
| `.claude/agents/build-story-writer.md` | Guidance | Update stories.yml reference |
| `modules/AgenticCLI/tests/test_stories_audit.py` | Test | Update fixture paths |
| `modules/AgenticCLI/tests/test_planner_loop.py` | Test | Update fixture paths |
| `modules/AgenticCLI/tests/integration/test_planner_loop_e2e.py` | Test | Update fixture paths |
| `docs/stories/` | Directory | New — durable story storage |

## Success Criteria

1. `docs/stories/` directory exists and holds all migrated stories.yml files
2. build-story-writer writes stories to `docs/stories/<epic>/stories.yml`
3. planner_loop reads stories from `docs/stories/<epic>/stories.yml`
4. `agentic stories audit --epic <name>` reads from new location
5. Archiving an epic to `docs/epics/completed/` does NOT move or delete stories
6. Backward-compat fallback reads from old location when new location is empty
7. All existing tests pass with updated paths
8. New test confirms stories survive epic archival

## Open Questions

None — the path change is straightforward and all affected components are identified.
