# Batch 4: Planning and Orchestration Definitions Audit

**Audit Date:** 2026-01-11
**Batch Focus:** Planning systems, orchestration executor, agent organization
**Files Reviewed:** 11

---

## Summary Table

| File | Lines | Classification | Redundancy | Obsolete Risk | Recommended Action | Priority |
|------|-------|----------------|------------|---------------|-------------------|----------|
| `plan-folder-conventions.yml` | 26 | Definition | HIGH - subset of plans.yml | Low | **MERGE** into plans.yml | High |
| `plan-inputs.yml` | 36 | Guideline | LOW | Low | **RECLASSIFY** to guidelines/ | Medium |
| `plan-mmd-schema.yml` | 841 | Definition | LOW | Low | **KEEP** as-is | Low |
| `plan-structure-requirements.yml` | 60 | Definition | HIGH - extracted from plans.yml | Low | **MERGE** back or deprecate | High |
| `plans.yml` | 181 | Definition + Guideline | N/A (canonical) | Low | **SPLIT** definition vs guideline | Medium |
| `orchestration-executor-specification.yml` | 960 | Specification | LOW | Low | **KEEP** as-is (consider rename) | Low |
| `orchestration-test-scenarios.yml` | 919 | Test Specification | LOW | Low | **RELOCATE** to tests/ | Medium |
| `voting-system.yml` | 35 | Definition | LOW | HIGH - deprecated | **DEPRECATE** or archive | High |
| `agent-categories.yml` | 140 | Definition | LOW | Low | **KEEP** as-is | Low |
| `agent-context-files.yml` | 81 | Definition | LOW | Low | **KEEP** as-is | Low |
| `agent-loops.yml` | 222 | Definition | LOW | Partial | **KEEP** with cleanup | Medium |

---

## Detailed Analysis

### 1. plan-folder-conventions.yml

**Classification:** Definition (correctly placed)

**Content Summary:**
- 26 lines defining naming conventions for plan folders
- Pattern: `YYMMDD<RepoAbbrev>_<BranchName>`
- Folder structure: `live/` and `completed/` subfolders

**Analysis:**
- **Redundancy:** HIGH - The file header explicitly states "Full lifecycle details: modules/AgenticGuidance/assets/definitions/plans.yml"
- This file is a minimal subset of `plans.yml` created for "deploy agents that only need scaffolding information"
- The information here duplicates content from the canonical `plans.yml`

**Recommendation:** **MERGE**
- The original intent (reducing context for deploy agents) is valid
- However, maintaining two sources of truth is problematic
- Better approach: Use selective loading in agent inputs.yml with YAML anchors or path fragments
- If kept, should be renamed to indicate it's a "view" not a source

**Priority:** High - duplicated content risks drift

---

### 2. plan-inputs.yml

**Classification:** **GUIDELINE** (misclassified as definition)

**Content Summary:**
- 36 lines describing how to specify inputs in plans
- Includes "best practices" section with prescriptive rules
- Shows example YAML for input specification

**Analysis:**
- **Is it a definition?** Partially - defines input types (file, directory, pattern)
- **Is it a guideline?** YES - "Best practices" section is prescriptive ("Be specific", "Be minimal")
- The file primarily teaches agents HOW to specify inputs, not WHAT inputs are

**Recommendation:** **RECLASSIFY**
- Move to `assets/guidelines/plan-inputs.yml`
- Or split: keep type definitions in definitions/, move best practices to guidelines/

**Priority:** Medium - functional but misplaced

---

### 3. plan-mmd-schema.yml

**Classification:** Definition (correctly placed)

**Content Summary:**
- 841 lines - comprehensive schema for Plan-MMD files
- Covers header comments, node naming, subgraph structure, edge patterns
- Includes validation checklist and complete example
- Also includes execution metadata patterns (AGENT_ROUTING, FEEDBACK_TRIGGERS, STATUS)

**Analysis:**
- **Is it a definition?** YES - formally defines structural schema
- **Is it redundant?** LOW - some overlap with `orchestration-executor-specification.yml` but serves different purpose
- **Scope creep:** The "execution metadata patterns" section (lines 556-841) could arguably be in the executor spec

**Recommendation:** **KEEP AS-IS**
- This is a well-structured schema definition
- The execution metadata patterns belong here (they define MMD structure, not runtime behavior)
- Consider adding cross-references to executor spec for behavioral details

**Priority:** Low - good as-is

---

### 4. plan-structure-requirements.yml

**Classification:** Definition (correctly placed)

**Content Summary:**
- 60 lines extracted from `plans.yml`
- Header states "Extracted from plans.yml for reviewer validation"
- Defines required_fields, folder_structure, validation_checklist

**Analysis:**
- **Redundancy:** HIGH - explicitly derived from plans.yml
- **Purpose:** Created for planner-reviewer to have focused context
- **Problem:** Two sources of truth for the same information

