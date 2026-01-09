# Unified Plan Pattern Example

This example demonstrates the **unified plan architecture** pattern:
- `plan_<name>.yml` - Plan definition (phases, tasks, inputs, success criteria)
- `orchestration_<name>.mmd` - Execution flow (Mermaid diagram with agents and loops)

## The Unified Pattern

Plans follow the naming convention `plan_<name>.yml` + `orchestration_<name>.mmd`:

| Plan File | Orchestration File | Purpose |
|-----------|-------------------|---------|
| `plan_example.yml` | `orchestration_example.mmd` | Reference example (root level) |
| `live/plan_live_build.yml` | - | Active implementation phases |
| `live/plan_live_test.yml` | - | Active testing phases |
| `live/plan_live_teach.yml` | - | Active guidance improvement |
| `live/plan_live_audit_clean.yml` | - | Active cleanup/audit phases |

**Key principle**: The plan file defines WHAT to do; the orchestration file defines HOW to execute it.

**Note**: The root-level `plan_example.yml` shows unified structure for reference. Active work uses phase-specific plans in `live/` subfolder.

## Folder Structure

```
YYMMDDRepo_Branch/
├── README.md                   # This file - explains the pattern
├── plan_example.yml            # Unified plan definition (phases, tasks, criteria)
├── orchestration_example.mmd   # Visual execution flow with agents and loops
├── live/                       # Active plans by category
│   ├── plan_live_build.yml     # Implementation phases
│   ├── plan_live_test.yml      # Testing phases
│   ├── plan_live_teach.yml     # Guidance improvement
│   └── plan_live_audit_clean.yml # Cleanup/audit phases
├── completed/                  # Archived completed plans
│   └── plan_completed.yml      # Summary of completed work
└── reference/                  # Supporting reference material
    └── test-scenarios-detailed.yml
```

## Plan File (plan_example.yml)

The plan file contains:
- **Root metadata**: name, worktree_path, branch, status, priority
- **Context**: Running narrative of progress
- **Related plans**: Link to orchestration MMD
- **Inputs**: Pre-gathered context needed across phases
- **Open questions**: Human-authority decisions
- **Phases and tasks**: Structured work breakdown
- **Success criteria**: Definition of done

## Orchestration File (orchestration_example.mmd)

The orchestration file defines (per `plan-mmd-schema.yml`):
- **Header comments**: GOAL, PROFILE, INPUT_PATH, guidelines
- **Flowchart structure**: Start/End nodes, decision points
- **Subgraphs**: Logical phase groupings
- **Agent spawns**: Which agents execute each phase
- **Loops**: Iteration patterns (test-fix-loop, etc.)
- **Feedback paths**: Re-planning triggers

## Example Metadata

- **Plan ID**: YYMMDDRepo_Branch
- **Worktree**: `/home/code/MyProject-feature-branch`
- **Branch**: `feature/new-capability`
- **Objective**: Implement new capability using Domain -> Workflow -> Entrypoint pattern

## Quick Reference

| File | Purpose |
|------|---------|
| `plan_example.yml` | Source of truth for phases, tasks, questions, success criteria |
| `orchestration_example.mmd` | Visual agent flow diagram with loops and feedback paths |
| `live/*.yml` | Active phase-specific plans (build, test, teach, audit) |
| `completed/*.yml` | Archived completed work |

## Schema References

- Plan structure: See `plan_example.yml` inline comments
- Orchestration structure: `modules/AgenticGuidance/assets/definitions/plan-mmd-schema.yml`
- Reusable MMD components: `modules/AgenticGuidance/assets/examples/planner/components/`

---

## Update Patterns

This section shows **how to update plans** as work progresses.

### Pattern 1: Recording Progress in Context

Update the context section in `plan_example.yml`:

```yaml
context: |
  UPDATE YYYY-MM-DD (Session 1): Initial planning completed.
  UPDATE YYYY-MM-DD (Session 2): Domain layer complete with tests.
  UPDATE YYYY-MM-DD (Session 3): Workflow layer in progress.  # <-- ADD NEW ENTRY
```

### Pattern 2: Updating Task Status

Change task status in the phases section:

```yaml
tasks:
  - id: "dev_001"
    name: "Domain Layer Build"
    status: "completed"        # <-- Change from "in_progress" to "completed"
    completed_date: "YYYY-MM-DD"
```

### Pattern 3: Recording a Human Decision

When a human answers an open question:

```yaml
open_questions:
  - id: "QUESTION-001"
    status: "ANSWERED"          # <-- Change from "OPEN"
    answer: "Use constructor injection"
    answered_by: "HUMAN"        # <-- Critical: marks as authoritative
```

**Note**: Once answered by HUMAN, the decision has authority and must not be reversed by AI.

### Pattern 4: Adding New Questions

Append to open_questions when decisions need human input:

```yaml
  - id: "QUESTION-003"
    question: "Error handling strategy for external API failures?"
    severity: "medium"
    status: "OPEN"
```

---

**Note**: This README serves as the landing page for the planning folder. The unified pattern ensures plan definition (WHAT) and orchestration (HOW) are clearly separated yet linked.
