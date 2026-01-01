# Agent Categories Analysis
**Plan**: 251218_agent_categories
**Date**: 2025-12-18
**Status**: In Progress

## Executive Summary

This analysis documents the current agent category structure and defines the plan for introducing a formal "agent categories" concept to the MyAgents framework. Agent categories represent the top-level organizational structure for grouping related agents by their primary responsibility domain.

## Current Agent Category Structure

The agent guidance is located at: `/home/code/myagents/MyAgents-staging/`

### 9 Agent Categories Identified

| Category | Sub-Agents | Primary Responsibility |
|----------|------------|------------------------|
| **build** | build-flutter, build-python | Building and compiling code for production |
| **planner** | planner-build, planner-cleaning, planner-test, planner-teach, planner-agent-exam | Planning and task decomposition |
| **test** | test-builder, test-runner, test-audit, test-user-simulator, test-service, test-final-output, test-flutter-builder, test-flutter-runner | Testing strategy and execution |
| **cleaner** | cleaner-identify, cleaner-execute, cleaner-core | Code quality and cleanup |
| **explore** | explore-architecture, explore-feature, explore-dependency, explore-test, explore-synthesis | Codebase exploration and analysis |
| **teacher** | teacher-process, teacher-update-assets | Agent guidance improvement (note: teacher-plan not found as sub-agent yet) |
| **deploy** | deploy-packaging, deploy-cicd, deploy-worktree | Deployment and release management |
| **documentation** | documentation-core | Documentation generation and maintenance |
| **orchestration** | orchestration-teach | Cross-domain workflow orchestration |

### Category Sizes

- **Largest**: test (8 sub-agents)
- **Medium**: planner (5), explore (5)
- **Small**: build (2), cleaner (3), teacher (2), deploy (3)
- **Minimal**: documentation (1), orchestration (1)

## Problem Statement

Currently, agent categories exist implicitly as folder names, but they are not:
1. **Formally defined** - No canonical definition of what each category represents
2. **Self-documenting** - Categories lack purpose statements and responsibility boundaries
3. **Referenced consistently** - Sub-agents don't explicitly declare their category membership
4. **Documented architecturally** - Category hierarchy not explained in architecture docs

## Proposed Solution

### 1. Create Canonical Definition File

**Location**: `assets/definitions/agent-categories.yml`

**Purpose**: Single source of truth for all agent categories

**Content Structure**:
```yaml
agent_categories:
  build:
    name: "Build"
    purpose: "Building and compiling code for production deployment"
    responsibility: "Transforms source code into executable artifacts"
    sub_agents:
      - build-flutter
      - build-python

  planner:
    name: "Planner"
    purpose: "Planning and task decomposition across domains"
    responsibility: "Breaks down complex requests into actionable task plans"
    sub_agents:
      - planner-build
      - planner-cleaning
      - planner-test
      - planner-teach
      - planner-agent-exam

  # ... (continue for all 9 categories)
```

### 2. Update Category-Level Manifests

Each category folder should have a `manifest.yml` that references the canonical definition:

```yaml
category:
  definition: "assets/definitions/agent-categories.yml#test"

sub_agents:
  - test-builder
  - test-runner
  # ...
```

### 3. Update Sub-Agent Inputs

Each sub-agent's `inputs.yml` should reference its category:

```yaml
agent_context:
  category: "assets/definitions/agent-categories.yml#test"
  role: "test-builder"
```

### 4. Update Architecture Documentation

**Files to Update**:
- `docs/ARCHITECTURE.md` - Add category hierarchy explanation
- `docs/agent-role-scope-matrix.md` - Organize by category with definitions

## Relationship Analysis

### Categories vs Sub-Agents

**Category (Parent)**:
- Top-level organizational unit
- Defines domain responsibility
- Groups related sub-agents
- Has shared principles/guidelines

**Sub-Agent (Child)**:
- Specific implementation within category
- Inherits category context
- Has specialized process/inputs
- Executes concrete tasks

### Current Implicit Relationships

The relationships currently exist only through folder structure:
```
agents/
  build/              <- Category (implicit)
    build-flutter/    <- Sub-agent
    build-python/     <- Sub-agent
  test/               <- Category (implicit)
    test-builder/     <- Sub-agent
    test-runner/      <- Sub-agent
```

### Proposed Explicit Relationships

