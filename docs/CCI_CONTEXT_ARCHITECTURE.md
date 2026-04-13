# CCI Context Architecture

## Overview

CCI (CLI Context Injection) Context is a Pull-based architecture for agent context retrieval. Instead of pre-loading large static markdown files (Push model), agents fetch exactly what they need via CLI commands (Pull model).

> **See also:** [JIT Context Architecture](JIT_CONTEXT_ARCHITECTURE.md) for the comprehensive architecture document with mermaid diagrams, Main-First resolution flow, and task lifecycle.

## Push vs Pull Model

### Push Model (Legacy)
- Large static markdown files (~2000-5000 tokens per agent)
- Pre-loaded at agent initialization
- Context may include stale or irrelevant information
- Context window consumed by static content

### Pull Model (CCI)
- Thin-client bootstrap files (~350 tokens per agent)
- Context fetched on-demand via CLI
- Only relevant context loaded
- Task-specific guidance retrieved dynamically

**Token Reduction**: 75-90% reduction in initial context load.

## Architecture Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Agent Session                           │
│  ┌─────────────────┐                                           │
│  │ Thin-Client     │  1. Read bootstrap instructions           │
│  │ Bootstrap File  │     (~350 tokens)                         │
│  │ (.claude/agents/│                                           │
│  │  planner-build. │                                           │
│  │  md)            │                                           │
│  └────────┬────────┘                                           │
│           │                                                     │
│           v                                                     │
│  ┌─────────────────┐                                           │
│  │ CLI Commands    │  2. Invoke CLI for context                │
│  │                 │                                           │
│  │ agentic context │     - bootstrap: Get seed context         │
│  │   bootstrap     │     - role: Get role guidance             │
│  │   --role build  │     - task: Get current task              │
│  │   -j            │     - inputs: Get input manifest          │
│  └────────┬────────┘                                           │
│           │                                                     │
│           v                                                     │
│  ┌─────────────────┐                                           │
│  │ MainFirstPlan   │  3. Resolve plan from main worktree       │
│  │ Resolver        │                                           │
│  │                 │     - Find main worktree via git          │
│  │                 │     - Scan docs/plans/live/               │
│  │                 │     - Match plan to current branch        │
│  └────────┬────────┘                                           │
│           │                                                     │
│           v                                                     │
│  ┌─────────────────┐                                           │
│  │ Structured      │  4. Return JSON context                   │
│  │ Context JSON    │                                           │
│  │                 │     {                                     │
│  │                 │       "role": "build",                    │
│  │                 │       "objective": "...",                 │
│  │                 │       "current_task": {...},              │
│  │                 │       "cli_commands": {...}               │
│  │                 │     }                                     │
│  └─────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

## CLI Command Reference

### Context Commands (`agentic context`)

| Command | Purpose | Output |
|---------|---------|--------|
| `bootstrap --role <id>` | Get seed context (role + task + inputs) | JSON with full bootstrap info |
| `role <role-id>` | Get role-specific process/guidelines | JSON with process steps |
| `task` | Get current task from resolved plan | JSON task object |
| `inputs --role <id>` | Get CCI manifest of relevant files | JSON input list |
| `generate-agent <id>` | Generate thin-client agent file | Markdown file |

### Plan Task Commands (`agentic plan task`)

| Command | Purpose | Output |
|---------|---------|--------|
| `list` | Show all tasks with status | Table or JSON |
| `current` | Get in_progress or next pending task | JSON task object |
| `update <id> --status <s>` | Update task status in YAML | Confirmation |
| `prefill --preset <name>` | Load preset task list | Task list |
| `add <description>` | Add new task to list | New task ID |

## Bootstrap Protocol

Thin-client agent files instruct agents to:

```bash
# 1. Get seed context (role, objective, current task)
agentic context bootstrap --role planner-build -j

# 2. Get current/next task details
agentic plan task current -j
```

### Execution Loop

1. **Read** current task from `agentic plan task current`
2. **Execute** the task following provided guidance
3. **Update** status: `agentic plan task update <id> --status completed`
4. **Repeat** from step 1 until all tasks complete

## CCI Command Chaining Pattern

CCI uses a chained command pattern where each command provides the next commands to run. This progressive disclosure approach minimizes initial context while enabling agents to fetch exactly what they need.

