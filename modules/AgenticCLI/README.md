# AgenticCLI

> **Note**: This project is in early development. This document describes the module's purpose and direction, not its current implementation state.

Standalone CLI commands for deterministic operations that Claude Code calls during sessions. AgenticCLI provides the **crystallized pattern layer** that handles predictable, repetitive processes.

## Purpose

Claude Code is the agent. AgenticCLI provides the **tool layer** that Claude Code invokes when:

- A task follows a predictable, well-understood pattern
- Deterministic execution is more reliable than reasoning through steps
- The operation has been codified from observed friction patterns

This is the "CLI as Maturity Layer" principle from the AgenticEngineering vision: processes that have stabilized through repeated use get crystallized into CLI commands.

## Current State

**Status**: Empty scaffold awaiting implementation.

The `/home/code/AgenticEngineering/modules/AgenticCLI/` directory currently contains only this README. No CLI commands have been implemented yet.

## Design: Thin CLI Calling API

AgenticCLI follows a "thin CLI calling API" pattern:

```
Claude Code
    |
    v
agentic <command>
    |
    +-- Local-only commands (git worktree, file operations)
    |       Direct execution, no network
    |
    +-- API-calling commands (session, deploy)
            Thin wrapper -> AgenticBackend API
```

**Local-only commands**: Execute entirely on the local machine. These handle git operations, file system scaffolding, and test execution.

**API-calling commands**: Act as thin wrappers that delegate to AgenticBackend. These handle operations requiring remote state or coordination.

## Planned Command Categories

Based on patterns from the legacy `MyAgents` codebase and the AgenticEngineering main README:

| Category | Type | Purpose | Legacy Reference |
|----------|------|---------|------------------|
| **worktree** | Local | Git worktree + planning folder scaffolding | `deploy-worktree/process.yml` |
| **plan** | Local | Planning folder state management | `planner-*/process.yml` |
| **test** | Local | Execute tests, parse results | `test-runner/process.yml` |
| **clean** | Local | Remove targets with safety checks | `cleaner-execute/process.yml` |
| **session** | API | Remote session management | `RemoteAgents/` |
| **deploy** | API | Deployment workflows | `deploy-*/process.yml` |

### worktree

Git worktree creation with integrated planning folder scaffolding.

```bash
# Aspirational usage
agentic worktree create <branch> [--base <base-branch>]
agentic worktree list
agentic worktree remove <branch>
```

**Operations**:
1. Create git worktree at standard path
2. Create planning folder at `docs/plans/live/YYMMDDRepo_Branch/`
3. Initialize live/ and completed/ subdirectories
4. Create placeholder plan files (plan_live_teach.yml, plan_live_test.yml, etc.)
5. Optionally update VS Code workspace file

### plan

Planning folder state management.

```bash
# Aspirational usage
agentic plan status [<plan-path>]
agentic plan task start <task-id>
agentic plan task complete <task-id>
agentic plan archive
```

**Operations**:
1. Parse YAML plan files
2. Update task states (pending -> in_progress -> complete)
3. Move completed items to plan_completed.yml
4. Archive entire planning folder when done

### test

Test execution with structured result parsing.

```bash
# Aspirational usage
agentic test run [<path>] [--type pytest|jest|etc]
agentic test parse <results-file>
agentic test summary
```

**Operations**:
1. Detect test framework from project configuration
2. Execute tests with appropriate runner
3. Parse results into structured format
4. Return exit code and summary for Claude Code consumption

### clean

Safe removal of targets with approval workflow.

```bash
# Aspirational usage
agentic clean identify <scope>
agentic clean execute <targets-file>
agentic clean dry-run <targets-file>
```

**Operations**:
1. Identify cleanup targets (orphaned files, stale branches, etc.)
2. Write targets to approval file
3. Execute approved removals with safety checks
4. Report what was removed

### session (API)

Remote session management via AgenticBackend.

```bash
# Aspirational usage
agentic session create [--command <cmd>]
agentic session connect <session-id>
agentic session list
agentic session terminate <session-id>
```

**Operations**:
1. Call AgenticBackend session API
2. Display connection info (pairing codes, URLs)
3. Manage session lifecycle

### deploy (API)

Deployment workflows via AgenticBackend.

```bash
# Aspirational usage
agentic deploy build [--target <env>]
agentic deploy status
agentic deploy rollback <version>
```

**Operations**:
1. Trigger deployment workflows via API
2. Stream status updates
3. Handle rollback requests

## Proposed Directory Structure

```
AgenticCLI/
├── src/
│   └── agentic/
│       ├── __init__.py
│       ├── main.py              # CLI entrypoint
│       ├── commands/            # Command implementations
│       │   ├── __init__.py
│       │   ├── worktree.py      # Local: git worktree ops
│       │   ├── plan.py          # Local: planning folder ops
│       │   ├── test.py          # Local: test execution
│       │   ├── clean.py         # Local: cleanup ops
│       │   ├── session.py       # API: session management
│       │   └── deploy.py        # API: deployment
│       │
│       ├── core/                # Shared utilities
│       │   ├── __init__.py
│       │   ├── git.py           # Git operations
│       │   ├── yaml_ops.py      # YAML file handling
│       │   ├── api_client.py    # AgenticBackend client
│       │   └── output.py        # Structured output formatting
│       │
│       └── config/              # Configuration
│           ├── __init__.py
│           └── settings.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── pyproject.toml
└── README.md
```

