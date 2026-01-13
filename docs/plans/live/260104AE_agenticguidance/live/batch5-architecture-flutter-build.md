# Batch 5: Architecture, Flutter & Build Definitions Audit

**Created:** 2026-01-11
**Scope:** Architecture patterns, Flutter testing, and build/deploy definitions
**Source:** `modules/AgenticGuidance/assets/definitions/`

---

## Summary Table

| File | Current Type | Actual Type | Status | Redundant | References | Priority | Action |
|------|--------------|-------------|--------|-----------|------------|----------|--------|
| architecture-pattern.yml | Definition | Definition | ACTIVE | No | 97 files | LOW | Keep as-is |
| folder-structure.yml | Definition | Definition | ACTIVE | Partial | Unknown | MEDIUM | Review for merge |
| domains.yml | Definition | Redirect | DEPRECATED | Yes | 97 files | HIGH | Delete |
| entrypoints.yml | Definition | Redirect | DEPRECATED | Yes | 97 files | HIGH | Delete |
| workflows.yml | Definition | Redirect | DEPRECATED | Yes | 97 files | HIGH | Delete |
| flutter-environments.yml | Definition | Guideline | LEGACY | No | 7 files | MEDIUM | Reclassify or deprecate |
| flutter-project-type.yml | Definition | Metadata | OBSOLETE | N/A | 7 files | HIGH | Delete |
| flutter-skipped-tests.yml | Definition | Guideline | LEGACY | Partial | 7 files | MEDIUM | Merge with flutter-test-* |
| flutter-test-execution.yml | Definition | Guideline | LEGACY | Partial | 7 files | MEDIUM | Consolidate |
| flutter-test-roles.yml | Definition | Definition | LEGACY | No | 7 files | MEDIUM | Consolidate |
| flutter-test-structure.yml | Definition | Definition | LEGACY | Partial | 7 files | MEDIUM | Consolidate |
| build-artifacts.yml | Definition | Guideline | ACTIVE | Partial | 14 files | LOW | Merge with packaging.yml |
| fence-build-deploy.yml | Definition | Guideline | ACTIVE | No | 14 files | LOW | Reclassify to guidelines |
| gcp-artifact-registry.yml | Definition | Definition | PROJECT-SPECIFIC | No | 14 files | MEDIUM | Move to project config |
| packaging.yml | Definition | Definition | ACTIVE | Partial | 14 files | LOW | Merge with build-artifacts |
| cleaner-shared-guidelines.yml | Definition | Definition | SPEC-ONLY | No | 10 files | LOW | Keep as-is |

---

## Detailed Analysis

### Architecture Files

#### 1. architecture-pattern.yml
**Path:** `modules/AgenticGuidance/assets/definitions/architecture-pattern.yml`

**Classification:** TRUE DEFINITION
- Defines the three-layer architecture pattern: Entrypoints -> Workflows -> Domains
- Answers "what is X?" for each layer with clear structure and examples
- Consolidates domains.yml, workflows.yml, entrypoints.yml into single source

**Content Summary:**
- Domains: Package structure for encapsulating human-understandable concepts
- Workflows: Orchestration files that coordinate domains
- Entrypoints: Routers for user/agent interaction
- Relationships: Flow diagram and layer responsibilities

**Usage:** 97 references across the codebase (many in process.yml files)

**Assessment:** This is a well-structured, authoritative definition file. It correctly consolidates related architecture concepts and provides concrete examples.

**Recommendation:** KEEP AS-IS
- Priority: LOW (no action needed)

---

#### 2. folder-structure.yml
**Path:** `modules/AgenticGuidance/assets/definitions/folder-structure.yml`

**Classification:** TRUE DEFINITION
- Defines path conventions and folder structures
- Delegates plan folder definitions to plans.yml (good separation)

**Content Summary:**
- Path conventions: Use relative paths from repo root
- Plans root reference to plans.yml
- Agent logs folder pattern: `docs/agent_logs/YYYYMMDD_<agent_name>`

**Assessment:** Minimal content, mostly references plans.yml. The agent_logs folder definition is the only unique content.

**Potential Issues:**
- Very thin file (35 lines)
- Only defines one non-plan folder (agent_logs)
- Could potentially be merged with plans.yml or another structural file

**Recommendation:** REVIEW FOR MERGE
- Consider consolidating with plans.yml under a "folder-conventions" section
- Priority: MEDIUM

---

#### 3. domains.yml (DEPRECATED)
**Path:** `modules/AgenticGuidance/assets/definitions/domains.yml`

