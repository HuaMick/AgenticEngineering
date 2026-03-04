# Plan: Auto-Archive Planning Folders

**Plan ID**: `260129CL_auto_archive_plans`  
**Status**: Planning / Ready for Implementation

## Overview
Currently, planning folders must be manually moved from `docs/plans/live` to `docs/plans/completed` using the `agentic plan move folder` command. This creates noise in agent sessions (like Claude's resume list) because completed plans stay "live" indefinitely.

This plan implements automatic archival: when the last task in a plan is marked as `completed`, the CLI will automatically trigger the archival process.

## Key Features
1.  **Automatic Move**: Hook into `task complete` and `task update` commands.
2.  **Safety First**: Ensure archival only happens if *all* tasks across *all* files in the plan are done.
3.  **Easy Reversal**: Implement an `unarchive` command to bring plans back to `live/` if needed.
4.  **Suppression**: Add a flag to prevent auto-archival for specific operations.

## Tasks
Implementation details are in `plan_implementation.yml`.

---
*Note: This plan was created in response to user request to reduce noise for agent sessions.*