## Legacy Patterns Informing Design

The `modules/legacy/MyAgents/` codebase provides several patterns:

### CLI Architecture (from MyAgentsBackend)

| Pattern | Description | Reference |
|---------|-------------|-----------|
| **Click-based commands** | Decorator-driven CLI with groups and subcommands | `RemoteAgents/services/terminal/entrypoints/cli.py` |
| **Argparse routing** | Global vs project-scoped command routing | `MyAgentsBackend/src/myagents/frontend/cli/` |
| **Workflow delegation** | CLI handlers call workflow classes, not direct logic | `myagents_cli.py` patterns |
| **Lazy imports** | Speed up CLI startup by deferring heavy imports | `myagents_cli.py` |

### Worktree Operations (from MyAgentsGuidance)

| Pattern | Description | Reference |
|---------|-------------|-----------|
| **Naming convention** | `YYMMDDRepo_Branch` for planning folders | `assets/definitions/folder-structure.yml` |
| **Planning scaffolding** | Four placeholder files in live/completed structure | `deploy-worktree/process.yml` |
| **Workspace integration** | VS Code workspace file updates | `deploy-worktree/inputs.yml` |
| **Branch strategy** | Dev -> staging -> main merge flow | `worktree-and-branching.yml` |

### Output Patterns

| Pattern | Description |
|---------|-------------|
| **Exit codes** | 0 for success, 1 for failure, consistent with Unix conventions |
| **Structured output** | JSON output option for machine consumption |
| **Progress indicators** | Clear status messages to stderr, results to stdout |
| **Error messages** | Actionable error messages with remediation hints |

## Technology Stack (Planned)

Based on legacy patterns and ecosystem requirements:

- **Python 3.11+**: Runtime environment
- **Click**: CLI framework (proven in RemoteAgents)
- **PyYAML**: YAML file parsing
- **httpx**: Async HTTP client for API calls
- **uv**: Package management
- **pytest**: Testing framework

## Integration with AgenticEngineering

AgenticCLI fits into the broader ecosystem:

```
┌─────────────────────────────────────────────────────────┐
│                     Claude Code                          │
│              (reasoning, tool use, code)                 │
└─────────────────────────┬───────────────────────────────┘
                          │
                          │ invokes
                          ▼
                 ┌─────────────────┐
                 │   AgenticCLI    │  <-- This module
                 │  (agentic cmd)  │
                 └────────┬────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                │                ▼
    ┌─────────┐           │         ┌───────────┐
    │  Local  │           │         │  Backend  │
    │   Ops   │           │         │    API    │
    └─────────┘           │         └─────┬─────┘
    (worktree,            │               │
     plan, test,          │               ▼
     clean)               │       ┌───────────────┐
                          │       │AgenticBackend │
                          │       └───────────────┘
                          │
                          ▼
                 ┌───────────────┐
                 │   Planning    │
                 │   Folders     │
                 └───────────────┘
                 (docs/plans/live/)
```

## Principles

AgenticCLI follows the core principles from AgenticEngineering:

### Deterministic Over Reasoning

CLI commands should produce the same output given the same input. If a command requires judgment, it should be handled by Claude Code, not the CLI.

### Minimal Surface Area

Each command does one thing well. Complex workflows are composed by Claude Code calling multiple simple commands.

### Fail Fast, Fail Clearly

Commands validate inputs before executing. Error messages explain what went wrong and suggest fixes.

### Evidence-Based Inclusion

Commands are added only when LangSmith traces (or manual analysis) show repeated friction patterns. Hypothetical needs don't justify new commands.

## Development

### Prerequisites

```bash
# Python 3.11+ required
python --version

# uv for package management
pip install uv
```

### Setup (Future)

```bash
cd /home/code/AgenticEngineering/modules/AgenticCLI

# Create virtual environment and install dependencies
uv sync

# Run tests
uv run pytest

# Install CLI in development mode
uv pip install -e .

# Test CLI
agentic --help
```

## Contributing

This module is built by Claude Code, for Claude Code. The workflow:

1. Claude Code works on tasks using AgenticEngineering scaffolding
2. Friction points are identified (via LangSmith traces or manual analysis)
3. Patterns that stabilize get proposed as CLI commands
4. Commands are implemented following the patterns documented here
5. Claude Code uses the new commands, freeing reasoning for novel work

## Next Steps

1. **Define `agentic` entrypoint**: Set up pyproject.toml with Click-based CLI
2. **Implement `worktree create`**: First command based on mature legacy pattern
3. **Implement `plan status`**: Planning folder introspection
4. **Add test infrastructure**: Unit and integration tests

---

*Part of [AgenticEngineering](../../docs/README.md) - scaffolding for Claude Code sessions*
