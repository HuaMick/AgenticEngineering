# Batch 6: Principles & Miscellaneous Definitions Audit

**Created:** 2026-01-11
**Status:** Analysis Complete
**Source:** `/home/code/AgenticEngineering-agenticguidance/modules/AgenticGuidance/assets/definitions/`

## Executive Summary

This batch contains 26 files spanning:
- Core principles (8 files): context, encapsulation, change management, separation
- Verification patterns (5 files): outcome, model-first, component, success criteria
- Technical references (6 files): paths, fragments, CLI, README patterns
- Project-specific (4 files): preserved files, leftovers, studio tests, workflow tests
- Domain-specific (3 files): user stories, exploration principles, reward hacking

**Key Findings:**
- 11 files are misclassified (should be guidelines, not definitions)
- 4 files have significant redundancy with other files
- 2 files are near-duplicates (should be merged)
- 3 files appear project-specific and may be obsolete
- 6 files are correctly classified and well-structured

---

## Summary Classification Table

| File | Current Type | Should Be | Redundant? | Action | Priority |
|------|-------------|-----------|------------|--------|----------|
| exploration-principles.yml | Definition | **Guideline** | No | Reclassify | Medium |
| knowledge-encapsulation.yml | Definition | Definition | Partial | Keep, link | Low |
| minimal-sufficient-change.yml | Definition | **Guideline** | Partial | Reclassify | Medium |
| overengineering.yml | Definition | Definition | No | Keep | Low |
| role-separation.yml | Definition | **Guideline** | Partial | Merge with separation-of-concerns | Medium |
| separation-of-concerns.yml | Definition | **Guideline** | Yes | Merge into role-separation | Medium |
| context-minimisation.yml | Definition | Definition | Yes | Keep (canonical) | Low |
| generalized-vs-specific.yml | Definition | **Guideline** | No | Reclassify | Low |
| iteration-approach.yml | Definition | **Guideline** | Partial | Reclassify | Low |
| reward-hacking.yml | Definition | Definition+Guideline | No | Split or restructure | Medium |
| root-cause-analysis.yml | Definition | **Guideline** | No | Reclassify | Low |
| model-first-verification.yml | Definition | **Guideline** | Partial | Review overlap | Low |
| outcome-verification.yml | Definition | **Guideline** | Partial | Keep, link | Low |
| component-verification.yml | Definition | **Guideline** | Partial | Review overlap | Low |
| success-criteria.yml | Definition | Definition | Partial | Keep (canonical) | Low |
| success-criteria-teacher.yml | Definition | **Guideline** | Yes | Deprecate/merge | High |
| signal-and-noise.yml | Definition | Definition | No | Keep (comprehensive) | Low |
| readme-context.yml | Definition | **Guideline** | No | Reclassify | Low |
| fragment-references.yml | Definition | Definition | No | Keep | Low |
| path-resolution.yml | Definition | Definition | No | Keep | Low |
| cli-commands.yml | Definition | Reference | No | Review location | Low |
| preserved-files.yml | Definition | **Guideline** | No | Reclassify | Low |
| leftover-folders.yml | Definition | Definition | No | Keep | Low |
| studio-integration-tests.yml | Definition | Reference | Potentially obsolete | Review usage | Medium |
| workflow-test-readme.yml | Definition | **Guideline** | Sparse | Deprecate or expand | Medium |
| user-stories.yml | Definition | Definition | No | Keep | Low |

---

## Detailed Analysis

### 1. Core Principles (8 files)

#### exploration-principles.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE - 74 lines of prescriptive rules for explorer agents
- **Content:** 5 numbered principles (Discover First, Context Minimization, Less Is More, Parallel Execution, Read-Only), scope boundaries, quality criteria
- **Analysis:** This is entirely prescriptive ("Follow these principles", "DO NOT cross boundaries"). It tells agents how to behave, not what concepts mean.
- **Recommendation:** Move to `guidelines/exploration-principles.yml`
- **Priority:** Medium

