# JIT Context Architecture

## Overview

JIT (Just-In-Time) Context, also known as CCI (CLI Context Injection), is a **Pull-based** architecture for agent context retrieval. Instead of pre-loading large static markdown files at agent initialization (Push model), agents fetch exactly what they need on-demand via CLI commands (Pull model).

This architecture makes the Agentic CLI a first-class participant in context engineering, reducing initial token overhead by 75-90% while ensuring agents always operate with fresh, task-specific context.

---

## Push vs Pull Model

### Push Model (Legacy)

In the legacy architecture, each agent loaded a large static markdown file (~2000-5000 tokens) at session start containing all possible context: role description, process steps, guidelines, input manifests, and examples.

**Problems:**
- High "context tax" paid on every turn, even when irrelevant
- Stale guidance if files changed after agent initialization
- Agents in feature worktrees lost access to plans stored in main
- One-size-fits-all: no task-specific context loading

### Pull Model (JIT/CCI)

In the Pull model, agents receive a **thin-client bootstrap file** (~350 tokens) that instructs them to call CLI commands for their operational context. Context is fetched incrementally, on-demand, and always reflects the latest state.

**Benefits:**
- **Minimal initial token usage** - 75-90% reduction in context overhead
- **Zero stale guidance** - agents always pull the latest from CLI/TinyDB
- **Main-First harmony** - CLI resolves plans from main worktree regardless of where the agent runs
- **Task-specific loading** - agents fetch only what their current task requires
- **Traceability** - context retrieval is visible in the terminal

### Comparison

| Aspect | Push (Legacy) | Pull (JIT/CCI) |
|--------|--------------|-----------------|
| Initial context size | 2000-5000 tokens | ~350 tokens |
| Context freshness | Stale (loaded at init) | Current (fetched on demand) |
| Worktree awareness | None (file-local only) | Main-First resolution |
| Task specificity | All context, all the time | Only what's needed now |
| Error recovery | Reload entire context | Re-run specific command |
| Update propagation | Requires agent restart | Immediate on next CLI call |

---

## Architecture Components

```mermaid
graph TB
    subgraph AgentSession["Agent Session (Feature Worktree)"]
        BF["Thin-Client Bootstrap File<br/>~350 tokens<br/>.claude/agents/*.md"]
        CLI["CLI Commands<br/>agentic context ..."]
        Agent["Agent Execution Loop"]
    end

    subgraph CLILayer["CLI Layer (AgenticCLI)"]
        Bootstrap["context bootstrap<br/>--role &lt;id&gt;"]
        Role["context role<br/>&lt;role-id&gt;"]
        Task["context task<br/>[--all]"]
        Inputs["context inputs<br/>--role &lt;id&gt;"]
        GenAgent["context generate-agent<br/>&lt;id&gt;"]
    end

    subgraph ServiceLayer["Service Layer (AgenticGuidance)"]
        MFPR["MainFirstEpicResolver"]
        RoleProcess["get_role_process()"]
        InputsManifest["get_role_inputs_manifest()"]
    end

    subgraph DataLayer["Data Layer"]
        TinyDB["TinyDB<br/>.agentic/epics.db"]
        GitWT["Git Worktrees<br/>git worktree list"]
        EpicDirs["docs/epics/live/<br/>YYMMDDXX_description/"]
        AgentDirs["agents/&lt;category&gt;/&lt;role&gt;/<br/>process.yml, inputs.yml"]
    end

    BF -->|"1. Read bootstrap instructions"| Agent
    Agent -->|"2. Invoke CLI"| CLI
    CLI --> Bootstrap
    CLI --> Role
    CLI --> Task
    CLI --> Inputs

    Bootstrap --> MFPR
    Bootstrap --> RoleProcess
    Bootstrap --> InputsManifest
    Role --> RoleProcess
    Task --> MFPR
    Inputs --> InputsManifest

    MFPR --> TinyDB
    MFPR --> GitWT
    MFPR --> EpicDirs
    RoleProcess --> AgentDirs
    InputsManifest --> AgentDirs

    style AgentSession fill:#1a1a2e,stroke:#e94560,color:#fff
    style CLILayer fill:#16213e,stroke:#0f3460,color:#fff
    style ServiceLayer fill:#0f3460,stroke:#533483,color:#fff
    style DataLayer fill:#533483,stroke:#e94560,color:#fff
```

---

## Agent Initialization Flow

The bootstrap sequence takes an agent from zero context to fully operational in a small number of CLI calls.

