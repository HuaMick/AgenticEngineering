# AgenticGuidance Services Architecture - 3-Layer Model

## Objective

Refactor the AgenticEngineering module structure to support multiple interfaces (CLI, tmux, voice, web) by:
1. Extracting business logic from AgenticCLI into AgenticGuidance/services/
2. Making AgenticCLI a thin presentation layer
3. Creating AgenticTmux for terminal session management
4. Creating AgenticVoice for voice-based planning and control

## Status

- Current Phase: **Planning**
- Created: 2026-01-26

## Architecture Decision

**Consensus reached via 3 advocate agents:**

| Position | Verdict |
|----------|---------|
| Separate AgenticTmux module | Rejected (creates duplication) |
| Keep in AgenticCLI | Rejected (creates monolith) |
| Thin CLI + AgenticGuidance services | **SELECTED** (enables reuse) |

**Key Decision**: Business logic belongs in AgenticGuidance/services/ because these services interpret guidance. "Core" was rejected as a meaningless name - the services naturally belong with the guidance they interpret.

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER (Thin Interfaces)                       │
│  - AgenticCLI      (~2,000 lines) - argparse + formatting   │
│  - AgenticTmux     (~1,500 lines) - tmux session UI         │
│  - AgenticVoice    (~1,000 lines) - speech + WebSocket      │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  BUSINESS LOGIC LAYER (AgenticGuidance/services/)           │
│  Services:                                                   │
│    - plan.py          (from plan_workflow.py)               │
│    - context.py       (from context_workflow.py)            │
│    - config.py        (from config_workflow.py)             │
│    - task.py          (from task_workflow.py)               │
│    - state.py         (from state_workflow.py)              │
│    - template.py      (from template_workflow.py)           │
│    - environment.py   (from environment_workflow.py)        │
│    - session.py       (NEW - tmux/remote management)        │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  DATA LAYER (AgenticGuidance assets - unchanged)            │
│  - Agent definitions (YAML)                                 │
│  - Guidelines, definitions, examples                        │
└─────────────────────────────────────────────────────────────┘
```

### Target Directory Structure

```
AgenticGuidance/
├── agents/              # Existing YAML definitions
├── assets/              # Existing guidelines, definitions
├── services/            # NEW - Python business logic (moved from CLI)
│   ├── __init__.py
│   ├── context.py       # MainFirstPlanResolver, role loading
│   ├── plan.py          # Plan scaffolding, validation
│   ├── task.py          # Task CRUD
│   ├── config.py        # Configuration management
│   ├── state.py         # Process registry
│   ├── template.py      # Template rendering
│   ├── session.py       # NEW - tmux/remote sessions
│   └── environment.py   # Environment loading
├── models/              # NEW - Data models
│   ├── __init__.py
│   ├── plan.py          # Plan data models
│   ├── task.py          # Task data models
│   └── context.py       # Context data models
└── pyproject.toml       # NEW - Make it a Python package
```

## User Goals Addressed

| Goal | Implementation |
|------|----------------|
| Code from phone | AgenticVoice WebSocket server calls AgenticGuidance services |
| tmux integration | AgenticTmux calls SessionService + PlanService |
| Voice planning | AgenticVoice calls PlanService for voice-driven planning |
| Thin CLI wrapper | CLI becomes ~2k lines (down from ~12.7k) |

## Phases

### Phase 1: Create AgenticGuidance Services Layer
- Create `modules/AgenticGuidance/services/` structure
- Move workflows from AgenticCLI to AgenticGuidance services
- Extract shared utilities and models
- Setup pyproject.toml and tests

### Phase 2: Refactor AgenticCLI
- Update CLI to call AgenticGuidance services
- Remove workflows/ directory
- Keep only presentation logic (commands/, cli.py, console.py)

### Phase 3: Build AgenticTmux
- Create tmux session management module
- Integrate with plan workflow (auto-create sessions)
- Build TUI dashboard for session overview

### Phase 4: Build AgenticVoice
- Create voice interface with STT/TTS
- WebSocket server for phone connection
- Integrate with AgenticGuidance services for voice commands

## Files Affected

### To Move (AgenticCLI → AgenticGuidance/services/)
- `workflows/plan_workflow.py` → `services/plan.py`
- `workflows/context_workflow.py` → `services/context.py`
- `workflows/config_workflow.py` → `services/config.py`
- `workflows/task_workflow.py` → `services/task.py`
- `workflows/state_workflow.py` → `services/state.py`
- `workflows/template_workflow.py` → `services/template.py`
- `workflows/environment_workflow.py` → `services/environment.py`

### To Create
- `modules/AgenticGuidance/services/` - Business logic layer
- `modules/AgenticGuidance/models/` - Data models
- `modules/AgenticTmux/` - Terminal session management
- `modules/AgenticVoice/` - Voice interface

## Key Metrics

| Before | After |
|--------|-------|
| AgenticCLI: ~12,700 lines | AgenticCLI: ~2,000 lines |
| Business logic in CLI | Business logic in AgenticGuidance/services/ |
| 1 interface (CLI) | 4 interfaces (CLI, tmux, voice, web) |
| Code duplication for new interfaces | Shared services, no duplication |

## Related Plans

- `260113LS_langsmith_backend` - LangSmith integration
- `261115CL_agenticcli` - CLI development
