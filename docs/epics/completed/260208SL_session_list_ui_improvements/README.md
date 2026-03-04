# Session List UI Improvements

**Plan ID**: 260208SL  
**Status**: Active  
**Created**: 2026-02-08

## Objective

Improve the `agentic session list` command UI to reduce clutter and provide more useful information.

## Current Issues

1. **Too many completed sessions** - The list is polluted with old completed/stopped sessions
2. **Columns are truncated** - Hard to read session IDs and status
3. **No description** - Each session has no prompt/description shown

## Proposed Improvements

- Add `--active` / `--running` flag to filter to only running sessions (default behavior)
- Add `--all` flag to show all sessions including completed
- Add description column (first N chars of prompt)
- Improve column widths for readability
- Add session age (e.g., "2h ago")
- Consider grouping by status or date

## Files to Modify

- `modules/AgenticCLI/src/agenticcli/commands/session.py`
- `modules/AgenticCLI/tests/test_session.py`
