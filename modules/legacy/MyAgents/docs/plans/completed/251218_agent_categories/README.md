# Agent Categories Refactor - Planning Folder

**Plan ID**: 251218_agent_categories
**Created**: 2025-12-18
**Status**: Planning Complete, Ready for Execution

## Overview

This plan introduces formal "agent categories" to the MyAgents framework. Agent categories represent the top-level organizational structure for grouping related agents by their primary responsibility domain.

## Problem Statement

Currently, agent categories exist implicitly as folder names but lack:
- Formal definitions
- Self-documentation
- Consistent references across agents
- Architectural documentation

## Solution

Create a canonical `agent-categories.yml` definition file and update all 9 categories and 30+ sub-agents to reference it explicitly.

## Structure

```
251218_agent_categories/
├── README.md (this file)
├── analysis/
│   └── agent-categories-analysis.md - Comprehensive analysis of current state
├── live/
│   ├── planner_definitions.yml - Core definitions and documentation updates
│   ├── planner_build.yml - Build category (2 sub-agents)
│   ├── planner_planner.yml - Planner category (5 sub-agents)
│   ├── planner_test.yml - Test category (8 sub-agents)
│   ├── planner_cleaner.yml - Cleaner category (3 sub-agents)
│   ├── planner_explore.yml - Explore category (5 sub-agents)
│   ├── planner_teacher.yml - Teacher category (2 sub-agents)
│   ├── planner_deploy.yml - Deploy category (3 sub-agents)
│   ├── planner_documentation.yml - Documentation category (1 sub-agent)
│   └── planner_orchestration.yml - Orchestration category (1 sub-agent)
└── completed/
    └── (completed tasks will move here)
```

## Agent Categories

| Category | Sub-Agents | Files to Update |
|----------|------------|-----------------|
| build | 2 | 3 (1 manifest + 2 inputs) |
| planner | 5 | 6 (1 manifest + 5 inputs) |
| test | 8 | 9 (1 manifest + 8 inputs) |
| cleaner | 3 | 4 (1 manifest + 3 inputs) |
| explore | 5 | 6 (1 manifest + 5 inputs) |
| teacher | 2 | 3 (1 manifest + 2 inputs) |
| deploy | 3 | 4 (1 manifest + 3 inputs) |
| documentation | 1 | 2 (1 manifest + 1 input) |
| orchestration | 1 | 2 (1 manifest + 1 input) |
| **TOTAL** | **30** | **39 agent files** |

## Additional Files

- **1** definition file: `assets/definitions/agent-categories.yml`
- **2** documentation files: `docs/ARCHITECTURE.md`, `docs/agent-role-scope-matrix.md`

**Grand Total**: 42 files to create/update

## Execution Order

### Phase 1: Foundation (MUST complete first)
1. Execute `planner_definitions.yml` to create:
   - `assets/definitions/agent-categories.yml`
   - Update `docs/ARCHITECTURE.md`
   - Update `docs/agent-role-scope-matrix.md`

### Phase 2: Category Integration (can run in parallel after Phase 1)
Execute all 9 category plans:
- `planner_build.yml`
- `planner_planner.yml`
- `planner_test.yml`
- `planner_cleaner.yml`
- `planner_explore.yml`
- `planner_teacher.yml`
- `planner_deploy.yml`
- `planner_documentation.yml`
- `planner_orchestration.yml`

### Phase 3: Validation
- Verify all file references resolve
- Test agent routing with category context
- Check documentation accuracy

## Success Criteria

- [ ] `agent-categories.yml` exists and defines all 9 categories
- [ ] All 9 category manifests reference the definition file
- [ ] All 30+ sub-agent inputs reference their category
- [ ] ARCHITECTURE.md explains category hierarchy
- [ ] agent-role-scope-matrix.md organized by category
- [ ] All file references resolve correctly
- [ ] No broken references
- [ ] Existing agent functionality unchanged

## Expected Impact

### Benefits
- **Clarity**: Explicit category definitions and relationships
- **Maintainability**: Single source of truth for category structure
- **Discoverability**: Clear hierarchy for new users
- **Documentation**: Better architectural understanding

### Scope
- **42 files** to create/update
- **9 categories** formalized
- **30 sub-agents** updated
- **Zero functional changes** (structure only)

## Notes

- The refactor is structural only - no changes to agent behavior
- All plans follow consistent pattern for easy systematic execution
- Dependencies clearly marked (Phase 1 must complete before Phase 2)
- teacher-plan sub-agent mentioned in original request doesn't exist yet
- May be created separately or as part of future teacher expansion

## Reference Files

- **Analysis**: `analysis/agent-categories-analysis.md` - Comprehensive current state analysis
- **Reference Plan**: `/home/code/myagents/MyAgents-staging/docs/plans/251216_context_min/` - Similar planning structure used for context minimization refactor

## Next Steps

1. Review and approve planning structure
2. Execute Phase 1 (planner_definitions.yml)
3. Validate Phase 1 completion
4. Execute Phase 2 (all 9 category plans)
5. Perform final validation
6. Move completed tasks to completed/ folder
7. Update this README with completion status
