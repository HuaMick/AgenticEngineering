# UAT User Story Integration

## Problem
User stories (540 total in `/docs/userstories/`) are currently untested (0% coverage). UAT testing in plans is done via ad-hoc user journeys defined inline rather than referencing centralized user stories. There's no linkage between plan UAT and the user story repository.

## Goals
1. **Add last_tested_at and test_status fields** to user story schema
2. **Link user stories to planning files** as checklists that get validated during UAT
3. **Update `agentic stories` CLI** to support test status tracking
4. **Integrate UAT validation** - when plan UAT passes, auto-update linked story status
5. **Create plan_test pattern** that references user stories by ID in affected_stories

## Current State
- `agentic stories find/init/cat/status/update/report/untested` commands exist
- Stories are stored in `/docs/userstories/` with 66 categories
- Plan files have `affected_stories: []` but never populated
- `plan_test.yml` has UAT tasks but no story references

## Desired State
- Each user story has `last_tested_at: <timestamp>` and `test_status: pass|fail|untested`
- Plan files reference stories in `affected_stories: [US-001, US-002]`
- `agentic stories update <id> --status pass` called after UAT
- `agentic stories report` shows actual coverage percentages
- Agents can query untested stories for validation targets

## Open Questions
- Q1: Should user story test status be stored in the story YAML or in a separate status file?
- Q2: Should plan completion auto-update story status, or require explicit CLI call?
- Q3: What should the checklist format look like in plan_test.yml?

## Scope
- AgenticGuidance: Story schema updates
- AgenticCLI: `agentic stories` command enhancements
- Plan templates: Add affected_stories patterns
- Test agents: Integrate story validation into UAT loops
