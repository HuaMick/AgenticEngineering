# Batch 2: Testing Framework Definition Files Audit

## Summary Table

| File | Current Type | Should Be | Redundancy | Usage | Priority | Action |
|------|-------------|-----------|------------|-------|----------|--------|
| test-roles.yml | Definition | **Guideline** | HIGH (overlaps test-builder-role + test-runner-role) | 15 refs | High | **Deprecate** - merge into role files |
| test-structure.yml | Definition | Guideline | LOW | 18 refs | Medium | Reclassify to guidelines/ |
| test-creation-principles.yml | Definition | **Guideline** | LOW | 13 refs | Medium | Reclassify to guidelines/ |
| test-execution-workflow.yml | Definition | **Guideline** | MEDIUM (project-specific content) | 16 refs | Medium | Reclassify + generalize |
| testing-documentation.yml | Definition | **Guideline** | HIGH (project-specific) | 10 refs | High | **Deprecate** - move to project docs |
| testing-types.yml | Definition | Definition (Index) | LOW | 21 refs | Low | Keep as-is (pure index) |
| skipped-test.yml | Definition | Definition | MEDIUM (overlaps acceptable-skips) | 7 refs | Medium | Merge with acceptable-skips |
| acceptable-skips.yml | Definition | **Guideline** | HIGH (project-specific) | 18 refs | High | **Deprecate** or generalize |
| test-builder-role.yml | Definition | Definition | LOW | 13 refs | Low | Keep as-is |
| test-runner-role.yml | Definition | Definition | LOW | 7 refs | Low | Keep as-is |
| guidance-test-scenarios.yml | Definition | Definition | LOW | 32 refs | Low | Keep as-is |

---

## Detailed Analysis

### 1. test-roles.yml

**Current Content:**
```yaml
test_roles: |
  - **Test Builder**: Responsible for creating and maintaining test files.
    * Goal: High code coverage, valid test logic.
    * Constraint: CANNOT execute tests for verification.
  - **Test Runner**: Responsible for executing tests and reporting results.
    * Goal: Accurate reporting of PASS/FAIL/SKIP.
    * Constraint: CANNOT modify test files or application code.
```

**Analysis:**
- **Classification:** This is a **guideline** (prescribes behavior, constraints) not a definition
- **Redundancy:** HIGH - Content is fully duplicated in:
  - `test-builder-role.yml` (more detailed version)
  - `test-runner-role.yml` (more detailed version)
- **Usage:** Referenced in 15 files, but always alongside the more detailed role files
- **Problem:** This file exists as a summary that adds no value over the detailed role files

**Recommendation:** **DEPRECATE**
- Remove this file entirely
- Update references to point to `test-builder-role.yml` and `test-runner-role.yml`
- The detailed role files already contain all this information plus language-specific extensions

**Priority:** HIGH - Removes token waste and confusion

---

### 2. test-structure.yml

**Current Content:**
```yaml
test_structure: |
  Tests are organized using "1 package per workflow" structure under tests/workflows/.
  Each workflow has its own test package containing workflow-specific tests.

  **Naming Conventions**:
  - CLI/infrastructure workflows: Use descriptive names...
  - Agent workflows: Prefix with "agent_"...
  ...
```

**Analysis:**
- **Classification:** This is a **guideline** (prescribes how to organize tests)
- **Redundancy:** LOW - unique content
- **Usage:** 18 references, actively used in test-builder agents
- **Problem:** Mislabeled as definition when it provides actionable organization rules

**Recommendation:** **RECLASSIFY**
- Move from `definitions/` to `guidelines/`
- Rename to `test-organization.yml` for clarity
- This is prescriptive guidance, not a concept definition

**Priority:** MEDIUM - Improves semantic accuracy

---

### 3. test-creation-principles.yml

**Current Content:**
```yaml
test_creation_principles: |
  When creating tests, test-builder agents must follow these principles:

  1. Evidence-based validation:
     - Verify actual outcomes, not just success flags
     - Check file contents, not just existence
     ...

  2. Avoid reward hacking patterns:
     See modules/AgenticGuidance/assets/definitions/reward-hacking.yml...
```

