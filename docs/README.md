# Documentation

This folder contains project documentation and planning state.

## Structure

```
docs/
├── README.md           # This file
└── plans/              # Planning folders (persistent state)
    ├── live/           # Active work in progress
    └── completed/      # Finished plans (reference)
```

## Plans Folder

Planning folders track work across Claude Code sessions using YAML-based state management.

### Live Plans (`plans/live/`)

Contains active work. Each subfolder follows the naming convention `YYMMDDRepo_Branch`:

| Folder | Description |
|--------|-------------|
| *(empty)* | No active plans - all work completed 2026-01-11 |

Within each planning folder:
- `live/` - Active plan files (`plan_*.yml`)
- `completed/` - Finished tasks moved here
- `analysis/` - Friction analysis and notes (if present)
- `audit/` - Audit reports (if present)

### Completed Plans (`plans/completed/`)

Archived plans for reference:

| Folder | Description |
|--------|-------------|
| `251230AE_main/` | Initial project setup |
| `260102AG_migration/` | Migration work |
| `260103AE_agentic-cli/` | CLI development |
| `260103_AgenticGuidance_dependency-migration/` | Dependency updates |
| `260103_AgenticGuidance_orchestration-planning/` | Orchestration planning |
| `260104AE_agenticguidance/` | AgenticGuidance (completed phases) |
| `260106AE_agenticguidance_remediation/` | Friction remediation |
| `260106AE_friction_improvements/` | Friction improvements |

## Plan File Format

Plan files use YAML with this structure:

```yaml
objective: "What this plan accomplishes"
phases:
  - phase: 1
    name: "Phase description"
    tasks:
      - id: "TASK-001"
        status: pending  # pending | in_progress | complete
        description: "Task description"
```

## Navigation

- **Starting a new task?** Check `plans/live/` for active work context
- **Looking for past decisions?** Browse `plans/completed/` for historical reference
- **Understanding the project?** See the root [README.md](../README.md) for architecture and principles
