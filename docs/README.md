# AgenticEngineering Documentation

This folder holds project documentation and the user-story surface for the
AgenticEngineering platform. Epic/ticket/phase state itself lives in **TinyDB**
(`~/.agentic/epics.db`), not on disk — this folder is docs only.

For CLI usage and the meta-orchestration contract, see the top-level
[CLAUDE.md](../CLAUDE.md).

## Modules

| Module | Description |
|--------|-------------|
| **AgenticCLI** | Typer CLI (`agentic` command) — epic, ticket, phase, orchestration, stories, session management |
| **AgenticGuidance** | Agent definitions + domain services (EpicRepository, StoryService, etc.) |
| **AgenticBackend** | Backend services |

## Data Model (TinyDB-only)

Epic state is stored exclusively in TinyDB at `~/.agentic/epics.db`:

- **Epics** — metadata, status (`seed` → `planning` → `in_progress` → `completed`)
- **Phases** — per-epic, each carries `agent` routing + `feedback_triggers`
- **Tickets** — per-epic, tracked by `status` (`proposed` → `pending` → `in_progress` → `completed`)

There are no `plan_*.yml`, no `*.mmd` routing files, and (usually) no disk
epic folder. The `epic_folder` field on an epic is a logical name, not a
required filesystem path.

## Folder Layout

```
docs/
├── README.md              # This file
├── epics/                 # Epic-related markdown (epic.md per live epic)
│   ├── live/              # Active epics (docs only — state is in TinyDB)
│   └── completed/         # Archived epic docs
└── userstories/           # User-story specs grouped by surface
    ├── EpicStories/       # Auto-generated per-epic stories ({folder}.yml)
    ├── Guidance/          # Stories about the guidance system
    ├── Planning/          # Stories about planning pipeline
    ├── Session/           # Stories about session lifecycle
    ├── Setup/             # Stories about install/config
    └── Stories/            # Meta-stories about the story system
```

## Epic Lifecycle

1. **Create** — `agentic epic new "<description>"` → epic appears in TinyDB as `seed`
2. **Plan** — `agentic orchestrate session plan --epic <folder>` → phases + tickets generated, status → `planning`
3. **Implement** — `agentic orchestrate session implement --epic <folder>` → phases executed by routed agents, status → `in_progress`
4. **Complete** — auto-archive when all tickets hit `completed`

See CLAUDE.md for the full command surface.

## Resolving Epics on the CLI

Most commands accept `--epic <folder-or-prefix>`. Resolution rules:

- **Exact match** wins first
- **Unique prefix match** is accepted (e.g. `260411AG` if only one epic starts with it)
- **Ambiguous prefix** is rejected with a list of candidates — use the full folder name

Tip: the full folder name is printed by `agentic epic new` and by
`agentic epic list --json`. Use `--json` when you need the untruncated name
for scripting.

## Orchestration Runs — Monitoring

Orchestration sessions (`plan` / `implement`) are tracked by `session_id`.
To observe a running session:

```bash
# List active and recent sessions with status summary
agentic orchestrate session list

# Health probe for a single session
agentic orchestrate health <session-id>

# Tail the session state / logs
agentic orchestrate debug logs <session-id>
agentic orchestrate debug state show <session-id>
```

Notes:
- During the first ~10s of a foreground run, log files may be empty while the
  SDK cold-starts; a temporary `health: FAIL` is expected until output lands.
- For long runs, prefer `--background` (or `-b`) so the CLI returns immediately
  and the session survives terminal disconnect.

## Budget Defaults

`orchestrate session plan` and `orchestrate session implement` both accept
`--budget <USD>` (default **$50**). Empirical reference points:

- Planning a small epic (single category, ~4 tickets): ~$1–2
- Implementing a single phase (build-python + test-builder pair): ~$1–3
- Full multi-phase epic execution: varies with ticket count; budget generously

The default of $50 is intentionally conservative-high — override downward only
when you know your workload. A too-low budget triggers "budget exhausted" mid-run.

## Navigation

- **CLI usage & meta-orchestration role** — [../CLAUDE.md](../CLAUDE.md)
- **Agent definitions** — `modules/AgenticGuidance/agents/`
- **User stories** — `docs/userstories/`
