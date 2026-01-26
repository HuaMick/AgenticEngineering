# 260127AG - Ralph Loop Orchestration Compliance

## Problem

On 2026-01-27, the Ralph Loop stop hook invoked an agent as "orchestration agent" but the agent failed to follow proper orchestration processes:

1. Did NOT follow `orchestration-planning/process.mmd`
2. Did NOT generate orchestration MMD files
3. Did NOT spawn planner-reviewer for validation
4. Executed tasks directly instead of spawning builder subagents
5. Archived plans without `mmd_presence` fence validation

This resulted in 2 plans (260126AT_agentictmux, 260126AV_agenticvoice) being processed without proper compliance.

## Potential Causes

1. **CCI System Interaction** - CLI Context Injection may not be properly injecting orchestration context
2. **Ralph Loop Design Gap** - Hook may be designed for different orchestration model than entrypoints
3. **Agent Interpretation Error** - Instructions may be ambiguous about process compliance
4. **Missing Infrastructure** - CLI may lack commands to support proper Ralph Loop orchestration

## Resolution Options

- **Option A**: Learn to use existing CLI system properly with Ralph Loop
- **Option B**: Build planning and Ralph Loop support into CLI (new commands)
- **Option C**: Hybrid - minimal CLI additions to bridge the gap

## Resolution Selected

**Option B: Build planning and Agent Loop support into AgenticGuidance**

Implementation approach: Geoffrey Huntley Ralph Loop with fresh context per iteration.
- Each iteration gets fresh context (no `--resume`)
- State persists via files (plan YAML, git history)
- `claude -p --output-format json` for clean subprocess control

## Files

- `live/plan_live_teach.yml` - Investigation and root cause analysis
- `live/plan_live_build.yml` - Implementation plan for Agent Loop services
- `live/orchestration_agent_loop.mmd` - Orchestration flowchart for execution

## Deliverables (Planned)

1. `agentic plan generate-mmd <folder>` - Generate orchestration MMD from plan YAML
2. `agentic plan validate --require-mmd` - Validate plan has MMD file
3. `agentic loop init|start|status|stop|run-once` - Agent loop commands

## Related Plans (Reopened for Revalidation)

- `260126AT_agentictmux` - Marked requires_revalidation
- `260126AV_agenticvoice` - Marked requires_revalidation
