# AgenticCore Architecture - 3-Layer Model

## Objective

Refactor the AgenticEngineering module structure to support multiple interfaces (CLI, tmux, voice, web) by:
1. Extracting business logic from AgenticCLI into a new AgenticCore module
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
| Thin CLI + AgenticCore | **SELECTED** (enables reuse) |

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
│  BUSINESS LOGIC LAYER (AgenticCore) - NEW MODULE            │
│  Services:                                                   │
│    - PlanService        (from plan_workflow.py)            │
│    - ContextService     (from context_workflow.py)         │
│    - ConfigService      (from config_workflow.py)          │
│    - TaskService        (from task_workflow.py)            │
│    - StateService       (from state_workflow.py)           │
│    - TemplateService    (from template_workflow.py)        │
│    - EnvironmentService (from environment_workflow.py)     │
│    - SessionService     (NEW - tmux/remote management)     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  DATA LAYER (AgenticGuidance - unchanged)                   │
│  - Agent definitions (YAML)                                 │
│  - Guidelines, definitions, examples                        │
└─────────────────────────────────────────────────────────────┘
```

## User Goals Addressed

| Goal | Implementation |
|------|----------------|
| Code from phone | AgenticVoice WebSocket server calls AgenticCore |
| tmux integration | AgenticTmux calls SessionService + PlanService |
| Voice planning | AgenticVoice calls PlanService for voice-driven planning |
| Thin CLI wrapper | CLI becomes ~2k lines (down from ~12.7k) |

## Phases

### Phase 1: Create AgenticCore Module
- Create `modules/AgenticCore/` structure
- Move workflows from AgenticCLI to AgenticCore services
- Extract shared utilities and models
- Setup pyproject.toml and tests

### Phase 2: Refactor AgenticCLI
- Update CLI to call AgenticCore services
- Remove workflows/ directory
- Keep only presentation logic (commands/, cli.py, console.py)

### Phase 3: Build AgenticTmux
- Create tmux session management module
- Integrate with plan workflow (auto-create sessions)
- Build TUI dashboard for session overview

### Phase 4: Build AgenticVoice
- Create voice interface with STT/TTS
- WebSocket server for phone connection
- Integrate with AgenticCore services for voice commands

## Files Affected

### To Move (AgenticCLI → AgenticCore)
- `workflows/plan_workflow.py` → `services/plan.py`
- `workflows/context_workflow.py` → `services/context.py`
- `workflows/config_workflow.py` → `services/config.py`
- `workflows/task_workflow.py` → `services/task.py`
- `workflows/state_workflow.py` → `services/state.py`
- `workflows/template_workflow.py` → `services/template.py`
- `workflows/environment_workflow.py` → `services/environment.py`

### To Create (New Modules)
- `modules/AgenticCore/` - Business logic layer
- `modules/AgenticTmux/` - Terminal session management
- `modules/AgenticVoice/` - Voice interface

## Key Metrics

| Before | After |
|--------|-------|
| AgenticCLI: ~12,700 lines | AgenticCLI: ~2,000 lines |
| Business logic in CLI | Business logic in AgenticCore |
| 1 interface (CLI) | 4 interfaces (CLI, tmux, voice, web) |
| Code duplication for new interfaces | Shared services, no duplication |

## Related Plans

- `260113LS_langsmith_backend` - LangSmith integration
- `261115CL_agenticcli` - CLI development
