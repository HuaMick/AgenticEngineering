# Plan Example

This example demonstrates the **epic folder pattern**:
- `epic.md` - Epic description and context
- Phases, tickets, and execution state are stored in TinyDB (not as files)

## Folder Structure

```
YYMMDDXX_description/
├── epic.md                     # Epic description and context
├── README.md                   # This file (optional)
└── reference/                  # Supporting reference material (optional)
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

## Epic Data Model

Epic data is stored in TinyDB at `~/.agentic/epics.db`. The database contains:
- **Epic metadata**: name, branch, status, priority
- **Phases**: Ordered execution stages with agent routing
- **Tickets**: Individual work items with status tracking
- **Success criteria**: Definition of done per ticket

Use `agentic epic` CLI commands to query and update epic data.

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
| `plan_example.yml` | Example plan structure |
| `context-minimisation.yml` | When and why to split plans |
| `plan-schema.yml` | Plan schema (TinyDB-first) |
