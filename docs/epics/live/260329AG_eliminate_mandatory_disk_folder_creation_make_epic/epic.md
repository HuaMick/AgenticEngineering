# Eliminate mandatory disk folder creation — make epic creation fully TinyDB-first

## Objective

Remove the mandatory `mkdir` for epic folders in `docs/epics/live/` during epic creation. TinyDB should be the sole requirement for epic existence. Disk folders should only be created lazily when an agent actually needs to write an artifact.

## Context (from trace-explorer friction report)

The intent to make epic creation TinyDB-first was stated across multiple user stories (US-PLN-001, US-PLN-002, US-PLN-053, US-PLN-054) but never fully implemented. Commits `53c58d4`, `c3b1933`, `ce22ca7` moved data to TinyDB but left `epic_path.mkdir()` in place.

### Current disk dependencies

| File on disk | Who writes it | Who reads it | TinyDB alternative |
|---|---|---|---|
| `stories.yml` | build-story-writer | planner_loop.py `_parse_story_categories()` | New `stories` field in TinyDB epic record |
| `README.md` | epic-creator agent | build-story-writer, epic-creator | TinyDB `context` field (already exists) |
| `epic.md` | user/agents | epic-creator (objective source) | TinyDB `context` field |

### Friction points to resolve

1. **FP-001 (HIGH)** — `planner-build/process.yml` FENCE requires disk folder before planning. Contradicts lazy-creation intent.
2. **FP-002 (HIGH)** — `epic-creator` reads README.md from disk as primary objective source; should read TinyDB `context` field.
3. **FP-003 (HIGH)** — `build-story-writer` writes stories.yml to disk — this is WHY the mkdir exists. Must move to TinyDB or lazy-create.
4. **FP-004 (MEDIUM)** — `build-story-writer` reads README.md/objective.md from disk; TinyDB `context` field is ignored.
5. **FP-005 (MEDIUM)** — `planner_loop.py:1455` has TinyDB guard immediately followed by unconditional mkdir.
6. **FP-006 (LOW)** — `cmd_init` output says "Created epic folder" when no folder is created.

## Scope

### Phase 1: Agent guidance updates (teacher-update-guidance)
- Remove planner-build FENCE requiring disk folder
- Update epic-creator process to read objective from `agentic -j epic status` (TinyDB context field)
- Update build-story-writer process to read objective from TinyDB, not disk

### Phase 2: Stories to TinyDB (build-python)
- Add `stories` field to TinyDB epic record schema
- Add `agentic epic stories set/get` CLI commands
- Update build-story-writer to write stories via CLI command instead of disk file
- Update `_parse_story_categories()` in planner_loop.py to read from TinyDB

### Phase 3: Remove mkdir (build-python)
- Remove `epic_path.mkdir()` from `planner_loop.py:1455`
- Add lazy mkdir in `_spawn_and_wait` or agent bootstrap only when Write tool targets epic dir
- Fix `cmd_init` output text

### Phase 4: Test + UAT (test-builder, test-uat)
- Verify `agentic orchestrate session plan` works without pre-existing disk folder
- Verify `agentic orchestrate session implement` works without pre-existing disk folder
- Regression test: existing epics with disk folders still work

## Constraints

- Backward compatible: existing epics with disk folders must continue to work
- stories.yml reading should fall back to disk if TinyDB field is empty (migration path)
- No agent should fail if the disk folder doesn't exist
