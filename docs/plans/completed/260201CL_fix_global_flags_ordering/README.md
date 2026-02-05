# Plan: Fix Global Flags Positioning in Agentic CLI

**Plan ID:** 260201CL
**Status:** Active
**Type:** Implementation
**Branch:** `fix-global-flags`
**Worktree:** `/home/code/AgenticEngineering-agentic-cli`
**Created:** 2026-02-01

## Problem Statement

The `agentic` CLI uses `argparse` for argument parsing. Currently, global flags like `--json` (`-j`) and `--debug` (`-d`) are only recognized if they appear *before* the subcommand. 

For example:
- `agentic -j plan list` (Works)
- `agentic plan list -j` (Fails with "unrecognized arguments: -j")

This causes friction for automated agents that frequently append flags like `-j` to the end of commands.

## Context

The `agentic CLI` has a deep hierarchy of subparsers (over 100). The global flags are defined on the top-level parser but are not inherited or accepted by subparsers.

## Objectives

1.  Enable global flags (`--json`, `--debug`, `--version`) to be accepted at any position in the command line.
2.  Ensure no conflicts arise with existing subcommand flags (e.g., `-d` is used for `--description` and `--directory` in some commands).
3.  Maintain compatibility with existing command structures.

## Plan Structure

```
260201CL_fix_global_flags_ordering/
├── README.md           # This file
├── plan_build.yml      # Implementation tasks
└── plan_test.yml       # Verification tasks
```

## Success Criteria

- [ ] `agentic plan list -j` returns JSON output.
- [ ] `agentic context bootstrap --role orchestration-executor -j` returns JSON output.
- [ ] `agentic plan init branch -d "Description"` still works (no conflict with global `-d`).
- [ ] `agentic session spawn -p "Prompt" -j` works and outputs JSON.
- [ ] Help output (`--help`) still correctly describes the flags.

## Implementation Strategy

1.  **Shared Parent Parser:** Create a shared parent parser that defines global flags.
2.  **Recursive Injection:** Modify `cli.py` to pass this parent parser to all `add_parser` calls for subparsers.
3.  **Conflict Resolution:**
    -   Flags like `--json`/`-j` are unique and can be added safely.
    -   Flags like `--debug`/`-d` conflict with `--description` and `--directory`. 
    -   Strategy: Only allow the long form `--debug` in subparsers where `-d` is taken, OR use a custom `ArgumentParser` that handles global flags by pre-parsing them.
    -   Best approach: Use a wrapper for `add_parser` that automatically adds the global flags unless they conflict.

## Next Steps

1.  Audit all commands for `-j`, `-d`, `-v` usage.
2.  Implement the shared parser and wrapper in `modules/AgenticCLI/src/agenticcli/cli.py`.
3.  Verify with test cases in `plan_test.yml`.
