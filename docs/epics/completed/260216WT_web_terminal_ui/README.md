# Web Terminal UI

## Objective
Replace tmux-based terminal panels with a browser-based terminal UI using xterm.js + terminado.
Orchestrator terminal on the left, sub-agent terminals appear on the right when spawned.

## Key Decisions
- **No polling**: WebSocket event channel pushes terminal_created/terminal_closed events
- **Hierarchical**: Orchestration agent → sub-agents. Each orchestrator gets its own panel group
- **Self-contained in AgenticFrontend**: Tornado server + xterm.js frontend, no build step
- **Auto-detection**: PTY sets `AGENTIC_TERMINAL_URL` env var so `session spawn` auto-creates web terminals
- **Delete AgenticBackend**: Existing modules already are the backend

## Architecture

```
Browser (localhost:8765)
├── /ws/events          ← WebSocket: terminal lifecycle events
├── /ws/terminals/<name> ← WebSocket: xterm.js ↔ PTY data (per terminal)
├── /api/terminals       ← REST: create/list/delete terminals
└── static/index.html    ← xterm.js split-pane UI

AgenticFrontend/
├── src/agenticfrontend/
│   ├── server.py        ← Tornado + terminado server
│   └── static/
│       └── index.html   ← xterm.js frontend
└── pyproject.toml

Flow:
1. `agentic terminal serve` starts the Tornado server
2. Server creates orchestrator PTY, sets AGENTIC_TERMINAL_URL in its env
3. Orchestrator runs `agentic session spawn --role build-python ...`
4. session spawn detects AGENTIC_TERMINAL_URL, calls POST /api/terminals
5. Server creates sub-agent PTY, pushes terminal_created via /ws/events
6. Frontend receives event, creates new xterm.js terminal on the right
```
