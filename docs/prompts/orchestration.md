# Orchestration

Launch an interactive Claude session with orchestration agent context.

## Modes

```bash
agentic orchestrate --mode planning     # Create and approve plans
agentic orchestrate --mode executor     # Execute approved plans via MMD routing
agentic orchestrate --mode friction     # Analyze traces for friction patterns
agentic orchestrate --mode loop         # Full lifecycle: discover, plan, execute, archive
```

## Options

| Flag | Description |
|------|-------------|
| `--mode` | **Required.** Orchestration mode: planning, executor, friction, loop |
| `--plan <folder>` | Scope to a specific plan folder |
| `--role <role>` | Override bootstrap role (defaults to mode) |
| `--prompt-file <path>` | Override the agent process file |
| `--model <model>` | Model to use for the Claude session |

## Agent Profiles

Each mode loads its process file from the agent profile directory:

```
modules/AgenticGuidance/agents/orchestration/
  orchestration-planning/   process.mmd   - planning flowchart
  orchestration-executor/   process.yml   - execution protocol
  orchestration-friction/   process.mmd   - friction analysis workflow
  orchestration-loop/       process.yml   - full lifecycle loop
```

These profiles are the source of truth. This file and the mode-specific
prompts alongside it are quick-reference documentation only.
