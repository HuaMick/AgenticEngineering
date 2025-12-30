# Staging Planning: Pre-Deployment Testing Log (MAG)

This directory is a permanent fixture for staging-level planning and pre-deployment testing logs for the `MyAgentsGuidance` (MAG) project. It serves as the single source of truth for the state of the `staging` worktree before it is promoted to `main`.

## Purpose
- **Pre-Deployment Validation**: Track UAT results, integration test status, and manual verification logs.
- **Permanent History**: Unlike date-prefixed feature plans, this folder remains constant, with logs archived or rotated as needed.
- **Orchestration Entrypoint**: The `live/plan_live_teach.yml` file defines the standard pre-deployment testing workflow.

## Structure
- `live/`: Contains the active execution plan for the current staging cycle.
- `logs/pre-deployment/`: Historical record of test runs, agent logs, and environment states.
- `results/`: Aggregated reports, gap analyses, and final validation sign-offs.