#### knowledge-encapsulation.yml
- **Current Classification:** Definition
- **Actual Nature:** Definition + Guideline hybrid (appropriate as definition)
- **Content:** Defines the principle, provides test question, examples, why/when patterns
- **Redundancy:** Partial overlap with `context-minimisation.yml` and `signal-and-noise.yml` (noted in "Related" section)
- **Analysis:** Well-structured definition with practical examples. The "Teacher application" section is slightly guideline-like but acceptable.
- **Recommendation:** Keep as definition, ensure cross-references are current
- **Priority:** Low

#### minimal-sufficient-change.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE - prescriptive rules about change scope
- **Content:** Principles list, "Why minimal", "Why sufficient", Balance guidance
- **Redundancy:** Related to `overengineering.yml` (noted), also overlaps with `guidelines/less-is-more.yml`
- **Analysis:** Uses imperative language ("Make the smallest change", "Resist the urge", "Stop when"). This is behavioral guidance.
- **Recommendation:** Move to guidelines or merge with `less-is-more.yml`
- **Priority:** Medium

#### overengineering.yml
- **Current Classification:** Definition
- **Actual Nature:** Definition (correctly classified)
- **Content:** Defines what overengineering is with examples
- **Analysis:** Concise, descriptive definition of the anti-pattern. Appropriate scope.
- **Recommendation:** Keep as-is
- **Priority:** Low

#### role-separation.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE - prescriptive behavioral rules
- **Content:** Principle statement, "Why separate", Division patterns, Anti-patterns
- **Redundancy:** HIGH overlap with `separation-of-concerns.yml`
- **Analysis:** Contains actionable patterns ("Builders receive build context, not test context"). Very similar purpose to separation-of-concerns but more detailed.
- **Recommendation:** Merge `separation-of-concerns.yml` into this file, move to guidelines
- **Priority:** Medium

#### separation-of-concerns.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE (9 lines, very sparse)
- **Content:** Single principle + example
- **Redundancy:** REDUNDANT with `role-separation.yml`
- **Analysis:** This is essentially a subset of role-separation.yml. Only 9 lines total, 4 of which are whitespace.
- **Recommendation:** Deprecate, merge content into `role-separation.yml`
- **Priority:** Medium

#### context-minimisation.yml (in definitions/)
- **Current Classification:** Definition
- **Actual Nature:** Definition (correctly classified)
- **Content:** Core principle statement + justification
- **Redundancy:** Note: A `guidelines/context-minimisation.yml` also exists with expanded rules
- **Analysis:** This is the canonical definition. The guideline file properly references this definition.
- **Recommendation:** Keep as-is (canonical definition)
- **Priority:** Low

#### generalized-vs-specific.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE (but misnamed/incomplete)
- **Content:** 7 lines about definitions being reusable vs project-specific
- **Analysis:** This is meta-guidance about how to write definitions. It tells authors what to do ("Definitions/guidelines should be reusable").
- **Recommendation:** Reclassify to guidelines or merge into definition.yml/guideline.yml meta-files
- **Priority:** Low

---

### 2. Verification Patterns (5 files)

#### iteration-approach.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE
- **Content:** 11 lines of builder iteration rules
- **Analysis:** Entirely prescriptive ("Build one component at a time", "Verify compilation", "Avoid premature optimizations")
- **Recommendation:** Move to guidelines, possibly merge with `guidelines/iteration.yml` if exists
- **Priority:** Low

#### reward-hacking.yml
- **Current Classification:** Definition
- **Actual Nature:** Definition + Guideline hybrid
- **Content:** Definition (lines 1-13) + Detailed signal patterns (lines 14-44)
- **Analysis:** First section defines the concept, second section is diagnostic guidelines. Well-structured but could be split.
- **Recommendation:** Keep as-is OR split into definition + guideline
- **Priority:** Medium (if splitting desired)

#### root-cause-analysis.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE (9 lines)
- **Content:** Imperative statement + pattern
- **Analysis:** "Fix the source, not the symptom" is actionable guidance. The pattern is a process prescription.
- **Recommendation:** Move to guidelines
- **Priority:** Low

#### model-first-verification.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE
- **Content:** 31 lines of verification guidance for generators
- **Redundancy:** Partial overlap with `outcome-verification.yml` (noted in "See also")
- **Analysis:** Prescriptive content ("Verify what was generated", "Check the generated artifact exists"). Has good/anti-patterns.
- **Recommendation:** Move to guidelines, ensure relationship with outcome-verification is clear
- **Priority:** Low

