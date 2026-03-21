# Orchestration Executor

Run the execution phase of an orchestrated plan using a deterministic Python runner.

## Quick Start

```bash
agentic orchestrate session implement
agentic orchestrate session implement --plan <folder>
agentic orchestrate session implement --plan <folder> --background
```

## What It Does

The `executing` subcommand is driven by a **deterministic Python `ExecutionRunner`** in the CLI,
not a meta-LLM agent. It reads TinyDB phase records, resolves agent routing,
and spawns the appropriate agent for each pending phase sequentially.

1. Discovers plans with completed orchestration planning (has TinyDB phases with agent routing).
2. Reads TinyDB phase records to extract agent routing and status metadata.
3. Finds the first phase with `pending` status.
4. Spawns the corresponding agent via `agentic orchestrate session spawn --role <agent> --plan <folder>`.
5. Waits for the agent to complete, then updates the TinyDB phase status.
6. Iterates to the next pending phase, or finishes when all phases are complete.
7. Handles `FEEDBACK_TRIGGERS` (e.g., `TEST_FAILURE -> Test`) to re-run failed phases.

## TinyDB as Source of Truth

TinyDB is the single source of truth for:

- **Phase ordering** - Phases listed in insertion/sequence order
- **Agent routing** - `agent` field maps each phase to its agent type
- **Phase status** - `status` tracks `pending`, `in_progress`, `completed`, `failed` per phase
- **Feedback triggers** - `feedback_triggers` field defines re-run rules on failure

## CLI Options

| Option | Description |
|--------|-------------|
| `--plan <folder>` | Scope to a specific plan folder |
| `--background, -b` | Run in background |
| `--max-iterations, -n` | Max iterations (default: 10) |
| `--project, -p` | Project filter |
| `--directory, -d` | Working directory |
| `--dangerously-skip-permissions` | Skip permission prompts for spawned agents |

## See Also

- `agentic orchestrate session plan` - Create and approve plans (creates TinyDB phase records)
- Orchestration phases stored in TinyDB
