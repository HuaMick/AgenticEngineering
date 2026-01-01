# Migration to Nested Sub-repositories (MyAgents)

## Overview
This plan tracks the migration of the MyAgents workspace from a flat directory structure to a nested submodule structure. The goal is to make `MyAgents` the canonical root repository, with all other modules residing in a `projects/` subdirectory.

## Goals
- **Isolation**: Each module remains its own repository (as a submodule).
- **Parallelism**: Enable the use of git worktrees within the nested structure so AI agents can work on different modules/features in parallel.
- **Unified Root**: Consolidate root-level infrastructure (Makefile, Docker, CI/CD) into the parent repository.
- **Clean Workspace**: Use `uv` workspaces to manage dependencies across all nested projects.

## Structure
- `live/`: Active migration plans.
  - `plan_1_structure_setup.yml`: Root consolidation and repository nesting.
  - `plan_2_wiring_config.yml`: Workspace configuration and service integration.
- `completed/`: Finished tasks and phases.
- `results/`: Validation reports and post-migration status.

## Current Status
- Diagnostics completed.
- Planning phase initiated.
- Ready for Phase 1: Root Consolidation.

## Reference
- Original Root: `/home/code/myagents/`
- Target Root: `/home/code/myagents/MyAgents/`
- Projects Dir: `/home/code/myagents/MyAgents/projects/`