```mermaid
sequenceDiagram
    participant A as Agent
    participant BF as Bootstrap File
    participant CLI as Agentic CLI
    participant MFPR as MainFirstEpicResolver
    participant DB as TinyDB
    participant Git as Git Worktrees

    Note over A,BF: Phase 1: Thin-Client Bootstrap (~350 tokens)
    A->>BF: Read .claude/agents/<role>.md
    BF-->>A: Role identity + bootstrap command

    Note over A,DB: Phase 2: Seed Context via CLI
    A->>CLI: agentic context bootstrap --role <id> -j
    CLI->>MFPR: resolve_active_epic()
    MFPR->>Git: git worktree list --porcelain
    Git-->>MFPR: Main worktree path
    MFPR->>Git: git rev-parse --abbrev-ref HEAD
    Git-->>MFPR: Current branch name
    MFPR->>DB: Query epics by branch
    DB-->>MFPR: Epic data + objective
    MFPR->>DB: get_current_ticket(epic)
    DB-->>MFPR: Current ticket details
    CLI-->>A: JSON: {role, objective, current_task, cli_commands}

    Note over A,DB: Phase 3: Task Execution Loop
    A->>A: Execute task from bootstrap context
    A->>CLI: agentic agent epic ticket update <id> --status completed
    CLI->>DB: Update ticket status
    A->>CLI: agentic context task
    CLI->>MFPR: extract_current_ticket()
    MFPR->>DB: Next pending ticket
    DB-->>CLI: Next ticket
    CLI-->>A: JSON: {task details}
    A->>A: Execute next task...
```

---

## CLI Command Reference

### Context Commands (`agentic context`)

| Command | Purpose | Key Output |
|---------|---------|------------|
| `bootstrap --role <id> [-j]` | **Primary entrypoint.** Returns Seed Context: role + objective + current task + CLI hints | `{role, objective, epic_folder, current_task, process, essential_inputs, cli_commands}` |
| `role <role-id> [-j]` | Get role-specific process and guidelines from `process.yml` | `{role_id, category, process, manifest, invocation_context}` |
| `task [--all] [-j]` | Get current task (or all tasks) from resolved epic | `{epic_folder, task}` or `{epic_folder, task_count, tasks}` |
| `inputs --role <id> [--resolve] [-j]` | Get input manifest with path resolution and existence checks | `{role, inputs: [{path, exists, description}], missing, layers}` |
| `generate-agent <id> [--output path]` | Generate thin-client bootstrap markdown file | Markdown content or file |

### Epic/Ticket Commands (`agentic agent epic ticket`)

| Command | Purpose |
|---------|---------|
| `list --epic <folder>` | List all tickets with status and phase |
| `start <id> --epic <folder>` | Mark ticket as `in_progress` |
| `complete <id> --epic <folder>` | Mark ticket as `completed` |
| `current --epic <folder>` | Get current in-progress or next pending ticket |

### Task Commands (`agentic plan task`)

| Command | Purpose |
|---------|---------|
| `list` | Show all tasks with status |
| `current` | Get in-progress or next pending task |
| `update <id> --status <s>` | Update task status |
| `prefill --preset <name>` | Load preset task template into TinyDB |
| `add <description>` | Add new task |

---

## Bootstrap Protocol

### Thin-Client Agent Files

Agent definition files in `.claude/agents/` are minimal (~350 tokens). They contain:

1. **Role Identity**: "You are the `<role-id>` agent."
2. **Bootstrap Command**: Instructions to run `agentic context bootstrap --role <id> -j`
3. **Execution Loop**: Read task, execute, update status, repeat

Example thin-client file:

```markdown
# Builder Agent

You are the **build-python** agent.

## Bootstrap Protocol

Before taking action, run these commands to get your context:

```bash
# 1. Get your role context and current task
agentic context bootstrap --role build-python -j

# 2. Get your current/next ticket details
agentic agent epic ticket current -j
```

## Execution Loop

1. Read current task from `agentic agent epic ticket current`
2. Execute the task following the guidance provided
3. Update status: `agentic agent epic ticket update <id> --status completed`
4. Repeat until all tasks are complete
```

### Bootstrap Output Structure

The `agentic context bootstrap` command returns:

```json
{
  "role": "build-python",
  "objective": "Implement feature X following the epic specification",
  "epic_folder": "260308PD_feature_implementation",
  "epic_path": "/home/code/Project/docs/epics/live/260308PD_feature_implementation",
  "current_task": {
    "id": "build_01",
    "name": "Implement core module",
    "description": "Create the main module with...",
    "status": "pending",
    "phase": "Build Phase",
    "agent_type": "build-python",
    "inputs": ["src/existing_module.py"],
    "target_files": ["src/new_module.py"],
    "guidance": "Follow existing patterns in...",
    "success_criteria": ["Tests pass", "No regressions"]
  },
  "process": {
    "role_id": "build-python",
    "category": "build",
    "process": { "...process.yml contents..." }
  },
  "essential_inputs": [
    {"path": "/abs/path/to/input.yml", "exists": true, "description": "Core inputs"}
  ],
  "cli_commands": {
    "task_prefill": "agentic plan task prefill --preset build-python",
    "task_status": "agentic plan task list",
    "task_update": "agentic plan task update <task-id> --status <status>",
    "task_current": "agentic context task"
  }
}
```

