# Planner Specialized Core Layers Pattern

## Overview

This pattern reduces token usage for planner agents by creating specialized core layers that include only the guidelines and system definitions actually used by planning work.

## Problem Statement

The generic `core-guidelines.yml` and `core-system.yml` layers include content designed for all 27+ agents across 9 categories. Planners do not need:

- `testing.yml` - Test category-specific operational guidelines
- `safety.yml` - Builder/tester operational concerns
- `architecture-pattern.yml` - Domain/Workflow/Entrypoint details (builder-specific)
- `ARCHITECTURE.md` - Reference documentation, not actionable input

Loading these files for every planner invocation wastes tokens and dilutes focus.

## Solution

Create specialized planner core layers:

```
modules/AgenticGuidance/assets/inputs/
  core-guidelines.yml          # Generic (all 8 guidelines)
  core-system.yml              # Generic (3 system files)
  planner-core-guidelines.yml  # Specialized (6 guidelines - no testing/safety)
  planner-core-system.yml      # Specialized (1 file - plans.yml only)
```

## T4.1 Audit Results

### Guidelines Usage Analysis

| Guideline | Planners Need? | Reason |
|-----------|----------------|--------|
| fix-the-source.yml | YES | Root cause analysis for plan creation |
| context-minimisation.yml | YES | Essential for reducing plan complexity |
| experiment-first.yml | YES | Discovery before planning |
| less-is-more.yml | YES | Minimal viable plans |
| worktree-and-branching.yml | YES | Branch strategy for plan organization |
| response-audit.yml | YES | Final verification of plan output |
| testing.yml | NO | Test-category-specific operations |
| safety.yml | NO | Builder/tester operational concerns |

### System Definitions Usage Analysis

| System File | Planners Need? | Reason |
|-------------|----------------|--------|
| plans.yml | YES | Essential - plan structure, lifecycle, taxonomy |
| architecture-pattern.yml | NO | Domain/Workflow/Entrypoint is builder-specific |
| ARCHITECTURE.md | NO | Reference doc, not actionable input |

## Token Savings Estimate

| Layer Type | Generic Size | Specialized Size | Savings |
|------------|--------------|------------------|---------|
| Core Guidelines | 8 files | 6 files | 25% reduction |
| Core System | 3 files | 1 file | 66% reduction |

Combined: Approximately **30-40% reduction** in core layer token usage per planner invocation.

## Implementation

### Planner-Core-Guidelines.yml

```yaml
layer_name: "planner-core-guidelines"
references:
  - path: "modules/AgenticGuidance/assets/guidelines/fix-the-source.yml"
  - path: "modules/AgenticGuidance/assets/guidelines/context-minimisation.yml"
  - path: "modules/AgenticGuidance/assets/guidelines/experiment-first.yml"
  - path: "modules/AgenticGuidance/assets/guidelines/less-is-more.yml"
  - path: "modules/AgenticGuidance/assets/guidelines/worktree-and-branching.yml"
  - path: "modules/AgenticGuidance/assets/guidelines/response-audit.yml"
```

### Planner-Core-System.yml

```yaml
layer_name: "planner-core-system"
references:
  - path: "modules/AgenticGuidance/assets/definitions/plans.yml"
```

### Updated Planner Inputs.yml Pattern

```yaml
layers:
  - type: layer
    path: "modules/AgenticGuidance/assets/inputs/planner-core-system.yml"
    description: "Planner-specific system definitions"
    required: true

  - type: layer
    path: "modules/AgenticGuidance/assets/inputs/planner-core-guidelines.yml"
    description: "Planner-specific guidelines"
    required: true

  - type: layer
    path: "modules/AgenticGuidance/assets/inputs/planner-shared.yml"
    description: "Planner shared inputs"
    required: true
```

## Applying This Pattern to Other Categories

To create specialized layers for another agent category (e.g., `builder`, `test`, `cleaner`):

1. **Audit Usage**: Review all agents in the category to identify which core files they actually reference
2. **Document Justification**: For each included/excluded file, document why
3. **Create Specialized Layers**: Create `{category}-core-guidelines.yml` and `{category}-core-system.yml`
4. **Update Agent Inputs**: Replace generic core layers with specialized versions
5. **Test**: Verify agents still have access to needed context

### Example: Builder Category

Builders likely need:
- `testing.yml` - Validation during build
- `safety.yml` - Operational concerns
- `architecture-pattern.yml` - Domain/Workflow/Entrypoint structure

Builders likely don't need:
- `reward-hacking-prevention.yml` - Audit-specific

### Example: Test Category

Testers likely need:
- `testing.yml` - Core testing principles
- `safety.yml` - Separation of concerns
- `reward-hacking-prevention.yml` - Detecting test gaming

Testers likely don't need:
- `worktree-and-branching.yml` - Branch management

## Files Modified

- `/modules/AgenticGuidance/assets/inputs/planner-core-guidelines.yml` (created)
- `/modules/AgenticGuidance/assets/inputs/planner-core-system.yml` (created)
- `/modules/AgenticGuidance/agents/planner/planner-cleaning/inputs.yml` (updated)
- `/modules/AgenticGuidance/agents/planner/planner-build/inputs.yml` (updated)
- `/modules/AgenticGuidance/agents/planner/planner-test/inputs.yml` (updated)
- `/modules/AgenticGuidance/agents/planner/planner-guidance/inputs.yml` (updated)
- `/modules/AgenticGuidance/agents/planner/planner-reviewer/inputs.yml` (updated)

## Audit Source

T4.1 Phase Audit (260109) - Specialized Core Layer Audit
