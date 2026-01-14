# Batch 3: Validation Strategies - Definition Audit

**Created**: 2026-01-11
**Source**: `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/`
**Scope**: 10 strategy files related to testing/validation

---

## Summary Table

| File | Current Type | Correct Type | Status | Recommendation | Priority |
|------|-------------|--------------|--------|----------------|----------|
| strategy-agent-blind-test.yml | Definition | **Guideline** | Misclassified | Reclassify to guidelines/ | High |
| strategy-agent-review-loop.yml | Definition | Definition | Correct | Keep as-is | Low |
| strategy-documentation-validation.yml | Definition | **Guideline** | Misclassified | Reclassify to guidelines/ | Medium |
| strategy-fresh-environment.yml | Definition | **Guideline** | Misclassified | Reclassify to guidelines/ | Medium |
| strategy-guidance-blind-test.yml | Definition | **Guideline** | Misclassified | Reclassify to guidelines/ | High |
| strategy-multi-layer.yml | Definition | Definition | Correct | Keep as-is | Low |
| strategy-test-suite.yml | Definition | Definition | Correct | Keep as-is | Low |
| strategy-user-acceptance.yml | Definition | **Guideline** | Misclassified | Reclassify to guidelines/ | High |
| strategy-user-simulation.yml | Definition | Definition | Correct | Keep as-is | Low |
| strategy-validation.yml | Definition | Definition | Correct | Keep as-is (meta-index) | Low |

**Summary**: 5 files correctly classified, 5 files need reclassification to guidelines/

---

## Detailed Analysis

### 1. strategy-agent-blind-test.yml

**Size**: 93 lines (extremely long for a definition)

**Content Analysis**:
- Contains "CRITICAL" warnings and "PROHIBITED BEHAVIOR" / "REQUIRED BEHAVIOR" sections
- Includes detailed execution checklists with imperative statements
- Specifies three testing layers with implementation details
- Contains "VALIDATION CHECKLIST (must answer YES to all before reporting PASS)"
- References specific process files and documentation paths

**Classification**: **GUIDELINE**

**Reasoning**:
- Definitions answer "what is X?" - this file prescribes "how to act"
- Contains imperative directives ("MUST execute", "Do NOT substitute")
- The checklist structure is inherently prescriptive, not descriptive
- A definition would say "agent-blind-test is a strategy where..." (2-3 sentences)
- This file is 93 lines of behavioral rules and implementation guidance

**Redundancy Check**:
- Partially overlaps with strategy-user-acceptance.yml (both discuss agent UAT)
- Referenced by testing.yml guideline as an input
- Referenced by testing-types.yml as detail for user_simulator type