**Analysis:**
- **Classification:** This is clearly a **guideline** (explicitly says "must follow these principles")
- **Redundancy:** LOW - unique principles, references reward-hacking.yml for anti-patterns
- **Usage:** 13 references, core input for test-builder agents
- **Problem:** Correctly identified as principles (actionable rules) but placed in definitions/

**Recommendation:** **RECLASSIFY**
- Move from `definitions/` to `guidelines/`
- This is prescriptive guidance for test creation behavior

**Priority:** MEDIUM - Improves semantic organization

---

### 4. test-execution-workflow.yml

**Current Content:**
```yaml
test_execution_workflow: |
  Test agents should follow this workflow when running tests:

  1. **Pre-Test Setup**:
     - Start LangGraph Studio service if not already running
     - Command: myagents studio start
     ...

  4. **Expected Results**:
     - All tests should pass except:
       - 5 tests requiring GCP registry authentication (acceptable skip)
       - 1 test requiring shellcheck (acceptable skip)
```

**Analysis:**
- **Classification:** This is a **guideline** (prescribes execution workflow)
- **Redundancy:** MEDIUM - overlaps with acceptable-skips.yml for expected skip counts
- **Usage:** 16 references, actively used in test-runner agents
- **Problem:** Contains **project-specific** content (LangGraph Studio, specific test counts)
  - References `myagents studio start/stop` commands
  - Specifies "5 tests requiring GCP registry" and "1 test requiring shellcheck"
  - These are MyAgents-specific details, not generalizable guidance

**Recommendation:** **RECLASSIFY + GENERALIZE**
- Move from `definitions/` to `guidelines/`
- Extract project-specific commands to project inputs (not shared definitions)
- Keep generic workflow pattern (pre-test setup, execution, cleanup, expected results)
- Make skip counts configurable via project-specific inputs.yml

**Priority:** MEDIUM - Removes hardcoded project dependencies from shared guidance

---

### 5. testing-documentation.yml

**Current Content:**
```yaml
testing_documentation: |
  Testing documentation is located in docs/testing/ with a hierarchical structure:
  - README.md: Quick reference for running tests (read this first)
  - LOCAL_TESTING.md: Detailed local/Docker testing guide
  - userstories.yml: Centralized user stories for UAT testing (agent-blind-test)
  - CI/CD documentation: docs/CICD_README.md (root level)

  Key constraint: Local tests may fail due to agent-gcptoolkit workspace dependency.
  Use Docker or CI for full validation. See docs/testing/README.md for quick commands.
```

**Analysis:**
- **Classification:** This describes documentation locations (pointer file)
- **Redundancy:** HIGH - this is 100% **project-specific**
  - References MyAgents-specific paths (`docs/testing/`, `docs/CICD_README.md`)
  - Mentions `agent-gcptoolkit` workspace (MyAgents infrastructure)
- **Usage:** 10 references, but all in MyAgents-related contexts
- **Problem:** Should not be in shared AgenticGuidance definitions at all

**Recommendation:** **DEPRECATE**
- Remove from shared definitions entirely
- This content belongs in the MyAgents project itself (docs/testing/README.md)
- If pattern is needed, create a generic "testing-documentation-pattern.yml" in guidelines/

**Priority:** HIGH - Removes project-specific content from shared framework

---

### 6. testing-types.yml

**Current Content:**
```yaml
testing_types:
  smoke_test:
    description: "Early validation of entrypoints and basic functionality"
    detail: "strategy-user-simulation.yml"
  user_simulator:
    description: "Validates agent usability by testing user stories with only default guidance"
    detail: "strategy-agent-blind-test.yml"
  ...
see_also:
  - "strategy-multi-layer.yml: Multi-layer testing strategy"
```

**Analysis:**
- **Classification:** This is a **definition** (names concepts and points to strategy details)
- **Redundancy:** LOW - serves as an index to detailed strategy files
- **Usage:** 21 references, heavily used
- **Problem:** None - this is correctly structured as a concept index

**Recommendation:** **KEEP AS-IS**
- Correctly structured as a definition index
- Follows pattern of naming concepts with pointers to detailed strategy files
- Valuable for test agents to understand available testing types

**Priority:** LOW - Already correct

---

### 7. skipped-test.yml

