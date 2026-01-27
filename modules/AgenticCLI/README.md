# AgenticCLI

Command-line interface for AgenticEngineering. Provides the **tool layer** that Claude Code invokes for deterministic, well-understood operations.

## Installation

```bash
cd /home/code/AgenticEngineering/modules/AgenticCLI
uv sync
uv pip install -e .
```

## Quick Reference

```bash
agentic --help              # Show all commands
agentic -v                  # Show version
agentic -j <command>        # JSON output mode
agentic -d <command>        # Debug mode
```

## Commands

### plan - Planning Folder Management

Initialize, scaffold, and manage planning folders for tracking implementation tasks.

```bash
# Initialize worktree + plan folder (Main-First Planning)
agentic plan init <branch> [--description <desc>] [--base <base-branch>]

# Example: Create worktree and plan folder for feature branch
agentic plan init feature-auth --description "user_authentication"
# Creates: /path/to/repo-feature-auth (worktree)
# Creates: docs/plans/live/260119AE_user_authentication/ (plan folder)

# Scaffold plan folder only (without worktree)
agentic plan scaffold <name> [--worktree <path>]

# Show plan status
agentic plan status [<path>]

# List all plans
agentic plan list

# Validate plan folder structure
agentic plan validate <path>

# Task management
agentic plan task start <task-id> [--plan <path>]
agentic plan task complete <task-id> [--plan <path>]

# Move completed tasks
agentic plan move task <task-id> [--plan <path>] [--dry-run] [--force]
agentic plan move tasks [--plan <path>] [--dry-run] [--force]
agentic plan move folder [--plan <path>] [--dry-run] [--force]

# Archive plan folder
agentic plan archive <path>
```

#### Main-First Planning with `plan init`

The `plan init` command enforces the Main-First Planning workflow:

1. **Creates worktree** (if not exists) at `../repo-<branch>`
2. **Generates plan folder name** using `YYMMDDXX_description` convention
3. **Scaffolds plan folder** with `live/` and `completed/` subdirectories

This eliminates naming convention errors by generating the folder name programmatically rather than relying on agent interpretation.

### langsmith (ls) - LangSmith Integration

Query LangSmith traces, runs, and project statistics.

```bash
# List recent runs
agentic langsmith runs [--project <name>] [--limit <n>] [--type llm|chain|tool|retriever] [--error]
agentic ls runs -p my-project -l 50

# Get details for a specific run
agentic langsmith run <run-id> [--url]
agentic ls run abc123 --url

# List all projects
agentic langsmith projects [--detail]
agentic ls projects -d

# Show project statistics
agentic langsmith stats --project <name> [--since YYYY-MM-DD] [--until YYYY-MM-DD]
agentic ls stats -p my-project --since 2026-01-01

# Analyze friction patterns
agentic langsmith friction [--project <name>] [--limit <n>] [--lookback-days <n>] [--recommend]
agentic ls friction -p my-project -r
```

**Environment Variables:**
- `LANGSMITH_API_KEY` - Required for all LangSmith commands
- `CC_LANGSMITH_PROJECT` - Default project for friction analysis

### worktree (wt) - Git Worktree Management

Manage git worktrees with integrated planning folder support.

```bash
# Create worktree with planning folder
agentic worktree create <branch> [--base <base-branch>] [--no-plan]
agentic wt create feature-auth --base main

# List all worktrees
agentic worktree list
agentic wt list

# Remove worktree
agentic worktree remove <branch> [--force]

# Show current worktree status
agentic worktree status
```

### config (cfg) - Configuration Management

Manage CLI configuration stored in `~/.config/agenticcli/`.

```bash
# Show current configuration
agentic config show

# Initialize configuration
agentic config init

# Preferences
agentic config get <key>
agentic config set <key> <value>
agentic config list
agentic config delete <key>

# Config file paths
agentic config show-path
agentic config set-path <path>

# Clear all configuration
agentic config clear --force
```

### preferences (prefs) - User Preferences

Manage user preferences (alternative interface to config).

```bash
agentic prefs get <key>
agentic prefs set <key> <value>
agentic prefs list
agentic prefs delete <key>
agentic prefs clear [--force]
```

### Global Commands

```bash
# Interactive setup wizard
agentic setup [--force]

# Health check
agentic health

# Package management
agentic update    # Reinstall from source (uv sync)
agentic rebuild   # Full rebuild and reinstall
```

### Additional Project Commands

