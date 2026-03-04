# Phone Notifications via ntfy + Interactive Wizard

**Plan ID**: 260208PN
**Status**: Active
**Created**: 2026-02-08

## Objective

Add phone push notifications via ntfy and interactive wizard CLI for answering questions from mobile.

## Scope

1. **ntfy integration** - Push notifications to phone when questions arrive
2. **Interactive wizard CLI** - `agentic question answer --interactive` for easy mobile answering
3. **Suggested answers** - Pre-defined answer options for common question types

## Architecture

```
Agent creates question → Daemon detects new question
                       → Sends ntfy push to phone
                       → User SSHs via Termux
                       → Runs: agentic question answer --interactive
                       → Selects from suggested answers or types custom
                       → Agent resumes work
```

## Implementation Phases

| Phase | Description | Tasks |
|-------|-------------|-------|
| Phase 1 | ntfy notification hook | Add ntfy client to question watcher |
| Phase 2 | Configuration | Add ntfy topic to config schema |
| Phase 3 | Interactive wizard | `--interactive` flag with rich prompts |
| Phase 4 | Suggested answers | Answer presets in question YAML |

## Dependencies

- 260203QF (Question Foundation) - ✅ Completed
- 260203QC (Question CLI) - ✅ Completed
- 260203QT (Question Tmux) - ✅ Completed

## Success Criteria

- [ ] ntfy notifications sent on new questions
- [ ] `agentic question answer --interactive` works
- [ ] Suggested answer options displayed
- [ ] Free-text fallback available
- [ ] Works from Termux on phone