**Current Content:**
```yaml
skipped_test: |
  A skipped test uses pytest.skip, pytest.skipif, or @pytest.mark.skipif to bypass execution.
  Acceptable only for true edge cases that cannot be fabricated (e.g., production infrastructure failures).
  All other skips should be fixed by fabricating the condition (start service, install tool, create fixture).
  Mocking requires explicit user permission - use real dependencies by default.
```

**Analysis:**
- **Classification:** This is a **definition** (explains "what is a skipped test")
- **Redundancy:** MEDIUM - overlaps conceptually with acceptable-skips.yml
  - skipped-test.yml: defines what a skip IS
  - acceptable-skips.yml: lists which skips ARE acceptable (project-specific)
- **Usage:** 7 references
- **Problem:** Two files handling related concepts; acceptable-skips has project-specific content

**Recommendation:** **MERGE**
- Keep skipped-test.yml as the definition of what a skip is
- Merge the generic guidance from acceptable-skips into this file
- Move project-specific acceptable skip lists to project inputs.yml

**Priority:** MEDIUM - Consolidates related concepts

---

### 8. acceptable-skips.yml

**Current Content:**
```yaml
acceptable_skips: |
  Only the following test skips are acceptable:

  1. **Registry Authentication Tests** (5 tests):
     - Require GCP Artifact Registry credentials
     - Skip reason: "Registry authentication packages not available"

  2. **Shellcheck Test** (1 test):
     - Requires shellcheck binary installed
     - Skip reason: "shellcheck not found"
```

**Analysis:**
- **Classification:** This is a **guideline** (prescribes what is acceptable)
- **Redundancy:** HIGH - this is 100% **project-specific**
  - Specific test counts (5 tests, 1 test)
  - Specific reasons (GCP Artifact Registry, shellcheck)
  - These are MyAgents infrastructure details
- **Usage:** 18 references, but mostly in MyAgents contexts
- **Problem:** Project-specific skip lists do not belong in shared definitions

**Recommendation:** **DEPRECATE or GENERALIZE**
- Option A: Remove entirely, move content to MyAgents project inputs
- Option B: Generalize to pattern: "acceptable skips are for infrastructure dependencies that cannot be fabricated locally"
- If keeping, rename and move to guidelines/

**Priority:** HIGH - Removes project-specific content

---

### 9. test-builder-role.yml

**Current Content:**
```yaml
test_builder_role: |
  Agent responsible for CREATING and MODIFYING tests, NOT running them.
  Separation from test_runner prevents reward hacking where the same
  agent that writes tests also runs them and could game the results.

  Responsibilities:
  - Create test files following test-structure organization...

  Constraints:
  - CANNOT execute tests for verification...

  Language-Specific Extensions:
  - Python: Test files in tests/workflows/...
  - Flutter: Test files mirror lib/ structure...
```

**Analysis:**
- **Classification:** This is a **definition** (defines what a test builder is and does)
- **Redundancy:** LOW - comprehensive role definition
- **Usage:** 13 references, used by test-builder agents and test-shared layer
- **Problem:** None - well-structured role definition

**Recommendation:** **KEEP AS-IS**
- Correctly defines a concept (agent role)
- Includes responsibilities, constraints, and language extensions
- Properly referenced in test-shared.yml layer

**Priority:** LOW - Already correct

---

### 10. test-runner-role.yml

**Current Content:**
```yaml
test_runner_role: |
  Agent responsible for executing tests and reporting results accurately.
  Separation from test_builder prevents reward hacking.

  Responsibilities:
  - Execute tests using appropriate test framework...
  - Report PASS/FAIL/SKIP results accurately with evidence...

  Constraints:
  - CANNOT modify test files or application code...
  - Must report actual test outcomes, not desired outcomes...
```

**Analysis:**
- **Classification:** This is a **definition** (defines what a test runner is and does)
- **Redundancy:** LOW - comprehensive role definition
- **Usage:** 7 references, used by test-runner agents
- **Problem:** None - well-structured role definition

**Recommendation:** **KEEP AS-IS**
- Correctly defines a concept (agent role)
- Paired with test-builder-role.yml for role separation
- Contains appropriate constraints and responsibilities

**Priority:** LOW - Already correct

