# Orchestration Executor

Run the execution phase of an orchestrated plan using a deterministic Python runner.

## Quick Start

```bash
agentic session orchestrate executing
agentic session orchestrate executing --plan <folder>
agentic session orchestrate executing --plan <folder> --background
```

## What It Does

The `executing` subcommand is driven by a **deterministic Python `ExecutionRunner`** in the CLI,
not a meta-LLM agent. It reads the orchestration MMD file, resolves AGENT_ROUTING metadata,
and spawns the appropriate agent for each pending phase sequentially.

1. Discovers plans with completed orchestration planning (has `orchestration_*.mmd`).
2. Parses the MMD header to extract `AGENT_ROUTING` and `STATUS` metadata.
3. Finds the first phase with `pending` status.
4. Spawns the corresponding agent via `agentic session spawn --role <agent> --plan <folder>`.
5. Waits for the agent to complete, then updates the MMD `STATUS` field.
6. Iterates to the next pending phase, or finishes when all phases are complete.
7. Handles `FEEDBACK_TRIGGERS` (e.g., `TEST_FAILURE -> Test`) to re-run failed phases.

## MMD as Source of Truth

The orchestration MMD file is the single source of truth for:

- **Phase ordering** - The `PHASES` header lists execution order
- **Agent routing** - `AGENT_ROUTING` maps each phase to its agent type
- **Phase status** - `STATUS` tracks `pending`, `in_progress`, `completed`, `failed` per phase
- **Feedback triggers** - `FEEDBACK_TRIGGER` defines re-run rules on failure

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

- `agentic session orchestrate planning` - Create and approve plans (generates the MMD)
- Orchestration MMD format: `docs/plans/live/<folder>/orchestration_*.mmd`
