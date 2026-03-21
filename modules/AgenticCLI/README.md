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

### plan - Epic Folder Management

Initialize, scaffold, and manage epic folders for tracking implementation tickets.

**User-facing commands** (under `agentic plan`):

```bash
# Show plan status
agentic plan status [<path>]

# List all plans
agentic plan list

# Create a new plan (interactive)
agentic plan new
```

**Agent-facing commands** (under `agentic agent plan`):

```bash
# Initialize worktree + plan folder (Main-First Planning)
agentic agent plan init <branch> [--description <desc>] [--base <base-branch>]

# Example: Create worktree and epic folder for feature branch
agentic agent plan init feature-auth --description "user_authentication"
# Creates: /path/to/repo-feature-auth (worktree)
# Creates: docs/epics/live/260119AE_user_authentication/ (epic folder)

# Scaffold plan folder only (without worktree)
agentic agent plan scaffold <name> [--worktree <path>]

# Validate plan folder structure
agentic agent plan validate <path>

# Task management
agentic agent plan task list [--plan <path>] [--status <filter>] [--verbose]
agentic agent plan task current [--plan <path>]
agentic agent plan task start <task-id> [--plan <path>]
agentic agent plan task complete <task-id> [--plan <path>]
agentic agent plan task status <task-id> [--plan <path>]
agentic agent plan task add <description> [--plan <path>] [--phase <id>] [--id <id>] [--priority <level>]
agentic agent plan task update <task-id> --status <status> [--plan <path>] [--note <text>]
agentic agent plan task prefill --preset <name> [--plan <path>] [--dry-run]

# Move completed tasks
agentic agent plan move task <task-id> [--plan <path>] [--dry-run] [--force]
agentic agent plan move tasks [--plan <path>] [--dry-run] [--force]
agentic agent plan move folder [--plan <path>] [--dry-run] [--force]

# Archive plan folder
agentic agent plan archive <path>

# Unarchive plan folder (move from completed back to live)
agentic agent plan unarchive --plan <name> [--force]

# Phase management
agentic agent plan phase add --id <id> --name <name> [--description <desc>] [--plan <path>]
agentic agent plan phase list [--plan <path>]
agentic agent plan phase update <phase-id> [--status <status>] [--name <name>] [--plan <path>]

# User stories management
agentic agent plan stories list [--plan <path>]
agentic agent plan stories test [--plan <path>] [--output <file>] [--format yaml|json]
```

#### Main-First Planning with `agent plan init`

The `agentic agent plan init` command enforces the Main-First Planning workflow:

1. **Creates worktree** (if not exists) at `../repo-<branch>`
2. **Generates epic folder name** using `YYMMDDXX_description` convention
3. **Scaffolds epic folder** with `live/` and `completed/` subdirectories

This eliminates naming convention errors by generating the folder name programmatically rather than relying on agent interpretation.

#### Ticket Management

Manage individual tickets within an epic's phases:

```bash
# List all tickets in the current epic folder
agentic agent plan task list
agentic agent plan task list --status pending        # Filter by status
agentic agent plan task list --verbose               # Show full ticket details

# Get the current ticket to work on (first in_progress, or first pending)
agentic agent plan task current
agentic agent plan task current --plan docs/epics/live/260128AB_feature

# Mark a ticket as in_progress
agentic agent plan task start build_01_001
agentic agent plan task start build_01_001 --plan docs/epics/live/260128AB_feature

# Mark a ticket as completed
agentic agent plan task complete build_01_001

# Show detailed status for a specific ticket
agentic agent plan task status build_01_001
agentic agent plan task status build_01_001 --plan docs/epics/live/260128AB_feature

# Add a new ticket to the epic
agentic agent plan task add "Implement user login endpoint"
agentic agent plan task add "Add unit tests" --phase P2 --priority high
agentic agent plan task add "Fix bug" --id hotfix_001 --phase P1

# Update ticket status with optional note
agentic agent plan task update build_01_001 --status completed
agentic agent plan task update build_01_001 --status blocked --note "Waiting for API spec"

# Prefill tickets from a preset template
agentic agent plan task prefill --preset planner-build
agentic agent plan task prefill --preset builder --dry-run  # Preview without changes
```

