# 260207SC: Guidance File Scoping

## Objective
Update agent guidance to use task-level `target_files` exclusively, deprecating plan-level `impacted_files`.

## Context
Simplifies the file scoping model:
- **Task-level `target_files`** = sole mechanism for parallelization decisions
- **Plan-level `impacted_files`** = deprecated (redundant)
- **Plan-level `impacted_artifacts`** = kept for semantic metadata

## Key Changes
1. Mark `impacted_files` as deprecated in `plan-schema.yml`
2. Remove from `plan_example.yml`
3. Update `planner-build` to stop generating it
4. Update `orchestration-executor` spec for task-level parallelism

## Dependencies
- Requires **260207TA_cli_task_spawn** to be completed first (references `--task` flag)

## Files
- `plan_build.yml` - Guidance update tasks (marked as teach phase work)
- `plan_teach.yml` - Teaching strategy (scaffolded)

## Worktree
`/home/code/AgenticEngineering-task-level-scoping`

## Status
**Active** - Blocked on 260207TA completion
