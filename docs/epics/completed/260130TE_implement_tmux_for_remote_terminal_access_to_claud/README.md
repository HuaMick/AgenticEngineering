# Plan: tmux Remote Terminal Access for Claude Code Mobile

**Plan ID:** 260130TE
**Status:** Completed (Validated)
**Branch:** `tmux-remote-terminal`
**Worktree:** `/home/code/AgenticEngineering-tmux-remote-terminal`

## Objective

Enable remote access to Claude Code sessions from mobile devices using the established tmux + Tailscale + SSH workflow (promoted by Geoffrey Huntley and others).

## Background

### Research Findings

The research phase identified a popular workflow for mobile Claude Code access:

1. **Desktop** runs Claude Code inside a tmux session
2. **Tailscale** creates a secure VPN between devices (no firewall config needed)
3. **SSH** connects from mobile to desktop
4. **tmux attach** reconnects to the existing Claude Code session
5. Sessions persist across disconnects

### Existing Infrastructure

| Component | Status | Location |
|-----------|--------|----------|
| AgenticTmux module | Phases 1-2 complete | `modules/AgenticTmux/` |
| SessionService | Complete (46 tests) | `modules/AgenticGuidance/src/.../session.py` |
| AgenticVoice | Deferred | `docs/plans/live/260126AV_agenticvoice/` |

## Plan Structure

```
260130TE_implement_tmux_for_remote_terminal_access_to_claud/
├── README.md                    # This file
├── plan_build.yml               # Build phase tasks
├── plan_test.yml                # Test phase tasks
└── orchestration_tmux_remote.mmd # Execution flowchart
```

## Phases

### Phase 1: tmux Configuration and Scripts
- Create optimized .tmux.conf for remote/mobile access
- Configure tmux-resurrect and tmux-continuum plugins
- Create `agentic-tmux remote setup` command

### Phase 2: Tailscale Integration
- Setup scripts for Tailscale VPN
- Network status command showing connection info
- SSH connection string generation

### Phase 3: Claude Code Session Templates
- Pre-configured session layouts for Claude Code
- Template-based session creation
- Quick-start command for mobile sessions

### Phase 4: agentic CLI Integration
- Register tmux commands with main agentic CLI
- Add remote access info to context bootstrap

## Success Criteria

- [x] `agentic-tmux remote setup` configures desktop for remote access
- [x] `agentic-tmux network status` shows Tailscale IP and connection info
- [x] `agentic-tmux claude-session` creates optimized Claude Code session
- [x] Mobile user can SSH + tmux attach from phone
- [x] Sessions persist across network disconnects (tmux-resurrect + tmux-continuum)
- [x] Configuration optimized for mobile screens

## Validation Notes

- **2026-01-30**: Remote phone access successfully validated. User confirmed SSH + tmux attach workflow from mobile device works correctly.
- **2026-01-30**: Full setup completed including TPM plugins (tmux-resurrect, tmux-continuum, tmux-yank, tmux-prefix-highlight). Session persistence validated.

## Future Integration: AgenticVoice

User expressed desire for voice control integration. AgenticVoice (plan 260126AV) is planned but currently deferred due to missing service dependencies. Voice control for tmux sessions can be added once AgenticVoice is implemented.

## Mobile Clients

| Platform | Recommended App | Notes |
|----------|----------------|-------|
| Android | Termux | Has built-in tmux, SSH client |
| iOS | Blink Shell | MOSH support for unreliable connections |
| Cross-platform | Termius | Good UI, sync across devices |

## References

- [tmux + Tailscale + Claude Code workflow articles](https://dev.to/skeptrune/how-i-use-claude-code-on-my-phone-with-termux-and-tailscale-nge)
- [Existing AgenticTmux plan](../completed/260126AT_agentictmux/plan_build.yml)
- [AgenticVoice deferred plan](260126AV_agenticvoice/)
