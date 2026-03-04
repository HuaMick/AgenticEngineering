# Plan: Fix LangSmith Stop Hook JQ Errors

## Overview
The LangSmith stop hook script (`~/.claude/hooks/stop_hook.sh`) is currently failing with a `jq` error: `object and array cannot be added`. This happens during trace generation when session data is being processed, likely due to improper JSON concatenation using `input + [input]` in bash pipelines.

## Problem Statement
The current implementation uses `printf "%s\n%s" "$current_state" "$new_data" | jq -n 'input + [input]'` to append items to JSON arrays. This pattern is fragile:
1. If the input is not a single valid JSON value (e.g., prettified multi-line JSON), `input` may not read the whole structure correctly.
2. If `new_data` is an empty array `[]`, `[input]` becomes `[[]]`, leading to `object + array` errors if the base was an object, or nested arrays if it was an array.
3. The truncation of `jq` error messages makes it clear that objects containing `parent_run_id` (truncated to `parentUui`) are involved.

## Proposed Fix
1. Refactor JSON concatenation to use `jq -s` (slurp) and `add` correctly, or use `--argjson` where appropriate.
2. Ensure every item being added to an array is itself wrapped in an array if it's an object, or added directly if it's an array.
3. Improve error handling in the script to provide better context when `jq` fails.
4. Use temporary files for large JSON payloads to avoid `Argument list too long` errors in shells.

## Plan Files
- `plan_build.yml`: Implementation steps to fix the script
- `plan_test.yml`: Verification and regression testing
- `plan_completed.yml`: Completion tracking

## Success Criteria
- Stop hook completes without `jq` errors.
- Traces are correctly sent to LangSmith.
- Large traces are handled without "Argument list too long" errors.
- Script is more robust against malformed transcript lines.
