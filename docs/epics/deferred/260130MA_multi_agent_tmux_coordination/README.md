# Plan: Multi-Agent tmux Coordination

**Plan ID:** 260130MA
**Status:** Deferred (pending complexity review)
**Branch:** `agentictmux`
**Worktree:** `/home/code/AgenticEngineering-agentictmux`

## Dependencies

| Plan ID | Name | Status | Required |
|---------|------|--------|----------|
| 260130TE | tmux Remote Terminal Access | Completed | Yes (prerequisite) |
| 260123AE | AgenticGuidance Services | Completed | Yes (SessionService) |

## Objective

Enable multiple Claude Code agents to coordinate work through tmux-based session monitoring and file-based messaging, supporting two primary patterns:
1. **Supervisor/Worker** - An orchestrator spawns and monitors multiple worker agents
2. **Quality Gate** - A reviewer must approve work before phases can proceed

## Background

### Research Findings

This plan builds on the completed AgenticTmux remote access feature (260130TE). Research identified key coordination patterns from:
- Geoffrey Huntley's Ralph Wiggum Technique (file-based state)
- mitsuhiko/agent-stuff (tmux capture-pane patterns)
- Agent Conductor (supervisor/worker with inbox messaging)
- Claude Squad (multi-agent management with worktrees)

### Technical Approach

| Component | Implementation |
|-----------|----------------|
| Terminal Output Reading | `tmux capture-pane -p -J -t session:window.pane -S -200` |
| Inbox Messaging | File-based at `~/.agentic/coordination/inbox/{session}/` |
| Session Roles | Extend SessionService with supervisor/worker/observer roles |
| Approval Gates | Block plan phase transitions until approval received |

### Existing Infrastructure

| Component | Status | Location |
|-----------|--------|----------|
| SessionService | Complete (46 tests) | `modules/AgenticGuidance/src/.../session.py` |
| AgenticTmux commands | Complete | `modules/AgenticTmux/src/agentictmux/commands/` |
| Plan CLI | Complete | `modules/AgenticCLI/src/agenticcli/commands/plan.py` |
| tmux Remote Access | Complete (260130TE) | Installed at `~/.tmux.conf` |

## Plan Structure

```
260130MA_multi_agent_tmux_coordination/
├── README.md                          # This file
├── plan_build.yml                     # Build phase tasks
├── orchestration_multi_agent.mmd      # Execution flowchart
├── proposal_supervisor_worker.md      # Supervisor/Worker pattern design
└── proposal_quality_gate.md           # Quality Gate pattern design
```

## Phases

### Phase 1: Session Role Infrastructure
- Extend SessionInfo with role field (supervisor/worker/observer)
- Add role-based session queries to SessionService
- Create `agentic coord supervisor create` command

### Phase 2: Terminal Output Capture
- Implement `capture_pane()` using `tmux capture-pane -p -J`
- Create `agentic coord observe capture <session>` command
- Add output parsing utilities for structured data extraction

### Phase 3: Inbox Messaging System
- Create file-based message passing at `~/.agentic/coordination/inbox/`
- Implement message schema (type, sender, recipient, payload, timestamp)
- Create inbox send/read/poll commands

### Phase 4: Supervisor/Worker Pattern
- Implement CoordinationService for spawning and tracking workers
- Create supervisor coordination loop with health monitoring
- Add worker status reporting via inbox

### Phase 5: Quality Gate Pattern
- Extend plan CLI with approval gate support
- Create `agentic review request/approve/reject` commands
- Implement approval blocking for phase transitions

### Phase 6: CLI Integration and Documentation
- Register new commands with agentic CLI
- Update help documentation
- Create usage examples and integration tests

## Success Criteria

### Functional Acceptance

- [ ] `agentic coord supervisor create` creates role-tagged session
- [ ] `agentic coord observe capture <session>` reads terminal output
- [ ] `agentic coord supervisor spawn-worker` creates worker with task
- [ ] Supervisor can monitor all workers via `observe monitor`
- [ ] File-based inbox messaging between sessions works
- [ ] Quality gate blocks phase transition until approved

### Quality Acceptance

- [ ] All new functionality has test coverage >= 80%
- [ ] No regressions in existing SessionService tests (46 tests)
- [ ] CLI commands have proper help text and error handling
- [ ] Integration tests pass on Linux environment

### Documentation Acceptance

- [ ] CLI commands documented with usage examples
- [ ] API documentation for CoordinationService and ReviewService
- [ ] Troubleshooting guide for common issues

## Use Cases

### Supervisor/Worker Pattern
```bash
# Create supervisor session
agentic coord supervisor create build-orchestrator --plan 260130MA

# Spawn workers for parallel tasks
agentic coord supervisor spawn-worker \
    --supervisor build-orchestrator \
    --worker-name backend-builder \
    --task "Build backend services"

agentic coord supervisor spawn-worker \
    --supervisor build-orchestrator \
    --worker-name frontend-builder \
    --task "Build frontend application"

# Monitor all workers
agentic coord observe monitor --supervisor build-orchestrator

# Check worker health
agentic coord status --supervisor build-orchestrator
```

### Quality Gate Pattern
```bash
# Worker requests review before phase completion
agentic review request --phase build_backend --reviewer senior-dev

# Reviewer observes worker session
agentic coord observe capture backend-builder --lines 200

# Reviewer approves or rejects
agentic review approve --phase build_backend
# OR
agentic review reject --phase build_backend --reason "Missing tests"
```

## Related Plans

- [260130TE - tmux Remote Terminal Access](../completed/260130TE_implement_tmux_for_remote_terminal_access_to_claud/) (prerequisite, completed)
- [260123AE - AgenticGuidance Services](../completed/260123AE_agenticguidance/) (prerequisite, completed)
- [260126AV - AgenticVoice](../live/260126AV_agenticvoice/) (future integration)

## References

- [Agent Conductor](https://github.com/gaurav-yadav/agent-conductor) - Supervisor/worker reference implementation
- [Claude Squad](https://github.com/smtg-ai/claude-squad) - Multi-agent tmux management
- [mitsuhiko/agent-stuff](https://github.com/mitsuhiko/agent-stuff) - tmux capture-pane patterns
- [Anthropic Multi-Agent Research](https://www.anthropic.com/engineering/multi-agent-research-system) - 90% performance improvement with multi-agent
