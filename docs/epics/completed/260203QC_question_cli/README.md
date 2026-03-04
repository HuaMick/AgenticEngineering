# Question CLI - Command-Line Interface for Question Management

**Plan ID**: 260203QC
**Status**: Active
**Created**: 2026-02-03
**Worktree**: `/home/code/AgenticEngineering` (main branch)

## Objective

Implement CLI commands for managing the question/answer queue. This provides the primary text-mode interface for human-in-the-loop (HITL) workflows.

## Scope

This plan implements **CLI commands** for question management:

1. **agentic question list** - Show pending questions for current/specified plan
2. **agentic question show <question-id>** - Display question details
3. **agentic question answer <question-id>** - Provide text-mode answer to a question
4. **agentic question defer <question-id>** - Mark question as deferred
5. **agentic question history** - Show answered questions

## Architecture Context

The CLI is the **primary interface** for the Text-Mode CLI-First strategy:
- Human operators use CLI to review and answer questions
- Voice interface (PersonaPlex) is an optional alternative consumer
- Both interfaces use the same QuestionQueue service from 260203QF

```
┌─────────────────────────────────────────────────────────────┐
│  AgenticGuidance                                             │
│  - Generates questions -> questions/pending/*.yml            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  QuestionQueue Service (from 260203QF)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  CLI Commands (THIS PLAN)                                    │
│  - agentic question list                                     │
│  - agentic question show <id>                                │
│  - agentic question answer <id>                              │
│  - agentic question defer <id>                               │
│  - agentic question history                                  │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

1. **Typer framework**: Follow existing AgenticCLI patterns using Typer
2. **Rich output**: Use rich library for formatted tables and syntax highlighting
3. **Plan context**: Auto-detect current plan or accept `--plan` flag
4. **Interactive prompts**: Multi-line text input for answers using rich.prompt
5. **YAML display**: Pretty-print question/answer YAML for review

## Dependencies

**Depends on**:
- 260203QF (Question Foundation) - QuestionQueue service and data models

**Required by**:
- 260203QG (Question Guidance) - Agents reference CLI commands in guidance
- 260203QT (Question Tmux) - Tmux session uses CLI for HITL workflow

## Implementation Phases

1. **Phase 1: Command Group Setup** - Create `agentic question` command group
2. **Phase 2: List/Show Commands** - Display questions with rich formatting
3. **Phase 3: Answer Command** - Interactive text input for answers
4. **Phase 4: Management Commands** - Defer, history, and status operations

## Success Criteria

- `agentic question list` shows pending questions with severity and context
- `agentic question show <id>` displays full question details with YAML
- `agentic question answer <id>` accepts multi-line text and creates answer YAML
- `agentic question defer <id>` moves question to deferred state
- `agentic question history` shows answered questions with timestamps
- Commands auto-detect current plan context
- `--plan` flag allows explicit plan selection
- Rich formatting makes output readable and actionable
- Unit and integration tests cover all commands

## Related Files

- Plan: [plan_build.yml](live/plan_build.yml) (to be created)
- Module: `modules/AgenticCLI/src/agenticcli/commands/question.py` (to be created)

## Next Steps

1. Create `plan_build.yml` with detailed implementation tasks
2. Implement command group and commands
3. Create integration tests with QuestionQueue
4. Document CLI usage in AgenticCLI README
5. Hand off to 260203QG for agent guidance integration
