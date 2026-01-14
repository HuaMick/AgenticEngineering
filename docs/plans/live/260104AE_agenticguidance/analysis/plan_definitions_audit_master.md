# Definitions Audit - Master Plan

**Created:** 2026-01-11
**Status:** Planning Complete - Ready for Implementation
**Scope:** 88 definition files in `/modules/AgenticGuidance/assets/definitions/`

## Executive Summary

Six parallel planner-guidance agents audited all 88 definition files to identify:
- Files misclassified as definitions (should be guidelines)
- Redundant/duplicate content
- Project-specific content that doesn't belong in shared framework
- Obsolete or sparse files that should be deprecated

### Key Metrics Across All Batches

| Metric | Count | Percentage |
|--------|-------|------------|
| Total files audited | 88 | 100% |
| Correctly classified | ~35 | 40% |
| Misclassified (should be guidelines) | ~30 | 34% |
| Redundant/should deprecate | ~12 | 14% |
| Project-specific (remove from shared) | ~8 | 9% |
| Potentially obsolete | ~3 | 3% |

---

## High Priority Actions

### 1. Files to Deprecate/Remove

| File | Reason | Batch |
|------|--------|-------|
| `test-roles.yml` | Fully redundant with test-builder-role.yml + test-runner-role.yml | Batch 2 |
| `testing-documentation.yml` | 100% project-specific (MyAgents paths) | Batch 2 |
| `acceptable-skips.yml` | Project-specific test counts | Batch 2 |
| `success-criteria-teacher.yml` | Redundant with success-criteria.yml | Batch 6 |
| `flutter-project-type.yml` | Only 22 bytes, likely obsolete | Batch 5 |

### 2. Files to Move to Guidelines

| File | Current Location | Reason | Batch |
|------|-----------------|--------|-------|
| `escalation.yml` | definitions/ | 100% prescriptive behavioral rules | Batch 1 |
| `exploration-principles.yml` | definitions/ | 74 lines of "how to act" rules | Batch 6 |
| `test-structure.yml` | definitions/ | Prescribes test organization | Batch 2 |
| `test-creation-principles.yml` | definitions/ | Explicitly "principles" (prescriptive) | Batch 2 |
| `test-execution-workflow.yml` | definitions/ | Workflow prescription | Batch 2 |
| All `strategy-*.yml` files (10) | definitions/ | Prescriptive strategies, not definitions | Batch 3 |
| `minimal-sufficient-change.yml` | definitions/ | Behavioral rules | Batch 6 |
| `iteration-approach.yml` | definitions/ | Builder iteration rules | Batch 6 |
| `root-cause-analysis.yml` | definitions/ | Actionable guidance | Batch 6 |
| `model-first-verification.yml` | definitions/ | Verification guidance | Batch 6 |
| `component-verification.yml` | definitions/ | Builder verification rules | Batch 6 |
| `readme-context.yml` | definitions/ | README structure guidelines | Batch 6 |
| `preserved-files.yml` | definitions/ | Cleaner constraints | Batch 6 |

### 3. Files to Consolidate/Merge

| Files to Merge | Target | Reason | Batch |
|----------------|--------|--------|-------|
| `fence.yml` + `signpost.yml` | `navigation-aids.yml` | Conceptually paired | Batch 1 |
| `guidance.yml` + `guidance-artifacts.yml` | Restructure into 3 files | Overlapping concerns | Batch 1 |
| `definition.yml` + `guideline.yml` + `example.yml` | Split definitional from prescriptive | Self-contradictory hybrids | Batch 1 |
| `separation-of-concerns.yml` → `role-separation.yml` | `role-separation.yml` | Near-duplicate | Batch 6 |
| Flutter test files (6) | Single file or remove | Potentially obsolete project-specific | Batch 5 |

---

## Medium Priority Actions

### 4. Files Needing Generalization

These files contain valuable patterns but have project-specific details that should be extracted:

| File | Issue | Action |
|------|-------|--------|
| `test-execution-workflow.yml` | Contains `myagents studio` commands | Generalize workflow, move specifics to project inputs |
| `gcp-artifact-registry.yml` | Project-specific GCP details | Consider moving to project-specific inputs |
| `studio-integration-tests.yml` | May be obsolete | Verify tests still exist |
| `workflow-test-readme.yml` | Too sparse (6 lines) | Expand significantly or deprecate |

### 5. Files Correctly Classified (Keep As-Is)

These files are well-structured definitions that should remain in `definitions/`:

**Core Concepts:**
- `path.yml` - Clean definition, 35 references
- `friction.yml` - Acceptable hybrid with examples
- `steps.yml` - Well-structured teaching content
- `success-criteria.yml` - Canonical source
- `overengineering.yml` - Concise anti-pattern definition

**Technical References:**
- `signal-and-noise.yml` - Comprehensive (151 lines)
- `fragment-references.yml` - Technical syntax reference
- `path-resolution.yml` - Resolution semantics
- `cli-commands.yml` - Command reference
- `plan-mmd-schema.yml` - Schema definition (32KB)
- `orchestration-executor-specification.yml` - Spec (37KB)
- `orchestration-test-scenarios.yml` - Test scenarios (37KB)

**Agent/Domain:**
- `agent-categories.yml` - Category definitions
- `agent-loops.yml` - Loop pattern definitions
- `agent-context-files.yml` - Context file definitions
- `testing-types.yml` - Type index
- `test-builder-role.yml` - Role definition
- `test-runner-role.yml` - Role definition
- `guidance-test-scenarios.yml` - Scenario definitions
- `user-stories.yml` - Structure definition

