# Missing Build/Deploy Agents - Requires Investigation

**Date:** 2026-01-03
**Status:** FLAGGED FOR HUMAN REVIEW

## Summary

The following agents are referenced in `orchestration-build/process.mmd` but do not exist in AgenticGuidance:

| Agent | Reference Location | Line |
|-------|-------------------|------|
| build-python | Implementation Loop Subgraph | L148-155 |
| build-flutter | Implementation Loop Subgraph | L148-155 |
| deploy-cicd | CI/CD Validation Phase | L171-184 |

## Context

These agents were **not migrated** during the dependency migration. The migration agent was instructed to skip redundancies, so these may have been intentionally excluded.

Possible reasons for exclusion:
- Agents may be redundant with existing capabilities
- Agents may not be implemented in legacy either
- Build agents may be project-specific rather than reusable

## Source Reference

From `modules/AgenticGuidance/agents/orchestration/orchestration-build/process.mmd`:
- Lines 147-149: "build-python: Python implementation tasks"
- Lines 147-149: "build-flutter: Flutter/Dart implementation tasks"
- Lines 171-176: "deploy-cicd agent audits pipeline configuration"

## Action Required

Human review needed to determine:
1. Do these agents exist in legacy? If so, should they be migrated?
2. Are they placeholders for future implementation?
3. Should orchestration-build be updated to remove references if agents won't be implemented?
