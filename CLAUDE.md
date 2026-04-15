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

The ExecutionRunner reads TinyDB phases, routes each to the correct agent (build-python, test-builder, etc.), and tracks status.

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
| **orchestration** | orchestration-planning, orchestration-executor | Route work to planners/builders, execute TinyDB phases |
| **planner** | epic-creator, planner-audit, planner-build, planner-orchestration, planner-test | Generate ticket files and plans |
| **build** | build-python, build-flutter, build-story-writer, build-docs-writer | Implement code changes |
| **test** | test-builder, test-audit, test-uat, trace-explorer | Validate implementations |
| **teacher** | teacher-update-guidance, teacher-update-assets | Improve agent guidance |
| **deploy** | deploy-cicd | CI/CD pipeline management |

## Epic Lifecycle

1. **Create** — Epic folder appears in `docs/epics/live/YYMMDDXX_description/`
2. **Plan** — `agentic orchestrate session plan` generates tickets + phases in TinyDB
3. **Execute** — `agentic orchestrate session implement` runs phases via agents
4. **Complete** — When all tickets done, epic auto-archives to `docs/epics/completed/`

Epic folders contain:
- `epic.md` — Epic description and context (phases/tickets are in TinyDB)

## Key Conventions

- **Python**: Use `python3` (not `python`)
- **Tests**: `pytest` with `tmp_path`, `monkeypatch`, mock subprocess
- **Services**: Domain → Workflow → Entrypoint pattern
- **TinyDB is the sole** data store for epics, tickets, and phases
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

## Using Your Own Agents (Fallback Orchestration)

When the SDK orchestration path is broken or you're told to "use your own agents", assume the orchestrator persona directly:

### For planning:
Read `.claude/agents/orchestration-planning.md` and its process file at
`modules/AgenticGuidance/agents/orchestration/orchestration-planning/process.yml`.
Follow that process: create epic, spawn planner subagents, validate, produce TinyDB phases.

### For execution:
Read `.claude/agents/orchestration-executor.md` and its process file at
`modules/AgenticGuidance/agents/orchestration/orchestration-executor/process.yml`.
Follow that process: read TinyDB phases, spawn builder/tester subagents per phase.agent field.

### Key distinction:
- You ARE the orchestrator — don't delegate orchestration to a subagent
- Spawn downstream agents (planner-build, test-builder, etc.) as subagents via the Agent tool
- Use `agentic epic ticket start/complete` to track progress through TinyDB

## Implementation Tracking (IMPORTANT)

When you implement work — whether from a plan, a user request, or your own initiative — **always track progress against the epic system**. This applies to manual implementation, not just orchestrated sessions.

### Before starting implementation:

1. Run `agentic epic list` to check for relevant epics
2. If a matching epic exists, run `agentic epic ticket list --epic <folder>` to see its tickets
3. If no epic exists for non-trivial work, create one:
   ```bash
   agentic epic new "<description>"
   ```

### While implementing:

1. **Get your current ticket**: `agentic epic ticket current --epic <folder> -j`
2. **Mark it started**: `agentic epic ticket start <id> --epic <folder>`
3. Implement the work described in the ticket
4. **Mark it complete**: `agentic epic ticket complete <id> --epic <folder>`
5. Move to the next ticket and repeat

### After plan mode:

When you exit plan mode with an approved plan, **bridge it into the epic system**:

1. Create an epic: `agentic epic new "<plan summary>"`
2. Add tickets for each plan step:
   ```bash
   agentic epic ticket add --epic <folder> --title "<step>" --description "<details>"
   ```
3. Add a phase to group the tickets:
   ```bash
   agentic epic phase add --epic <folder> --name "<phase>" --agent build-python
   ```
4. Then implement by working through tickets sequentially, marking each started/completed

### Key principle:

The epic system is the **source of truth for work status**. If you do work without tracking it, the user loses visibility. Always prefer updating tickets over silently completing tasks.

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
