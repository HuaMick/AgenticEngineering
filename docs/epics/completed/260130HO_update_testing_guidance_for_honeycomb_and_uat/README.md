# Plan: Update Testing Guidance for Honeycomb and UAT

## Objective
Update the `AgenticGuidance` module to prioritize the **"Honeycomb Integration First"** testing model and reinforce **"User Story UAT"** as the core success criterion.

## Current Problem
The existing guidance focuses on a traditional "Three-Layer" or "Multi-Layer" approach. There is no explicit definition or strategy for "Honeycomb" testing, which prioritizes the middle layer (integration/service tests) over unit and E2E tests. Additionally, while UAT is mandatory, its status as the "Core" requirement needs stronger alignment with user stories.

## Deliverables
- Updated `testing-types.yml` with Honeycomb definition.
- Updated `strategy-validation.yml` with Honeycomb strategy as the default.
- Updated `testing.yml` reinforcing UAT as the core anchored to user stories.
- Updated `agent-loops.yml` reflecting UAT-core phase ordering.

## Phases
1. **Definitions**: Core concept updates in `assets/definitions/`.
2. **Guidelines**: Strategy and behavioral rule updates in `assets/guidelines/`.
3. **Loops**: Ordering and priority updates in `assets/definitions/agent-loops.yml`.
4. **Validation**: Self-review of all changes using `agent-self-review` loop.
5. **Audit**: Verification of template alignment and removal of stale references.

## Key Files
- `plan_teach.yml`: Main instruction set for guidance updates.
- `plan_audit_clean.yml`: Verification and cleanup tasks.
- `analysis/friction-analysis.md`: Detailed breakdown of the gap and remediation.

## Worktree
- Path: `/home/code/AgenticEngineering-guidance-testing-honeycomb`
- Branch: `guidance-testing-honeycomb`

## Strategy
This is a **Guidance Refactor**. We follow the `planner-guidance` $\rightarrow$ `teacher-update-assets` $\rightarrow$ `planner-reviewer` workflow.

---
*Created by planner-guidance on 2026-01-30*
