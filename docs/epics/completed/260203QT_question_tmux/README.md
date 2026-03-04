# Question Tmux - Remote Session Support for HITL Workflow

**Plan ID**: 260203QT
**Status**: Active
**Created**: 2026-02-03
**Worktree**: `/home/code/AgenticEngineering` (main branch)

## Objective

Implement Tmux session support for human-in-the-loop (HITL) workflows, enabling remote operators to review and answer agent questions via CLI in a dedicated Tmux pane.

## Scope

This plan implements **Tmux-based HITL** workflow support:

1. **Tmux session detection**: Identify if agent is running in Tmux
2. **Question notification pane**: Create/update a dedicated pane for pending questions
3. **CLI integration**: Display `agentic question` commands in notification pane
4. **Polling/watching**: Optional file watcher to update notification pane
5. **Resumption signals**: Agent waits for answer before continuing

## Architecture Context

This plan enables **remote HITL workflows** where operators answer questions from another terminal:
- Agent generates question while running in Tmux
- Question notification appears in dedicated Tmux pane
- Operator switches to notification pane, runs CLI commands to answer
- Agent detects answer and resumes work

```
┌─────────────────────────────────────────────────────────────┐
│  Tmux Session                                                │
│  ┌───────────────────────────┬──────────────────────────┐   │
│  │ Pane 1: Agent Execution   │ Pane 2: Question Queue   │   │
│  │                            │                           │   │
│  │ Agent: "I need input..."  │ PENDING QUESTIONS:        │   │
│  │ Generated: q_001          │                           │   │
│  │ Waiting for answer...     │ [1] q_001 (high)          │   │
│  │                            │ Module: agenticvoice      │   │
│  │                            │ Question: "Should we..."  │   │
│  │                            │                           │   │
│  │                            │ To answer:                │   │
│  │                            │ agentic question answer   │   │
│  │                            │   q_001                   │   │
│  └───────────────────────────┴──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

1. **Tmux-native**: Use `tmux split-window` and `tmux send-keys` for pane management
2. **Optional feature**: Gracefully degrade if not in Tmux (use stderr notification)
3. **File watcher**: Use `watchdog` to monitor questions/ folder and update pane
4. **CLI-centric**: Notification pane shows CLI commands, not interactive prompts
5. **Session context**: Use `TMUX` environment variable to detect Tmux sessions

## Dependencies

**Depends on**:
- 260203QF (Question Foundation) - QuestionQueue service
- 260203QC (Question CLI) - CLI commands displayed in notification pane
- 260203QG (Question Guidance) - Agents use updated patterns for question generation

**Required by**:
- None (optional enhancement for remote workflows)

**Related to**:
- 260203VP (Voice PersonaPlex) - Alternative HITL interface (voice instead of Tmux)

## Implementation Phases

1. **Phase 1: Tmux Detection** - Detect Tmux environment and session info
2. **Phase 2: Notification Pane** - Create/update dedicated pane with question list
3. **Phase 3: File Watcher** - Monitor questions/ folder for changes
4. **Phase 4: Agent Integration** - Update workflow to use Tmux notifications

## Success Criteria

- Agent detects when running in Tmux session
- Dedicated notification pane is created automatically
- Pending questions displayed with severity and context
- CLI commands shown for answering questions
- File watcher updates pane when new questions arrive
- Graceful fallback when not in Tmux (stderr messages)
- Operator can answer questions from notification pane
- Agent resumes work after answer is provided
- Integration tests validate Tmux workflow end-to-end

## Related Files

- Plan: [plan_build.yml](live/plan_build.yml) (to be created)
- Module: `modules/AgenticGuidance/src/agenticguidance/utils/tmux.py` (to be created)
- Workflow: `modules/AgenticGuidance/src/agenticguidance/workflows/question_workflow.py` (to be updated)

## Next Steps

1. Create `plan_build.yml` with detailed implementation tasks
2. Implement Tmux detection and pane management
3. Create file watcher for question notifications
4. Update agent workflows to use Tmux notifications
5. Test with real agent execution in Tmux session
6. Document Tmux workflow in AgenticGuidance README
