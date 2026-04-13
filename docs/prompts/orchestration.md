# Orchestration

Launch an interactive Claude session with orchestration agent context.

## Modes

```bash
agentic orchestrate session plan     # Create and approve plans
agentic orchestrate session implement # Execute approved plans via agent routing
agentic orchestrate session spawn    # Spawn a single agent session
agentic orchestrate session list     # List active sessions
agentic orchestrate session stop     # Stop a running session
agentic orchestrate health           # Session health check
agentic orchestrate debug logs       # Session logs
agentic orchestrate debug state      # State inspection
```

## Options

| Flag | Description |
|------|-------------|
| `--plan <folder>` | Scope to a specific plan folder |
| `--role <role>` | Override bootstrap role |
| `--prompt-file <path>` | Override the agent process file |
| `--model <model>` | Model to use for the Claude session |

## Agent Profiles

Each mode loads its process file from the agent profile directory:

```
modules/AgenticGuidance/agents/orchestration/
  orchestration-planning/   process.yml   - planning process
  orchestration-executor/   process.yml   - execution protocol
```

These profiles are the source of truth. This file and the mode-specific
prompts alongside it are quick-reference documentation only.
