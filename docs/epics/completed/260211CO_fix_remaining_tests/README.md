# Fix Remaining 11 Test Failures (Typer Migration Residual)

## Objective

Fix 11 remaining test failures across 6 files that are residual issues from the
argparse-to-Typer CLI migration. Tests expect old argparse behaviors (error formats,
help output, exit codes) that differ in the Typer backend.

## Failure Summary

| File | Failures | Root Cause |
|------|----------|------------|
| test_plan.py | 3 | Rich table truncates plan names; task start blocked by missing orchestration_*.mmd; error message changed |
| test_cli_task.py | 2 | Typer doesn't reject invalid --status/--priority values (no choices= constraint) |
| test_agent_help.py | 2 | KNOWN_AGENTS has 24 agents, tests expect 26; orchestration count 3 vs 5 |
| test_cli.py | 1 | Typer help output uses hidden commands for aliases, not "(wt)" epilog format |
| test_entry.py | 1 | entry.py only translates -h when AGENTIC_USE_TYPER=1; test calls main() without it |
| test_workflow_sequences.py | 2 | Scaffold creates flattened structure but tests expect live/completed subdirs |

## Phases

1. **Fix Test Assertions (P1)** - Update test expectations to match actual Typer behavior
2. **Fix Source Constraints (P2)** - Add Typer Enum/callback constraints for --status and --priority validation
3. **Test Verification (P3)** - Run all 6 test files to confirm 0 failures
4. **UAT (P4)** - Validate CLI user stories still hold after changes

## Dependencies

- Typer CLI backend in `modules/AgenticCLI/src/agenticcli/cli.py`
- Agent help registry in `modules/AgenticCLI/src/agenticcli/commands/agent_help.py`
- Entry point in `modules/AgenticCLI/src/agenticcli/entry.py`

## Success Criteria

- All 11 previously failing tests pass
- No regressions in the 105 currently passing tests
- CLI behavior is correct for end users
