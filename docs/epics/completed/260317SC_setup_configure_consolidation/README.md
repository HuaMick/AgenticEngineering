# 260317SC: Consolidate Setup & Configure Command Groups

## Problem
The CLI has two overlapping command groups (`setup` and `configure`) with redundant nesting and misclassified commands:
- `configure preferences` and `configure config` both hit the same `preferences.yml` via `ConfigWorkflow` — duplicate APIs
- `configure state` is a process registry (runtime), not configuration — belongs under `session`
- `configure` adds unnecessary nesting depth — `agentic configure config get` vs `agentic config get`
- `setup health` is a diagnostic, not a setup step

## Target State
```
agentic setup init|update|rebuild          # One-time bootstrap ops
agentic health                             # Top-level diagnostic
agentic config show|get|set|list|delete|clear|init|show-path|set-path  # Merged prefs+config
agentic config env show|export|run         # Env stays under config
agentic session state list|show|clear|cleanup  # State moves to session
```

## Key Changes
1. **Merge `preferences` into `config`** — kill duplicate command, keep `prefs` as hidden alias
2. **Promote `config` to top-level** — eliminate `configure` wrapper group
3. **Move `state` to `session`** — it's operational, not configuration
4. **Promote `health` to top-level** — it's a diagnostic you run anytime
5. **Keep `configure` as hidden deprecated alias** for backward compat
6. **Update CLAUDE.md** and agent guidance references

## Scope
- CLI command registration (cli.py)
- Command handlers (preferences.py, config.py, state.py)
- Tests referencing old command paths
- Documentation and agent guidance
