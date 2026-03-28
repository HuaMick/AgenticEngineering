# Mandatory Ticket-Story Binding for Build Plans

## Objective

Make `story_ids` a hard requirement on tickets in build-phase epics. Every ticket created under a build plan must link to at least one user story. Enforce this at ticket creation, planning validation, and execution gates.

## Context

Currently `story_ids` on tickets is optional. This means work can be planned and executed without traceability back to user stories, undermining our story-first SDLC. The orchestration executor validates story *coverage* (pytest markers), but there's no upstream enforcement that tickets themselves are linked to stories.

## Scope

1. **Ticket creation enforcement** — `agentic epic ticket add` must require `--story-ids` when the epic is a build plan (not infrastructure/guidance)
2. **Planning validation** — `_validate_planning_output()` in planner_loop.py should fail if build-phase tickets lack `story_ids`
3. **Ticket data model** — Consider whether `story_ids` should be non-optional in the Ticket dataclass for build contexts
4. **Story audit command** — Add `agentic stories audit` to report tickets without stories and stories without tickets
5. **Agent guidance updates** — Update planner-build, epic-creator, and orchestration-executor guidance to enforce story linkage

## Out of Scope

- Changing story schema or lifecycle
- Modifying test coverage enforcement (already strong)
- Infrastructure/guidance epics (these have escape hatches)

## Success Criteria

- No build-phase ticket can be created without story_ids
- Planning validation blocks on tickets missing story linkage
- `agentic stories audit` reports bidirectional coverage gaps
- All existing agent guidance references mandatory story binding
