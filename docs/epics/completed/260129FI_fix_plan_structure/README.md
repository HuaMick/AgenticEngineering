# Plan: Fix Plan Folder Structure Inconsistencies

**Plan ID**: `260129FI_fix_plan_structure`
**Status**: Ready for Execution

## Problem

Two plan folders have incorrect nested structure that the CLI cannot detect:
- `260129FI_auto_archive_plans` - has nested `live/` subdirectory
- `260129UP_review_cli_movement_fixes` - has nested `live/` subdirectory

## Root Cause

The example template at `modules/AgenticGuidance/assets/examples/planner/YYMMDDXX_description/` uses an outdated nested structure. The CLI expects `plan_*.yml` files directly in the plan folder root.

## Solution

1. Update guidance example to use flattened structure
2. Update `plans.yml` definition to clarify requirements
3. Restructure the two broken folders
4. Verify CLI detection works

## Files

- `plan_fix.yml` - Implementation tasks
- `orchestration.mmd` - Orchestration flow