### Command Chain Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CCI Command Chaining Flow                            │
│                                                                         │
│  Step 1: Initial Instructions                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ $ agentic planner-build                                          │   │
│  │                                                                   │   │
│  │ OUTPUT:                                                           │   │
│  │   - Agent role/purpose                                            │   │
│  │   - Current task summary                                          │   │
│  │   - Process step overview                                         │   │
│  │   - Input file paths (for source exploration)                     │   │
│  │   - NEXT COMMANDS to run                                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              v                                          │
│  Step 2: Full Bootstrap Context (--bootstrap flag)                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ $ agentic planner-build --bootstrap                              │   │
│  │                                                                   │   │
│  │ OUTPUT:                                                           │   │
│  │   - Complete process.yml content                                  │   │
│  │   - Full inputs.yml with resolved paths                           │   │
│  │   - Current task with full guidance                               │   │
│  │   - FILE PATHS for all referenced sources                         │   │
│  │   - NEXT COMMANDS for task management                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              v                                          │
│  Step 3: Agent Reads Source Files                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Agent uses file paths from CLI output to read:                    │   │
│  │   - modules/AgenticGuidance/agents/planner/planner-build/*.yml   │   │
│  │   - modules/AgenticGuidance/assets/definitions/*.yml              │   │
│  │   - docs/plans/live/YYMMDDXX_*/plan_*.yml                        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│                              v                                          │
│  Step 4: Task Loop                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ $ agentic plan task current -j      # Get next task               │   │
│  │ $ agentic plan task update <id> --status completed  # Mark done   │   │
│  │ (repeat until all tasks complete)                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### File Path Output Pattern

CLI commands output **file paths** rather than file contents. The agent is responsible for reading the files it needs. This pattern:

1. **Reduces CLI output size** - Paths are compact; contents can be large
2. **Enables selective reading** - Agent reads only what it needs
3. **Supports exploration** - Agent can discover related files
4. **Maintains freshness** - Agent reads current file state, not cached

**Example CLI Output with File Paths:**

```json
{
  "agent": "planner-build",
  "role": "Create implementation plans from PRDs",
  "inputs": [
    {
      "path": "modules/AgenticGuidance/agents/planner/planner-build/process.yml",
      "description": "Process steps and guidance"
    },
    {
      "path": "modules/AgenticGuidance/assets/definitions/plans.yml",
      "description": "Plan structure definitions"
    }
  ],
  "next_commands": [
    "agentic context bootstrap --role planner-build -j  # Get full seed context",
    "agentic plan task current -j                       # Get current task details"
  ]
}
```

The agent then reads these paths directly rather than receiving embedded content.

### Full Chain Execution Example

Complete bootstrap sequence for `planner-build` agent:

```bash
# Step 1: Get initial instructions (lightweight)
$ agentic planner-build
============================================================
AGENT: planner-build
============================================================

ROLE: Create implementation plans from PRDs

CURRENT TASK:
  ID: build_001
  Name: Create feature implementation plan
  Status: pending

PROCESS STEPS:
  1. Load PRD context
  2. Analyze scope and dependencies
  3. Create phased task list
  4. Document inputs and outputs

INPUTS TO READ:
  - modules/AgenticGuidance/agents/planner/planner-build/process.yml
  - modules/AgenticGuidance/assets/definitions/plans.yml
  - docs/plans/live/260123AE_feature/plan_build.yml

NEXT COMMANDS:
  agentic context bootstrap --role planner-build -j  # Get full seed context
  agentic plan task current -j                       # Get current task details
  agentic plan task update <id> --status completed   # Mark task done

# Step 2: Get full bootstrap context (when needed)
$ agentic context bootstrap --role planner-build -j
{
  "role": "planner-build",
  "objective": "Create implementation plans following guidance structure",
  "current_task": {
    "id": "build_001",
    "name": "Create feature implementation plan",
    "status": "pending",
    "guidance": "Follow process.yml steps, reference plan examples..."
  },
  "process_file": "modules/AgenticGuidance/agents/planner/planner-build/process.yml",
  "inputs_file": "modules/AgenticGuidance/agents/planner/planner-build/inputs.yml",
  "cli_commands": {
    "task_current": "agentic plan task current -j",
    "task_update": "agentic plan task update {task_id} --status {status}",
    "task_list": "agentic plan task list"
  }
}

# Step 3: Agent reads files from provided paths
# (Agent uses Read tool to fetch process.yml, inputs.yml, etc.)

# Step 4: Execute task loop
$ agentic plan task current -j
{"id": "build_001", "name": "Create feature implementation plan", ...}

# ... agent works on task ...

$ agentic plan task update build_001 --status completed
Task build_001 marked as completed

$ agentic plan task current -j
{"id": "build_002", "name": "Review plan with stakeholder", ...}
```

