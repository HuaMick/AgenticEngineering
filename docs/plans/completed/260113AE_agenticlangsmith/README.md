# AgenticLangSmith Lean Plan

## Overview
This is a high-speed, 5-step deployment for LangSmith tracing across your AgenticEngineering worktrees. It eliminates the 29 redundant tasks and "syslink architecture" of the previous iteration in favor of a direct, durable installation.

## Deployment Roadmap
1. **Validation**: Check dependencies.
2. **Hook Installation**: Deploy `stop_hook.sh` to `~/.claude/hooks/`.
3. **Global Config**: Register the hook in Claude's global settings.
4. **Worktree Sync**: Batch-configure environment variables and Git ignores.
5. **Verification**: Confirm traces appear in LangSmith.

## Status
- **Current Iteration**: 12 (The "Hooks Format Fix" Iteration)
- **Status**: COMPLETED - Hooks format corrected

## Change Log
### Iteration 12
- **Issue**: Claude Code hooks format changed - now requires nested `hooks` array with optional `matcher`
- **Fix**: Updated `~/.claude/settings.json` from old format to new matcher-based format
- **Old**: `{"type": "command", "command": "..."}` directly in Stop array
- **New**: `{"hooks": [{"type": "command", "command": "..."}]}` with nested hooks array

## Execution Summary
Phases 1-3 establish the global capability. Phase 4 activates it for your specific worktrees. Phase 5 confirms success.

**Required from User**: Your LangSmith API Key (QUESTION-001).