---

## Main-First Plan Resolution

### Problem

Epics are created and maintained in the **main branch/worktree** for centralized visibility (`docs/epics/live/`). But agents execute in **feature worktrees**. How does an agent in a feature worktree find its active epic?

### Solution: `MainFirstEpicResolver`

The resolver bridges the worktree gap by:

1. Detecting the main worktree via `git worktree list --porcelain`
2. Scanning `docs/epics/live/` in the main worktree
3. Matching the epic to the current branch using multiple strategies

```mermaid
flowchart TD
    Start["Agent calls<br/>agentic context bootstrap"]
    GetBranch["Get current branch<br/>git rev-parse --abbrev-ref HEAD"]
    FindMain["Find main worktree<br/>git worktree list --porcelain"]

    Start --> GetBranch --> FindMain

    subgraph Resolution["Epic Resolution Strategies (in order)"]
        S1["Strategy 1: TinyDB Branch Match<br/>Query epics DB for branch field"]
        S2["Strategy 2: Folder Name Match<br/>Epic folder contains branch identifier"]
        S3["Strategy 3: Disk Scan Fallback<br/>Iterate docs/epics/live/ folders"]
        S4["Strategy 4: Main Branch Default<br/>Return most recent live epic"]
    end

    FindMain --> S1
    S1 -->|"No match"| S2
    S2 -->|"No match"| S3
    S3 -->|"No match + on main"| S4

    S1 -->|"Match!"| Result
    S2 -->|"Match!"| Result
    S3 -->|"Match!"| Result
    S4 -->|"Match!"| Result

    Result["Return Epic Info<br/>{plan_folder, objective, status}"]
    ExtractTask["Extract Current Ticket<br/>TinyDB: in_progress or next pending"]

    Result --> ExtractTask

    style Resolution fill:#1a1a2e,stroke:#e94560,color:#fff
```

### Branch-to-Folder Matching

Epic folders follow the `YYMMDDXX_description` naming convention (e.g., `260307EO_eliminate_mmd_tinydb_orchestration`). The resolver normalizes both the branch name and folder description (removing hyphens, underscores, case differences) and checks for substring containment.

| Strategy | How it Works | When Used |
|----------|-------------|-----------|
| TinyDB branch field | Exact match on stored branch metadata | Primary: most reliable |
| Folder name contains branch | Normalized substring matching | Fallback: when TinyDB branch is empty |
| Disk folder scan | Iterate live epic directories | Fallback: when TinyDB lookup fails entirely |
| Most recent on main | Sort folders descending, return first | Special case: agent on main/master branch |

---

## Task Lifecycle

Tasks (tickets) flow through a defined lifecycle managed by CLI commands and persisted in TinyDB.

```mermaid
stateDiagram-v2
    [*] --> proposed: Epic created with tickets
    proposed --> pending: Phase activated
    pending --> in_progress: agentic agent epic ticket start
    in_progress --> completed: agentic agent epic ticket complete
    in_progress --> blocked: Dependency unresolved
    blocked --> in_progress: Blocker resolved
    completed --> [*]

    note right of proposed: Initial state from planner
    note right of in_progress: Only ONE ticket in_progress at a time
    note right of completed: Triggers auto-archive when all done
```

### Task Data Model

Each ticket in TinyDB contains:

| Field | Description |
|-------|-------------|
| `id` | Unique ticket identifier (e.g., `build_01_001`) |
| `name` | Short description of the work |
| `description` | Detailed description |
| `status` | proposed, pending, in_progress, completed, blocked |
| `phase_name` | Phase grouping (e.g., "Build Phase") |
| `agent` | Agent type responsible (e.g., `build-python`) |
| `inputs` | List of input file paths |
| `target_files` | List of files to create/modify |
| `guidance` | Step-by-step implementation guidance |
| `success_criteria` | List of conditions for completion |

### Preset Templates

Task presets allow bulk-loading predefined task lists for common workflows:

```bash
# Load a preset task list
agentic plan task prefill --preset planner-build
```

Preset templates are YAML files stored at:
`modules/AgenticGuidance/assets/templates/presets/<preset-name>.yml`

---

## CCI Command Chaining Pattern

CCI uses **progressive disclosure**: each command's output includes hints for the next commands to run. This minimizes initial context while enabling agents to fetch exactly what they need.

