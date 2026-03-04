# Question Guidance - Agent Integration for Question Generation

**Plan ID**: 260203QG
**Status**: Active
**Created**: 2026-02-03
**Worktree**: `/home/code/AgenticEngineering` (main branch)

## Objective

Update agent guidance documents to teach agents how to generate and handle questions when they encounter blockers or need clarification during task execution.

## Scope

This plan implements **agent guidance** for the question/answer workflow:

1. **When to ask questions**: Guidance on identifying blockers vs solvable issues
2. **How to generate questions**: YAML format, severity levels, context inclusion
3. **Question file creation**: Where to write questions (plan-scoped folders)
4. **Resumption patterns**: How to check for answers and resume work
5. **CLI references**: Point agents to `agentic question` commands for testing

## Architecture Context

This plan bridges agent behavior with the CLI-First infrastructure:
- Agents learn to generate well-formed questions when blocked
- Questions follow the YAML contract established in 260203QF
- Agents reference CLI commands for human operators to answer
- Resumption logic checks for answered questions and continues work

```
┌─────────────────────────────────────────────────────────────┐
│  AgenticGuidance (updated with guidance from THIS PLAN)      │
│  - Detects blockers                                          │
│  - Generates question YAML -> questions/pending/             │
│  - References CLI: "Human can answer via agentic question"   │
│  - Checks for answers and resumes                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  QuestionQueue (260203QF) + CLI (260203QC)                   │
│  - Human answers via CLI or voice                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  AgenticGuidance (resumes)                                   │
│  - Loads answer from questions/answered/                     │
│  - Continues task execution with clarification               │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

1. **Guidance-first approach**: Teach agents the pattern through inputs.yml and process.yml updates
2. **YAML examples**: Provide complete question templates in guidance documents
3. **Severity levels**: high, medium, low - teach agents when to use each
4. **Context inclusion**: Require agents to provide task ID, module, and relevant context
5. **CLI integration**: Reference CLI commands so agents can instruct humans on next steps

## Dependencies

**Depends on**:
- 260203QF (Question Foundation) - Data model schema for questions
- 260203QC (Question CLI) - CLI commands to reference in guidance

**Required by**:
- 260203QT (Question Tmux) - Tmux workflow uses updated agent patterns
- 260203VP (Voice PersonaPlex) - Voice daemon consumes questions from agents

## Implementation Phases

1. **Phase 1: Question Generation Guidance** - Update agent inputs.yml with when/how to ask
2. **Phase 2: YAML Template Examples** - Add complete question/answer examples
3. **Phase 3: Resumption Patterns** - Teach agents to check for answers and continue
4. **Phase 4: Role-Specific Guidance** - Customize for planner, builder, tester, reviewer agents

## Success Criteria

- Agent guidance documents include clear instructions for question generation
- YAML templates are complete and follow 260203QF schema
- Severity level guidance helps agents choose appropriate urgency
- Context inclusion guidance ensures questions have all necessary information
- Resumption patterns teach agents to check for answers before escalating
- CLI command references enable agents to instruct human operators
- Role-specific guidance addresses unique needs of each agent type
- Example scenarios demonstrate the full question-answer workflow

## Related Files

- Plan: [plan_build.yml](live/plan_build.yml) (to be created)
- Guidance Files:
  - `modules/AgenticGuidance/agents/builder/inputs.yml` (to be updated)
  - `modules/AgenticGuidance/agents/planner/inputs.yml` (to be updated)
  - `modules/AgenticGuidance/assets/guidelines/question-workflow.yml` (to be created)

## Next Steps

1. Create `plan_build.yml` with detailed implementation tasks
2. Update agent guidance documents with question workflow
3. Create comprehensive examples and templates
4. Test with builder agents encountering real blockers
5. Hand off to 260203QT for Tmux integration
