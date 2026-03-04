# 260202CT: Comprehensive CLI Command Test Suite

## Overview

This test plan validates all AgenticCLI commands after the removal of the MCP GUI dashboard feature. It ensures all remaining CLI functionality works correctly through unit tests, integration tests, and UAT validation.

## Context

The MCP GUI dashboard feature was recently removed from AgenticCLI. This test plan provides comprehensive coverage of all remaining CLI commands to ensure:
- No regression from the dashboard removal
- All commands work in isolation
- Realistic workflows execute correctly
- JSON output mode works for automation
- Error messages are helpful

## Scope

### CLI Command Groups Tested

1. **Core Commands**: `--version`, `--help`, `--json`, `--debug`
2. **Plan Commands**: init, scaffold, status, validate, list, archive, unarchive, move
3. **Plan Task Commands**: list, start, complete, current, add, update, prefill, status
4. **Plan Phase Commands**: add, list, update
5. **Plan Orchestration Commands**: generate, validate (dashboard removed)
6. **Plan Stories Commands**: list, test
7. **Worktree Commands**: create, list, delete, switch
8. **Context Commands**: bootstrap, seed
9. **Session Commands**: list, spawn, status
10. **Loop Commands**: start, status, history
11. **Template Commands**: generate, list
12. **Inputs Commands**: validate, resolve
13. **Entrypoint Commands**: list, execute
14. **Agent Help Commands**: `<agent-name> --help`, `<agent-name> --bootstrap`
15. **Additional Commands**: setup, preferences, health, config, update, rebuild, langsmith, manifest, cicd, state, env

### Testing Strategy

- **Component Testing**: smoke-test strategy for individual commands
- **Integration Testing**: agent-blind-test strategy for workflows
- **Testing Layers**: Local + Docker (recommended baseline)
- **UAT Validation**: PRIMARY SUCCESS CRITERIA using test-user-simulator

## Plan Structure

### Phase 1: Environment Setup (MANDATORY)
- Local environment: Install CLI via `uv pip install -e .`
- Docker environment: Build `agenticcli-test` image
- Verify CLI accessible and version correct

### Phase 2: Component Testing (test-fix-loop)
- Test each command group independently
- Validate success cases and error handling
- Verify JSON output format
- Test in both local and Docker environments

### Phase 3: Integration Testing (test-fix-loop)
- Plan creation workflow
- Task management workflow
- Context injection workflow
- JSON automation workflow

### Phase 4: Cleanup
- Remove test artifacts
- Verify test suite structure

### Phase 5: Test Quality Audit (MANDATORY - audit-test-fix-loop)
- Detect reward hacking patterns
- Validate test quality
- Review skipped tests
- Ensure edge cases covered

### Phase 6: UAT Validation (MANDATORY - user-story-validation-loop)
- Basic CLI usage validation
- Context injection validation
- Advanced workflow validation
- Uses test-user-simulator for real user workflows

### Phase 7: Documentation Review
- Update CLI documentation
- Verify examples work
- Remove references to dashboard

## Loop Structures

1. **test-fix-loop**: Component and integration testing (max 5 iterations)
2. **audit-test-fix-loop**: MANDATORY test quality validation (max 3 iterations)
3. **user-story-validation-loop**: PRIMARY SUCCESS CRITERIA (max 3 iterations)

## Success Criteria

- All CLI commands tested and working
- Unit tests pass in local and Docker
- Integration workflows validated
- Audit passes with no quality issues
- UAT validation passes for all user stories
- JSON output works for automation
- Error messages helpful
- Documentation accurate
- No dashboard references

## Testing Layers

**Recommended**: Local + Docker

- **Local**: Validates developer workflow with installed CLI
- **Docker**: Validates CI/CD parity with containerized environment

**Cloud Build NOT required** because:
- Test-only changes
- No infrastructure modifications
- pyproject.toml unchanged
- Dockerfile.test unchanged

## User Stories

Relevant user stories:
- `/home/code/AgenticEngineering/modules/AgenticGuidance/userstories/MyAgents/02_cli_basics.yml`
- `/home/code/AgenticEngineering/modules/AgenticGuidance/userstories/MyAgents/04_cli_context.yml`

Note: US-INSTALL-* stories NOT required (no packaging changes)

## Files

- `live/plan_test.yml`: Main test plan with phases and tasks
- `README.md`: This file (plan overview)

## Next Steps

1. Execute Phase 1: Environment Setup
2. Spawn test-runner agents for component testing
3. Execute test-fix-loop until all tests pass
4. Run mandatory audit-test-fix-loop
5. Execute UAT validation (primary success criteria)
6. Update documentation

## References

- Test strategies: `modules/AgenticGuidance/assets/guidelines/`
- Loop definitions: `modules/AgenticGuidance/assets/definitions/agent-loops.yml`
- User stories: `modules/AgenticGuidance/userstories/MyAgents/`
- Existing tests: `/home/code/AgenticEngineering/modules/AgenticCLI/tests/`
