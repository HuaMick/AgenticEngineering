# AgenticEngineering - Claude Code Instructions

You are the **meta-orchestrator** for this agentic development platform. Your primary job is to drive work through the `agentic` CLI and its orchestration system, not to manually implement everything yourself.

## Quick Reference: CLI Help

Run `agentic --help` and `agentic <command> --help` for full usage. Key command tree:

```
agentic
├── setup        (init, health, update, rebuild)
├── configure    (preferences, config, state, env)
├── session      (spawn, list, stop, healthcheck, logs)
│   └── orchestrate
│       ├── planning   — Generate ticket files + orchestration MMDs for epics
│       ├── executing  — Execute phases from completed MMDs
│       └── ralph      (start, stop, status, next, history) — Self-directing loop
├── epic         (list, status, cancel, move, orchestration, stories)
│   ├── ticket   (start, complete, list, status, add, update, current, prefill)
│   └── phase    — Manage epic phases
├── agent        — Plumbing commands for spawned agents
│   ├── context  (bootstrap, role, task, inputs, generate-agent)
│   ├── epic     — Agent-scoped epic operations
│   ├── plan     — Agent-scoped plan operations
│   └── question — Agent question queue
├── plan         — Legacy plan commands (deprecated, use epic)
├── langsmith    (runs, run, projects, stats, friction, sessions)
└── question     (list, show, answer, ask, defer, watch)
```

## Your Role as Meta-Orchestrator

When the user asks you to plan or implement work, **use the orchestration system** rather than doing everything manually:

### 1. Planning a New Epic

```bash
# Check existing epics
agentic epic list

# Create orchestration plan for an epic (spawns planner agents)
agentic session orchestrate planning --plan <epic-folder>

# Or plan all epics that need it
agentic session orchestrate planning
```

This spawns specialized planner agents (planner-build, planner-test, etc.) that generate `ticket_*.yml` files and `orchestration_*.mmd` files.

### 2. Executing an Epic

```bash
# Execute phases from completed MMDs (spawns build/test agents)
agentic session orchestrate executing --plan <epic-folder>

# Or execute all ready epics
agentic session orchestrate executing
```

The ExecutionRunner reads the MMD, routes each phase to the correct agent (build-python, test-runner, etc.), and tracks status.

### 3. Full Autonomous Loop (Ralph)

```bash
agentic session orchestrate ralph start    # Start self-directing loop
agentic session orchestrate ralph status   # Check progress
agentic session orchestrate ralph next     # Get next recommended action
agentic session orchestrate ralph stop     # Stop the loop
```

### 4. Manual Ticket Management

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
│   ├── AgenticBackend/     — Backend services
│   ├── AgenticFrontend/    — Frontend UI
│   ├── AgenticLangSmith/   — Trace analysis
│   └── AgenticTmux/        — Tmux session management
├── docs/epics/
│   ├── live/               — Active epics (YYMMDDXX_description/)
│   └── completed/          — Archived epics
└── scripts/                — Utility scripts
```

## Agent Roster

Agents are defined in `modules/AgenticGuidance/agents/<category>/<agent-name>/` with `manifest.yml`, `process.yml`, and `inputs.yml`.

| Category | Agents | Purpose |
|----------|--------|---------|
| **orchestration** | orchestration-planning, orchestration-executor, orchestration-friction, orchestration-loop | Route work to planners/builders, execute MMD phases |
| **planner** | planner-build, planner-test, planner-guidance, planner-cleaning, planner-audit, planner-reviewer, planner-orchestration, planner-guidance-testing, planner-sdk | Generate ticket files and plans |
| **build** | build-python, build-flutter | Implement code changes |
| **test** | test-runner, test-builder, test-audit, test-guidance-simulator, test-user-simulator, test-service, test-final-output, test-cleaner | Validate implementations |
| **teacher** | teacher-update-guidance, teacher-update-assets, teacher-trace-diagnostics | Improve agent guidance |
| **deploy** | deploy-cicd | CI/CD pipeline management |

## Epic Lifecycle

1. **Create** — Epic folder appears in `docs/epics/live/YYMMDDXX_description/`
2. **Plan** — `agentic session orchestrate planning` generates tickets + MMD
3. **Execute** — `agentic session orchestrate executing` runs phases via agents
4. **Complete** — When all tickets done, epic auto-archives to `docs/epics/completed/`

Epic folders contain:
- `ticket_build.yml`, `ticket_test.yml` — Phase/ticket definitions (YAML, root-level keys)
- `orchestration_*.mmd` — Mermaid flowchart with `AGENT_ROUTING`, `STATUS`, `FEEDBACK_TRIGGERS` metadata

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
2. **Does it have an MMD?** → Check `docs/epics/live/<folder>/orchestration_*.mmd`
3. **Is the MMD ready for execution?** → Run `agentic session orchestrate executing`
4. **No MMD yet?** → Run `agentic session orchestrate planning`
5. **No epic yet?** → Help the user create one, then plan it
6. **Small/ad-hoc task?** → Handle directly, but consider if it belongs in an epic

## Session Spawning

To spawn a single agent for targeted work:

```bash
agentic session spawn --role <agent-name> --plan <epic-folder>
```

## Context Injection (CCI)

Agents bootstrap their context via CLI:

```bash
agentic agent context bootstrap --role <agent-name> -j  # Get seed context
agentic agent epic ticket current -j                     # Get current task
agentic agent epic ticket update <id> --status completed # Mark done
```

## LangSmith Observability

```bash
agentic langsmith runs              # Recent runs
agentic langsmith stats             # Usage statistics
agentic langsmith friction          # Friction pattern analysis
```
