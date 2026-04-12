# _fixtures — UAT-only deterministic fixture agents

This directory contains **test harness agents** that are spawned by UAT
journeys to exercise specific orchestration paths. They are **not production
agents** and must never be routed by a planner or executor in a real epic.

## Agents

| Name | Purpose | Target path |
|---|---|---|
| `fixture-crash-fast` | Exits non-zero immediately with a fixed stderr line | crash-fast branch in `planner_loop.py` |
| `fixture-hang-long` | Blocks silently; role timeout is 5 s | stall detection / `wait_for_session()` timeout path |
| `fixture-slow-steady` | Emits 12 heartbeats over 60 s then exits 0 | pane-log capture truncation (FIX-004) |

## Guardrails

1. **Excluded from valid agent roster** — `get_valid_agent_types()` in
   `modules/AgenticCLI/src/agenticcli/commands/epic.py` skips any category
   directory whose name starts with `_`. This means fixture agents cannot be
   assigned to a production epic phase via `agentic epic phase add --agent`.

2. **`excluded_from_roster: true`** is set in `agent-categories.yml` for the
   `_fixtures` category.

3. **`uat_only: true`** is set in every fixture `manifest.yml`.

## Determinism mechanism

Fixtures work by giving Claude a tightly-constrained process.yml prompt that
instructs it to run a single Bash command and do nothing else. The prompts are
written to be unambiguous; the LLM has no decision space. If a fixture ever
behaves non-deterministically the UAT should be treated as a framework bug.

## UAT routing workaround

Since `agentic epic phase add --agent fixture-*` is rejected by the production
roster validation, UAT journeys must use a two-step workaround:

```bash
# Step 1: add phase with any valid agent
agentic epic phase add --epic <folder> --id P2 --name Crash --agent build-python

# Step 2: override the agent field directly
agentic epic phase update Crash --epic <folder> --agent fixture-crash-fast
```

`phase update --agent` bypasses the roster check, allowing fixtures to be
routed for UAT purposes only.

**Note**: fixture agents require a live Claude SDK connection to execute their
constrained process.yml prompts. Without SDK, the pane runner times out at the
SDK query level before the fixture's bash command runs.

## Adding new fixtures

1. Create `agents/_fixtures/<fixture-name>/manifest.yml` with `uat_only: true`
   and `category: _fixtures`.
2. Create `agents/_fixtures/<fixture-name>/process.yml` with a single FIXTURE
   INSTRUCTION step.
3. Add a `ROLE_TIMEOUT_SECONDS` entry in
   `modules/AgenticCLI/src/agenticcli/utils/sdk_runner.py`.
4. Document the new fixture in the table above.
