# AgenticEngineering Documentation

This folder contains project documentation and planning state for the AgenticEngineering system.

## System Overview

AgenticEngineering is an agentic development platform with the following modules:

| Module | Description |
|--------|-------------|
| **AgenticGuidance** | 24 active agents organized in 6 categories: orchestration, planner, build, test, teacher, deploy |
| **AgenticCLI** | Command-line interface with epic, context, session, loop, worktree, entrypoint commands |
| **AgenticBackend** | Backend services |

## Key Concepts

- **CCI (CLI Context Injection)**: Agents bootstrap context via CLI commands instead of static file loading
- **Main-First Planning**: Epics created in main worktree for visibility before execution
- **Plan-MMD**: Mermaid flowcharts with AGENT_ROUTING metadata for dynamic agent routing
- **Reference Layer Architecture**: Shared inputs.yml layers for context minimization

## Workflow

### 1. Planning Phase
```
_plan_build.yml or _plan_teach.yml -> orchestration-planning -> approved plan
```

### 2. Execution Phase
```
_orchestrate.yml -> orchestration-executor -> dynamic agent routing from MMD
```

## Structure

```
docs/
├── README.md           # This file
└── epics/              # Epic folders (persistent state)
    ├── live/           # Active work in progress
    └── completed/      # Finished epics (reference)
```

## Epics Folder

Epic folders track work across Claude Code sessions using YAML-based state management.

### Live Epics (`epics/live/`)

Contains active work in progress. Each subfolder follows the naming convention `YYMMDDXX_Description` (e.g., `260104AE_agenticguidance`), where `XX` is the Worktree Identifier (e.g., `AE` for AgenticEngineering).

Example folder structure (when active work exists):
```
epics/live/
└── YYMMDDXX_Description/   # e.g., 260104AE_agenticguidance (XX=AE triggers worktree association)
    ├── plan_*.yml          # Active epic files
    └── completed/          # Finished tickets within this epic
```

### Completed Epics (`epics/completed/`)

Archived epics for reference. Epics are moved here when finished.

## Epic File Format

Epic files use YAML with this structure:

```yaml
name: plan-name-kebab-case
status: pending  # pending | in_progress | completed | removed
priority: high   # high | medium | low
created: "YYYY-MM-DD"
phase_type: build  # build | test | teach | deploy

objective: |
  What this epic accomplishes and why.

context: |
  Background information and constraints.

phases:
  - name: "Phase Name"
    status: pending
    description: "Phase description"
    tasks:
      - id: "task_001"
        name: "Ticket name"
        status: "pending"  # pending | in_progress | completed
        description: "Ticket description"
```

## Navigation

- **Starting a new ticket?** Check `epics/live/` for active work context
- **Looking for past decisions?** Browse `epics/completed/` for historical reference
- **Understanding the project?** See the root [README.md](../README.md) for architecture and principles