#### outcome-verification.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE (9 lines)
- **Content:** Brief imperative + examples
- **Redundancy:** Referenced by model-first-verification.yml and success-criteria.yml
- **Analysis:** Very concise behavioral guidance. Works as a lightweight reference.
- **Recommendation:** Keep as lightweight definition/principle, cross-reference from related guidelines
- **Priority:** Low

#### component-verification.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE
- **Content:** 12 lines of builder verification rules
- **Redundancy:** Partial overlap with `iteration-approach.yml`
- **Analysis:** Prescriptive checklist for builder agents. Clear scope distinction from comprehensive testing.
- **Recommendation:** Move to guidelines
- **Priority:** Low

#### success-criteria.yml
- **Current Classification:** Definition
- **Actual Nature:** Definition (correctly classified)
- **Content:** 26 lines defining what success criteria are
- **Redundancy:** Partial with `success-criteria-teacher.yml`
- **Analysis:** Good definition with examples of good/bad criteria and test question. This is the canonical source.
- **Recommendation:** Keep as-is
- **Priority:** Low

#### success-criteria-teacher.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE (sparse, 10 lines)
- **Content:** Brief guidance on outcome-based criteria
- **Redundancy:** REDUNDANT with `success-criteria.yml`
- **Analysis:** This is a subset of success-criteria.yml with no unique content. The "teacher" suffix suggests it was meant for a specific agent but the content is generic.
- **Recommendation:** Deprecate, merge any unique content into success-criteria.yml
- **Priority:** High

---

### 3. Signal & Context (2 files)

#### signal-and-noise.yml
- **Current Classification:** Definition
- **Actual Nature:** Definition (correctly classified)
- **Content:** 151 lines - comprehensive definition of signal, noise, signal-to-noise ratio, maximizing/minimizing techniques, examples
- **Analysis:** Well-structured, comprehensive definition file. Contains both descriptive definitions and practical examples. The examples section is borderline guideline but serves to illustrate the concepts.
- **Recommendation:** Keep as-is (canonical reference for signal/noise)
- **Priority:** Low

---

### 4. Technical References (5 files)

#### readme-context.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE (113 lines)
- **Content:** readme-as-context pattern, structure guidelines, manifest relationship, when-not-to-use
- **Analysis:** Mostly prescriptive ("Structure READMEs for effective agent consumption", "Clear headings: Use consistent heading hierarchy"). The pattern description is definitional but the bulk is guidance.
- **Recommendation:** Move to guidelines
- **Priority:** Low

#### fragment-references.yml
- **Current Classification:** Definition
- **Actual Nature:** Definition (correctly classified)
- **Content:** 138 lines documenting fragment reference syntax and resolution rules
- **Analysis:** Technical reference documentation. Describes what fragment references are and how they work. Contains valid/invalid examples and resolution rules.
- **Recommendation:** Keep as-is
- **Priority:** Low

#### path-resolution.yml
- **Current Classification:** Definition
- **Actual Nature:** Definition (correctly classified)
- **Content:** 110 lines documenting path resolution semantics
- **Analysis:** Technical reference documentation. Describes path resolution rules, roots, conventions. Contains agent guidance section but primarily definitional.
- **Recommendation:** Keep as-is
- **Priority:** Low

#### cli-commands.yml
- **Current Classification:** Definition
- **Actual Nature:** Reference document
- **Content:** 96 lines documenting CLI commands
- **Analysis:** This is command reference documentation. Not a definition in the conceptual sense, but a technical reference. Location in definitions/ is acceptable.
- **Recommendation:** Keep as-is (consider future move to a `references/` folder if one is created)
- **Priority:** Low

---

### 5. Project-Specific (4 files)

#### preserved-files.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE (project-specific)
- **Content:** 26 lines listing files the cleaner agent must never remove
- **Analysis:** This is a specific constraint/rule for cleaner agents. The content is prescriptive ("CRITICAL: The following files must NEVER be removed").
- **Recommendation:** Move to guidelines, possibly to a cleaner-specific guidelines file
- **Priority:** Low