**Options for `agent plan task list`:**
- `--plan`, `-p`: Path to epic folder (auto-detected if omitted)
- `--status`, `-s`: Filter by status (pending, in_progress, completed, or all)
- `--verbose`, `-v`: Show full ticket details including guidance and success criteria

**Options for `agent plan task current`:**
- `--plan`, `-p`: Path to epic folder (auto-detected if omitted)

Returns the first `in_progress` ticket, or the first `pending` ticket if none are in progress. This is the primary "what should I do next?" query for agents.

**Options for `agent plan task start`:**
- `task_id` (required): Ticket ID to mark as in_progress
- `--plan`, `-p`: Path to epic folder (auto-detected if omitted)

**Options for `agent plan task complete`:**
- `task_id` (required): Ticket ID to mark as completed
- `--plan`, `-p`: Path to epic folder (auto-detected if omitted)

**Options for `agent plan task status`:**
- `task_id` (required): Ticket ID to display details for
- `--plan`, `-p`: Path to epic folder (auto-detected if omitted)

Displays comprehensive ticket information including description, status, phase, inputs, target files, guidance, and success criteria.

**Options for `agent plan task add`:**
- `description` (required): Description of the new ticket
- `--plan`, `-p`: Path to epic folder (auto-detected if omitted)
- `--phase`: Phase ID to add the ticket to (default: last phase)
- `--id`: Custom ticket ID (default: auto-generated from phase ID)
- `--priority`: Ticket priority - low, medium, high (default: medium)

**Options for `agent plan task update`:**
- `task_id` (required): Ticket ID to update
- `--status`, `-s` (required): New status (pending, in_progress, completed, blocked)
- `--plan`, `-p`: Path to epic folder (auto-detected if omitted)
- `--note`, `-n`: Add a completion note to the ticket

Status transitions are validated. When marking a ticket as `completed`, a timestamp is automatically recorded.

**Options for `agent plan task prefill`:**
- `--preset` (required): Name of the preset template to load (e.g., planner-build, builder)
- `--plan`, `-p`: Path to epic folder (auto-detected if omitted)
- `--dry-run`: Show tickets that would be added without making changes

#### Phase Management

Manage phases within an epic's `plan_build.yml` file:

```bash
# Add a new phase to the epic
agentic agent plan phase add --id P1 --name "Core Implementation" --description "Build the main features"

# List all phases with their status and ticket counts
agentic agent plan phase list --plan docs/epics/live/260128AB_feature

# Update a phase's status or name
agentic agent plan phase update P1 --status in_progress
agentic agent plan phase update P1 --name "Updated Phase Name" --status completed
```

**Options for `agent plan phase add`:**
- `--id` (required): Phase identifier (e.g., P1, build_01)
- `--name` (required): Human-readable phase name
- `--description`: Optional description of the phase scope
- `--plan`, `-p`: Path to epic folder (auto-detected if omitted)

**Options for `agent plan phase update`:**
- `phase_id`: The ID of the phase to update
- `--status`, `-s`: New status (pending, in_progress, completed, blocked)
- `--name`, `-n`: New name for the phase
- `--plan`, `-p`: Path to epic folder

#### User Stories Management

List and test user stories defined in epic YAML files:

```bash
# List all user stories in an epic
agentic agent plan stories list --plan docs/epics/live/260128AB_feature

# Generate blind test scenarios from user stories
agentic agent plan stories test --plan docs/epics/live/260128AB_feature

# Output test cases to a file
agentic agent plan stories test --output tests/story_tests.yml --format yaml
agentic agent plan stories test --output tests/story_tests.json --format json
```

**Options for `agent plan stories list`:**
- `--plan`, `-p`: Path to epic folder (auto-detected if omitted)

**Options for `agent plan stories test`:**
- `--plan`, `-p`: Path to epic folder
- `--output`, `-o`: Output file path (default: stdout)
- `--format`, `-f`: Output format - `yaml` (default) or `json`

### question - Question Queue Management

Manage questions that arise during agent workflows. Questions are stored in an epic's `questions/` directory with pending and answered status tracking.

All question commands are under `agentic agent question`:

