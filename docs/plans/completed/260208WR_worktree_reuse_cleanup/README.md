# Worktree Reuse and Auto-Cleanup

## Problem
The guidance (error-driven-planning-protocol.yml) says:
- "Only create new worktree if ALL existing worktrees have active sessions"
- "Multiple plans per worktree are allowed"
- "New worktree creation is a last resort"

But the CLI (`agentic plan init`) always creates a new worktree and never checks for available ones. Worktrees also never get cleaned up — removal is manual only.

## Goals
1. **Enforce reuse rule** in `agentic plan init` — check for idle worktrees before creating new ones
2. **Auto-cleanup** — remove worktrees when their plans archive to completed/

## Open Questions
- Q1: Should auto-cleanup happen immediately when the last plan in a worktree completes, or on a delay (e.g., after validation confirms staleness)?
- Q2: Should there be a maximum number of worktrees allowed? If so, what's the limit?
- Q3: When reusing a worktree, should the CLI rebase it to latest main automatically?
- Q4: Should there be a "protected" flag to prevent auto-cleanup of certain worktrees?

## Scope
- Modify `agentic plan init` to check for available worktrees first
- Add auto-cleanup hook to plan archiving flow
- Update deploy-worktree agent process.yml to reflect new behavior
- Update error-driven-planning-protocol.yml if needed
- Tests for new behavior
