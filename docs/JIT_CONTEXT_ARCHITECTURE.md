# JIT Context Architecture

## Overview

JIT (Just-In-Time) Context is a Pull-based architecture for agent context retrieval. Instead of pre-loading large static markdown files (Push model), agents fetch exactly what they need via CLI commands (Pull model).

## Push vs Pull Model

### Push Model (Legacy)
- Large static markdown files (~2000-5000 tokens per agent)
- Pre-loaded at agent initialization
- Context may include stale or irrelevant information
- Context window consumed by static content

### Pull Model (JIT)
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
| `inputs --role <id>` | Get JIT manifest of relevant files | JSON input list |
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

26 thin-client agent files in `.claude/agents/`:

- **7 planner agents**: planner-build, planner-test, planner-audit, etc.
- **2 build agents**: build-python, build-flutter
- **7 test agents**: test-runner, test-builder, test-audit, etc.
- **5 orchestration agents**: orchestration-build, orchestration-planning, etc.
- **3 teacher agents**: teacher-update-guidance, teacher-update-assets, etc.
- **2 deploy agents**: deploy-cicd, deploy-worktree

Each file is ~350 tokens (vs. ~2000-5000 in legacy Push model).

## Success Criteria

- Agents can identify task objective via `agentic context bootstrap`
- CLI plan task commands are operational
- Agents can update task status without holding plan in context
- Main-First planning folders resolved in feature worktree sessions
- All agents migrated to Pull model (<500 tokens each)