---

### 11. guidance-test-scenarios.yml

**Current Content:**
```yaml
test_scenarios:
  task_completion_test:
    id: "task_completion_test"
    purpose: "Can agent complete task with guidance only?"
    description: |
      Validates that an agent can complete its assigned task using only the information
      provided in its guidance files...
    inputs: ...
    constraints: ...
    expected_outputs: ...

  reference_resolution_test: ...
  loop_context_test: ...
  subagent_spawning_test: ...
  cross_agent_dependency_test: ...
  friction_detection_test: ...
```

**Analysis:**
- **Classification:** This is a **definition** (defines test scenario structures)
- **Redundancy:** LOW - unique, comprehensive scenario definitions
- **Usage:** 32 references, heavily used in guidance testing
- **Problem:** None - well-structured with clear purpose, inputs, constraints, expected outputs
- **Strength:** Follows structured schema pattern consistently across all scenarios

**Recommendation:** **KEEP AS-IS**
- Excellent definition file - defines concepts and structures
- Provides reusable test scenario patterns
- High usage indicates value
- Contains categorization rules and execution patterns

**Priority:** LOW - Already well-designed

---

## Recommendations Summary

### Immediate Actions (High Priority)

1. **DEPRECATE test-roles.yml**
   - Content is duplicated in test-builder-role.yml and test-runner-role.yml
   - Update 15 references to use specific role files
   - Reduces token waste

2. **DEPRECATE testing-documentation.yml**
   - 100% project-specific (MyAgents paths, infrastructure)
   - Move content to MyAgents project documentation
   - Remove from shared framework

3. **DEPRECATE or GENERALIZE acceptable-skips.yml**
   - Contains specific test counts and project infrastructure references
   - Option A: Remove, move to MyAgents inputs
   - Option B: Generalize pattern, remove specific examples

### Medium Priority Actions

4. **RECLASSIFY test-structure.yml**
   - Move from definitions/ to guidelines/
   - Rename to test-organization.yml
   - Update references

5. **RECLASSIFY test-creation-principles.yml**
   - Move from definitions/ to guidelines/
   - Already correctly named as "principles"

6. **RECLASSIFY + GENERALIZE test-execution-workflow.yml**
   - Move from definitions/ to guidelines/
   - Remove project-specific commands (myagents studio)
   - Make skip counts configurable

7. **MERGE skipped-test.yml with acceptable-skips pattern**
   - Keep skipped-test.yml as concept definition
   - Add generic acceptable skip criteria
   - Move specific skip lists to project inputs

### Keep As-Is (Low Priority)

8. **testing-types.yml** - Correctly structured as definition index
9. **test-builder-role.yml** - Correct role definition
10. **test-runner-role.yml** - Correct role definition
11. **guidance-test-scenarios.yml** - Excellent scenario definitions

---

## Impact Assessment

### Files to Remove (3)
- test-roles.yml
- testing-documentation.yml
- acceptable-skips.yml (or heavily generalize)

### Files to Move to guidelines/ (3)
- test-structure.yml -> guidelines/test-organization.yml
- test-creation-principles.yml -> guidelines/test-creation-principles.yml
- test-execution-workflow.yml -> guidelines/test-execution-workflow.yml

### Files to Keep in definitions/ (5)
- testing-types.yml
- skipped-test.yml (with merged generic guidance)
- test-builder-role.yml
- test-runner-role.yml
- guidance-test-scenarios.yml

### Reference Updates Required
- ~60 file references need updating across the codebase
- test-shared.yml layer needs update to reflect reorganization
- testing.yml guideline needs update for new locations

---

## Migration Plan

### Phase 1: Remove Redundant Files
1. Deprecate test-roles.yml - update 15 references
2. Deprecate testing-documentation.yml - update 10 references
3. Generalize acceptable-skips.yml - update 18 references

### Phase 2: Reclassify Guidelines
1. Move test-structure.yml to guidelines/test-organization.yml
2. Move test-creation-principles.yml to guidelines/
3. Move test-execution-workflow.yml to guidelines/ (generalized)

### Phase 3: Update Layers
1. Update test-shared.yml with new paths
2. Update testing.yml guideline references
3. Verify all agent inputs.yml files
