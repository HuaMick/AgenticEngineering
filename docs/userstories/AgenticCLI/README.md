# AgenticCLI User Stories

Comprehensive user stories covering all capabilities of the AgenticCLI module.

## Overview

These user stories document the acceptance criteria for all CLI commands, organized by functional area. Each story follows the standard format:

```yaml
- id: "US-CLI-XXX"
  title: "Short title"
  category: "functional_area"
  priority: "critical|high|medium|low"
  as_a: "role"
  i_want: "to do something"
  so_that: "I achieve some goal"
  acceptance_criteria:
    - "Criterion 1"
    - "Criterion 2"
  related_commands:
    - "agentic command subcommand"
  related_agents:
    - "agent-name"
```

## Story Files

| File | Stories | Range | Description |
|------|---------|-------|-------------|
| 01_feedback_metrics.yml | 2 | US-FB-001 to 002 | Progress indicators and context awareness |
| 02_plan_management.yml | 16 | US-CLI-010 to 024 | Plan init, tasks, phases, orchestration |
| 03_session_and_loop.yml | 7 | US-CLI-030 to 036 | Session spawn/stop/status, loop management |
| 04_context_bootstrap.yml | 5 | US-CLI-040 to 044 | CCI bootstrap, role, task, inputs |
| 05_langsmith.yml | 8 | US-CLI-050 to 057 | Traces, friction analysis, session forensics |
| 06_question_queue.yml | 8 | US-CLI-060 to 067 | Question ask/answer/defer, tmux watch |
| 07_configuration.yml | 5 | US-CLI-070 to 074 | Setup, health, config, prefs, update |
| 08_entrypoints.yml | 4 | US-CLI-075 to 078 | Entrypoint list, show, execute, compile |
| 09_worktree.yml | 4 | US-CLI-090 to 093 | Worktree create, list, remove, status |
| 10_templates.yml | 4 | US-CLI-100 to 103 | Template list and generation |
| 11_stories.yml | 3 | US-CLI-110 to 112 | User story discovery and management |
| 12_ralph.yml | 5 | US-CLI-120 to 124 | Ralph Loop start/stop/status/history |
| 13_completion.yml | 2 | US-CLI-130 to 131 | Shell auto-completion install/show |
| 14_utilities.yml | 9 | US-CLI-140 to 148 | State, env, inputs, manifest commands |

**Total: 82 user stories**

## Story Categories

### Critical Priority
Stories that are essential for core functionality:
- Agent self-initialization (bootstrap)
- Plan initialization and scaffolding
- Session spawning
- Task management (start/complete)
- Question creation and answering
- Ralph Loop orchestration

### High Priority
Important features for effective workflows:
- Session monitoring and stopping
- Context retrieval (role, task, inputs)
- LangSmith trace querying and friction analysis
- Plan status and listing
- Entrypoint execution
- Configuration management

### Medium Priority
Valuable features that enhance usability:
- Template generation
- Worktree management
- Question watch notifications
- User story discovery
- Environment management
- State registry management

### Low Priority
Nice-to-have features for specialized use cases:
- Detailed process state inspection
- LangSmith URL retrieval
- Completion script display

## Command Categories

### Global Commands
Work from any directory:
- setup, health, config, prefs
- update, rebuild
- state, env
- session, loop, ralph

### Project Commands
Require .git or .agenticcli.yml:
- plan, worktree
- context, entrypoint
- langsmith, question
- template, stories
- inputs, manifest

## Usage Notes

### For Developers
- Stories define acceptance criteria for testing
- Each story includes related commands for documentation
- Priority indicates implementation order

### For Testers
- Use acceptance criteria as test cases
- Related commands show CLI usage examples
- Category indicates functional grouping for test suites

### For Product Managers
- Priority indicates feature importance
- Story counts reflect command surface area
- Categories map to user workflows

## Related Documentation

- Module README: `/home/code/AgenticEngineering/modules/AgenticCLI/README.md`
- CLI Commands Reference: See module README for detailed command documentation
- Agent Guidance: `/home/code/AgenticEngineering/modules/AgenticGuidance/agents/`

## Principles

These user stories follow AgenticCLI principles:

1. **Deterministic Over Reasoning** - Commands produce consistent output
2. **Minimal Surface Area** - Each command does one thing well
3. **Fail Fast, Fail Clearly** - Validate inputs before execution
4. **Evidence-Based Inclusion** - Commands added based on observed friction

## Maintenance

When adding new CLI commands:
1. Create user stories with clear acceptance criteria
2. Follow the ID numbering scheme (increments of 10 per file)
3. Include related commands and agents
4. Update 00_metadata.yml with new story counts
5. Add test cases based on acceptance criteria
