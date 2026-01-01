# AgenticEngineering

> **Note**: This document describes the target architecture. The repository is in early development—directories and features described here are aspirational until implemented.

A scaffolding and orchestration layer for Claude Code sessions, designed around the principle of **progressive automation through CLI maturity**.

## Vision

Claude Code is the agent. This repository provides the **memory, guidance, and tooling layer** that augments Claude Code sessions with:

- **Persistent context** across sessions (planning folders, project knowledge)
- **Guidance constraints** (rules, patterns, scope boundaries)
- **Mature CLI commands** for predictable, repetitive processes

The goal is not to build custom agents—Claude Code's capabilities continue to improve rapidly. Instead, we build scaffolding that helps Claude Code work more effectively, and let Claude Code build its own tooling.

## Core Principle: CLI as Maturity Layer

Processes evolve through a maturity lifecycle:

```
Agent Reasoning (flexible, exploratory)
        ↓
LangSmith Traces (capture execution patterns)
        ↓
Teacher Analysis (identify friction points)
        ↓
Pattern Recognition (what's predictable?)
        ↓
CLI Command (deterministic, reliable)
```

**Early stage**: Claude Code reasons through a process manually, making decisions at each step.

**Mature stage**: Predictable patterns are codified into CLI commands. Claude Code calls the CLI instead of reasoning through known territory, freeing cognitive capacity for novel problems.

This is evidence-based automation—LangSmith traces reveal actual friction points, not guessed ones.

## Architecture

### Claude Code + CLI + Planning Folders

```
┌─────────────────────────────────────────────────────────┐
│                     Claude Code                          │
│              (reasoning, tool use, code)                 │
└─────────────────────────┬───────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    ┌─────────┐    ┌───────────┐    ┌───────────┐
    │   CLI   │    │  Planning │    │  Guidance │
    │ Commands│    │  Folders  │    │   Files   │
    └─────────┘    └───────────┘    └───────────┘
    (mature        (persistent      (constraints,
     processes)     state)           patterns)
```

- **Claude Code**: The agent—handles reasoning, code generation, tool execution
- **CLI Commands**: Crystallized patterns—deterministic operations that don't need reasoning
- **Planning Folders**: Persistent state—YAML files tracking work across sessions
- **Guidance Files**: Constraints and patterns—rules that shape agent behavior

### Five Workflow Phases