**Classification:** REDIRECT STUB
- File is marked DEPRECATED with `_redirect` to architecture-pattern.yml#domains
- Contains no actual content, only migration instructions

**Assessment:** This file exists only for backward compatibility. The actual content has been migrated to architecture-pattern.yml.

**Usage Check:** The 97 references found include architecture-pattern.yml references, suggesting the pattern is to search for "domains.yml" broadly.

**Recommendation:** DELETE
- Update any remaining direct references to use architecture-pattern.yml
- Priority: HIGH (dead code)

---

#### 4. entrypoints.yml (DEPRECATED)
**Path:** `modules/AgenticGuidance/assets/definitions/entrypoints.yml`

**Classification:** REDIRECT STUB
- File is marked DEPRECATED with `_redirect` to architecture-pattern.yml#entrypoints
- Contains no actual content

**Recommendation:** DELETE
- Priority: HIGH (dead code)

---

#### 5. workflows.yml (DEPRECATED)
**Path:** `modules/AgenticGuidance/assets/definitions/workflows.yml`

**Classification:** REDIRECT STUB
- File is marked DEPRECATED with `_redirect` to architecture-pattern.yml#workflows
- Contains no actual content

**Recommendation:** DELETE
- Priority: HIGH (dead code)

---

### Flutter Files

#### 6. flutter-environments.yml
**Path:** `modules/AgenticGuidance/assets/definitions/flutter-environments.yml`

**Classification:** GUIDELINE (mislabeled as definition)
- Contains prescriptive guidance on environment-specific behavior
- Rules about what to use in different environments
- "Use for all test types" / "Use only for pure Dart logic tests" = actionable guidance

**Content Summary:**
- Native Flutter: Full dart:io access, preferred for all test types
- Docker: WebSocket limitations, only for pure Dart logic tests
- CI/CD: Uses specific image, localhost works normally

**Assessment:** This is prescriptive guidance, not a definition. It tells agents "how to act" in different environments.

**Usage:** Referenced in legacy Flutter test agents (7 files, all in modules/legacy/)

**Recommendation:** RECLASSIFY OR DEPRECATE
- If Flutter agents are still needed: Move to guidelines folder as `flutter-environment-testing.yml`
- If Flutter agents are legacy-only: Mark as legacy, consider deletion
- Priority: MEDIUM

---

#### 7. flutter-project-type.yml
**Path:** `modules/AgenticGuidance/assets/definitions/flutter-project-type.yml`

**Classification:** OBSOLETE METADATA
- Contains only: `project_type: flutter`
- Single line, provides no meaningful definition or guidance

**Assessment:** This appears to be leftover configuration metadata. Provides no value as a definition file.

**Usage:** Referenced only in legacy files (7 files in modules/legacy/)

**Recommendation:** DELETE
- This is not a definition, it's project configuration
- If needed, should be in project-level config, not definitions
- Priority: HIGH (no meaningful content)

---

#### 8. flutter-skipped-tests.yml
**Path:** `modules/AgenticGuidance/assets/definitions/flutter-skipped-tests.yml`

**Classification:** GUIDELINE (mislabeled as definition)
- Defines what constitutes an acceptable test skip (prescriptive)
- Contains rules: "Only the following test skips are acceptable"
- Action-oriented: "should be fixed by setting up the required condition"

**Content Summary:**
- Acceptable skips: Platform-specific tests, WebSocket tests in Docker
- Unacceptable skips: All others (must be fixed)

**Assessment:** This is a quality guideline masquerading as a definition. It shapes agent behavior around test management.

**Overlap:** Content overlaps with flutter-environments.yml (Docker WebSocket limitations)

**Recommendation:** CONSOLIDATE
- Merge into unified `flutter-testing.yml` guideline
- Priority: MEDIUM

---

#### 9. flutter-test-execution.yml
**Path:** `modules/AgenticGuidance/assets/definitions/flutter-test-execution.yml`

**Classification:** GUIDELINE (mislabeled as definition)
- Workflow instructions: "Test agents should follow this workflow"
- Prescriptive steps: pre-test setup, execution commands, post-test cleanup
- Contains specific commands to run

**Content Summary:**
- Pre-Test: `flutter pub get`, check mock servers
- Execution: `flutter test <path>`, `--reporter expanded`
- Post-Test: Stop mock servers, clean up artifacts

**Assessment:** This is an execution guideline, not a definition. It tells agents exactly what to do.

**Recommendation:** CONSOLIDATE
- Merge into unified `flutter-testing.yml` guideline
- Priority: MEDIUM

