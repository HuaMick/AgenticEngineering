# AgenticTmux

Terminal session management for AgenticEngineering workflows.

## Overview

AgenticTmux provides tmux session management commands integrated with AgenticGuidance services. It acts as a thin presentation layer over the SessionService in AgenticGuidance.

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Create a new session
agentic-tmux session create my-session

# Link to worktree
agentic-tmux session create my-session --worktree /path/to/worktree

# Attach to session
agentic-tmux session attach my-session

# List sessions
agentic-tmux session list

# Kill session
agentic-tmux session kill my-session

# Show session status
agentic-tmux session status my-session
```

## Architecture

AgenticTmux follows the thin-client pattern:
- Business logic lives in `agenticguidance.services.session.SessionService`
- This module provides CLI commands that call the service layer
- Session metadata is persisted in `~/.config/agenticcli/sessions.json`

## Integration

Sessions can be linked to:
- **Worktrees**: Auto-navigate to worktree directory on attach
- **Plan folders**: Track which plan a session is working on
