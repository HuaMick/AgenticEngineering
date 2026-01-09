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

Agent categories represent the top-level organizational structure of the MyAgents framework. They group related sub-agents that share a common purpose and responsibility domain.

### What Are Agent Categories?

Categories are organizational units that contain one or more sub-agents. Each category has:
- A clear **purpose** (what problem domain it addresses)
- Defined **responsibilities** (what actions its sub-agents perform)
- Explicit **boundaries** (what the category does NOT do)

### Why Categories Exist

Categories provide several benefits:

1. **Clear Scope Boundaries**: Each category has explicit boundaries that help agents understand when to escalate vs. when to proceed
2. **Logical Organization**: Related capabilities are grouped together, making the framework easier to understand and navigate
3. **Routing Context**: Categories help the orchestrator route tasks to the appropriate specialist agents
4. **Separation of Concerns**: Categories enforce separation between different types of work (planning vs. implementation vs. validation)

### Category Hierarchy

The framework has 9 categories:

1. **Build**: Implementation of code changes and new functionality
2. **Planner**: Create executable implementation plans from objectives
3. **Test**: Validation through testing and quality assurance
4. **Cleaner**: Safe removal of dead code and redundant content
5. **Explore**: Codebase discovery and analysis before planning
6. **Teacher**: Build paths, fences, and signposts for agents
7. **Deploy**: Packaging, CI/CD, and infrastructure management
8. **Documentation**: Maintain minimal, accurate documentation
9. **Orchestration**: Coordinate agent execution and manage workflows

### How Categories Relate to Sub-Agents

Each category contains one or more sub-agents:
- **Category-level responsibilities** define the overall problem domain
- **Sub-agent-level responsibilities** define specific tasks within that domain

For example, the Test category is responsible for "validation through testing" while:
- `test-builder` writes tests
- `test-runner` executes tests
- `test-audit` reviews test quality
- Other test sub-agents handle specific validation tasks

### Canonical Source

The authoritative definition of all categories is maintained at:
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

| Agent | Purpose | Subagents |
|-------|---------|-----------|
| **Planner** | Build execution plans from objectives | planner-build, planner-test, planner-cleaning, planner-guidance, planner-reviewer, planner-guidance-testing |
| **Builder** | Implementation and code changes | build-python, build-flutter |
| **Test** | Validation through testing | test-runner, test-builder, test-user-simulator, test-audit, test-service, test-final-output, test-flutter-builder, test-flutter-runner |
| **Cleaner** | Safe removal with voting consensus | cleaner-identify, cleaner-execute, cleaner-core |
| **Explore** | Codebase discovery before planning | explore-architecture, explore-feature, explore-dependency, explore-test, explore-synthesis |
| **Documentation** | Update docs to match code | documentation-core |
| **Deploy** | Packaging, CI/CD, worktree management | deploy-packaging, deploy-cicd, deploy-worktree |
| **Teacher** | Build paths, fences, and signposts for agents | teacher-plan, teacher-process, teacher-update-assets |

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
    - location: "test/test-runner/inputs.yml"
      description: "Self-contained sub-agent inputs (each sub-agent has its own complete inputs.yml)"
    - location: "process/specific/input.yml"
      description: "Process-specific additions (if needed)"

  steps:
    - "Step 1..."
```

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
    │               ├─→ Test Builder
    │               └─→ Test Runner
    │
    ├─→ audit-test-fix-loop (MANDATORY, max 3)
    │       └─→ Test Auditor + Test Runner
    │
    ├─→ cleaner-voting-loop
    │       ├─→ 3x Cleaner Identify (vote)
    │       └─→ Cleaner Execute
    │
    ├─→ Documentation Agent
    │
    └─→ Deploy Agent
```

