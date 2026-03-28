# Agent Guidance System Architecture

## Hub-and-Spoke Model

```
                    ┌──────────────────────┐
                    │   modules/AgenticGuidance/assets/            │  (HUB)
                    │   ├── definitions/   │
                    │   ├── guidelines/    │
                    │   └── examples/      │
                    └──────────┬───────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
   ┌────▼────┐            ┌────▼────┐           ┌────▼────┐
   │ planner │            │  test   │           │ cleaner │  (SPOKES)
   │inputs.yml│           │inputs.yml│          │inputs.yml│
   └────┬────┘            └────┬────┘           └────┬────┘
        │                      │                      │
   ┌────▼────┐            ┌────▼────┐           ┌────▼────┐
   │process.yml│          │process.yml│         │process.yml│
   └─────────┘            └─────────┘           └─────────┘
```

- **Hub**: `modules/AgenticGuidance/assets/` contains shared definitions, guidelines, and examples
- **Spokes**: Each agent folder has `inputs.yml` referencing the hub
- **Process Files**: Reference their agent's `inputs.yml` as first input

---

## Agent Categories

Agent categories represent the top-level organizational structure of the MyAgents framework.

### Why Categories Exist

Categories provide several benefits:

1. **Clear Scope Boundaries**: Each category has explicit boundaries that help agents understand when to escalate vs. when to proceed
2. **Logical Organization**: Related capabilities are grouped together, making the framework easier to understand and navigate
3. **Routing Context**: Categories help the orchestrator route tasks to the appropriate specialist agents
4. **Separation of Concerns**: Categories enforce separation between different types of work (planning vs. implementation vs. validation)

### Canonical Source

The authoritative definition of all 9 agent categories (Build, Planner, Test, Cleaner, Explore, Teacher, Deploy, Documentation, Orchestration) is maintained at:
`modules/AgenticGuidance/assets/definitions/agent-categories.yml`

This file defines each category's purpose, responsibilities, sub-agents, and boundaries.

---

## Directory Structure

```
modules/AgenticGuidance/agents/
├── modules/AgenticGuidance/assets/                     # HUB: Shared resources
│   ├── definitions/           # Shared terminology and concepts
│   ├── guidelines/            # Reusable behavioral guidelines
│   ├── examples/              # Reference patterns
│   └── processes/             # Reusable process templates
│
├── orchestration/             # Core orchestration files
│   ├── guidelines.yml         # Universal agent guidelines
│   ├── definitions.yml        # Core terminology
│   └── inputs.yml
│
├── {agent}/                   # Agent-specific folders
│   └── {subagent}/
│       ├── inputs.yml         # Core inputs for this subagent
│       └── process.yml        # References inputs.yml first
│
├── docs/                      # Documentation
│   ├── ARCHITECTURE.md        # This file
│   └── agent-role-scope-matrix.md  # Registry of all agents and their scopes
└── ...
```

---

## Agents

For agent roles and scopes, see [agent-role-scope-matrix.md](agent-role-scope-matrix.md).

---

## Agent Role-Scope Matrix

See [agent-role-scope-matrix.md](agent-role-scope-matrix.md) for the complete matrix defining each agent's inputs and scope boundaries.

---

## Guidelines

Located in `modules/AgenticGuidance/assets/guidelines/`:

| Guideline | Purpose |
|-----------|---------|
| `safety.yml` | Separation of concerns, preflight validation, escalation |
| `testing.yml` | Testing strategies (user-simulation-testing, agent-blind-test) |
| `iteration.yml` | Loop patterns and iteration limits |
| `reward-hacking-prevention.yml` | Evidence-based validation, anti-gaming |
| `less-is-more.yml` | Minimal viable changes |
| `fix-the-source.yml` | Root cause analysis |
| `experiment-first.yml` | Discovery before implementation |
| `context-minimisation.yml` | Provide only what's needed |
| `context-offloading.yml` | Move context to files agents read |
| `response-audit.yml` | Final check before output |
| `follow-the-expected-path.yml` | Stay on the defined path |
| `focus-on-what-didnt-work.yml` | Learn from failures |
| `worktree-and-branching.yml` | Source of truth and merge strategy |
| `manifest.yml` | Index of all guidelines |

---

## Input Specification

Each agent's `inputs.yml` follows this structure:

```yaml
inputs:
  agent_type: "test"           # Must match folder name
  version: "1.0"

  core_inputs:
    - type: file | directory | pattern
      path: "relative/path"
      description: "Why needed"
      required: true | false

  guidelines:
    - path: "modules/AgenticGuidance/assets/guidelines/testing.yml"

  definitions:
    term_name: |
      Definition specific to this agent
```

Process files reference inputs.yml as **first input**:

```yaml
process:
  goal: "What this process accomplishes"

  inputs:
    - location: "test/test-builder/inputs.yml"
      description: "Self-contained sub-agent inputs (each sub-agent has its own complete inputs.yml)"
    - location: "process/specific/input.yml"
      description: "Process-specific additions (if needed)"

  steps:
    - "Step 1..."
```

## JIT Context Architecture

Agents use a **Pull-based** (JIT/CCI) context model instead of loading large static files. Thin-client bootstrap files (~350 tokens) instruct agents to fetch context on-demand via CLI commands.

For the complete JIT Context architecture including mermaid diagrams, CLI command reference, Main-First plan resolution, and task lifecycle:

See: [JIT Context Architecture](../../../docs/JIT_CONTEXT_ARCHITECTURE.md)

---

## Execution Flow

```
Orchestrator (with plan)
    │
    ├─→ Explore Agents (parallel) → Synthesis
    │
    ├─→ Planner Agents → Live Plans
    │
    ├─→ Builder Agent
    │       │
    │       └─→ test-fix-loop (max 5)
    │               └─→ Test Builder
    │
    ├─→ audit-test-fix-loop (MANDATORY, max 3)
    │       └─→ Test Auditor + Test Builder
    │
    ├─→ cleaner-dependency-loop (max 3)
    │       ├─→ Cleaner Identify
    │       ├─→ Explorer (dependency check)
    │       └─→ Cleaner Execute
    │
    ├─→ Documentation Agent
    │
    └─→ Deploy Agent
```