---

#### 10. flutter-test-roles.yml
**Path:** `modules/AgenticGuidance/assets/definitions/flutter-test-roles.yml`

**Classification:** TRUE DEFINITION
- Defines two distinct agent roles: Test Builder, Test Runner
- Answers "what is a Test Builder?" / "what is a Test Runner?"
- Describes responsibilities and constraints for each

**Content Summary:**
- Test Builder: Creates/maintains tests, CANNOT execute
- Test Runner: Executes tests, CANNOT modify code

**Assessment:** This is a proper definition of agent role boundaries. Separation of concerns is clearly articulated.

**Recommendation:** KEEP (but consider consolidation)
- Could be part of a consolidated flutter-testing file
- Or referenced from agent-categories.yml if roles are cross-cutting
- Priority: MEDIUM

---

#### 11. flutter-test-structure.yml
**Path:** `modules/AgenticGuidance/assets/definitions/flutter-test-structure.yml`

**Classification:** MIXED (Definition + Convention)
- Defines test directory structure (definition)
- Naming conventions (guideline/standard)

**Content Summary:**
- Test directory mirrors lib/ structure
- Naming: `<source_file>_test.dart`
- Organization: Use group() for related tests

**Assessment:** Primarily a structural definition with some convention guidance. Appropriate as a definition.

**Recommendation:** CONSOLIDATE
- Merge into unified `flutter-testing.yml` definition/guideline
- Priority: MEDIUM

---

### Build & Deploy Files

#### 12. build-artifacts.yml
**Path:** `modules/AgenticGuidance/assets/definitions/build-artifacts.yml`

**Classification:** GUIDELINE (mislabeled as definition)
- Prescriptive rules: "should always be placed", "Never commit"
- Contains actionable directives, not definitions

**Content Summary:**
- Artifacts go in `build-artifacts/` directory
- Wheels: `build-artifacts/dist/*.whl`
- Must be git-ignored, never committed

**Overlap:** Related to packaging.yml content

**Recommendation:** MERGE WITH packaging.yml
- Create consolidated `build-packaging.yml` definition
- Keep structural definitions, move rules to guidelines if needed
- Priority: LOW

---

#### 13. fence-build-deploy.yml
**Path:** `modules/AgenticGuidance/assets/definitions/fence-build-deploy.yml`

**Classification:** GUIDELINE (mislabeled as definition)
- Highly prescriptive: "Build should NOT", "Deploy should NOT"
- Contains examples of mistakes and how to avoid them
- Action-oriented: "hand off to deploy agent"

**Content Summary:**
- Build Boundary: Write code, verify compilation, tests pass
- Deploy Boundary: Create artifacts, install/configure systems
- The Fence: Clear separation of responsibilities
- Common Mistakes: Examples of boundary violations

**Assessment:** This is an excellent separation-of-concerns guideline. It shapes agent behavior and prevents scope creep. Should be in guidelines folder.

**Recommendation:** RECLASSIFY TO GUIDELINES
- Move to `guidelines/fence-build-deploy.yml`
- Rename to `separation-build-deploy.yml` for consistency
- Priority: LOW (file is valuable, just mislabeled)

---

#### 14. gcp-artifact-registry.yml
**Path:** `modules/AgenticGuidance/assets/definitions/gcp-artifact-registry.yml`

**Classification:** PROJECT-SPECIFIC CONFIGURATION
- Contains specific registry URL, package names, authentication details
- References MyAgents project specifically

**Content Summary:**
- Registry URL: `https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/`
- Published packages: agent-gcptoolkit
- Authentication via netrc, install-global.sh script

**Assessment:** This is project-specific infrastructure configuration, not a general definition. It belongs in project configuration, not the definitions folder.

**Recommendation:** MOVE TO PROJECT CONFIG
- Move to project-specific location (AgenticBackend or similar)
- Or create `config/` folder for infrastructure definitions
- Priority: MEDIUM (organizational improvement)

---

#### 15. packaging.yml
**Path:** `modules/AgenticGuidance/assets/definitions/packaging.yml`

**Classification:** TRUE DEFINITION
- Defines what packaging involves conceptually
- Lists key steps without being overly prescriptive

**Content Summary:**
- Definition of packaging as creating distributable artifacts
- Key steps: build wheel, verify structure, output location, handle dependencies

**Overlap:** Related to build-artifacts.yml

**Recommendation:** MERGE WITH build-artifacts.yml
- Consolidate into `build-packaging.yml`
- Priority: LOW

