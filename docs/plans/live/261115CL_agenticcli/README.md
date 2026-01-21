# Plan: 261115CL_agenticcli

## Status: IMPLEMENTATION COMPLETE - EXPERIMENT READY

**Updated**: 2026-01-21
**Branch**: `agenticcli`

## Overview

Planning folder for AgenticCLI module development and enhancements.

## Current Initiative: CLI Task Lists Experiment

Implement CLI-based preset task lists to help agents remember ancillary tasks (like MMD generation, README updates) that they often forget due to task momentum.

### Plan Files

| File | Purpose | Status |
|------|---------|--------|
| `plan_live_build.yml` | Build phases: CLI commands, handlers, workflow, templates | completed |
| `plan_live_test.yml` | Test phases: unit, integration, blind experiment | completed |
| `orchestration_cli_task_lists.mmd` | Execution flow for orchestrator | completed |

### Implementation Phases

1. **Build Phase 1**: CLI Task Command Extensions (argparse parsers) - COMPLETED
2. **Build Phase 2**: Command Handler Implementation (plan.py handlers) - COMPLETED
3. **Build Phase 3**: Task Workflow Module (TaskPresetWorkflow class) - COMPLETED
4. **Build Phase 4**: Preset Templates (YAML templates for agent roles) - COMPLETED
5. **Build Phase 5**: Integration and Polish - COMPLETED
6. **Test Phases 1-4**: Unit and Integration Tests - COMPLETED (64 tests, all passing)
7. **Test Phase 5**: Blind Testing Experiment - FRAMEWORK READY (requires manual execution)
8. **Test Phase 6**: CI Integration - COMPLETED (pytest markers configured)

### Key Commands (Implemented)

```bash
agentic plan task prefill --preset planner-build  # Load preset tasks
agentic plan task list                            # Show all tasks
agentic plan task status <task-id>                # Task details
agentic plan task add <description>               # Add new task
```

## Folder Structure

```
261115CL_agenticcli/
├── README.md           # This file
├── analysis/           # Analysis documents
├── audit/              # Audit reports
├── completed/          # Completed plans
└── live/               # Active plans and backlogs
```

## Test Results

- **64 new tests** written for CLI Task Lists feature
- **All tests passing** (64/64)
- Test categories: unit (44), integration (20), experiment (documentation only)
- Pytest markers configured: `unit`, `integration`, `experiment`, `slow`

## Blind Testing Experiment

The experiment framework is ready in `modules/AgenticCLI/tests/experiments/`:
- `test_blind_baseline.py` - Baseline protocol (no prefill)
- `test_blind_treatment.py` - Treatment protocol (with prefill)
- `experiment_results_template.yml` - Recording template

**To run the experiment**:
1. Execute baseline sessions without prefill
2. Execute treatment sessions with prefill
3. Record observations using templates
4. Compare improvement (target: >15%)

## Completed Work

- `plan_completed_folder_creation_automation.yml` - Implemented `agentic plan init` command with YYMMDDXX naming convention enforcement
- CLI Task Lists feature implementation and testing (this plan)

## Active Work

- Blind testing experiment awaiting manual execution
- See `live/` folder for current plans and backlogs
