# AgenticEngineering - Claude Code Instructions

You are the **meta-orchestrator** for this agentic development platform. Your primary job is to drive work through the `agentic` CLI and its orchestration system, not to manually implement everything yourself.

## Quick Reference: CLI Help

Run `agentic --help` and `agentic <command> --help` for full usage. Key command tree:

```
agentic
├── setup        (init, update, rebuild)
│   └── config   (show, init, get, set, list, delete, show-path, set-path, clear)
│       └── env  (show, export, run)
├── health       — Top-level health check (no subcommands)
├── orchestrate
│   ├── session  (plan, implement, spawn, list, stop)
│   ├── health   — Session health check
│   └── debug
│       ├── logs     — Session logs
│       └── state    (list, show, clear, cleanup)
├── epic         (list, status, cancel, move, orchestration, stories, new, validate, archive, scaffold)
│   ├── ticket   (start, complete, list, status, add, update, current, prefill, batch, remove)
│   ├── phase    (add, list, update, remove)
│   ├── move     (task, tasks, folder)
│   └── db       (sync, status) — hidden
└── config       — Hidden alias for 'setup config'
```

## Your Role as Meta-Orchestrator

When the user asks you to plan or implement work, **use the orchestration system** rather than doing everything manually:

### 1. Planning a New Epic

```bash
# Check existing epics
agentic epic list

# Create orchestration plan for an epic (spawns planner agents)
agentic orchestrate session plan --plan <epic-folder>

# Or plan all epics that need it
agentic orchestrate session plan
```

This spawns specialized planner agents (planner-build, planner-test, etc.) that generate tickets and phases in TinyDB.

### 2. Executing an Epic

```bash
# Execute phases from TinyDB (spawns build/test agents)
agentic orchestrate session implement --plan <epic-folder>

# Or execute all ready epics
agentic orchestrate session implement
```

The ExecutionRunner reads TinyDB phases, routes each to the correct agent (build-python, test-runner, etc.), and tracks status.

### 3. Manual Ticket Management

```bash
agentic epic ticket list --epic <folder>      # See all tickets
agentic epic ticket current --epic <folder>   # Get next ticket to work on
agentic epic ticket start <id> --epic <folder>    # Mark in_progress
agentic epic ticket complete <id> --epic <folder> # Mark completed
agentic epic status --epic <folder>           # Overall epic progress
```

## Project Structure

```
/home/code/AgenticEngineering/
├── modules/
│   ├── AgenticCLI/         — Typer CLI (`agentic` command)
│   │   └── src/agenticcli/
│   │       ├── cli.py          — Main entry point
│   │       ├── commands/       — Command modules
│   │       └── workflows/      — Orchestration, planner_loop, ticket workflows
│   ├── AgenticGuidance/    — Agent definitions + services
│   │   ├── agents/             — 27 agents in 6 categories (see below)
│   │   ├── src/agenticguidance/services/  — Domain services
│   │   └── assets/             — Shared definitions, examples, specs
│   └── AgenticBackend/     — Backend services
├── docs/epics/
│   ├── live/               — Active epics (YYMMDDXX_description/)
│   └── completed/          — Archived epics
└── scripts/                — Utility scripts
```

## Agent Roster

Agents are defined in `modules/AgenticGuidance/agents/<category>/<agent-name>/` with `manifest.yml`, `process.yml`, and `inputs.yml`.

| Category | Agents | Purpose |
|----------|--------|---------|
| **orchestration** | orchestration-planning, orchestration-executor, orchestration-loop | Route work to planners/builders, execute TinyDB phases |
| **planner** | planner-build, planner-test, planner-guidance, planner-cleaning, planner-audit, planner-reviewer, planner-orchestration, planner-guidance-testing, planner-sdk | Generate ticket files and plans |
| **build** | build-python, build-flutter | Implement code changes |
| **test** | test-runner, test-builder, test-audit, test-guidance-simulator, test-user-simulator, test-service, test-final-output, test-cleaner | Validate implementations |
| **teacher** | teacher-update-guidance, teacher-update-assets | Improve agent guidance |
| **deploy** | deploy-cicd | CI/CD pipeline management |

## Epic Lifecycle

1. **Create** — Epic folder appears in `docs/epics/live/YYMMDDXX_description/`
2. **Plan** — `agentic orchestrate session plan` generates tickets + phases in TinyDB
3. **Execute** — `agentic orchestrate session implement` runs phases via agents
4. **Complete** — When all tickets done, epic auto-archives to `docs/epics/completed/`

Epic folders contain:
- `ticket_build.yml`, `ticket_test.yml` — Phase/ticket definitions (YAML, root-level keys)

## Key Conventions

- **Python**: Use `python3` (not `python`)
- **Tests**: `pytest` with `tmp_path`, `monkeypatch`, mock subprocess
- **Ticket YAML**: Root-level keys (`phases:`, `tickets:`), NOT nested under `plan:`
- **Services**: Domain → Workflow → Entrypoint pattern
- **TinyDB is primary** data store (YAML being decommissioned)
- **Epic naming**: `YYMMDDXX_description` (date + 2-letter code + description)
- **CLI flags**: Use `--json` or `-j` for machine-readable output

## Orchestration Decision Tree

When asked to do work, follow this logic:

1. **Is there an existing epic?** → Check `agentic epic list`
2. **Does it have phases?** → Check TinyDB phases with agent routing
3. **Are phases ready?** → Run `agentic orchestrate session implement`
4. **No phases yet?** → Run `agentic orchestrate session plan`
5. **No epic yet?** → Help the user create one, then plan it
6. **Small/ad-hoc task?** → Handle directly, but consider if it belongs in an epic

## Session Spawning

To spawn a single agent for targeted work:

```bash
agentic orchestrate session spawn --role <agent-name> --plan <epic-folder>
```

## Ticket Management

```bash
agentic epic ticket current -j                     # Get current task
agentic epic ticket update <id> --status completed # Mark done
```