```bash
# List questions
agentic agent question list [--plan <path>] [--status pending|answered|deferred|all]
agentic agent question list --status pending              # List pending questions (default)
agentic agent question list --status answered             # List answered questions
agentic agent question list --status all                  # List all questions

# Show question details
agentic agent question show <question_id> [--plan <path>]
agentic agent question show Q-20260203-143022-a1b2

# Create a new question
agentic agent question ask <text> [--plan <path>] [--severity blocking|high|medium|low] [--context <text>]
agentic agent question ask "What testing framework should we use?" --severity high
agentic agent question ask "Should we add this feature?" --severity medium --context "Feature request from user"

# Answer a question
agentic agent question answer <question_id> [--plan <path>] [--text <answer>] [--confidence high|medium|low]
agentic agent question answer Q-20260203-143022-a1b2 --text "Use pytest for testing" --confidence high
agentic agent question answer Q-20260203-143022-a1b2   # Prompt for answer text

# Defer a question
agentic agent question defer <question_id> [--plan <path>]
agentic agent question defer Q-20260203-143022-a1b2
```

**Question ID Format:**
- `Q-YYYYMMDD-HHMMSS-XXXX` (e.g., `Q-20260203-143022-a1b2`)
- Timestamp provides chronological ordering
- Random suffix ensures uniqueness

**Directory Structure:**
```
epic_folder/
  questions/
    pending/          # Unanswered questions
      Q-20260203-143022-a1b2.yml
    answered/         # Answered questions
      Q-20260203-143022-a1b2.yml          # Answer
      Q-20260203-143022-a1b2_question.yml # Original question
```

**Severity Levels:**
- `blocking` - Must be answered before proceeding
- `high` - Important, should be answered soon
- `medium` - Normal priority (default)
- `low` - Can be deferred

