# Plans Directory

This directory contains plan files that track the state and progress of agent workflows.

## Directory Structure

- **live/** - Active plans currently being executed by agents
- **backlog/** - Plans that are queued but not yet started
- **completed/** - Plans that have been successfully executed

## Purpose

Plans are YAML files that contain:
- Success criteria and requirements
- Current state and progress tracking
- Failure reports and remediation steps
- Execution history and checkpoints

## Usage

### Test Agents
Test agents reference `docs/plans/live/*/` for:
- Structured failure reporting
- State tracking across test-fix loops
- Coordination between test runners and builders

Plans are now organized in folder-based structure where each plan is a folder containing related files.

### Build Agents
Build agents use plans to:
- Track implementation progress
- Document completed features
- Report blockers and issues

### Orchestration
Orchestration agents manage plan lifecycle:
- Create new plans in backlog/
- Move plans to live/ when execution starts
- Archive completed plans to completed/

## Plan File Format

Plans should be valid YAML files with the following structure:

```yaml
plan:
  id: unique-plan-identifier
  title: Brief description of the plan
  status: pending|in_progress|completed|failed

success_criteria:
  - Criterion 1
  - Criterion 2

current_state:
  progress: Description of current progress
  next_steps: What needs to happen next

failures:
  - test_name: Name of failing test
    component: Component being tested
    failure_description: What went wrong
    expected_behavior: What should happen
    actual_behavior: What actually happened
    files_involved: Files that need changes
```

## Important Notes

- Plans in live/ indicate active work - agents may be reading/writing these files
- Never manually edit live plans while agents are running
- Use .gitkeep files are only temporary - replace with actual plan files during execution