**Recommendation:** **MERGE OR DEPRECATE**
- Option A: Merge back into plans.yml, have reviewer load full file
- Option B: Keep as specialized view, but add tooling to auto-generate from plans.yml
- Option C: Move plans.yml to be the "view" and this to be canonical (unlikely desired)

**Priority:** High - maintenance burden

---

### 5. plans.yml

**Classification:** **MIXED** - Definition + Guideline

**Content Summary:**
- 181 lines - canonical source for plan concepts
- Defines: plan types, lifecycle states, file taxonomy, two-level completion pattern
- Contains prescriptive rules: "DO/DON'T" section, "FENCE" statements, pattern recommendations

**Analysis:**
- **Definition content:** plan_lifecycle (4 states), file_taxonomy, scrap_file_taxonomy
- **Guideline content:** follow_on_work_pattern (DO/DON'T), two_level_completion_pattern behavior
- **Is it redundant?** No - this is the canonical source
- **Problem:** Mixes structural definitions with behavioral guidelines

**Recommendation:** **SPLIT (if strict separation needed)**
- Keep structural definitions here (lifecycle, taxonomy)
- Extract behavioral patterns to `guidelines/plan-management.yml`
- Alternative: Keep as-is but document that this is a "hybrid" file by design

**Priority:** Medium - works but violates classification principle

---

### 6. orchestration-executor-specification.yml

**Classification:** **SPECIFICATION** (correctly placed, but consider terminology)

**Content Summary:**
- 960 lines - comprehensive executor specification
- 9 sections: scope, routing, triggers, state model, fallbacks, protocol, integration, examples, validation
- Defines runtime behavior for a generic orchestration executor

**Analysis:**
- **Is it a definition?** More than that - it's a behavioral specification
- **Is it a guideline?** No - it specifies implementation, not general behavior rules
- **Redundancy:** LOW - some conceptual overlap with plan-mmd-schema.yml but different focus
- **Quality:** Excellent - comprehensive, well-structured, includes examples

**Recommendation:** **KEEP AS-IS**
- Consider whether "specification" should be a distinct category from "definition"
- Could rename to `orchestration-executor-spec.yml` for clarity
- Or move to a `specs/` directory if this pattern recurs

**Priority:** Low - excellent as-is

---

### 7. orchestration-test-scenarios.yml

**Classification:** **TEST SPECIFICATION** (misplaced in definitions/)

**Content Summary:**
- 919 lines defining test scenarios for orchestration executor
- Four major test suites: MMD parsing, agent routing, feedback triggers, state persistence
- Detailed test cases with inputs, expected outputs, validation criteria

**Analysis:**
- **Is it a definition?** NO - it defines tests, not concepts
- **Is it a guideline?** NO - it's test documentation
- **Proper location:** Should be in `tests/` or `assets/test-specifications/`
- **Relationship:** Directly validates `orchestration-executor-specification.yml`

**Recommendation:** **RELOCATE**
- Move to `tests/orchestration-executor/` or `assets/test-scenarios/`
- This is test documentation, not a definition
- Keeping it in definitions/ pollutes the namespace

**Priority:** Medium - functional but misplaced

---

### 8. voting-system.yml

**Classification:** Definition (correctly placed)

**Content Summary:**
- 35 lines defining multi-agent voting for cleanup decisions
- Defines thresholds (3/3 unanimous, 2/3, 1/3, 0/3)
- Documents agent roles in voting (cleaner-identify, orchestrator, cleaner-execute)

**Analysis:**
- **Obsolete Risk:** HIGH
- Header states "IMPLEMENTATION STATUS: SPECIFICATION ONLY" and "NOT YET IMPLEMENTED"
- Related cleaner agents are listed as NOT YET IMPLEMENTED in agent-categories.yml
- `agent-loops.yml` shows `cleaner-voting-loop` as `status: deprecated`
- Replaced by `cleaner-dependency-loop` per agent-loops.yml

**Recommendation:** **DEPRECATE OR ARCHIVE**
- The voting system concept has been superseded by dependency checking
- Add deprecation notice if keeping for historical reference
- Or move to `archived/` directory

**Priority:** High - deprecated content in active definitions

---

### 9. agent-categories.yml

**Classification:** Definition (correctly placed)

**Content Summary:**
- 140 lines defining 9 agent categories
- Canonical taxonomy: build, planner, test, cleaner, explore, teacher, deploy, documentation, orchestration
- Includes implementation status notes distinguishing implemented vs planned agents

**Analysis:**
- **Is it a definition?** YES - defines the agent organizational structure
- **Redundancy:** LOW - canonical source, referenced by other files
- **Quality:** Good - includes implementation status, boundaries, sub-agents

**Recommendation:** **KEEP AS-IS**
- This is the canonical agent taxonomy
- Consider moving implementation status notes to a separate tracking file
- The "patterns" section at the end could be extracted to guidelines

**Priority:** Low - good as-is

---

### 10. agent-context-files.yml

**Classification:** Definition (correctly placed)

**Content Summary:**
- 81 lines defining standard agent folder structure
- Documents required files: manifest.yml, inputs.yml, process.yml/process.mmd
- Explains YAML vs Mermaid process file formats

**Analysis:**
- **Is it a definition?** YES - defines file structure conventions
- **Redundancy:** LOW - unique content not duplicated elsewhere
- **Quality:** Good - clear documentation of agent file structure

**Recommendation:** **KEEP AS-IS**
- Valuable reference for agent structure
- Well-organized and focused

**Priority:** Low - good as-is

---

### 11. agent-loops.yml

**Classification:** Definition (correctly placed)

**Content Summary:**
- 222 lines defining loop types and patterns
- 10 loop types: test-fix, audit-test-fix, cleaner-voting (deprecated), cleaner-dependency, documentation, user-story-validation, exploration, planner, guidance-test, agent-self-review
- Includes phase ordering and mandatory loops

**Analysis:**
- **Is it a definition?** YES - defines loop structures conceptually
- **Partial Obsolescence:** `cleaner-voting-loop` is marked deprecated
- **Quality:** Good separation of concerns - notes that behavioral guidelines are in separate file
- **Note:** Header correctly points to `guidelines/iteration.yml` for behavioral guidelines

**Recommendation:** **KEEP WITH CLEANUP**
- Remove or archive the deprecated `cleaner-voting-loop` entry
- Consider adding more "alternative_to" and "selection_criteria" fields for consistency
- The `guidance-self-review-loop` section is particularly well-documented as an example

**Priority:** Medium - functional but needs deprecated entry cleanup

---

## Recommendations Summary

### High Priority Actions

| Action | File(s) | Rationale |
|--------|---------|-----------|
| **MERGE** | plan-folder-conventions.yml | Duplicates plans.yml; merge back or convert to generated view |
| **MERGE OR DEPRECATE** | plan-structure-requirements.yml | Extracted from plans.yml; creates dual source of truth |
| **DEPRECATE** | voting-system.yml | System deprecated in agent-loops.yml; cleaner agents not implemented |

### Medium Priority Actions

| Action | File(s) | Rationale |
|--------|---------|-----------|
| **RECLASSIFY** | plan-inputs.yml | Contains "best practices" guidelines, not just definitions |
| **SPLIT** | plans.yml | Mixes definitions with DO/DON'T behavioral guidelines |
| **RELOCATE** | orchestration-test-scenarios.yml | Test specification, not a definition; belongs in tests/ |
| **CLEANUP** | agent-loops.yml | Remove deprecated cleaner-voting-loop entry |

### Low Priority (Keep As-Is)

| File | Status |
|------|--------|
| plan-mmd-schema.yml | Well-structured schema definition |
| orchestration-executor-specification.yml | Comprehensive specification |
| agent-categories.yml | Canonical agent taxonomy |
| agent-context-files.yml | Clear structure documentation |

---

## Cross-Reference Analysis

### Files That Reference Each Other

```
plans.yml (canonical)
  ├── plan-folder-conventions.yml (subset)
  ├── plan-structure-requirements.yml (extracted)
  └── guidelines/plan-completion.yml (referenced for examples)

orchestration-executor-specification.yml
  ├── plan-mmd-schema.yml (structural schema it interprets)
  ├── agent-loops.yml (loop definitions)
  ├── agent-categories.yml (agent type resolution)
  └── orchestration-test-scenarios.yml (validation tests)

agent-loops.yml
  ├── voting-system.yml (deprecated, replaced by cleaner-dependency-loop)
  └── guidelines/iteration.yml (behavioral guidelines)

agent-categories.yml
  ├── fence-build-deploy.yml (boundary fence)
  └── agent-context-files.yml (file structure)
```

### Consolidation Opportunities

1. **Plan-related files:** Could consolidate plan-folder-conventions.yml and plan-structure-requirements.yml back into plans.yml, using YAML anchors or agent-specific views

2. **Orchestration files:** Keep separate - they serve distinct purposes (schema vs runtime spec vs tests)

3. **Agent meta-files:** Keep separate - agent-categories.yml, agent-context-files.yml, and agent-loops.yml each serve distinct roles

---

## Implementation Notes

### For MERGE actions:
- Use git history to track the merge
- Update all files that reference the merged file
- Consider using YAML fragment references for agent-specific views

### For RECLASSIFY actions:
- Move file to new location
- Update all references in other definition/guideline files
- Update agent inputs.yml files that load the file

### For DEPRECATE actions:
- Add clear deprecation header with replacement reference
- Consider moving to `archived/` subdirectory
- Remove from agent inputs.yml files that load it

---

## File Paths Reference

All files analyzed are at:
```
/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/
```

Files:
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/plan-folder-conventions.yml`
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/plan-inputs.yml`
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/plan-mmd-schema.yml`
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/plan-structure-requirements.yml`
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/plans.yml`
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/orchestration-executor-specification.yml`
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/orchestration-test-scenarios.yml`
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/voting-system.yml`
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/agent-categories.yml`
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/agent-context-files.yml`
- `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/agent-loops.yml`