Work flows through five lifecycle phases (distinct from legacy's 9 agent categories—these are workflow stages, not agent organization):

| Category | Purpose | Maturity Target |
|----------|---------|-----------------|
| **Explore** | Understand codebase, gather context | Medium—discovery requires reasoning |
| **Plan** | Decompose objectives into executable phases | Medium—decomposition requires judgment |
| **Build** | Implement code changes | Low-Medium—implementation varies |
| **Test** | Validate changes work correctly | High—test execution is predictable |
| **Deploy** | Package, release, infrastructure | High—deployment is procedural |

Categories toward the end of the lifecycle (Test, Deploy) tend to mature into CLI commands faster because they're more procedural.

## Directory Structure

```
AgenticEngineering/
├── docs/
│   ├── README.md              # This file
│   └── plans/                 # Planning folders (state)
│       ├── live/              # Active work
│       │   └── YYMMDDRepo_Branch/
│       │       ├── live/
│       │       │   └── plan_live_<purpose>.yml  # Named by purpose (build, test, teach, audit, etc.)
│       │       └── completed/
│       │           └── plan_completed.yml
│       ├── completed/         # Finished work (reference)
│       └── backlog/           # Future work
│
├── modules/
│   ├── AgenticBackend/        # Backend services (future)
│   ├── AgenticFrontend/       # Frontend UI (future)
│   ├── AgenticGuidance/       # Guidance system (future)
│   └── legacy/
│       └── MyAgents/          # Legacy reference (submodule)
│
├── cli/                       # CLI commands (future)
│   └── (mature patterns live here)
│
└── guidance/                  # Guidance files (future)
    ├── definitions/           # Structural knowledge
    ├── guidelines/            # Behavioral constraints
    └── examples/              # Reference implementations
```

## Planning Folders

Planning folders provide persistent state across Claude Code sessions:

### Naming Convention
`YYMMDDRepo_Branch` — e.g., `251230AgenticEngineering_main`

### Structure

Plan files are named by purpose (e.g., `plan_live_build.yml`, `plan_live_test.yml`, `plan_live_teach.yml`, `plan_live_audit.yml`):

```yaml
# plan_live_<purpose>.yml
objective: "What this plan accomplishes"
phases:
  - phase: 1
    name: "Phase description"
    tasks:
      - id: "TASK-001"
        status: pending          # pending | in_progress | complete
        description: "What the task does"
        acceptance_criteria:
          - "Measurable outcome 1"
          - "Measurable outcome 2"
        files:
          - path/to/affected/file
```

### Lifecycle
1. Tasks start as `pending`
2. Active work moves to `in_progress`
3. Completed tasks move to `completed/plan_completed.yml`
4. When all phases complete, folder moves to `docs/plans/completed/`

## CLI Commands (As They Mature)

CLI commands are documented here as they're codified from mature patterns.

### Currently Available
*(None yet—patterns still maturing)*

### Candidates (Based on Legacy Analysis)
These patterns from `modules/legacy/MyAgents/` show high maturity and are candidates for CLI:

| Pattern | Maturity | Notes |
|---------|----------|-------|
| `worktree create` | High | Git worktree + planning folder scaffolding |
| `worktree deploy` | High | Full worktree setup with VS Code workspace update |
| `test run` | High | Execute tests, parse results, report |
| `clean execute` | High | Remove approved targets with safety checks |
| `plan update` | Medium | State management for planning folders |

## LangSmith Integration

> **Status**: LangSmith tracing is configured in the legacy system. Setup for this project is pending.

LangSmith traces capture Claude Code execution patterns, enabling data-driven maturity:

1. **Trace collection**: Claude Code sessions trace to LangSmith (requires setup)
2. **Friction analysis**: Identify where Claude Code struggles or repeats work
3. **Pattern extraction**: Find consistent patterns across traces
4. **CLI codification**: Convert proven patterns to deterministic commands

Until LangSmith is configured, friction analysis can be done manually via markdown notes in planning folders (as legacy demonstrates in `analysis/friction-analysis.md` files).

## Legacy Reference

`modules/legacy/MyAgents/` contains the previous agent scaffolding system, preserved as reference:

- **9 agent categories**: Build, Planner, Test, Cleaner, Explore, Teacher, Deploy, Documentation, Orchestration
- **35 sub-agents**: Specialized agents that Claude Code's capabilities now subsume
- **Hub-and-spoke architecture**: Central assets with agent-specific references (pattern still relevant)
- **Extensive documentation**: Patterns, anti-patterns, strategies, friction analyses
- **Planning folder conventions**: YAML-based state management (adopted in this system)

The legacy system's value is in its documented patterns, friction analyses, and proven conventions. The separate `/home/code/myagents/MyAgentsGuidance-staging/` repository contains the detailed agent guidance if deeper reference is needed.

## Contributing

This scaffolding is built by Claude Code, for Claude Code. The primary workflow:

1. Claude Code works on tasks using this scaffolding
2. Friction points are captured (via LangSmith traces once configured, or manual analysis)
3. Patterns that stabilize get proposed as CLI commands
4. CLI commands are implemented and documented here
5. Claude Code uses CLI commands, freeing reasoning for novel work

## Principles

### Context Minimization
Provide only what's needed. Large context windows don't mean dump everything in—focused context produces better reasoning.

### Less is More
Make minimal sufficient changes. Don't add features, refactor code, or make "improvements" beyond what's asked.

### Fix the Source
Address root causes, not symptoms. If a pattern keeps causing friction, fix the pattern—don't keep working around it.

### Progressive Automation
Start manual, graduate to automated. Don't pre-build CLI commands for hypothetical patterns. Wait for evidence.

### Evidence-Based
Use traces, not intuition. LangSmith shows where friction actually occurs—that's what gets automated.
