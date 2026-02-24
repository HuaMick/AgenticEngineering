# Plan 260221TU: Redesign Question Notification - tmux TUI

Replaces the ntfy push-notification system with a Rich-based tmux TUI for
question answering. The TUI runs in a dedicated tmux window, auto-refreshes
pending questions, and supports inline answering over SSH/Termux.

## Files

- `plan_build.yml` - Implementation phases (P01-P04)
- `plan_test.yml` - Test strategy
- `plan_teach.yml` - Architecture guidance and TUI design rationale
- `plan_audit_clean.yml` - Post-implementation compliance checks
- `orchestration_redesign_question_notification_tmux_tui.mmd` - Execution flowchart

## Entry point

```
agentic question dashboard
```
