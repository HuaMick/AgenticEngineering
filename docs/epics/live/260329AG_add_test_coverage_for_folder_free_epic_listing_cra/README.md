# Epic: Add Test Coverage for Folder-Free Epic Listing Crash Fix

## Objective

Expand test coverage for the folder-free epic listing crash fix (commit c4e830b).
The fix changed `cmd_list` to use `meta.epic_folder_name` (always a string) instead
of `meta.epic_folder.name` (crashes when `epic_folder` is `None` for TinyDB-only epics).

Existing regression tests in `test_epic_list_folder_free.py` cover the basic crash
scenario. This epic adds deeper coverage for:
- Service and repository layer folder-free handling
- `cmd_list` display status normalization with folder-free epics
- `cmd_list` filtering, progress strings, and hint messages
- Edge cases: all-folder-free, multi-phase, error handling
- `cmd_status` JSON output for folder-free epics

## Affected User Stories

- **US-PLN-004**: List All Epics (passing)
- **US-PLN-085**: Epic Listing and Discovery (untested)
- **US-PLN-003**: View Epic Status (untested)
- **US-PLN-082**: Epic CRUD Operations (untested)

## Phases Overview

### Phase 1: Service Layer Tests
Tests for `EpicRepository.list_epics()` and `EpicService.list_epics()/get_epic()`
handling of folder-free epics at the data layer.

### Phase 2: CLI Display Logic Tests
Tests for `cmd_list` display status normalization, `--all` flag filtering,
progress string formatting, and hint messages — all with folder-free epics.

### Phase 3: CLI Edge Cases & cmd_status Tests
Tests for error handling in `cmd_list` when `get_epic()` fails on a folder-free
epic, `cmd_status` JSON output, and multi-phase folder-free scenarios.

### Phase 4: UAT
Run full test suites to verify all new tests pass and no regressions.
Validate against user story acceptance criteria.

## Dependencies and Prerequisites

- Commit c4e830b (folder-free crash fix) must be present
- Commit bed15d3 (folder-free epic init) must be present
- `test_epic_list_folder_free.py` already exists with 8 baseline regression tests
- `conftest.py` has `populate_tinydb_from_yaml()` helper and `_isolate_tinydb` fixture

## Success Criteria

1. All new tests pass (pytest exit code 0)
2. No regressions in existing AgenticCLI or AgenticGuidance test suites
3. Every new test is annotated with `@pytest.mark.story()` referencing affected stories
4. Coverage of `cmd_list` lines 1910-2009 is comprehensive (all branches exercised)
5. Coverage of `EpicRepository.list_epics()` lines 488-492 for empty epic_folder path
6. `cmd_status` folder-free paths tested in both table and JSON output modes
