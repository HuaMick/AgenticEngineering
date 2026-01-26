# AgenticTmux Module

## Objective

Create AgenticTmux module for terminal session management, providing a unified interface for managing tmux sessions within the AgenticEngineering ecosystem.

## Dependency

**BLOCKED** - This plan is blocked until the AgenticGuidance services refactor is complete (260123AE_agenticguidance). The SessionService foundation must be established in AgenticGuidance/services/ before AgenticTmux can be built on top of it.

## Architecture

AgenticTmux will be a thin presentation layer for tmux session management. The core business logic lives in AgenticGuidance:

```
┌─────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                          │
│  - AgenticTmux     (~1,500 lines) - tmux session UI         │
│    - commands/session.py - CLI commands                     │
│    - tui/dashboard.py - Terminal UI                         │
└─────────────────────┬───────────────────────────────────────┘
                      │ imports from
┌─────────────────────▼───────────────────────────────────────┐
│  SERVICE LAYER (AgenticGuidance/services/)                   │
│  - session.py     - Session lifecycle management            │
│  - plan.py        - Plan-session integration                │
│  - worktree.py    - Worktree-session mapping                │
│                                                              │
│  Location: modules/AgenticGuidance/src/agenticguidance/     │
│            services/session.py                               │
└─────────────────────────────────────────────────────────────┘
```

### Import Pattern

```python
# In AgenticTmux commands
from agenticguidance.services.session import SessionService
from agenticguidance.services.plan import PlanService
```

## Phases

### Phase 1: Module Structure and SessionService in AgenticGuidance
- Define AgenticTmux module structure and interfaces
- Implement SessionService base class in AgenticGuidance/services/session.py
- Establish session lifecycle management patterns
- Create session configuration schema

### Phase 2: tmux Session Commands
- Implement `tmux session create` command
- Implement `tmux session attach` command
- Implement `tmux session list` command
- Implement `tmux session kill` command
- Add session naming conventions and validation

### Phase 3: Integration with Worktree and Plan Workflows
- Auto-create sessions for new worktrees
- Link sessions to active plans
- Session environment variable injection
- Worktree-session mapping persistence

### Phase 4: TUI Dashboard for Session Overview
- Real-time session status display
- Session switching interface
- Resource usage monitoring
- Log streaming integration

## File Paths

### AgenticGuidance Services (Blocker: 260123AE_agenticguidance)
- `modules/AgenticGuidance/src/agenticguidance/services/session.py`

### AgenticTmux Module (This Plan)
- `modules/AgenticTmux/src/agentictmux/__init__.py`
- `modules/AgenticTmux/src/agentictmux/commands/session.py`
- `modules/AgenticTmux/src/agentictmux/tui/dashboard.py`

## Status

**Status:** Pending (Blocked)
**Blocked By:** 260123AE_agenticguidance
**Created:** 2026-01-26
**Plan ID:** 260126AT
