# 260207TA: CLI Task Spawn

## Objective
Add `--task <task_id>` flag to `agentic session spawn` command for task-level parallel execution.

## Context
Enables orchestration executor to spawn agents for specific tasks rather than just by role, allowing parallel execution of non-conflicting tasks within a single plan.

## Key Changes
- New `--task` argument on `agentic session spawn`
- Task context loading from plan YAML
- Mutual exclusion with `--role` flag

## Execution Order
This plan should execute **BEFORE** 260207SC_guidance_file_scoping, since the guidance plan references the `--task` CLI flag.

## Files
- `plan_build.yml` - Implementation tasks
- `plan_test.yml` - Test strategy (scaffolded)

## Worktree
`/home/code/AgenticEngineering-session-spawn-task`

## Status
**Active** - Ready for execution