---

## Batch Summary Links

| Batch | Focus | Files | Plan Location |
|-------|-------|-------|---------------|
| 1 | Core Concepts & Meta-definitions | 11 | `batch1-core-concepts.md` |
| 2 | Testing Framework | 11 | `batch2-testing-framework.md` |
| 3 | Validation Strategies | 10 | `batch3-validation-strategies.md` |
| 4 | Planning & Orchestration | 11 | `batch4-planning-orchestration.md` |
| 5 | Architecture, Flutter & Build | 16 | `batch5-architecture-flutter-build.md` |
| 6 | Principles & Miscellaneous | 26 | `batch6-principles-misc.md` |

---

## Proposed Directory Structure After Cleanup

```
definitions/                    # Pure definitions only (~35 files)
  # Core vocabulary
  definition.yml               # Brief: "A definition names a concept..."
  guideline.yml                # Brief: "A guideline is a rule-of-thumb..."
  example.yml                  # Brief: "An example is a concrete illustration..."
  path.yml                     # Agent navigation paths
  fence.yml                    # Guardrails (or merge with signpost)
  signpost.yml                 # Teaching artifacts (or merge with fence)
  friction.yml                 # Agent friction definition
  steps.yml                    # Steps vs criteria
  guidance.yml                 # Brief definition only

  # Agent roles & loops
  agent-categories.yml
  agent-loops.yml
  agent-context-files.yml
  test-builder-role.yml
  test-runner-role.yml
  builder-role.yml

  # Technical specifications
  plan-mmd-schema.yml
  orchestration-executor-specification.yml
  orchestration-test-scenarios.yml
  plans.yml
  plan-inputs.yml
  plan-folder-conventions.yml
  plan-structure-requirements.yml
  voting-system.yml

  # Testing types & scenarios
  testing-types.yml
  guidance-test-scenarios.yml
  skipped-test.yml

  # Technical references
  signal-and-noise.yml
  fragment-references.yml
  path-resolution.yml
  cli-commands.yml

  # Domain concepts
  user-stories.yml
  success-criteria.yml
  overengineering.yml
  knowledge-encapsulation.yml
  reward-hacking.yml
  leftover-folders.yml

  # Architecture (if not project-specific)
  architecture-pattern.yml
  folder-structure.yml
  domains.yml
  entrypoints.yml
  workflows.yml

guidelines/                     # Prescriptive behavioral rules (~25+ files)
  # Moved from definitions/
  escalation.yml
  exploration-principles.yml
  test-organization.yml        # Renamed from test-structure.yml
  test-creation-principles.yml
  test-execution-workflow.yml  # Generalized
  minimal-sufficient-change.yml
  iteration-approach.yml
  role-separation.yml          # Merged with separation-of-concerns
  root-cause-analysis.yml
  model-first-verification.yml
  component-verification.yml
  readme-context.yml
  preserved-files.yml
  generalized-vs-specific.yml
  outcome-verification.yml

  # Strategies (all 10)
  strategy-validation.yml
  strategy-multi-layer.yml
  strategy-agent-blind-test.yml
  strategy-agent-review-loop.yml
  strategy-documentation-validation.yml
  strategy-fresh-environment.yml
  strategy-guidance-blind-test.yml
  strategy-test-suite.yml
  strategy-user-acceptance.yml
  strategy-user-simulation.yml

  # Existing guidelines
  (current guideline files remain)

deprecated/                     # Files to remove (~12 files)
  test-roles.yml               # Redundant
  testing-documentation.yml    # Project-specific
  acceptable-skips.yml         # Project-specific
  success-criteria-teacher.yml # Redundant
  separation-of-concerns.yml   # Merged into role-separation
  flutter-project-type.yml     # Likely obsolete
  workflow-test-readme.yml     # Too sparse
  studio-integration-tests.yml # If obsolete
  (other flutter-specific if obsolete)
```

---

## Implementation Phases

### Phase 1: Remove Redundant Files
1. Verify no critical references to redundant files
2. Update any direct references to point to canonical files
3. Remove/archive redundant files
4. Estimated impact: 5-8 files, ~60 reference updates

### Phase 2: Reclassify Guidelines
1. Move strategy-*.yml files (10) to guidelines/
2. Move prescriptive definitions to guidelines/
3. Update all references in agent inputs.yml files
4. Update layer files (test-shared.yml, etc.)
5. Estimated impact: ~25 files moved, ~200 reference updates

### Phase 3: Consolidate/Merge
1. Merge guidance.yml + guidance-artifacts.yml
2. Merge fence.yml + signpost.yml (optional)
3. Merge separation-of-concerns into role-separation
4. Split meta-definitions (definition/guideline/example)
5. Estimated impact: 5-7 consolidation actions

### Phase 4: Generalize Project-Specific Content
1. Extract MyAgents-specific paths from shared files
2. Create project-specific inputs where needed
3. Remove/archive obsolete Flutter files if confirmed
4. Estimated impact: ~8 files modified

---

## Success Criteria

1. All files in `definitions/` answer "what is X?" (descriptive)
2. All files in `guidelines/` answer "how should I act?" (prescriptive)
3. No project-specific content in shared framework files
4. No redundant/duplicate files
5. All cross-references updated and working
6. Agent inputs.yml files reference correct locations

---

## Next Steps

1. Review this master plan for approval
2. Create implementation tickets for each phase
3. Execute Phase 1 (remove redundant) first to reduce scope
4. Execute remaining phases in order
5. Run validation tests after each phase
