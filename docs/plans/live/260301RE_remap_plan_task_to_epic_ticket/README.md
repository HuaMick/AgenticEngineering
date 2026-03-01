# Plan: Remap Plan/Task Terminology to Epic/Ticket

## Objective

Migrate all terminology and structure from the existing plan/task model to align with
industry-standard Jira/Agile conventions, where:
- Planning folders (`docs/plans/live/YYMMDDXX_*/`) become **Epics**
- Individual plan files (`plan_build.yml`, `plan_test.yml`, etc.) become **Tickets** within epics
- Directories rename from `docs/plans/` to `docs/epics/`
- CLI commands migrate from `agentic plan ...` to `agentic epic ...`
- Service classes rename from `PlanService` / `TaskService` to `EpicService` / `TicketService`
- TinyDB tables rename from `plans`/`tasks`/`phases` to `epics`/`tickets`/`phases`

## Scope

This is a full-codebase rename affecting (updated after 5-agent audit):
1. Filesystem structure (`docs/plans/` -> `docs/epics/`)
2. CLI commands and their argparse namespaces
3. Python service layer (5 modules, 30+ classes and functions)
4. Agent guidance YAML files (60+ files across planner/orchestration/test/deploy/build/teacher agents)
5. `.claude/agents/` markdown files (25 files)
6. Asset definitions, guidelines, inputs, and examples (~50 files)
7. Test files (100+ test files across both modules, including conftest.py fixtures)
8. User story YAMLs (~30 files across all modules)
9. Documentation (agents.md, README files, MEMORY.md)
10. TinyDB database schema and bootstrap paths
11. CLI support files: exceptions.py, validation.py, git.py env vars, question_watcher.py, TUI
12. Infrastructure: settings.local.json permissions, .gitignore, pyproject.toml, entrypoint files
13. Orchestration agents: orchestration-friction, orchestration-loop (originally omitted)
14. Parent/hierarchical manifest files across all agent categories

## Plan Files

- `plan_teach.yml` - Phase 1: Teach/Guidance update (20 tasks, ~165 files)
- `plan_build.yml` - Phase 2: Core implementation (20 tasks, ~40 source files)
- `plan_test.yml` - Phase 3: Test validation (15 tasks, ~100 test files)
- `plan_cleaning.yml` - Phase 4: Cleanup (remove deprecated aliases, dead code)
- `plan_uat.yml` - Phase 5: UAT (end-to-end CLI workflow validation)
- `plan_audit_clean.yml` - Phase 6: Plan folder compliance audit

## Backward Compatibility Strategy

During transition, old CLI commands (`agentic plan ...`) will emit deprecation warnings
and redirect to new commands (`agentic epic ...`). The old `docs/plans/` directories
will be git-mv'd to `docs/epics/` as part of a single atomic migration phase.

## Status

Status: planning
Created: 2026-03-01