```bash
# Validate inputs.yml references
agentic inputs validate <file>
agentic inputs resolve <file>

# Generate plan files from templates
agentic template generate <type> [--output <file>]
agentic template list
agentic tpl generate build -o plan.yml

# Find user stories
agentic stories find [--project <name>] [--changes <files>]
agentic st find -p my-project

# Manage agent manifests
agentic manifest show <path>
agentic manifest list [<path>]
agentic manifest validate <path>
agentic mf show ./agents/my-agent

# CI/CD configuration
agentic cicd audit
agentic cicd list
agentic cicd show [<path>]

# State management
agentic state list [--active]
agentic state show <pid>
agentic state clear [--all] [--force]
agentic state cleanup

# Environment management
agentic env show
agentic env export [--format shell|json]
agentic env run <command> [args...]
```

## Command Categories

| Category | Scope | Commands |
|----------|-------|----------|
| **Global** | Any directory | setup, health, config, prefs, update, rebuild, state, env |
| **Project** | Requires .git | worktree, plan, langsmith, inputs, template, stories, manifest, cicd |

Project commands require being in a git repository or having a `.agenticcli.yml` file in the directory tree.

## Output Modes

```bash
# Human-readable output (default)
agentic plan status

# JSON output for scripting
agentic -j plan status

# Debug logging to console
agentic -d plan init my-branch
```

## Directory Structure

```
AgenticCLI/
├── src/agenticcli/
│   ├── __init__.py
│   ├── cli.py              # Main CLI parser and routing
│   ├── context.py          # CLIContext for dependency injection
│   ├── console.py          # Output formatting (Rich-based)
│   ├── logging.py          # Logging configuration
│   ├── commands/           # Command implementations
│   │   ├── plan.py         # Plan management
│   │   ├── worktree.py     # Worktree management
│   │   ├── langsmith.py    # LangSmith integration
│   │   ├── config.py       # Configuration
│   │   ├── preferences.py  # Preferences
│   │   ├── setup.py        # Setup wizard
│   │   ├── health.py       # Health checks
│   │   └── ...
│   ├── core/               # Shared utilities
│   ├── utils/              # Helper functions
│   └── workflows/          # Business logic
├── tests/
├── pyproject.toml
└── README.md
```

## Principles

### Deterministic Over Reasoning

CLI commands produce the same output given the same input. Complex judgment is left to Claude Code.

### Minimal Surface Area

Each command does one thing well. Complex workflows are composed by Claude Code calling multiple commands.

### Fail Fast, Fail Clearly

Commands validate inputs before executing. Error messages explain what went wrong and suggest fixes.

### Evidence-Based Inclusion

Commands are added when LangSmith traces show repeated friction patterns. Hypothetical needs don't justify new commands.

## CLI vs Agent Architecture

### CLI Responsibility Boundary

**CLI is a deterministic executor - no decision making.**

The CLI handles operations with predictable, rule-based outcomes. Given the same inputs, a CLI command produces the same output every time. There is no interpretation, judgment, or context-sensitivity in CLI execution.

| CLI Handles | Agent Handles |
|-------------|---------------|
| Folder naming conventions | Deciding when to create folders |
| YAML/JSON validation | Interpreting requirements |
| Git worktree mechanics | Choosing branch strategy |
| Task status updates | Determining task completion |
| File movement (live/ to completed/) | Deciding what to archive |

### When to Add New CLI Commands

Add a CLI command when:

1. **Established pattern exists** - The operation follows documented conventions that don't require interpretation
2. **Mechanical operation** - The work is repetitive and rule-based
3. **LangSmith traces show friction** - Agents repeatedly struggle with the same deterministic task
4. **Verification can be eliminated** - CLI enforcement removes the need for verification agents

Do NOT add a CLI command when:
- The operation requires context-sensitivity or creativity
- Judgment is needed to determine inputs
- The operation is rare or one-off
- The command would just wrap agent reasoning

### The Handoff Pattern

Operations evolve from agent-handled to CLI-handled as patterns become established:

```
Novel Situation          Agent handles with judgment
       |
       v
Repeated Pattern         Agent still handles, friction observed
       |
       v
Established Convention   Document the pattern, design CLI interface
       |
       v
CLI Implementation       Offload to CLI, agent invokes tool
```

**Example: Plan Folder Naming**

1. Initially, agents interpreted naming conventions from documentation
2. LangSmith traces showed naming drift and verification loops
3. Convention was documented: `YYMMDDXX_description`
4. `agentic plan init` now enforces naming programmatically
5. Agents call CLI - no interpretation, no verification needed

### Boundary Definition

The boundary between CLI and agent sits at the point where **determinism ends**:

- **Deterministic** (CLI): "Create folder named `260128AB_feature_auth`"
- **Judgment** (Agent): "Should we create a new plan folder for this work?"

CLI commands guarantee: **correct output or explicit failure**. Agents guarantee: **thoughtful handling of ambiguity**.

---

*Part of [AgenticEngineering](../../docs/README.md) - scaffolding for Claude Code sessions*
