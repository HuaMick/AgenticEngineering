# Migration Summary - AgenticGuidance Dependency Migration
**Date:** 2026-01-03
**Status:** COMPLETED

## Overview

This migration added missing agent directories and assets from legacy to the AgenticGuidance module based on an audit of what was actually referenced by existing orchestration and planner agents.

## Migrated Items

### Agent Categories

| Category | Sub-agents | Priority | Status |
|----------|-----------|----------|--------|
| **deploy** | deploy-worktree | CRITICAL | MIGRATED |
| **test** | test-runner, test-audit, test-final-output, test-guidance-simulator | CRITICAL | MIGRATED |
| **teacher** | teacher-update-guidance, teacher-update-assets | HIGH | MIGRATED |

### Assets

| Asset | Location | Status |
|-------|----------|--------|
| orchestration-policy.yml | assets/guidelines/ | MIGRATED |

## Skipped Items

| Agent | Reason |
|-------|--------|
| teacher-plan | Not yet implemented in legacy |
| test-builder | Not referenced by AgenticGuidance |
| test-user-simulator | Not referenced by AgenticGuidance |
| test-service | Not referenced by AgenticGuidance |
| test-flutter-builder | Flutter-specific |
| test-flutter-runner | Flutter-specific |
| deploy-packaging | Not referenced by orchestration |
| deploy-cicd | Not referenced by orchestration |

## Files Created

### Directory Structure
```
modules/AgenticGuidance/agents/
├── deploy/
│   ├── manifest.yml
│   └── deploy-worktree/
│       ├── manifest.yml
│       ├── process.yml
│       └── inputs.yml
├── test/
│   ├── manifest.yml
│   ├── test-runner/
│   │   ├── process.yml
│   │   └── inputs.yml
│   ├── test-audit/
│   │   ├── process.yml
│   │   └── inputs.yml
│   ├── test-final-output/
│   │   ├── process.yml
│   │   └── inputs.yml
│   └── test-guidance-simulator/
│       ├── manifest.yml
│       ├── process.yml
│       └── inputs.yml
└── teacher/
    ├── manifest.yml
    ├── teacher-update-guidance/
    │   ├── manifest.yml
    │   ├── process.yml
    │   └── inputs.yml
    └── teacher-update-assets/
        ├── manifest.yml
        ├── process.yml
        └── inputs.yml
```

## Updates Made

### Main Manifest
- `modules/AgenticGuidance/agents/manifest.yml` - Added deploy, test, teacher categories

### Reference Updates
- `agents/planner/planner-test/inputs.yml` - Marked test-runner, test-audit as MIGRATED
- `agents/planner/planner-guidance-testing/inputs.yml` - Marked test-guidance-simulator as MIGRATED, set required: true

### Path Updates
- `agents/deploy/deploy-worktree/process.yml` - Updated inputs.yml path to use agents/ prefix

## Validation Results

- All YAML files pass syntax validation
- Cross-references from orchestration-planning to deploy-worktree resolve
- Cross-references from planner-test to test agents resolve
- Cross-references from planner-guidance-testing to test-guidance-simulator resolve
- orchestration-policy.yml exists and is accessible

## Known Remaining Work

1. **test-user-simulator** - Marked as required: false in planner-test/inputs.yml. May need migration if UAT testing is required.
2. **teacher-plan** - Documented but not implemented. May be added in future.
3. **Other test agents** - test-builder, test-service remain in legacy for potential future migration.

## Next Steps

The AgenticGuidance module now has all agents required for:
- Planning workflows (orchestration-planning can spawn deploy-worktree)
- Test execution (planner-test can reference test-runner, test-audit)
- Guidance testing (planner-guidance-testing can use test-guidance-simulator)
- Teaching workflows (teacher agents available for guidance improvement)

Use `_execute.yml` or `_teach.yml` entrypoints to begin using the migrated agents.
