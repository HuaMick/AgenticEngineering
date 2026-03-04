# LangSmith CLI Frontend Plan

**Status:** COMPLETE
**Branch:** agentic-cli (merged to main)
**Updated:** 2026-01-23

## Summary

Add LangSmith trace querying commands to the agentic CLI, consuming the AgenticLangSmith backend module.

## Folder Structure

```
260113LS_langsmith_cli/
├── README.md                           # This file
├── completed/
│   └── plan_live_build.yml             # Build plan (all tasks complete)
└── live/
    └── orchestration_langsmith_cli.mmd # Orchestration flowchart (reference)
```

## Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1. CLI Commands | langsmith command group + subcommands | ✅ COMPLETE |
| 2. Dependencies | Add agenticlangsmith to pyproject.toml | ✅ COMPLETE |
| 3. Testing | CLI command tests with mocked backend | ✅ COMPLETE |
| 4. Audit | User acceptance testing | ✅ COMPLETE |

## Commands Implemented

- `agentic langsmith runs` - List recent runs with filtering
- `agentic langsmith run <id>` - Show run details
- `agentic langsmith projects` - List projects
- `agentic langsmith stats` - Show project statistics
- Alias: `agentic ls` = `agentic langsmith`

## Implementation Files

- `modules/AgenticCLI/src/agenticcli/commands/langsmith.py` - Command implementations
- `modules/AgenticCLI/tests/test_langsmith_commands.py` - CLI tests

## Completion Notes

All phases completed. LangSmith CLI commands are functional and integrated with the AgenticLangSmith backend module.
