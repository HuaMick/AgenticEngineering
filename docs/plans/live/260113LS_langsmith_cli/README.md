# LangSmith CLI Frontend Plan

**Status:** Approved
**Branch:** agentic-cli
**Worktree:** /home/code/AgenticEngineering-agentic-cli

## Summary

Add LangSmith trace querying commands to the agentic CLI, consuming the AgenticLangSmith backend module.

## Folder Structure

```
260113_langsmith_cli/
├── README.md                           # This file
└── live/
    ├── plan_live_build.yml             # Build plan with phases and tasks
    └── orchestration_langsmith_cli.mmd # Orchestration flowchart
```

## Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1. CLI Commands | langsmith command group + subcommands | Pending |
| 2. Dependencies | Add agenticlangsmith to pyproject.toml | Pending |
| 3. Testing | CLI command tests with mocked backend | Pending |
| 4. Audit | User acceptance testing | Pending |

## Commands to Implement

- `agentic langsmith runs` - List recent runs with filtering
- `agentic langsmith run <id>` - Show run details
- `agentic langsmith projects` - List projects
- `agentic langsmith stats` - Show project statistics
- Alias: `agentic ls` = `agentic langsmith`

## Parallel Execution

This plan can run in parallel with the backend plan:
- **Sibling plan:** `/home/code/AgenticEngineering-agenticlangsmith/docs/plans/live/260113_langsmith_backend`
- **This plan requires:** `agenticlangsmith` package with `LangSmithService` class
- **Mock strategy:** Mock `LangSmithService` during development until backend ready

## Next Steps

Execute with `_orchestrate.yml` entrypoint after approval.
