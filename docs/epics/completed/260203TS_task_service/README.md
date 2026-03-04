# TaskService Implementation Plan

Implementation of TaskService in AgenticGuidance to provide CRUD operations for tasks within plan YAML files.

## Objective

Create a domain service layer for task manipulation in plan files, enabling programmatic access to:
- Task retrieval (get, list, get_current)
- Task status updates (update_status, start, complete)
- Support for both nested (phases[].tasks[]) and flat (plan.tasks[]) structures

## Folder Structure

```
260203TS_task_service/
├── README.md                                    # This file
├── live/
│   ├── plan_build.yml                          # Implementation plan
│   └── orchestration_task_service_implementation.mmd  # Execution flow diagram
```

## Plan Components

### Implementation Phases

1. **Service Implementation Phase**
   - Create TaskService class structure (task.py)
   - Implement task retrieval methods (get, list, get_current)
   - Implement task update methods (update_status, start, complete)
   - Export TaskService in services package

2. **Test Implementation Phase** (with test-fix-loop)
   - Create test file structure with fixtures
   - Implement retrieval method tests
   - Implement update method tests
   - Implement edge case and error tests
   - Run full test suite iteratively

3. **Integration Validation Phase**
   - Test TaskService against real plan files
   - Validate YAML round-trip preservation
   - Verify backward compatibility

4. **Quality Validation Phase** (MANDATORY, with audit-test-fix-loop)
   - Audit test quality to prevent reward hacking
   - Fix identified test quality issues
   - Ensure proper assertions and real behavior validation

### Success Criteria

- TaskService class implemented with all 6 required methods
- Task dataclass supports all plan task fields
- TaskStatus enum provides pending/in_progress/completed states
- All unit tests pass (>90% coverage)
- Integration tests validate against real plan files
- Test audit passes with no reward hacking detected
- TaskService exported from agenticguidance.services package
- Both nested and flat task structures supported
- File locking prevents concurrent modification
- YAML formatting preserved after updates

## Session History

### Session 1: 2026-02-03 (Planning)
**Agent**: planner-build
**Status**: Planning complete
**Actions**:
- Analyzed existing service patterns (plan.py, state.py, config.py)
- Reviewed test structure and patterns
- Created comprehensive implementation plan with 4 phases
- Defined loop structures for iterative testing and quality validation
- Created orchestration MMD diagram

**Decisions**:
- Support both nested (phases[].tasks[]) and flat (plan.tasks[]) structures for backward compatibility
- get_current_task() prioritizes in_progress over pending tasks
- Use FileLock for atomic YAML updates
- Follow existing service patterns for consistency

**Next Steps**:
- Execute Phase 1: Service Implementation
- Begin with impl_001 (TaskService class structure)

## Architecture Alignment

**Layer**: Domain Service
**Pattern**: Pure service class (no workflow/entrypoint yet)
**Dependencies**:
- yaml (YAML parsing)
- pathlib (Path handling)
- dataclasses (Task model)
- FileLock from state.py (atomic writes)

**Future Extensions**:
- Workflow layer: Task manipulation workflows
- Entrypoint layer: CLI commands using TaskService
- Integration with agentic CLI for task management

## Related Plans

- **CLI Context Injection**: TaskService may be used by context bootstrap commands
- **Plan Management**: Complements existing PlanMovementWorkflow
- **State Registry**: Uses FileLock pattern from state.py

## Key Files

| File | Purpose |
|------|---------|
| `live/plan_build.yml` | Full implementation plan with tasks and success criteria |
| `live/orchestration_task_service_implementation.mmd` | Visual execution flow with loops |
| `modules/AgenticGuidance/src/agenticguidance/services/task.py` | Target implementation file |
| `modules/AgenticGuidance/tests/test_services_task.py` | Test suite file |

## Notes

- This plan implements ONLY the domain service layer
- No CLI commands or workflow layers included (future work)
- Must maintain backward compatibility with existing plan file formats
- Test quality validation is MANDATORY (audit-test-fix-loop)
- Maximum 5 iterations for test-fix-loop, 3 for audit-test-fix-loop