```mermaid
flowchart LR
    subgraph Step1["Step 1: Bootstrap (~350 tokens)"]
        B1["Read .claude/agents/role.md"]
    end

    subgraph Step2["Step 2: Seed Context"]
        B2["agentic context bootstrap<br/>--role &lt;id&gt; -j"]
    end

    subgraph Step3["Step 3: Read Files"]
        B3["Agent reads file paths<br/>from bootstrap output"]
    end

    subgraph Step4["Step 4: Task Loop"]
        B4["Execute task<br/>Update status<br/>Get next task"]
    end

    Step1 -->|"Bootstrap command"| Step2
    Step2 -->|"File paths + CLI hints"| Step3
    Step3 -->|"Full context loaded"| Step4
    Step4 -->|"Repeat until done"| Step4
```

### File Path Output Pattern

CLI commands output **file paths** rather than file contents. The agent reads the files it needs directly. This:

1. **Reduces CLI output size** - paths are compact; contents can be large
2. **Enables selective reading** - agent reads only what it needs
3. **Supports exploration** - agent can discover related files nearby
4. **Maintains freshness** - agent reads current file state, not cached content

---

## Separation of Concerns

```mermaid
graph LR
    subgraph Planners["Planner Agents"]
        P["Create & structure epics<br/>Define phases & tickets<br/>Set objectives"]
    end

    subgraph CLI["Agentic CLI"]
        C["Context retrieval (read-only)<br/>Task status updates<br/>Preset loading"]
    end

    subgraph Executors["Executor Agents"]
        E["Read context via CLI<br/>Execute tasks<br/>Update status via CLI"]
    end

    subgraph Persistence["Persistence Layer"]
        DB["TinyDB (.agentic/epics.db)<br/>Epic folders (docs/epics/)<br/>Agent guidance (agents/)"]
    end

    Planners -->|"Write"| DB
    CLI -->|"Read/Update status"| DB
    Executors -->|"Invoke"| CLI

    style Planners fill:#0f3460,stroke:#e94560,color:#fff
    style CLI fill:#16213e,stroke:#0f3460,color:#fff
    style Executors fill:#1a1a2e,stroke:#533483,color:#fff
    style Persistence fill:#533483,stroke:#e94560,color:#fff
```

| Responsibility | Owner | Access Pattern |
|---------------|-------|----------------|
| Epic/plan management (create, structure, phases) | Planner agents | Write to TinyDB |
| Context retrieval | CLI context commands | Read-only from TinyDB + filesystem |
| Task status updates | CLI ticket commands | Write status field only |
| Persistence layer | TinyDB + epic folders | Source of truth for all state |
| Task execution | Executor agents | Read via CLI, write code, update status via CLI |

The CLI is an **external memory / persistence layer**, NOT a planning engine.

---

## Generated Agent Files

The system supports 26+ thin-client agent files organized by category:

| Category | Agents | Count |
|----------|--------|-------|
| Planner | planner-build, planner-test, planner-audit, planner-explore, planner-orchestration, epic-creator | 6 |
| Build | build-python, build-flutter, build-docs-writer, build-story-writer | 4 |
| Test | test-builder, test-audit, test-uat, trace-explorer | 4 |
| Orchestration | orchestration-executor, orchestration-planning | 2 |
| Teacher | teacher-update-guidance, teacher-update-assets | 2 |
| Deploy | deploy-cicd | 1 |

Each file is **~350 tokens** (vs. ~2000-5000 in the legacy Push model).

Generate new agent files with:
```bash
agentic context generate-agent <role-id> --output .claude/agents/<role-id>.md
```

---

## Key Implementation Files

| File | Module | Purpose |
|------|--------|---------|
| `commands/context.py` | AgenticCLI | CLI command handlers for bootstrap, role, task, inputs |
| `services/context.py` | AgenticGuidance | `MainFirstEpicResolver`, `get_role_process()`, `get_role_inputs_manifest()` |
| `workflows/ticket_workflow.py` | AgenticCLI | `TicketPresetWorkflow` for task prefill from presets |
| `services/epic_repository.py` | AgenticGuidance | TinyDB backend for epic/ticket CRUD |
| `services/epic.py` | AgenticGuidance | `EpicService` domain logic |
| `services/ticket.py` | AgenticGuidance | `TicketService` domain logic |
| `templates/bootstrap-agent-template.md` | AgenticGuidance | Template for generating thin-client agent files |
| `templates/presets/*.yml` | AgenticGuidance | Preset task templates for bulk loading |

---

## Related Documentation

- [CCI Context Architecture](CCI_CONTEXT_ARCHITECTURE.md) - Detailed CCI patterns including self-review workflows
- [Agent Guidance Architecture](../modules/AgenticGuidance/docs/ARCHITECTURE.md) - Hub-and-spoke model, agent categories, input specifications