#### leftover-folders.yml
- **Current Classification:** Definition
- **Actual Nature:** Definition (correctly classified)
- **Content:** 18 lines defining what leftover folders are and detection process
- **Analysis:** Defines the concept of leftover folders with detection criteria. Useful for cleaner agents.
- **Recommendation:** Keep as-is
- **Priority:** Low

#### studio-integration-tests.yml
- **Current Classification:** Definition
- **Actual Nature:** Reference/Checklist
- **Content:** 15 lines listing tests requiring LangGraph Studio
- **Analysis:** Project-specific test list. May be obsolete if the test infrastructure has changed. Should verify if these tests still exist.
- **Recommendation:** Review usage, potentially deprecate if obsolete
- **Priority:** Medium

#### workflow-test-readme.yml
- **Current Classification:** Definition
- **Actual Nature:** GUIDELINE (very sparse, 6 lines)
- **Content:** Brief mention that workflow tests may have READMEs
- **Analysis:** Too sparse to be useful. Either expand with actual guidance or deprecate.
- **Recommendation:** Deprecate or expand significantly
- **Priority:** Medium

---

### 6. Domain-Specific (1 file)

#### user-stories.yml
- **Current Classification:** Definition
- **Actual Nature:** Definition (correctly classified)
- **Content:** 27 lines defining user story structure and usage
- **Analysis:** Well-structured definition explaining user story format and orchestration usage. Includes both structural definition and usage context.
- **Recommendation:** Keep as-is
- **Priority:** Low

---

## Recommendations Summary

### High Priority Actions

1. **Deprecate `success-criteria-teacher.yml`**
   - Redundant with `success-criteria.yml`
   - No unique content
   - Action: Remove after verifying no direct references

### Medium Priority Actions

2. **Merge `separation-of-concerns.yml` into `role-separation.yml`**
   - Near-duplicate content
   - role-separation is more comprehensive
   - Action: Combine, move result to guidelines/

3. **Reclassify to Guidelines (batch move):**
   - `exploration-principles.yml` - comprehensive prescriptive content
   - `minimal-sufficient-change.yml` - behavioral rules (or merge with less-is-more.yml)

4. **Review obsolescence:**
   - `studio-integration-tests.yml` - verify tests still exist
   - `workflow-test-readme.yml` - too sparse, expand or deprecate

### Low Priority Actions

5. **Reclassify to Guidelines (single files):**
   - `generalized-vs-specific.yml`
   - `iteration-approach.yml`
   - `root-cause-analysis.yml`
   - `model-first-verification.yml`
   - `component-verification.yml`
   - `readme-context.yml`
   - `preserved-files.yml`

6. **Keep as-is (correctly classified):**
   - `overengineering.yml`
   - `context-minimisation.yml`
   - `knowledge-encapsulation.yml`
   - `success-criteria.yml`
   - `signal-and-noise.yml`
   - `fragment-references.yml`
   - `path-resolution.yml`
   - `cli-commands.yml`
   - `leftover-folders.yml`
   - `user-stories.yml`
   - `reward-hacking.yml` (hybrid acceptable)
   - `outcome-verification.yml` (lightweight, works as principle)

---

## Action Checklist

```
[ ] HIGH: Deprecate success-criteria-teacher.yml (check references first)
[ ] MEDIUM: Merge separation-of-concerns.yml into role-separation.yml
[ ] MEDIUM: Move exploration-principles.yml to guidelines/
[ ] MEDIUM: Review minimal-sufficient-change.yml vs less-is-more.yml
[ ] MEDIUM: Verify studio-integration-tests.yml is current
[ ] MEDIUM: Decide on workflow-test-readme.yml (expand or deprecate)
[ ] LOW: Reclassify 7 guideline-natured files (see list above)
[ ] LOW: Update cross-references after any moves/merges
```

---

## Metrics

- **Total files analyzed:** 26
- **Correctly classified:** 12 (46%)
- **Misclassified (should be guidelines):** 11 (42%)
- **Redundant/deprecated:** 3 (12%)
- **Potentially obsolete:** 2 (8%)
