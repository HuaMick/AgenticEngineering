# Orchestration Executor

Launch an execution session that reads Plan-MMD files and dynamically routes to agents.

## Quick Start

```bash
agentic session orchestrate --mode executor
agentic session orchestrate --mode executor --plan <folder>
```

## What It Does

- Reads orchestration MMDs and resolves AGENT_ROUTING metadata
- Spawns agents (build-python, test-runner, teacher-update-guidance, etc.) per phase
- Manages phase lifecycle: startup, execution loop, validation gate, shutdown
- Tracks remediation plans for out-of-scope errors
- Enforces validation/audit gates before shutdown

## Agent Profile

Source of truth for the full process definition:

```
modules/AgenticGuidance/agents/orchestration/orchestration-executor/
  manifest.yml   - spawns fence, routing types, purpose
  process.yml    - structured execution protocol with steps and guidelines
  inputs.yml     - input contract
```

## See Also

- `agentic session orchestrate --mode planning` - Create and approve plans
- `agentic session orchestrate --mode friction` - Analyze traces for friction patterns