### Chaining Benefits

| Aspect | Without Chaining | With CCI Chaining |
|--------|-----------------|-------------------|
| Initial context | 2000-5000 tokens | ~350 tokens |
| Context freshness | Stale (loaded at init) | Current (fetched on demand) |
| Discoverability | Must know all commands | Each command suggests next |
| Error recovery | Reload all context | Re-run specific command |
| Task tracking | Manual status updates | CLI tracks state |

## Main-First Plan Resolution

Plans are stored in the main worktree at `docs/plans/live/` for centralized visibility. The `MainFirstPlanResolver` enables agents in feature worktrees to access these plans.

### Resolution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ Agent in Feature Worktree                                       │
│                                                                 │
│  1. git branch --show-current                                   │
│     └─> "feature-xyz"                                          │
│                                                                 │
│  2. git worktree list --porcelain                              │
│     └─> Find main worktree: /home/code/Project                 │
│                                                                 │
│  3. Scan main_worktree/docs/plans/live/                        │
│     └─> Find folder matching branch: "260123_feature_xyz"      │
│                                                                 │
│  4. Extract objective and current task                         │
│     └─> Return bootstrap context                               │
└─────────────────────────────────────────────────────────────────┘
```

### Branch-to-Folder Matching

Plans are matched to branches by:
1. Exact branch name match in plan metadata
2. Folder name contains branch identifier
3. Plan status is "active" for current branch

## Separation of Concerns

| Responsibility | Owner |
|---------------|-------|
| Plan management (create, structure, phases) | Planner agents |
| Context retrieval (read-only) | CLI context commands |
| Task status updates | CLI plan task commands |
| Persistence layer | YAML files in docs/plans/ |

The CLI is a **persistence layer / external memory**, NOT a planning engine.

## Generated Agent Files

20 thin-client agent files in `.claude/agents/`:

- **6 planner agents**: planner-build, planner-test, planner-audit, planner-explore, planner-orchestration, epic-creator
- **4 build agents**: build-python, build-flutter, build-docs-writer, build-story-writer
- **4 test agents**: test-builder, test-audit, test-uat, trace-explorer
- **2 orchestration agents**: orchestration-executor, orchestration-planning
- **2 teacher agents**: teacher-update-guidance, teacher-update-assets
- **1 deploy agent**: deploy-cicd

Each file is ~350 tokens (vs. ~2000-5000 in legacy Push model).

## Agent Self-Review Testing

Self-review is a basic-level testing practice for validating agent guidance. When guidance files (process.yml, inputs.yml, outputs.yml) are modified, agents can self-review their own guidance to catch issues before deployment.

### CCI-Based Self-Review Workflow

Self-review follows the CCI (CLI Context Injection) pattern: agents receive minimal bootstrap context via CLI, then load additional context by reading files directly. This 6-step workflow is the canonical approach:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CCI Self-Review Workflow                                                    │
│                                                                             │
│  Step 1: Run CLI for initial context                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ $ agentic <agent-name>                                              │   │
│  │                                                                     │   │
│  │ Output:                                                             │   │
│  │   Agent: test-audit                                                 │   │
│  │   Path: modules/AgenticGuidance/agents/test/test-audit/             │   │
│  │   Files:                                                            │   │
│  │     - process.yml: modules/.../test-audit/process.yml               │   │
│  │     - inputs.yml: modules/.../test-audit/inputs.yml                 │   │
│  │     - manifest.yml: modules/.../test-audit/manifest.yml             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│           │                                                                 │
│           v                                                                 │
│  Step 2: Read self-review-criteria.yml                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Path: modules/AgenticGuidance/assets/definitions/                   │   │
│  │       self-review-criteria.yml                                      │   │
│  │                                                                     │   │
│  │ Purpose: Load PASS/NEEDS_ATTENTION criteria and output requirements │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│           │                                                                 │
│           v                                                                 │
│  Step 3: Read agent-self-review.yml                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Path: modules/AgenticGuidance/assets/guidelines/                    │   │
│  │       agent-self-review.yml                                         │   │
│  │                                                                     │   │
│  │ Purpose: Load the self-review protocol and validation checklist     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│           │                                                                 │
│           v                                                                 │
│  Step 4: Read agent guidance files                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Files (from CLI output):                                            │   │
│  │   - {agent_path}/process.yml - The agent's process definition       │   │
│  │   - {agent_path}/inputs.yml - The agent's input specifications      │   │
│  │   - {agent_path}/outputs.yml - Output schema (if present)           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│           │                                                                 │
│           v                                                                 │
│  Step 5: Apply self-review protocol                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Procedure:                                                          │   │
│  │   - Validate paths resolve to existing files                        │   │
│  │   - Check cross-file consistency                                    │   │
│  │   - Apply pass_criteria from self-review-criteria.yml               │   │
│  │   - Check for needs_attention_triggers                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│           │                                                                 │
│           v                                                                 │
│  Step 6: Generate structured output                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Required fields (from self-review-criteria.yml#output_requirements):│   │
│  │   - status: PASS | NEEDS_ATTENTION                                  │   │
│  │   - findings: list of issues with id, severity, description         │   │
│  │   - plan_file_path: path to plan file (required if NEEDS_ATTENTION) │   │
│  │   - spot_check_eligible: boolean                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### File Paths Reference

The following paths are stable and can be read directly without CLI lookup:

| File | Path | Purpose |
|------|------|---------|
| Self-Review Criteria | `modules/AgenticGuidance/assets/definitions/self-review-criteria.yml` | PASS/NEEDS_ATTENTION rules |
| Self-Review Guideline | `modules/AgenticGuidance/assets/guidelines/agent-self-review.yml` | Protocol and validation checklist |
| Spot-Check Checklist | `modules/AgenticGuidance/assets/definitions/spot-check-checklist.yml` | Sampling criteria |
| Agent Categories | `modules/AgenticGuidance/assets/definitions/agent-categories.yml` | Agent classification |
| Test Scenarios | `modules/AgenticGuidance/assets/definitions/guidance-test-scenarios.yml` | Validation scenarios |
| CLI Preset | `modules/AgenticCLI/src/agenticcli/templates/presets/self-review-preset.yml` | Task prefill template |

### Running Self-Review via CLI

Load the self-review task preset:
```bash
agentic plan task prefill --preset self-review
```

This loads standard self-review tasks that validate:
- All input paths resolve to existing files
- All asset/definition/guideline references exist
- Process steps are internally consistent
- Prerequisites are explicitly documented
- Loop context is defined (if applicable)
- Output specifications are complete

### Self-Review Output

Self-review produces a structured report with:
- Path validation results (broken paths, missing files)
- Consistency check results (contradictions, ambiguities)
- Severity breakdown (CRITICAL/HIGH/MEDIUM/LOW)
- Recommended action (PASS/FIX_REQUIRED/ESCALATE)

**Critical Rule**: PASS requires ALL criteria to be met (conjunction). NEEDS_ATTENTION is triggered if ANY single criterion fails (disjunction).

### Integration with Guidance Changes

Self-review should be run after any guidance modification:

1. Modify agent guidance (process.yml, inputs.yml, etc.)
2. Load self-review preset: `agentic plan task prefill --preset self-review`
3. Execute self-review tasks following the 6-step CCI workflow
4. Fix any issues found
5. Re-run until self-review passes
6. Commit guidance changes

### Detailed Protocol Reference

For the complete self-review protocol including:
- Full validation checklist (path, process, loop, output, consistency validation)
- Borderline examples for PASS vs NEEDS_ATTENTION decisions
- Severity rules and escalation triggers
- Integration with guidance-test-loop

See: `modules/AgenticGuidance/assets/guidelines/agent-self-review.yml`

### Related Artifacts

- **Guideline**: `modules/AgenticGuidance/assets/guidelines/agent-self-review.yml`
- **Criteria**: `modules/AgenticGuidance/assets/definitions/self-review-criteria.yml`
- **Test Scenarios**: `modules/AgenticGuidance/assets/definitions/guidance-test-scenarios.yml`
- **Test Simulator**: `modules/AgenticGuidance/agents/test/test-guidance-simulator/`
- **CLI Preset**: `modules/AgenticCLI/src/agenticcli/templates/presets/self-review-preset.yml`

## Success Criteria

- Agents can identify task objective via `agentic context bootstrap`
- CLI plan task commands are operational
- Agents can update task status without holding plan in context
- Main-First planning folders resolved in feature worktree sessions
- All agents migrated to Pull model (<500 tokens each)
