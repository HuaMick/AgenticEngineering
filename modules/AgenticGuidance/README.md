# AgenticGuidance

> **Note**: This project is in early development. This document describes the module's purpose and direction, not its current implementation state.

The guidance layer for Claude Code sessions within the AgenticEngineering ecosystem. AgenticGuidance provides the constraints, patterns, and behavioral rules that shape how Claude Code works.

## Purpose

Claude Code is the agent. AgenticGuidance provides the **knowledge layer** that helps Claude Code work more effectively by supplying:

- **Definitions**: Stable concepts and terminology ("what is X?")
- **Guidelines**: Behavioral rules and constraints ("how to act")
- **Patterns**: Reusable approaches for common situations
- **Boundaries**: Scope limits that prevent drift

The goal is focused, consistent agent behavior through minimal, well-structured guidance.

## Current State

**Implemented**: Nothing yet. This directory is a placeholder for future development.

**Planned**: A structured system for organizing and delivering guidance to Claude Code sessions.

## Design Direction

### Core Guidance Types

Based on patterns from the legacy MyAgentsGuidance system, guidance falls into two primary categories:

| Type | Purpose | Character |
|------|---------|-----------|
| **Definitions** | Name concepts and explain meaning | Descriptive ("what it is") |
| **Guidelines** | Shape behavior and decisions | Prescriptive ("what to do") |

**Definitions** should be:
- Stable, concise, and broadly applicable
- Reusable across different contexts
- Free of project-specific details where possible

**Guidelines** should be:
- Actionable and testable where possible
- Include minimal rationale to prevent misapplication
- Reference definitions rather than duplicating explanations

### Foundational Principles

These principles from the legacy system inform the direction:

**Context Minimization**
Provide only what's needed. Irrelevant context dilutes attention and increases error risk. Load guidance just-in-time for the current task.

**Less is More**
Make minimal sufficient changes. Complete requirements without "nice-to-have" additions. Stop when success criteria are met.

**Fix the Source**
Address root causes, not symptoms. Symptom-masking creates technical debt. Trace problems back to their origin.

### Planned Structure

```
AgenticGuidance/
├── definitions/           # Stable concepts
│   ├── context-minimization.yml
│   ├── minimal-sufficient-change.yml
│   └── ...
├── guidelines/            # Behavioral rules
│   ├── less-is-more.yml
│   ├── fix-the-source.yml
│   └── ...
├── patterns/              # Reusable approaches (TBD)
└── examples/              # Reference implementations (TBD)
```

### Path Resolution

AgenticGuidance uses two path resolution strategies:

| Path Type | Convention | Resolved Against | Example |
|-----------|------------|------------------|---------|
| **Module-relative** | Paths NOT starting with `docs/` | AgenticGuidance module root | `modules/AgenticGuidance/assets/`, `modules/AgenticGuidance/agents/`, `definitions/` |
| **Repo-relative** | Paths starting with `docs/` | Target repository root (at orchestration time) | `docs/userstories/`, `docs/plans/` |

**Why this distinction?**
- Module-relative paths reference AgenticGuidance's own resources (definitions, guidelines, assets)
- Repo-relative paths reference artifacts that belong to the target project being worked on (user stories, plans, documentation)

The orchestration layer resolves repo-relative paths against whichever repository AgenticGuidance is operating within.

## Relationship to AgenticEngineering

AgenticGuidance is one of three project modules:

```
AgenticEngineering/
├── modules/
│   ├── AgenticBackend/    # Backend services
│   ├── AgenticFrontend/   # Frontend UI
│   └── AgenticGuidance/   # This module - guidance layer
```

The main `docs/README.md` describes the overall architecture. AgenticGuidance serves the **Guidance Files** component in that architecture:

```
┌─────────────────────────────────────────────────────────┐
│                     Claude Code                          │
└─────────────────────────┬───────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    ┌─────────┐    ┌───────────┐    ┌───────────┐
    │   CLI   │    │  Planning │    │  Guidance │  ← AgenticGuidance
    │ Commands│    │  Folders  │    │   Files   │
    └─────────┘    └───────────┘    └───────────┘
```

## Legacy Reference

The `modules/legacy/MyAgents/projects/MyAgentsGuidance/` directory contains the previous guidance system, which organized guidance for a 9-category, 35+ sub-agent framework:

**Key legacy patterns to draw from:**
- `modules/AgenticGuidance/assets/definitions/`: 70+ definition files covering concepts from context-minimization to test structures
- `modules/AgenticGuidance/assets/guidelines/`: 15+ guideline files for behavioral rules (less-is-more, fix-the-source, etc.)
- `modules/AgenticGuidance/assets/examples/`: Project-specific reference implementations
- YAML-based structure with cross-references between files

**What's different now:**
- Claude Code's capabilities have advanced, reducing the need for specialized sub-agents
- Focus shifts from orchestrating many agents to guiding a single, capable agent (Claude Code)
- Simpler structure needed: fewer categories, more focused guidance

## Aspirations

1. **Deliver focused guidance** that improves Claude Code session quality without overwhelming context
2. **Capture proven patterns** from actual Claude Code usage (via LangSmith traces when configured)
3. **Evolve through evidence** - guidance that doesn't improve outcomes should be removed
4. **Stay minimal** - the best guidance is the guidance you don't need to write

## Contributing

This project follows the AgenticEngineering contribution model:

1. Claude Code works on tasks
2. Friction points are identified (via traces or manual analysis)
3. Patterns that address friction are documented as guidance
4. Guidance is validated through actual use
5. Ineffective guidance is removed

---

*Part of [AgenticEngineering](../../docs/README.md) - scaffolding for Claude Code sessions*
