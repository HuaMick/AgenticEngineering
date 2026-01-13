# Assessment: Guidance Consistency and Planning Artifact Proliferation

**Date:** 2026-01-09  
**Plan Reference:** 260104AE_agenticguidance  
**Subject:** Analysis of the conflict between "Unified Planning" and "Split Phase Orchestration"

## Executive Summary
An analysis of the current planner agent guidance reveals a fundamental architectural conflict between **Asset Examples** (which promote a "Unified Plan") and **Orchestration Logic** (which expects "Split Phase Plans"). This conflict, combined with a lack of explicit cleanup guidance for the Planner-Reviewer loop, has resulted in a "file explosion" within the active `live/` directory and confusion regarding best practices.

## 1. The Core Conflict: Unified vs. Split
There is a contradictory signal being sent to planner agents regarding how to structure their output:

| Component | Guidance Signal | Reason |
| :--- | :--- | :--- |
| **Orchestration Logic** | **Split Phases** (`plan_live_build.yml`, `plan_live_test.yml`, etc.) | Context Minimisation: Specialized agents should only read what they need to execute. |
| **Asset Examples** | **Unified Plan** (`plan_example.yml`) | Simplicity: A single-file overview of the entire feature lifecycle. |
| **Planner Sub-agents** | **Specialized Output** | `planner-build` and `planner-guidance` are instructed to output only to their specific phase files. |

**Discovery:** Agents receiving the "Unified Plan" example attempt to consolidate everything into a single file to follow "best practice," while the orchestrators and sub-planners continue to generate separate files, leading to a redundant and cluttered workspace.

## 2. Artifact Proliferation (The "Scrap Paper" Issue)
The **Planner-Reviewer Loop** (Audit → Remediation Plan → Review) is currently treated as an additive process rather than a destructive/consolidative one.

*   **Audit Files (`audit_*.yml`):** These are essentially "Bug Reports" for guidance.
*   **Review Files (`review_*.yml`):** These are "Critiques" of proposed fixes.
*   **Remediation Plans:** Intermediate plans designed to fix the issues found in the audit.

**Problem:** Current guidance does not explicitly tell agents to **Merge and Archive**. Once a Review is `APPROVED`, the tasks in the Remediation Plan should be merged into the primary Phase Plan, and the "scrap" files (Audits and Reviews) should be moved out of the `live/` folder.

## 3. Recommended Guidance Corrections

### 3.1 Policy: "One File per Feature, Many Files per Worktree"
We should move away from the "Unified Plan" terminology, as it implies a single file for everything.
*   **Recommendation:** Rename the example to **"Authoritative Phase Plan"**.
*   **Signpost:** Clarify that multiple phase files (Teach, Build, Test) are the preferred architecture for complex worktrees to support **Context Minimisation**.

### 3.2 Policy: "Merge and Archive"
Update the `planner-reviewer` and `orchestration-planning` guidance with an explicit post-approval cleanup step:
1.  **Consolidate:** Approved remediation tasks must be merged into the primary `plan_live_<phase>.yml`.
2.  **Move to Analysis:** All `audit_*.yml` and `review_*.yml` files must be moved to the `analysis/` or `audit/` subfolders immediately after approval.
3.  **Delete Plans:** Intermediate remediation plans (`plan_remediation_*.yml`) should be deleted from `live/` once their tasks are merged.

## 4. Immediate Actionable Cleanup
To restore organizational health to the `260104AE_agenticguidance` plan folder, the following reorganization is proposed:

*   **Move to `audit/`:** All `audit_deploy_worktree.yml`, `audit_planner_build.yml`, etc.
*   **Move to `analysis/`:** All `review_*.yml` files and historical remediation plan fragments.
*   **Retain in `live/`:** Only the current `plan_agenticguidance.yml`, `orchestration_agenticguidance.mmd`, and the active phase plans that have not yet been fully merged.

---
**Status:** Assessment Complete. Ready for guidance refinement tasks.
