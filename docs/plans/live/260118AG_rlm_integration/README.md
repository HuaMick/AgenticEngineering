# Teacher-Trace-Diagnostics Agent Plan - 260118AG_rlm_integration

## Overview

This plan creates a new `teacher-trace-diagnostics` agent that analyzes LangSmith traces to identify guidance friction patterns. The agent consumes traces via the LangSmith API and identifies backtracking, error clusters, path ambiguity, and token anomalies.

**RLM TEST CASE**: This agent serves as a practical test case for RLM (Recursive Language Model) patterns, validating that RLM decomposition works effectively for real-world context management scenarios.

## Motivation

Orchestration systems spawn many subagents, producing numerous traces that can flood the context window. This agent provides:
- Automated friction detection across trace data
- Structured recommendations mapped to specific guidance files
- Context management strategies for large trace volumes

## Plan Structure

```
docs/plans/live/260118AG_rlm_integration/
├── README.md                                    # This file
├── live/
│   ├── plan_live_teach_trace_diagnostics.yml   # Phase plan with 4 phases, 11 tasks
│   ├── orchestration_trace_diagnostics.mmd     # Execution flowchart (NEW)
│   ├── plan_live_teach.yml                     # Original RLM plan (reference)
│   └── orchestration_rlm_integration.mmd       # Original RLM orchestration
├── completed/                                   # For completed task artifacts
├── analysis/                                    # For iteration logs
└── audit/                                       # For audit reports
```

## Phases (Trace Diagnostics Plan) - ALL COMPLETE

| Phase | Name | Tasks | Status |
|-------|------|-------|--------|
| Phase 1 | Agent Structure | td_01_01, td_01_02, td_01_03, td_01_04 | COMPLETED |
| Phase 2 | Trace Analysis Definitions | td_02_01, td_02_02 | COMPLETED |
| Phase 3 | LangSmith Integration Patterns | td_03_01, td_03_02 | COMPLETED |
| Phase 4 | Validation | td_04_01, td_04_02, td_04_03 | COMPLETED |

## Key Deliverables

1. **Agent Files**:
   - `modules/AgenticGuidance/agents/teacher/teacher-trace-diagnostics/manifest.yml`
   - `modules/AgenticGuidance/agents/teacher/teacher-trace-diagnostics/process.yml`
   - `modules/AgenticGuidance/agents/teacher/teacher-trace-diagnostics/inputs.yml`

2. **Shared Definition**: `modules/AgenticGuidance/assets/definitions/trace-diagnostics.yml`

3. **Examples**: `modules/AgenticGuidance/assets/examples/teacher/langsmith-trace-analysis.yml`

4. **Tests**: `modules/AgenticGuidance/agents/teacher/teacher-trace-diagnostics/tests/test_trace_analysis.py`

## Friction Patterns Detected

| Pattern | Signal | Guidance Fix |
|---------|--------|--------------|
| `backtracking` | Agent revisits previous decisions | path_clarity |
| `error_cluster` | Same errors repeat across runs | fence_strengthening |
| `path_ambiguity` | Agent hesitates or tries multiple approaches | signpost_addition |
| `token_anomaly` | Token consumption exceeds norm | context_minimisation |

## Review Status

**Consensus Achieved**: 5/5 independent reviewers approved (2026-01-19)

| Reviewer | Focus | Decision | Confidence |
|----------|-------|----------|------------|
| 1 | Plan Structure | APPROVE | HIGH |
| 2 | Inputs and References | APPROVE | HIGH |
| 3 | Success Criteria | APPROVE | HIGH |
| 4 | Task Ordering & Dependencies | APPROVE | HIGH |
| 5 | MMD Presence & Final | APPROVE | HIGH |

## Design Decisions (Resolved)

| ID | Decision | Rationale |
|----|----------|-----------|
| TQ-001 | **Time-bounded with configurable default (24h)** | Aligns with "recent activity" mental model for high-activity orchestration |
| TQ-002 | **RLM decomposition** | Agent serves as TEST CASE for RLM patterns; validates RLM for real-world context management |

### RLM Context Management Pattern

This agent uses RLM (Recursive Language Model) patterns:
1. **Store Context**: Trace metadata as environment variables (CONTEXT_TRACES_*)
2. **Programmatic Access**: Write code to filter/examine traces
3. **Recursive Decomposition**: Process large sets in subsets by time window
4. **Accumulator Pattern**: Collect findings progressively, signal FINAL(report)

## Execution

```bash
# Via orchestration-executor with trace diagnostics plan
agentic run _orchestrate.yml --plan-folder docs/plans/live/260118AG_rlm_integration --plan-file plan_live_teach_trace_diagnostics.yml
```

## Target Worktree

- **Branch**: agenticguidance
- **Worktree**: AgenticGuidance module
- **Dependency**: Requires `modules/AgenticLangSmith` service wrapper
