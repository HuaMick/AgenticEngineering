# Question Auto-Notify on Creation

## Problem
The bidirectional phone notification system (ntfy) works well WHEN a watcher daemon is running. But questions created by agents during plan execution don't automatically notify the user's phone unless someone manually starts `agentic question watch-daemon`.

### Current Flow (broken)
1. Agent creates blocking question via `agentic question ask`
2. Question sits in `<plan>/questions/pending/`
3. User never knows unless they check manually or have watcher running
4. Plan execution blocks silently

### Desired Flow
1. Agent creates blocking question via `agentic question ask`
2. Phone notification sent immediately
3. User answers from phone via ntfy reply
4. NtfyReplyPoller picks up answer, auto-resolves question
5. Plan execution continues

## Root Cause
- `notify_new_question()` lives in `agenticcli.utils.ntfy` (CLI module)
- `QuestionQueue.create_question()` lives in `agenticguidance.services.question` (Guidance module)
- No hook connects creation to notification
- Watcher daemon bridges the gap but must be manually started

## Goals
1. Auto-send ntfy notification when a question is created (without requiring watcher)
2. Auto-start NtfyReplyPoller when questions exist (without requiring watcher daemon)
3. Orchestration executor should auto-start question watching before phase execution

## Open Questions
- Q1: Should we add ntfy as a hook in `cmd_ask()` directly (CLI-level), or find a way to hook it into QuestionQueue (service-level)?
- Q2: Should the orchestration executor guidance be updated to auto-start `agentic question watch-daemon` before executing phases?
- Q3: Should ALL questions trigger phone notifications, or only blocking/high severity ones?
- Q4: Is there a risk of circular dependency if AgenticGuidance imports from AgenticCLI for ntfy?

## Scope
- Add ntfy notification hook to question creation flow
- Auto-start reply polling when questions are created
- Update orchestration-executor guidance to start watcher
- Tests for auto-notify behavior