**Recommendation**: **Reclassify to guidelines/**
- Extract the pure definition (first 5-6 lines) to a slim definition file
- Move the behavioral rules, checklists, and execution patterns to guidelines/

**Priority**: High - this is heavily prescriptive content in definitions/

---

### 2. strategy-agent-review-loop.yml

**Size**: 8 lines

**Content Analysis**:
```yaml
agent-review-loop: |
    A testing strategy where an agent is spawned to review the work done
    by the previous agent/s...
```

**Classification**: **Definition (Correct)**

**Reasoning**:
- Answers "what is agent-review-loop?" concisely
- Provides justification for the concept
- Does not prescribe detailed behaviors or checklists
- Stable, descriptive, broadly applicable

**Redundancy Check**:
- No obvious overlap with other files
- Referenced by testing.yml guideline
- Referenced by testing-types.yml for "audit" type

**Recommendation**: **Keep as-is**

**Priority**: Low

---

### 3. strategy-documentation-validation.yml

**Size**: 46 lines

**Content Analysis**:
- Contains "Test approach:" section with numbered steps
- Lists "What this catches:" (actionable checklist)
- Contains "Success criteria:" with specific requirements
- References "Phase 7" and "Phase 7b" of pre-release checklist
- Contains "must pass before documentation sign-off" prescriptions

**Classification**: **GUIDELINE**

**Reasoning**:
- A definition would say "documentation-validation-testing is X"
- This file prescribes test steps, success criteria, and integration requirements
- Contains actionable requirements ("must pass before")
- The structure is a process guide, not a concept explanation

**Redundancy Check**:
- Overlaps conceptually with strategy-guidance-blind-test.yml (both test documentation)
- strategy-guidance-blind-test tests internal guidance; this tests external documentation
- Could potentially merge with documentation testing guidance

**Recommendation**: **Reclassify to guidelines/**
- Keep a 3-4 line definition explaining the concept
- Move test approach, success criteria, and integration guidance to guidelines/

**Priority**: Medium

---

### 4. strategy-fresh-environment.yml

**Size**: 38 lines

**Content Analysis**:
- Contains "MANDATORY before any release" (prescriptive fence)
- Lists "Test environment requirements:" with specific constraints
- Contains "Test scenarios:" numbered list (implementation detail)
- Contains "Success criteria:" with specific requirements
- Contains "Integration with release process:" with phase references

**Classification**: **GUIDELINE**

**Reasoning**:
- The "MANDATORY" statement is a fence, which belongs in guidelines
- Contains prescriptive requirements, not just concept explanation
- Test scenarios and success criteria are implementation guidance
- Phase references ("Phase 5 of pre-release checklist") are procedural

**Redundancy Check**:
- Unique concept, no direct duplication
- Referenced by testing.yml guideline
- Referenced by testing-types.yml for "service_test" type
- strategy-multi-layer.yml references fresh environment as layer 2

**Recommendation**: **Reclassify to guidelines/**
- Keep slim definition (first 3-4 lines)
- Move requirements, scenarios, criteria to guidelines/

**Priority**: Medium

---

### 5. strategy-guidance-blind-test.yml

**Size**: 215 lines (extremely long)

**Content Analysis**:
- Contains "CRITICAL REQUIREMENTS" section with all-caps warnings
- Contains "PROHIBITED BEHAVIORS" and "REQUIRED BEHAVIORS" lists
- Contains 5 detailed TEST SCENARIOS with success/failure indicators
- Contains "VALIDATION CHECKLIST" with numbered sections
- Contains "FAILURE REPORTING STRUCTURE" with templates
- Contains "EXECUTION PATTERN" with orchestration flow

**Classification**: **GUIDELINE** (strongly)

**Reasoning**:
- This is the most heavily prescriptive file in the batch
- 215 lines of behavioral rules, templates, and checklists
- A definition would be 5-10 lines explaining the concept
- Contains implementation templates and reporting structures
- The entire file is "how to act" not "what is X"

**Redundancy Check**:
- Related to strategy-agent-blind-test.yml (explicitly compared in the file)
- Unique in testing internal agent guidance vs external documentation
- Very detailed - possibly over-specified for current needs

**Recommendation**: **Reclassify to guidelines/**
- Create slim definition (first 4-5 lines of CONCEPT section)
- Move all requirements, scenarios, checklists to guidelines/
- Consider whether 215 lines is over-engineering for this concept

**Priority**: High - most egregious misclassification in the batch

---

### 6. strategy-multi-layer.yml

**Size**: 65 lines

**Content Analysis**:
- Marked "STATUS: OPTIONAL" in header
- Contains `multi-layer-testing:` with structured YAML
- Lists `testing_layers:` with layer names and what each catches
- Contains `when_to_use:` and `alternative_strategies:` sections

**Classification**: **Definition (Correct)**

**Reasoning**:
- Describes what multi-layer testing is and its components
- The "when_to_use" is descriptive (explains applicability), not prescriptive
- Alternative strategies section is a reference, not rules
- Well-structured definition with appropriate scope

**Redundancy Check**:
- Overlaps with strategy-validation.yml (both describe testing strategies)
- strategy-validation.yml is higher-level (strategy selection)
- strategy-multi-layer.yml is one specific strategy option
- Could consider merging, but they serve different granularities

**Recommendation**: **Keep as-is**
- Good example of a well-scoped definition
- Appropriate length and structure

**Priority**: Low

---

### 7. strategy-test-suite.yml

**Size**: 8 lines

**Content Analysis**:
```yaml
test-suite: |
    A testing strategy where reproducible tests that validate the success criteria.
    Includes:
    - integration tests: validate components work together as expected
    - e2e tests: validate a workflow or chain of workflows.
    Excludes:
    - Unit tests: should be used only during active development...
```

**Classification**: **Definition (Correct)**

**Reasoning**:
- Concisely defines what a test-suite strategy is
- Lists what's included/excluded (descriptive)
- Does not prescribe behaviors or checklists
- Appropriate scope and length for a definition

**Redundancy Check**:
- Referenced by testing-types.yml for "end2end" type
- Referenced by testing.yml guideline
- Unique, no duplication

**Recommendation**: **Keep as-is**

**Priority**: Low

---

### 8. strategy-user-acceptance.yml

**Size**: 62 lines

**Content Analysis**:
- Contains "CRITICAL DISTINCTION" and "CRITICAL PREREQUISITE" warnings
- Contains "Pre-test requirements:" with numbered steps
- Contains "Test execution:" with numbered steps
- Contains "Success criteria:" with specific requirements
- Contains "Why this matters:" explanatory section

**Classification**: **GUIDELINE**

**Reasoning**:
- Contains prescriptive "CRITICAL" statements
- Numbered pre-test requirements are procedural guidance
- Test execution steps are implementation instructions
- Success criteria prescribe what must be achieved
- Much of this is "how to do UAT" not "what is UAT"

**Redundancy Check**:
- Significant overlap with strategy-agent-blind-test.yml (both discuss agent UAT)
- Overlap with strategy-user-simulation.yml (both relate to user testing)
- The distinction between "Agent UAT" and user-simulation is somewhat blurry
- testing.yml guideline references this for UAT implementation options

**Recommendation**: **Reclassify to guidelines/**
- Keep slim definition (types of UAT: agent vs human)
- Move requirements, execution steps, criteria to guidelines/
- Consider consolidating with overlapping strategy files

**Priority**: High - heavily prescriptive, overlaps with other files

---

### 9. strategy-user-simulation.yml

**Size**: 25 lines

**Content Analysis**:
```yaml
user-simulation-testing: |
    A testing strategy where builder agents validate functionality
    by simulating the user experience...

    Key principles:
    - Execute entrypoints as a user would...

    Execution approach:
    1. Builder agent implements minimal components...
```

**Classification**: **Definition (Marginally Correct)**

**Reasoning**:
- Primarily describes what user-simulation-testing is
- "Key principles" section is borderline (principles vs rules)
- "Execution approach" is borderline (description vs prescription)
- Shorter and more conceptual than strategy-user-acceptance.yml
- Could go either way, but leans definition

**Redundancy Check**:
- Related to strategy-user-acceptance.yml (user testing theme)
- Related to strategy-agent-blind-test.yml (agent testing theme)
- This focuses on builder agents validating during development
- Others focus on UAT phases after development

**Recommendation**: **Keep as-is** (borderline)
- The execution approach could be trimmed
- Core concept is definitional

**Priority**: Low

---

### 10. strategy-validation.yml

**Size**: 132 lines

**Content Analysis**:
- Marked "STATUS: OPTIONAL" in header
- Contains `validation-strategies:` meta-structure
- Lists available strategies (three-layer, single-layer, etc.)
- Contains `selection_guidance:` with decision factors
- Contains `fence:` referencing UAT requirements

**Classification**: **Definition (Correct - Meta-Index)**

**Reasoning**:
- This is a strategy index/reference document
- Describes what validation strategy options exist
- Selection guidance is informational, not prescriptive
- The fence section references testing.yml (correctly delegating prescription)
- Serves as a high-level overview document

**Redundancy Check**:
- Overlaps with strategy-multi-layer.yml (full-coverage references it)
- Acts as an index to other strategy files
- Useful as a single entry point for strategy selection

**Recommendation**: **Keep as-is**
- Valuable as a meta-index/overview
- Correctly references specific strategies for details
- Fence properly delegates to testing.yml

**Priority**: Low

---

## Redundancy Analysis

### Overlap Groups

**Group A: Agent/User Simulation Testing**
- strategy-agent-blind-test.yml
- strategy-user-acceptance.yml
- strategy-user-simulation.yml

These three files all address testing via agents simulating users. The distinctions are:
- agent-blind-test: Subagent tests with minimal documentation
- user-acceptance: UAT categories (agent vs human) and prerequisites
- user-simulation: Builder agents validating during development

**Recommendation**: Consider consolidating after reclassification. The behavioral rules could merge into a single `testing-agent-simulation.yml` guideline.

**Group B: Documentation/Guidance Testing**
- strategy-documentation-validation.yml
- strategy-guidance-blind-test.yml

Both test documentation completeness but:
- documentation-validation: External docs (README, user docs)
- guidance-blind-test: Internal guidance (process.yml, inputs.yml)

**Recommendation**: Keep separate - they test different artifacts. But both should be guidelines.

**Group C: Strategy Overview**
- strategy-validation.yml (high-level options)
- strategy-multi-layer.yml (specific detailed strategy)

**Recommendation**: Keep separate - different levels of abstraction.

---

## Recommendations Summary

### Action Items

#### High Priority (Reclassify)

1. **strategy-agent-blind-test.yml**
   - Create: `definitions/strategy-agent-blind-test.yml` (5-6 line definition)
   - Create: `guidelines/testing-agent-blind-test.yml` (behavioral rules, checklists)
   - Update: testing.yml references

2. **strategy-guidance-blind-test.yml**
   - Create: `definitions/strategy-guidance-blind-test.yml` (5-6 line definition)
   - Create: `guidelines/testing-guidance-blind-test.yml` (requirements, scenarios, checklists)
   - Consider: Is 215 lines over-specified? May need trimming.

3. **strategy-user-acceptance.yml**
   - Create: `definitions/strategy-user-acceptance.yml` (10 line definition - UAT types)
   - Create: `guidelines/testing-user-acceptance.yml` (prerequisites, execution, criteria)
   - Update: testing.yml references

#### Medium Priority (Reclassify)

4. **strategy-documentation-validation.yml**
   - Create: `definitions/strategy-documentation-validation.yml` (5 line definition)
   - Create: `guidelines/testing-documentation-validation.yml` (approach, criteria)

5. **strategy-fresh-environment.yml**
   - Create: `definitions/strategy-fresh-environment.yml` (4 line definition)
   - Create: `guidelines/testing-fresh-environment.yml` (requirements, scenarios)

#### Low Priority (Keep As-Is)

6. **strategy-agent-review-loop.yml** - Correct classification
7. **strategy-multi-layer.yml** - Correct classification
8. **strategy-test-suite.yml** - Correct classification
9. **strategy-user-simulation.yml** - Correct classification (borderline)
10. **strategy-validation.yml** - Correct classification (meta-index)

### Post-Reclassification Updates

After reclassifying files, update references in:
- `guidelines/testing.yml` - inputs section
- `definitions/testing-types.yml` - detail references
- Any agent process files that load these definitions

### Naming Convention

For reclassified guideline files, consider adopting:
- `guidelines/testing-*.yml` (testing domain)
- Rather than `guidelines/strategy-*.yml`

This better reflects that these are guidelines about testing behaviors, not just strategy descriptions.

---

## Appendix: Classification Criteria Applied

**Definition Criteria**:
- Names a concept and explains "what is X?"
- Descriptive, stable, broadly applicable
- Typically 5-30 lines
- No imperative statements or checklists
- No "MUST", "CRITICAL", "PROHIBITED" language

**Guideline Criteria**:
- Shapes behavior with rules-of-thumb
- Prescriptive, actionable, "how to act"
- May include fences, requirements, checklists
- Contains imperative language
- Tells agents what to do/not do

**Key Indicators of Misclassification**:
- All-caps warnings (CRITICAL, PROHIBITED, MANDATORY)
- Numbered execution steps
- Success criteria / validation checklists
- Phase references (integration with release process)
- Templates and reporting structures
- Length > 50 lines (typically indicates behavioral content)
