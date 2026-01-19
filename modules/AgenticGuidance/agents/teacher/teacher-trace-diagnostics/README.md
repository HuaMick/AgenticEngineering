# Teacher-Trace-Diagnostics Agent

Analyze LangSmith traces to identify guidance friction patterns and generate recommendations for improvement.

## Purpose

This agent examines structured trace data from LangSmith to detect patterns indicating guidance friction:
- **Backtracking**: Agent revisits previous decisions
- **Error clusters**: Same errors repeat across runs
- **Path ambiguity**: Agent hesitates or tries multiple approaches
- **Token anomaly**: Abnormal token consumption

## Prerequisites

1. **LANGSMITH_API_KEY**: Set this environment variable with your LangSmith API key
2. **AgenticLangSmith module**: The `modules/AgenticLangSmith` service wrapper must be available

## Usage

### Via Orchestration

The agent is typically invoked by an orchestrator after agent runs complete:

```yaml
# Example orchestration invocation
teacher-trace-diagnostics:
  project_name: "my-agent-project"
  time_range_hours: 24
  run_limit: 100
```

### Standalone

When invoked directly, the agent writes its diagnostics report to the plan audit folder.

## Configuration

Defaults (can be overridden in inputs):
- `time_range_hours`: 24
- `run_limit`: 100
- `max_run_limit`: 500
- `min_run_duration_seconds`: 1.0

## Output

The agent produces a `trace_diagnostics_report` with:
- `analysis_summary`: Scope and counts
- `friction_findings`: Detected patterns ordered by severity
- `statistics`: Aggregate metrics

See `process.yml` for the complete output schema.

## Integration

This agent is complementary to `teacher-update-guidance`:
- `teacher-trace-diagnostics`: Identifies friction patterns in traces
- `teacher-update-guidance`: Consumes recommendations to update guidance files

## Files

- `manifest.yml`: Agent metadata and boundaries
- `process.yml`: Detailed workflow steps
- `inputs.yml`: Configuration and friction pattern definitions
- `tests/test_trace_analysis.py`: Unit tests for pattern detection

## Related

- `modules/AgenticLangSmith/src/agenticlangsmith/service.py`: LangSmith API wrapper
- `modules/AgenticGuidance/assets/definitions/trace-diagnostics.yml`: Shared definitions
- `modules/AgenticGuidance/assets/examples/teacher/langsmith-trace-analysis.yml`: Usage examples
