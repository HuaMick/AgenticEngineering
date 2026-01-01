# Proposal: planner-test-guidance Agent

## Problem Statement

Currently there is no defined testing strategy for agent guidance changes. The `planner-test` agent focuses on implementation testing (smoke_test, agent-blind-test, service_test), not guidance testing.

When guidance is updated (process files, inputs, definitions), we rely on:
- Manual reference validation (Task 4.1 in our recent plan)
- Friction checkpoint verification (Task 4.2)

This is insufficient because it doesn't test whether an agent can actually **follow the guidance successfully**.

## Proposed Solution

Create a `planner-test-guidance` agent that plans guidance validation tests using **agent simulation** - spawning subagents that attempt to follow guidance with minimal context.

### Core Concept: Guidance-Blind-Test

Adapt the `agent-blind-test` pattern for guidance:

| User Story Testing | Guidance Testing |
|-------------------|------------------|
| User story definition | Agent task definition |
| User simulator agent | Guidance simulator agent |
| README + ARCHITECTURE only | process.yml + inputs.yml only |
| Complete user journey | Complete agent task |
| Documentation gaps found | Guidance gaps found |

### New Loop Type: guidance-test-loop

```yaml
guidance-test-loop:
  purpose: "Validate guidance completeness through agent simulation"
  phase: "guidance-validation"
  when_to_use: "After guidance changes to validate agents can follow them"
  maximum_iterations: 3
  core_pattern: "Define task → Spawn simulator → Execute with guidance only → Report gaps → Fix → Repeat"
```

## Agent Structure

### planner-test-guidance

**Location**: `agents/planner/planner-test-guidance/`

**Purpose**: Create test plans for validating agent guidance using simulation.

**Inputs** (reusable from existing):
- `assets/definitions/agent-loops.yml` - Loop definitions (add guidance-test-loop)
- `assets/definitions/friction.yml` - Friction patterns to detect
- `assets/definitions/path.yml` - Path concept
- `assets/definitions/fence.yml` - Fence concept
- `assets/definitions/signpost.yml` - Signpost concept
- `assets/definitions/agent-categories.yml` - Agent categories
- `assets/definitions/guidance-artifacts.yml` - Guidance artifact types

**New Inputs** (to create):
- `assets/definitions/strategy-guidance-blind-test.yml` - Guidance testing strategy
- `assets/definitions/guidance-test-scenarios.yml` - Standard test scenarios

**Outputs**:
- `plan_live_test_guidance.yml` - Guidance test plan phases

### test-guidance-simulator

**Location**: `agents/test/test-guidance-simulator/`

**Purpose**: Execute agent tasks using only provided guidance (process.yml, inputs.yml).

**Key Constraints** (parallel to test-user-simulator):
- NO additional context beyond process.yml, inputs.yml, and task definition
- NO reading source code or implementation details
- Report guidance gaps when task cannot be completed
- Test with subagent spawning to validate orchestration patterns

## Test Scenarios

### 1. Task Completion Test
- Give simulator a realistic task matching agent's purpose
- Provide only process.yml and inputs.yml
- Can the agent complete the task?
- What guidance was missing or unclear?

### 2. Reference Resolution Test
- Parse all file references in inputs.yml
- Attempt to load each referenced file
- Report broken references

### 3. Loop Context Test
- For agents participating in loops, verify loop_context is defined
- Verify max_iterations is specified
- Verify escalation path exists

### 4. Subagent Spawning Test
- For orchestration agents, simulate spawning child agents
- Verify child agents have sufficient context
- Verify handoff patterns are clear

### 5. Friction Detection Test
- Execute common task patterns
- Measure steps required vs expected
- Identify hidden prerequisites
- Flag late validation issues

### 6. SNR Validation
- **Purpose**: Validate that guidance maintains high signal-to-noise ratio
- **Test approach**: Evaluate guidance against signal/noise criteria from `assets/definitions/signal-and-noise.yml`
- **Inputs**: process.yml, inputs.yml from target agent
- **Expected outputs**: SNR score, noise categories identified, improvement recommendations
- **Pass criteria**: SNR above threshold, no critical noise categories present
- **Signal criteria**: Actionable, Specific, Verifiable, Evidence-Based content with Discriminatory Power
- **Noise categories to detect**: Meta-Talk, Stale Context, Generic Philosophy, Structural Redundancy

## Integration with Orchestration

The `_teach.yml` entrypoint would be updated:

```yaml
Step 4: Final Audit
  Spawn `planner-test-guidance` to create guidance test plan.
  Spawn `test-guidance-simulator` to execute guidance tests.
  If tests fail, return to Step 2 with guidance gaps as friction.
```

## Files to Create

1. **Agent Process Files**:
   - `agents/planner/planner-test-guidance/process.yml`
   - `agents/planner/planner-test-guidance/inputs.yml`
   - `agents/planner/planner-test-guidance/manifest.yml`
   - `agents/test/test-guidance-simulator/process.yml`
   - `agents/test/test-guidance-simulator/inputs.yml`
   - `agents/test/test-guidance-simulator/manifest.yml`

2. **Definitions**:
   - `assets/definitions/strategy-guidance-blind-test.yml`
   - `assets/definitions/guidance-test-scenarios.yml`
   - Update `assets/definitions/agent-loops.yml` with guidance-test-loop

3. **Examples**:
   - `assets/examples/test/guidance-test-plan.yml`
   - `assets/examples/test/guidance-test-report.yml`

## Success Criteria

1. Guidance simulator can detect the friction points we manually identified
2. Reference validation catches broken paths automatically
3. Loop context validation catches missing loop_context sections
4. Subagent tests validate orchestration handoffs work
5. Friction detection identifies hidden prerequisites

## Reusable Patterns

The following existing patterns apply directly:

| Pattern | Source | Application |
|---------|--------|-------------|
| Blind test | strategy-agent-blind-test.yml | Minimal context testing |
| Multi-layer | strategy-multi-layer.yml | Multiple validation approaches |
| Failure reporting | test-user-simulator/inputs.yml | Structured gap reporting |
| Loop structure | agent-loops.yml | guidance-test-loop definition |
| Friction concept | friction.yml | Gap categorization |

## Implementation Phases

### Phase 1: Core Structure
- Create planner-test-guidance process/inputs
- Create test-guidance-simulator process/inputs
- Add guidance-test-loop to agent-loops.yml

### Phase 2: Test Scenarios
- Implement task completion test
- Implement reference resolution test
- Implement loop context test

### Phase 3: Advanced Tests
- Implement subagent spawning test
- Implement friction detection test
- Create example test plans and reports

### Phase 4: Integration
- Update _teach.yml to include guidance testing
- Update agents/orchestration/orchestration-guidance/process.mm and orchestration-build/process.mm with guidance test step
- Create documentation

## Estimated Scope

- 6 new files (2 agents × 3 files each)
- 2 new definition files
- 2 new example files
- 4 updates to existing files (agent-loops.yml, _teach.yml, orchestration-guidance/process.mm, orchestration-build/process.mm)
