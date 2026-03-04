# Test Plan Summary: 260202CT Comprehensive CLI Command Test Suite

## Quick Overview

**Purpose**: Validate all AgenticCLI commands after MCP GUI dashboard removal  
**Status**: Active  
**Priority**: High  
**Testing Layers**: Local + Docker

## Test Coverage

### 15 Command Groups Tested
1. Core (--version, --help, --json, --debug)
2. Plan (init, scaffold, status, validate, list, archive, unarchive, move)
3. Plan Task (list, start, complete, current, add, update, prefill, status)
4. Plan Phase (add, list, update)
5. Plan Orchestration (generate, validate - dashboard removed ✓)
6. Plan Stories (list, test)
7. Worktree/wt (create, list, delete, switch)
8. Context/ctx (bootstrap, seed)
9. Session (list, spawn, status)
10. Loop (start, status, history)
11. Template/tpl (generate, list)
12. Inputs (validate, resolve)
13. Entrypoint/ep (list, execute)
14. Agent Help (<agent> --help, --bootstrap)
15. Additional (setup, preferences, health, config, update, rebuild, langsmith, manifest, cicd, state, env)

## Test Plan Phases

### Phase 1: Environment Setup ⚙️
- Install CLI locally: `uv pip install -e .`
- Build Docker image: `agenticcli-test`
- Verify CLI accessible and correct version

### Phase 2: Component Testing 🧪 (test-fix-loop, max 5 iterations)
- 15 test tasks (one per command group)
- smoke-test strategy (entry point testing)
- Local + Docker layers
- Success and error case coverage
- JSON output validation

### Phase 3: Integration Testing 🔗 (test-fix-loop, max 5 iterations)
- Plan creation workflow
- Task management workflow
- Context injection workflow
- JSON automation workflow
- agent-blind-test strategy

### Phase 4: Cleanup 🧹
- Remove test artifacts
- Verify test structure

### Phase 5: Test Quality Audit 🔍 (audit-test-fix-loop, max 3 iterations, MANDATORY)
- Detect reward hacking
- Validate test quality
- Review skipped tests
- Ensure edge cases covered

### Phase 6: UAT Validation ✅ (user-story-validation-loop, max 3 iterations, MANDATORY)
- **PRIMARY SUCCESS CRITERIA**
- Basic CLI usage validation
- Context injection validation
- Advanced workflow validation
- Uses test-user-simulator

### Phase 7: Documentation Review 📚
- Update CLI docs
- Verify examples work
- Remove dashboard references

## Loop Structures

| Loop Type | Phase | Max Iterations | Purpose |
|-----------|-------|----------------|---------|
| test-fix-loop | Component + Integration | 5 | Build and test CLI commands |
| audit-test-fix-loop | Test Quality Audit | 3 | Detect reward hacking (MANDATORY) |
| user-story-validation-loop | UAT | 3 | Validate real workflows (PRIMARY) |

## Success Criteria Checklist

- [ ] All CLI commands tested and working
- [ ] Unit tests pass (local + Docker)
- [ ] Integration workflows validated
- [ ] Audit passes (no reward hacking)
- [ ] **UAT validation passes (PRIMARY CRITERIA)**
- [ ] JSON output works for automation
- [ ] Error messages helpful
- [ ] Documentation accurate
- [ ] No dashboard references

## Key Features

✅ **Comprehensive Coverage**: All 15 command groups  
✅ **Multi-Layer Testing**: Local + Docker  
✅ **JSON Automation**: Validates scripting/automation use cases  
✅ **Real Workflows**: Integration tests simulate actual usage  
✅ **Quality Assurance**: Mandatory audit-test-fix-loop  
✅ **UAT Focus**: User story validation as primary success criteria  
✅ **Error Handling**: Tests both success and failure paths  

## File Locations

- **Test Plan**: `live/plan_test.yml` (1077 lines)
- **Overview**: `README.md` (141 lines)
- **Summary**: `SUMMARY.md` (this file)

## Next Actions

1. **Start Environment Setup** → Install CLI + Build Docker
2. **Run Component Tests** → 15 command groups via test-fix-loop
3. **Run Integration Tests** → 4 workflow scenarios
4. **Cleanup** → Remove test artifacts
5. **Run Audit** → MANDATORY audit-test-fix-loop
6. **Run UAT** → PRIMARY success criteria validation
7. **Update Docs** → Ensure documentation accurate

## Testing Strategy Matrix

| Test Type | Strategy | Agent | Layers | Iterations |
|-----------|----------|-------|--------|------------|
| Component | smoke-test | test-runner | Local+Docker | 5 |
| Integration | agent-blind-test | test-user-simulator | Local+Docker | 5 |
| Audit | audit | test-audit | Local+Docker | 3 |
| UAT | user-story-validation | test-user-simulator | Local+Docker | 3 |

## User Stories Referenced

- `MyAgents/02_cli_basics.yml` - Basic CLI workflows
- `MyAgents/04_cli_context.yml` - CCI context injection

Note: US-INSTALL-* stories NOT required (no packaging changes)

---

**Status**: Ready to execute  
**Last Updated**: 2026-02-02  
**Plan ID**: 260202CT_comprehensive_cli_command_test_suite