**Epic Path Detection:**
- Auto-detects from Main-First plan resolver (current branch's active epic)
- Override with `--plan <path>` flag
- Useful for working across multiple epics

**JSON Output:**
All commands support `--json` flag for structured output:
```bash
agentic --json agent question list --status pending
agentic --json agent question show Q-20260203-143022-a1b2
```

**Tmux Integration:**
For remote/SSH scenarios, see the [Tmux HITL Workflow Guide](../../docs/epics/live/260203QT_question_tmux/WORKFLOW.md) for setting up automatic question notifications in tmux panes.

### worktree (wt) - Git Worktree Management

Manage git worktrees with integrated epic folder support.

```bash
# Create worktree with epic folder
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

### context (ctx) - CCI Context Injection

CLI Context Injection (CCI) commands for agents to fetch exactly what they need via CLI instead of loading large static files. The context command is the primary mechanism for agents to self-initialize with the right context for their role and current task.

```bash
# Primary entrypoint - aggregates task, role guidance, and essential inputs
agentic agent context bootstrap [--role <role-id>]
agentic agent ctx bootstrap --role build-python

# Get role-specific process.yml and manifest.yml content
agentic agent context role <role-id> [--format yaml|json]
agentic agent ctx role planner-build
agentic agent ctx role build-python --format json

# Get active ticket from Main-First epic (crawls docs/epics/live/)
agentic agent context task [--all]
agentic agent ctx task
agentic agent ctx task --all

# Get input files for a role with path resolution
agentic agent context inputs --role <role-id> [--resolve]
agentic agent ctx inputs --role build-python
agentic agent ctx inputs --role planner-build --resolve

# Generate thin-client agent file from bootstrap template
agentic agent context generate-agent <role-id> [--output <file>]
agentic agent ctx generate-agent build-python
agentic agent ctx generate-agent planner-build --output agent.md
```

#### Subcommand Details

**bootstrap** - Primary entrypoint for agents to self-initialize

Returns a combined context bundle containing:
- Active Ticket from the current epic (from docs/epics/live/)
- Role-specific process guidance (process.yml)
- Essential input file references

```bash
# Auto-detect role from context
agentic agent context bootstrap

# Specify role explicitly
agentic agent ctx bootstrap --role build-python

# Preview first 50 lines of bootstrap output
agentic agent ctx bootstrap | head -50
```

**role** - Returns process.yml and manifest.yml content for a role

Retrieves the process guidance and manifest definition from the AgenticGuidance module for the specified role ID.

```bash
# Get role guidance as YAML (default)
agentic agent ctx role planner-build

# Get role guidance as JSON
agentic agent ctx role build-python --format json
```

**task** - Crawls docs/epics/live/ to find active ticket

Searches epic YAML files for the first in_progress ticket, or the first pending ticket if none are in progress. Returns ticket details including ID, description, and guidance.

```bash
# Get current/next task to work on
agentic agent ctx task

# Show all tasks in the plan
agentic agent ctx task --all
```

**inputs** - Returns input files for a role with path resolution

Retrieves the inputs.yml file for the specified role and resolves all file paths, layer references, and existence checks. Provides a manifest of relevant project files.

```bash
# Get inputs for a role
agentic agent ctx inputs --role build-python

# Get inputs with layer expansion
agentic agent ctx inputs --role planner-build --resolve
```

**generate-agent** - Generate thin-client agent file from bootstrap template

Creates a minimal agent markdown file that uses the CCI bootstrap protocol to self-initialize at runtime rather than embedding static context.

```bash
# Output to stdout
agentic agent ctx generate-agent build-python

# Save to file
agentic agent ctx generate-agent planner-build --output agent.md
```

### entrypoint (ep) - Workflow Entrypoints

Discover and execute workflow entrypoints that define starting points for orchestration and planning. Entrypoint files are named with an underscore prefix (e.g., `_plan_build.yml`) and are located in `.claude/entrypoints/` or `modules/AgenticGuidance/entrypoints/`.

```bash
# List all available entrypoints
agentic agent entrypoint list
agentic agent ep list

# Show the full contents of an entrypoint file
agentic agent entrypoint show plan_build
agentic agent ep show _orchestrate

# Execute entrypoint with variable substitution
agentic agent entrypoint execute plan_build
agentic agent ep execute orchestrate --context "Additional context here"

# Execute with custom variables
agentic agent ep execute plan_build --vars TASK_ID=build_01 --vars BRANCH=feature-auth

# Compile complete context bundle (includes orchestration, inputs, and references)
agentic agent ep execute plan_build --compile
agentic agent ep execute orchestrate --compile --context "My context"
```

#### Subcommand Details

**list** - Display all available entrypoints

Searches for entrypoint files in two locations (in priority order):
1. `.claude/entrypoints/` in the current working directory
2. `modules/AgenticGuidance/entrypoints/` in the project root

```bash
# List all entrypoints with their descriptions
agentic agent ep list

# JSON output for scripting
agentic -j agent ep list
```

**show** - Show the full contents of an entrypoint file

Retrieves and displays the raw content of an entrypoint file by name. The underscore prefix is optional.

```bash
# Show entrypoint content (underscore optional)
agentic agent ep show plan_build
agentic agent ep show _plan_build

# JSON output includes path and type
agentic -j agent ep show orchestrate
```

**execute** - Execute entrypoint with variable substitution

Reads the entrypoint file, applies variable substitution using `{{VAR}}` syntax, and outputs the processed content. Supports custom variables, context prepending, and full context compilation.

```bash
# Basic execution with variable substitution
agentic agent ep execute plan_build

# Add custom variables (KEY=VALUE format)
agentic agent ep execute plan_build --vars TASK_ID=build_01
agentic agent ep execute orchestrate --vars BRANCH=main --vars PHASE=P1

# Prepend context text to output
agentic agent ep execute orchestrate --context "Working on feature authentication"

# Compile complete context bundle
agentic agent ep execute plan_build --compile
```

**Options for `entrypoint execute`:**
- `name` (required): Entrypoint name (with or without underscore prefix)
- `--vars`: Variable substitution pairs in KEY=VALUE format (can be repeated)
- `--context`: Additional context text to prepend to the entrypoint content
- `--compile`, `-c`: Compile complete context bundle including orchestration file, inputs.yml, and all referenced files

**Compile Mode:**

When `--compile` is specified, the command builds a complete context bundle by:
1. Reading and processing the entrypoint file with variable substitution
2. Finding and including the orchestration file (process.yml) referenced by the entrypoint
3. Locating and including the inputs.yml file for the orchestration
4. Resolving all `location:` references in inputs.yml and including those files

Output sections are delimited with headers like `# === ENTRYPOINT: name ===` for easy parsing.

**Built-in Variables:**
- `TIMESTAMP`: Current ISO timestamp (automatically injected)

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

### orchestrate - Orchestration and Session Management

Orchestrate epics and manage Claude Code sessions. Sessions can run in the foreground or background, with full tracking of status, output logs, and process lifecycle.

```bash
# Plan an epic (spawns planner agents)
agentic orchestrate session plan --plan <epic-folder>
agentic orchestrate session plan  # Plan all unplanned epics

# Implement an epic (execute phases via agents)
agentic orchestrate session implement --plan <epic-folder>
agentic orchestrate session implement  # Execute all ready epics

# Spawn a new Claude Code session
agentic orchestrate session spawn --prompt "Implement the feature"
agentic orchestrate session spawn -p "Fix the bug in auth.py" --max-turns 10

# Spawn in background mode (returns immediately)
agentic orchestrate session spawn --prompt "Run tests" --background
agentic orchestrate session spawn -p "Build docs" --background --directory /path/to/project

# List all sessions
agentic orchestrate session list
agentic orchestrate session list --active  # Only show running sessions

# Get health check of a session
agentic orchestrate health <session-id>

# Get session output logs
agentic orchestrate debug logs abc123

# Stop a running session
agentic orchestrate session stop <session-id>
agentic orchestrate session stop abc123 --force  # Force kill (SIGKILL)

# State inspection
agentic orchestrate debug state list
agentic orchestrate debug state show <session-id>
agentic orchestrate debug state clear
agentic orchestrate debug state cleanup
```

#### Subcommand Details

**session spawn** - Start a new Claude Code session

Launches the `claude` CLI with the specified prompt. In foreground mode, waits for completion and displays output. In background mode, returns immediately and logs output to files.

```bash
# Basic foreground session
agentic orchestrate session spawn --prompt "Analyze the codebase and suggest improvements"

# Background session with turn limit
agentic orchestrate session spawn -p "Refactor the utils module" --max-turns 5 --background

# Session in a specific directory
agentic orchestrate session spawn -p "Fix failing tests" --directory /home/code/project
```

**Options for `orchestrate session spawn`:**
- `--prompt`, `-p` (required): The prompt to send to Claude Code
- `--max-turns`: Maximum number of conversation turns (passed to claude CLI)
- `--background`: Run session in background, return immediately
- `--directory`: Working directory for the session (default: current directory)

**session list** - Display all Claude Code sessions

Shows a table of all tracked sessions with their status, PID, start time, and prompt summary.

```bash
# List all sessions
agentic orchestrate session list

# List only running sessions
agentic orchestrate session list --active

# JSON output for scripting
agentic -j orchestrate session list
```

**Options for `orchestrate session list`:**
- `--active`: Filter to show only running sessions

**session stop** - Stop a running session

Sends a termination signal to the session process. By default uses SIGTERM for graceful shutdown.

```bash
# Graceful stop (SIGTERM)
agentic orchestrate session stop abc123

# Force kill (SIGKILL)
agentic orchestrate session stop abc123 --force
```

**Options for `orchestrate session stop`:**
- `session_id` (required): Full or partial session UUID
- `--force`: Use SIGKILL instead of SIGTERM

**health** - Get session health information

Displays health and status information about a session. Use `--diagnose` to auto-spawn diagnostics.

```bash
# Get session health check
agentic orchestrate health abc123

# Auto-spawn diagnostics on unhealthy session
agentic orchestrate health abc123 --diagnose

# JSON output
agentic -j orchestrate health abc123
```

**debug logs** - Get session output logs

Displays the output logs of a session.

```bash
# Get session logs
agentic orchestrate debug logs abc123
```

**Options for `orchestrate health`:**
- `session_id` (required): Full or partial session UUID
- `--diagnose`: Auto-spawn diagnostics if the session is unhealthy

**Session Storage:**

Sessions are tracked in `~/.agentic/sessions/`:
- Session metadata: `~/.agentic/sessions/<session-id>.json`
- Output logs: `~/.agentic/sessions/logs/<session-id>.stdout.log`
- Error logs: `~/.agentic/sessions/logs/<session-id>.stderr.log`

### Additional Project Commands

```bash
# Validate inputs.yml references
agentic inputs validate <file>
agentic inputs resolve <file>

# Generate plan files from templates
agentic template generate <type> [--output <file>] [--objective <text>] [--phases <phases>] [--success-criteria <criteria>]
agentic template list
agentic tpl generate build -o plan.yml

# Example: Generate with custom objective and phases
agentic template generate build --objective "Implement user authentication" --phases "P1:Setup,P2:Build,P3:Test" --success-criteria "Tests pass,Coverage > 80%"

# Find user stories
agentic agent stories find [--project <name>] [--changes <files>]
agentic agent st find -p my-project

# Manage agent manifests
agentic agent manifest show <path>
agentic agent manifest list [<path>]
agentic agent manifest validate <path>
agentic agent mf show ./agents/my-agent

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

### template (tpl) - Epic Template Generation

Generate epic YAML files from templates with optional customization:

```bash
# List available template types
agentic template list

# Generate a build epic to stdout
agentic template generate build

# Generate to file with objective
agentic template generate build --output plan_build.yml --objective "Implement CLI commands"

# Generate with custom phases
agentic template generate build --phases "P1:Setup,P2:Implementation,P3:Testing,P4:Docs"

# Generate with success criteria
agentic template generate build --success-criteria "All tests pass,Coverage > 80%,No lint errors"

# Full example with all options
agentic template generate build \
  --output plan_build.yml \
  --objective "Add new authentication system with OAuth2 support" \
  --phases "P1:Setup OAuth,P2:Build Auth Flow,P3:Add Tests" \
  --success-criteria "OAuth flow works,Unit tests pass,Integration tests pass"
```

**Template Types:**
| Type | Description |
|------|-------------|
| `build` | Implementation epic for building new features with phased tickets |
| `test` | Test epic with unit, integration, and e2e test phases |
| `cleanup` | Audit and cleanup epic for code review and documentation |
| `guidance` | Guidance improvement epic for agent guidance quality |

**Options for `template generate`:**
- `type` (required): Template type (build, test, cleanup, guidance)
- `--output`, `-o`: Output file path (default: stdout)
- `--objective`: Objective description to inject into the template (replaces placeholder text)
- `--phases`: Comma-separated list of `ID:Name` pairs (e.g., `P1:Build,P2:Test`)
- `--success-criteria`: Comma-separated or newline-separated list of success criteria

## Command Categories

| Category | Scope | Commands |
|----------|-------|----------|
| **Global** | Any directory | setup, health, config, prefs, update, rebuild, orchestrate |
| **Project** | Requires .git or .agenticcli.yml | worktree, plan, agent (context, entrypoint, stories, manifest, question), inputs, template |

Project commands require being in a git repository or having a `.agenticcli.yml` file in the directory tree.

## Output Modes

```bash
# Human-readable output (default)
agentic plan status

# JSON output for scripting
agentic -j plan status

# Debug logging to console
agentic -d agent plan init my-branch
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
│   │   ├── context.py      # CCI context injection
│   │   ├── entrypoint.py   # Workflow entrypoints
│   │   ├── orchestrate.py  # Orchestrate command (session, health, debug subcommands)
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

Commands are added when evidence shows repeated patterns. Hypothetical needs don't justify new commands.

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
3. **Repeated agent struggles observed** - Agents repeatedly struggle with the same deterministic task
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

**Example: Epic Folder Naming**

1. Initially, agents interpreted naming conventions from documentation
2. Agent traces showed naming drift and verification loops
3. Convention was documented: `YYMMDDXX_description`
4. `agentic agent plan init` now enforces naming programmatically
5. Agents call CLI - no interpretation, no verification needed

### Boundary Definition

The boundary between CLI and agent sits at the point where **determinism ends**:

- **Deterministic** (CLI): "Create folder named `260128AB_feature_auth`"
- **Judgment** (Agent): "Should we create a new plan folder for this work?"

CLI commands guarantee: **correct output or explicit failure**. Agents guarantee: **thoughtful handling of ambiguity**.

---

*Part of [AgenticEngineering](../../docs/README.md) - scaffolding for Claude Code sessions*
