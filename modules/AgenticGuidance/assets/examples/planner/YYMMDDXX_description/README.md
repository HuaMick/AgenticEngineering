# Plan Example

This example demonstrates the **unified plan pattern**:
- `live/plan_<name>.yml` - Plan definition (phases, tasks, inputs, success criteria)
- `orchestration_<name>.mmd` - Execution flow (Mermaid diagram with agents and loops)

## Folder Structure

```
YYMMDDXX_description/
├── README.md                   # This file
├── orchestration_example.mmd   # Visual execution flow with agents and loops
├── live/                       # Active plans
│   └── plan_example.yml        # Unified plan with all phases
├── completed/                  # Archived completed plans
│   └── plan_completed.yml      # Summary of completed work
└── reference/                  # Supporting reference material
    └── test-scenarios-detailed.yml
```

## When to Split vs Keep Unified

**Context minimisation** is the deciding factor.

### Keep Unified (Default)

A single plan file is the default. Use this when:
- Phases share context, inputs, or open_questions
- Total plan size is manageable (~500 lines or less)
- Cross-phase dependencies exist
- Agents benefit from seeing the full picture

### Split Into Multiple Files

Split only when context minimisation provides clear benefit:
- Plan exceeds ~500 lines (context dilution becomes a problem)
- Phases have completely independent inputs (no shared context)
- Different agents need strictly different subsets of information
- Large amounts of phase-specific guidance that other agents do not need

See: `modules/AgenticGuidance/assets/guidelines/context-minimisation.yml`

## Plan File Structure

The plan file (`live/plan_example.yml`) contains:
- **Root metadata**: name, worktree_path, branch, status, priority
- **Context**: Running narrative of progress
- **Related plans**: Link to orchestration MMD
- **Inputs**: Pre-gathered context needed across phases
- **Open questions**: Human-authority decisions
- **Phases and tasks**: All phases in one file (default)
- **Success criteria**: Definition of done

## Orchestration File

The orchestration file (`orchestration_example.mmd`) defines:
- **Header comments**: GOAL, PROFILE, INPUT_PATH, guidelines
- **Flowchart structure**: Start/End nodes, decision points
- **Subgraphs**: Logical phase groupings
- **Agent spawns**: Which agents execute each phase
- **Loops**: Iteration patterns (test-fix-loop, etc.)
- **Feedback paths**: Re-planning triggers

See: `modules/AgenticGuidance/assets/specifications/plan-mmd-schema.yml`

## Update Patterns

### Recording Progress

Update the context section:

```yaml
context: |
  UPDATE YYYY-MM-DD (Session 1): Initial planning completed.
  UPDATE YYYY-MM-DD (Session 2): Domain layer complete.
  UPDATE YYYY-MM-DD (Session 3): Workflow layer in progress.  # Add new
```

### Updating Task Status

```yaml
tasks:
  - id: "dev_001"
    name: "Domain Layer Build"
    status: "completed"        # Change from "in_progress"
    completed_date: "YYYY-MM-DD"
```

### Recording Human Decisions

```yaml
open_questions:
  - id: "QUESTION-001"
    status: "ANSWERED"          # Change from "OPEN"
    answer: "Use constructor injection"
    answered_by: "HUMAN"        # Marks as authoritative
```

Once answered by HUMAN, the decision has authority and must not be reversed by AI.

## Key References

| Resource | Purpose |
|----------|---------|
| `live/plan_example.yml` | Unified plan structure example |
| `orchestration_example.mmd` | Visual agent flow diagram |
| `context-minimisation.yml` | When and why to split plans |
| `plan-mmd-schema.yml` | Orchestration file schema |
