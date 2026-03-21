# Decommission Plan Command

## Objective
Fully remove the `agentic plan` command tree and `agentic agent plan` command tree from the CLI. The plan commands were replaced by `agentic epic` but ~50+ dead Typer registrations remain in cli.py routing to a handle() that just errors.

## Scope

### 1. Remove plan command tree from cli.py
- Delete `plan_app` Typer and all its subcommands (task, phase, move, orchestration, stories, db)
- Delete `agent_plan_app` Typer and all its subcommands
- Remove `_plan_handle` helper and `_ns` if only used by plan
- Remove "plan" from `PROJECT_COMMANDS` set

### 2. Stub out helper functions still imported by production code
- `find_plan_folder()` in question.py:210 — stub it to print "not working right now" and return/exit
- `has_pending_questions()` in session.py:862 — stub it to always return False
- These are temporary until the question module is revisited

### 3. Clean up plan.py module
- Remove `handle()` function (no longer called)
- Keep `get_valid_agent_types()` and `get_valid_loop_types()` if they have non-test consumers, otherwise move to test fixtures or delete
- Rename module to `plan_utils.py` if keeping helpers, or inline them where used

### 4. Clean up tests
- Remove/update tests that import from plan.py for removed functions
- Update tests that test plan CLI commands (they should be deleted, not just updated)

## Constraints
- Do NOT touch the `agentic epic` commands — those are the replacement and working fine
- The question module (`commands/question.py`) is known-broken; just stub `find_plan_folder` usage there
- `get_valid_agent_types()` and `get_valid_loop_types()` may still be needed by orchestration code — check before removing
