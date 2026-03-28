# Epic: Fix Story Parsing Race Condition in Planning Pipeline

## Objective

Fix race conditions in the planning pipeline where story files written by the
`build-story-writer` agent (running in a separate tmux pane process) are read by
the orchestrator process before they are fully flushed to disk, causing spurious
"stories.yml missing or invalid" errors. Additionally, harden concurrent TinyDB
access when parallel explore agents write ticket updates from separate processes.

## Affected Stories

- **US-PLN-091**: Planning Pipeline Story Generation
- **US-PLN-053**: Initiate Implementation Planning
- **US-PLN-055**: Specialized Planner Agents
- **US-PLN-057**: Generate Orchestration Phases (TinyDB) from Epic
- **US-STR-012**: Planner-Design Agent Solution Architecture Scaffolding

## Race Conditions Identified

### RC1 (HIGH): stories.yml Write vs. Read — No Filesystem Sync Barrier

- **Location**: `planner_loop.py` lines 1145-1180 and 1457-1472
- **Mechanism**: `build-story-writer` runs in a separate tmux pane. It writes
  `stories.yml` via the Write tool. The orchestrator process immediately reads
  this file via `_parse_story_categories()` after `run_agent_sync()` returns.
  The agent completion signal is a logical signal, not a filesystem sync
  guarantee. The file may be partially written, empty, or not yet visible.
- **Symptoms**: `"stories.yml missing or invalid after build-story-writer completed"`
  or `"stories.yml has no categories"`.
- **Root cause**: No retry logic, no file lock, no fsync barrier between the
  tmux pane write and the orchestrator read. The broad `except Exception`
  swallows parse errors from truncated YAML.

### RC2 (MEDIUM): Parallel Explore Agents Contending on TinyDB

- **Location**: `planner_loop.py` lines 623-680 and `epic_repository.py`
- **Mechanism**: N parallel explore agents each run in their own tmux pane.
  Each creates its own `EpicRepository` instance with its own `FileLock`.
  All contend on `~/.agentic/epics.db.lock`. The 10-second lock timeout
  can cause failures with >3-4 concurrent agents. TinyDB's per-process
  cache means agents don't see each other's writes.
- **Symptoms**: Lock timeout errors; stale reads causing ticket overwrites.

### RC3 (LOW): StoryService Read-Modify-Write Without Locking

- **Location**: `story.py` lines 180-255
- **Mechanism**: `update_lifecycle()` and `update_test_status()` perform
  read-modify-write on `docs/userstories/` YAML files with no file locking.
  Not on the hot planning pipeline path but a latent data corruption risk.

### RC4 (LOW): StoryService.load_all() Non-Atomic Glob + Parse

- **Location**: `story.py` lines 98-114
- **Mechanism**: `glob()` enumerates files while concurrent writes may be
  in progress. `_parse_file()` silently returns `[]` on parse failure.

## Phases Overview

### Phase 1: Fix stories.yml Read Race (RC1)
Add retry-with-backoff to `_parse_story_categories()` so the orchestrator
retries reading stories.yml when the file is missing, empty, or yields
invalid YAML. Add structured error logging instead of swallowing exceptions.

### Phase 2: Harden TinyDB Concurrent Access (RC2)
Increase FileLock timeout for parallel explore scenarios. Add `refresh()`
calls within the explore agent result aggregation path. Consider adding
a TinyDB cache invalidation mechanism for cross-process writes.

### Phase 3: Add File Locking to StoryService Writes (RC3 + RC4)
Add FileLock to `update_lifecycle()` and `update_test_status()` in
`StoryService`. Make `_parse_file()` log warnings instead of silently
returning empty lists.

### Phase 4: Tests
Unit and integration tests for all fixes. Test the retry logic, concurrent
TinyDB access, and StoryService locking.

### Phase 5: UAT
Validate that the planning pipeline completes end-to-end without story
parsing failures, anchored to affected user stories.

## Dependencies and Prerequisites

- `modules/AgenticCLI/src/agenticcli/workflows/planner_loop.py` — primary fix target
- `modules/AgenticGuidance/src/agenticguidance/services/epic_repository.py` — TinyDB locking
- `modules/AgenticGuidance/src/agenticguidance/services/story.py` — StoryService hardening
- `modules/AgenticGuidance/src/agenticguidance/services/state.py` — FileLock infrastructure
- Existing test suites in both AgenticCLI and AgenticGuidance modules

## Success Criteria

1. `_parse_story_categories()` retries up to 3 times with exponential backoff
   before returning None — eliminates transient "stories.yml missing" errors.
2. Parallel explore agents (up to 6 concurrent) do not hit FileLock timeouts
   under normal conditions.
3. `StoryService.update_lifecycle()` and `update_test_status()` use FileLock
   for atomic read-modify-write.
4. `_parse_file()` logs warnings on parse failure instead of silently returning [].
5. All existing tests continue to pass (AgenticCLI + AgenticGuidance).
6. New tests cover: retry logic, concurrent TinyDB writes, StoryService locking.
7. Planning pipeline UAT completes without story-related race condition errors.

## Impacted Artifacts

| Artifact | Type | Impact |
|----------|------|--------|
| `planner_loop.py` | Workflow | Retry logic in `_parse_story_categories()` |
| `epic_repository.py` | Service | Increased lock timeout, refresh patterns |
| `story.py` | Service | FileLock for write operations, parse error logging |
| `state.py` | Infrastructure | Possible FileLock timeout parameter changes |

## Open Questions

None — all race conditions are well-characterized with clear fix paths.
