# Orchestration Test Fixtures

Test plan folders for validating the orchestration-executor agent.

## Folder Structure

Each test scenario is a complete plan folder containing:
- `live/plan_test.yml` - Plan YAML with phases and tasks
- `live/orchestration_test.mmd` - Plan-MMD with metadata

## Test Scenarios

### PARSE_001: Valid MMD with All Metadata
- **Folder**: `parse_001_valid/`
- **Purpose**: Verify executor correctly parses complete Plan-MMD
- **Expected**: All metadata extracted, phase execution starts

### PARSE_002: Missing AGENT_ROUTING
- **Folder**: `parse_002_missing_routing/`
- **Purpose**: Verify executor handles missing AGENT_ROUTING gracefully
- **Expected**: Inference attempted or blocked for user resolution

### PARSE_003: Invalid Agent Types
- **Folder**: `parse_003_invalid_agents/`
- **Purpose**: Verify executor detects and reports invalid agent types
- **Expected**: Error reported, transition to blocked

### PARSE_004: Malformed Feedback Triggers
- **Folder**: `parse_004_malformed_triggers/`
- **Purpose**: Verify executor detects malformed trigger syntax
- **Expected**: Parsing errors reported for each malformed trigger

## Running Tests

To test the orchestration-executor with a fixture:

```
# Set required inputs
plan_folder_path: modules/AgenticGuidance/assets/test-fixtures/orchestration/parse_001_valid/
target_project_path: /home/code/AgenticEngineering-agenticguidance

# Invoke orchestration-executor agent
```

## Related Files

- Executor: `agents/orchestration/orchestration-executor/`
- Specification: `assets/definitions/orchestration-executor-specification.yml`
- Test Scenarios: `assets/definitions/orchestration-test-scenarios.yml`
