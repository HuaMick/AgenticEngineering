# 260321TI: Fix Flaky Test Isolation in AgenticCLI

## Problem

`test_update_ticket_story_ids_in_text_output` in `test_ticket_story_ids_cli.py` fails intermittently when run in the full test suite but passes consistently in isolation. This is a test-ordering dependency.

## Root Cause Analysis

The test at line 316 relies on `capsys` to capture text output (no `is_json_output` mock). When run after other tests in `TestCmdTaskUpdateStoryIds` that patch `is_json_output`, the mock teardown ordering can leak state. The `_isolate_tinydb` autouse fixture correctly isolates the DB path, but `cmd_task_update` opens its own `_get_repo()` instance — if a prior test's `EpicRepository` still holds a write lock during deferred cleanup, the text-output test can race.

## Additional Issue: Orphaned conftest fixture

The `temp_repo` fixture in `tests/conftest.py` (line 283) still writes a legacy `plan_test.yml` file with the old `plan:` nested YAML structure. Since YAML scanning is eliminated, this file is inert but misleading. Any test using `temp_repo` that expects plan data will find nothing in TinyDB.

## Scope

1. Fix `test_update_ticket_story_ids_in_text_output` — add explicit `is_json_output` mock or ensure proper fixture teardown ordering
2. Update `temp_repo` conftest fixture to populate TinyDB instead of writing legacy YAML
3. Audit other tests for similar TinyDB isolation gaps

## Files

- `modules/AgenticCLI/tests/test_ticket_story_ids_cli.py`
- `modules/AgenticCLI/tests/conftest.py` (temp_repo fixture, lines 283-315)