---

#### 16. cleaner-shared-guidelines.yml
**Path:** `modules/AgenticGuidance/assets/definitions/cleaner-shared-guidelines.yml`

**Classification:** META-DEFINITION (Definition of shared guidelines)
- Specification-only: Cleaner agents not yet implemented
- Defines which guidelines cleaner agents will share
- Reduces duplication across future cleaner agents

**Content Summary:**
- 7 shared guidelines: context-minimisation, less-is-more, safety, experiment-first, worktree-and-branching, response-audit, testing
- Each guideline has path, description, and purpose
- Impact analysis: ~600 token savings

**Assessment:** This is a valid organizational file. It's a definition of what cleaner agents share, not a guideline itself. The "SPECIFICATION ONLY" status is clearly marked.

**Usage:** 10 references, including cleaner-shared.yml inputs files

**Recommendation:** KEEP AS-IS
- Properly structured for future use
- Clear specification status
- Priority: LOW (no action needed)

---

## Recommendations Summary

### HIGH Priority Actions

| Action | Files | Effort | Impact |
|--------|-------|--------|--------|
| DELETE deprecated redirect stubs | domains.yml, entrypoints.yml, workflows.yml | Low | Clean up dead code |
| DELETE obsolete metadata | flutter-project-type.yml | Low | Remove meaningless file |

### MEDIUM Priority Actions

| Action | Files | Effort | Impact |
|--------|-------|--------|--------|
| CONSOLIDATE Flutter testing | flutter-environments.yml, flutter-skipped-tests.yml, flutter-test-execution.yml, flutter-test-roles.yml, flutter-test-structure.yml | Medium | Reduce fragmentation |
| MOVE project config | gcp-artifact-registry.yml | Low | Proper organization |
| REVIEW for merge | folder-structure.yml | Low | Reduce thin files |

### LOW Priority Actions

| Action | Files | Effort | Impact |
|--------|-------|--------|--------|
| RECLASSIFY to guidelines | fence-build-deploy.yml | Low | Correct categorization |
| MERGE packaging files | build-artifacts.yml, packaging.yml | Low | Reduce overlap |
| KEEP as-is | architecture-pattern.yml, cleaner-shared-guidelines.yml | None | Already well-structured |

---

## Flutter Testing Consolidation Plan

If Flutter testing remains active, consolidate 6 files into 2:

**New Structure:**
```
definitions/
  flutter-testing.yml          # Consolidated definition
    - test_structure           # from flutter-test-structure.yml
    - test_roles               # from flutter-test-roles.yml
    - environment_behavior     # from flutter-environments.yml (definition parts)

guidelines/
  flutter-testing-execution.yml # Consolidated guideline
    - execution_workflow       # from flutter-test-execution.yml
    - skip_policy             # from flutter-skipped-tests.yml
    - environment_guidance    # from flutter-environments.yml (guideline parts)
```

**Migration Steps:**
1. Create new consolidated files
2. Update all references in inputs.yml files
3. Mark old files as deprecated
4. After validation, delete deprecated files

---

## Build Consolidation Plan

**Merge build-artifacts.yml + packaging.yml into:**
```yaml
# build-packaging.yml
packaging:
  definition: |
    Packaging creates distributable artifacts (wheels, source distributions).

  artifacts:
    location: "build-artifacts/"
    types:
      - "build-artifacts/dist/*.whl"
      - "build-artifacts/dist/*.tar.gz"

  rules:
    - All build outputs should be git-ignored
    - Never commit build artifacts to version control

  workflow:
    - Build wheel files using uv build or setuptools
    - Verify package structure and metadata
    - Output artifacts to build-artifacts/ directory
    - Handle dependencies and versioning
```

---

## Legacy Assessment

**Files primarily referenced in legacy:**
- All flutter-*.yml files (7 references, all in modules/legacy/)

**Consideration:** If Flutter development is discontinued, these files could be moved to legacy or deleted entirely rather than consolidated.

**Decision Required:** Is Flutter testing still active in the main AgenticGuidance module?

---

## Metrics

| Category | Count | Action Needed |
|----------|-------|---------------|
| True Definitions | 6 | 0 |
| Mislabeled (should be guidelines) | 5 | 5 reclassify |
| Deprecated/Redirect | 3 | 3 delete |
| Obsolete | 1 | 1 delete |
| Project-Specific | 1 | 1 relocate |
| **Total** | **16** | **10** |

**Post-cleanup projection:** 6-8 files (down from 16) with proper categorization