After this refactor, relationships will be explicit through references:
```
agent-categories.yml  <- Canonical definition
  ↓ referenced by
build/manifest.yml    <- Category manifest
  ↓ lists
build-flutter/        <- Sub-agent
  inputs.yml          <- References category
  process.yml
  manifest.yml
```

## Benefits of Formal Categories

### 1. Improved Discoverability
- New users can understand the agent system hierarchy
- Category purpose statements clarify responsibilities
- Clear boundaries between domains

### 2. Better Maintainability
- Single source of truth for category definitions
- Easier to add new categories or sub-agents
- Consistent structure across all categories

### 3. Enhanced Context
- Agents can reference their category context
- Shared category-level guidelines/principles
- Clearer routing logic for orchestration

### 4. Documentation Quality
- Architecture docs can reference canonical definitions
- Category boundaries documented explicitly
- Easier to explain the system to new contributors

## Implementation Phases

### Phase 1: Foundation (High Priority)
1. Create `assets/definitions/agent-categories.yml`
2. Update architecture documentation
3. Update agent-role-scope-matrix.md

### Phase 2: Category Integration (9 tasks)
For each category (build, planner, test, cleaner, explore, teacher, deploy, documentation, orchestration):
1. Ensure category `manifest.yml` exists and references definition
2. Update all sub-agent `inputs.yml` to reference category
3. Verify references resolve correctly

### Phase 3: Validation
1. Test agent routing with category context
2. Verify documentation accuracy
3. Check for broken references

## Files to Create

1. `/home/code/myagents/MyAgents-staging/assets/definitions/agent-categories.yml`

## Files to Update

### Documentation
1. `/home/code/myagents/MyAgents-staging/docs/ARCHITECTURE.md`
2. `/home/code/myagents/MyAgents-staging/docs/agent-role-scope-matrix.md`

### Category Manifests (where missing)
3. `/home/code/myagents/MyAgents-staging/planner/manifest.yml`
4. `/home/code/myagents/MyAgents-staging/test/manifest.yml`
5. `/home/code/myagents/MyAgents-staging/cleaner/manifest.yml`
6. `/home/code/myagents/MyAgents-staging/explore/manifest.yml`
7. `/home/code/myagents/MyAgents-staging/teacher/manifest.yml`
8. `/home/code/myagents/MyAgents-staging/deploy/manifest.yml`
9. `/home/code/myagents/MyAgents-staging/documentation/manifest.yml`
10. `/home/code/myagents/MyAgents-staging/orchestration/manifest.yml`

### Sub-Agent Inputs (36 files)
- 2 build sub-agents
- 5 planner sub-agents
- 8 test sub-agents
- 3 cleaner sub-agents
- 5 explore sub-agents
- 2 teacher sub-agents (+ 1 new: teacher-plan)
- 3 deploy sub-agents
- 1 documentation sub-agent
- 1 orchestration sub-agent

## Validation Checklist

- [ ] agent-categories.yml defines all 9 categories
- [ ] Each category has: name, purpose, responsibility, sub_agents list
- [ ] All 9 category manifests reference the definition file
- [ ] All 36+ sub-agent inputs reference their category
- [ ] ARCHITECTURE.md explains category hierarchy
- [ ] agent-role-scope-matrix.md organized by category
- [ ] All file references resolve correctly
- [ ] No broken references in any agent files

## Success Criteria

1. **Definition Complete**: agent-categories.yml exists and is comprehensive
2. **References Valid**: All category/sub-agent references resolve
3. **Documentation Updated**: Architecture docs explain categories
4. **Structure Consistent**: All categories follow same pattern
5. **No Regressions**: Existing agent functionality unchanged

## Notes

- The "teacher-plan" sub-agent mentioned in the request doesn't exist yet in the teacher/ folder
  - Current teacher sub-agents: teacher-process, teacher-update-assets
  - May need to be created as part of this refactor or separate task
- Orchestration category only has one sub-agent (orchestration-teach)
  - May indicate this is a new/growing category
  - Or that orchestration is handled differently than other categories

## Conclusion

Formalizing agent categories will significantly improve the MyAgents framework's:
- **Clarity**: Explicit category definitions and relationships
- **Maintainability**: Single source of truth for category structure
- **Discoverability**: Clear hierarchy for new users
- **Documentation**: Better architectural understanding

The refactor touches 40+ files but follows a consistent pattern, making it straightforward to implement systematically.
