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
agentic plan task list [--plan <path>] [--status <filter>] [--verbose]
agentic plan task current [--plan <path>]
agentic plan task start <task-id> [--plan <path>]
agentic plan task complete <task-id> [--plan <path>]
agentic plan task status <task-id> [--plan <path>]
agentic plan task add <description> [--plan <path>] [--phase <id>] [--id <id>] [--priority <level>]
agentic plan task update <task-id> --status <status> [--plan <path>] [--note <text>]
agentic plan task prefill --preset <name> [--plan <path>] [--dry-run]

# Move completed tasks
agentic plan move task <task-id> [--plan <path>] [--dry-run] [--force]
agentic plan move tasks [--plan <path>] [--dry-run] [--force]
agentic plan move folder [--plan <path>] [--dry-run] [--force]

# Archive plan folder
agentic plan archive <path>

# Unarchive plan folder (move from completed back to live)
agentic plan unarchive --plan <name> [--force]

# Phase management
agentic plan phase add --id <id> --name <name> [--description <desc>] [--plan <path>]
agentic plan phase list [--plan <path>]
agentic plan phase update <phase-id> [--status <status>] [--name <name>] [--plan <path>]

# Orchestration (MMD workflow diagrams)
agentic plan orchestration generate [--plan <path>] [--output <file>] [--force]
agentic plan orchestration validate [--plan <path>] [--strict]

# User stories management
agentic plan stories list [--plan <path>]
agentic plan stories test [--plan <path>] [--output <file>] [--format yaml|json]
```

#### Main-First Planning with `plan init`

The `plan init` command enforces the Main-First Planning workflow:

1. **Creates worktree** (if not exists) at `../repo-<branch>`
2. **Generates plan folder name** using `YYMMDDXX_description` convention
3. **Scaffolds plan folder** with `live/` and `completed/` subdirectories

This eliminates naming convention errors by generating the folder name programmatically rather than relying on agent interpretation.

#### Task Management

Manage individual tasks within a plan's phases:

```bash
# List all tasks in the current plan folder
agentic plan task list
agentic plan task list --status pending        # Filter by status
agentic plan task list --verbose               # Show full task details

# Get the current task to work on (first in_progress, or first pending)
agentic plan task current
agentic plan task current --plan docs/plans/live/260128AB_feature

# Mark a task as in_progress (requires orchestration_*.mmd to exist)
agentic plan task start build_01_001
agentic plan task start build_01_001 --plan docs/plans/live/260128AB_feature

# Mark a task as completed
agentic plan task complete build_01_001

# Show detailed status for a specific task
agentic plan task status build_01_001
agentic plan task status build_01_001 --plan docs/plans/live/260128AB_feature

# Add a new task to the plan
agentic plan task add "Implement user login endpoint"
agentic plan task add "Add unit tests" --phase P2 --priority high
agentic plan task add "Fix bug" --id hotfix_001 --phase P1

# Update task status with optional note
agentic plan task update build_01_001 --status completed
agentic plan task update build_01_001 --status blocked --note "Waiting for API spec"

# Prefill tasks from a preset template
agentic plan task prefill --preset planner-build
agentic plan task prefill --preset builder --dry-run  # Preview without changes
```

**Options for `plan task list`:**
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)
- `--status`, `-s`: Filter by status (pending, in_progress, completed, or all)
- `--verbose`, `-v`: Show full task details including guidance and success criteria

**Options for `plan task current`:**
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)

Returns the first `in_progress` task, or the first `pending` task if none are in progress. This is the primary "what should I do next?" query for agents.

**Options for `plan task start`:**
- `task_id` (required): Task ID to mark as in_progress
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)

Note: Requires an `orchestration_*.mmd` file to exist in the plan folder. Plans must be orchestrated before task execution begins.

**Options for `plan task complete`:**
- `task_id` (required): Task ID to mark as completed
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)

**Options for `plan task status`:**
- `task_id` (required): Task ID to display details for
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)

Displays comprehensive task information including description, status, phase, inputs, target files, guidance, and success criteria.

**Options for `plan task add`:**
- `description` (required): Description of the new task
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)
- `--phase`: Phase ID to add the task to (default: last phase)
- `--id`: Custom task ID (default: auto-generated from phase ID)
- `--priority`: Task priority - low, medium, high (default: medium)

**Options for `plan task update`:**
- `task_id` (required): Task ID to update
- `--status`, `-s` (required): New status (pending, in_progress, completed, blocked)
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)
- `--note`, `-n`: Add a completion note to the task

Status transitions are validated. When marking a task as `completed`, a timestamp is automatically recorded.

**Options for `plan task prefill`:**
- `--preset` (required): Name of the preset template to load (e.g., planner-build, builder)
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)
- `--dry-run`: Show tasks that would be added without making changes

#### Phase Management

Manage phases within a plan's `plan_build.yml` file:

```bash
# Add a new phase to the plan
agentic plan phase add --id P1 --name "Core Implementation" --description "Build the main features"

# List all phases with their status and task counts
agentic plan phase list --plan docs/plans/live/260128AB_feature

# Update a phase's status or name
agentic plan phase update P1 --status in_progress
agentic plan phase update P1 --name "Updated Phase Name" --status completed
```

**Options for `plan phase add`:**
- `--id` (required): Phase identifier (e.g., P1, build_01)
- `--name` (required): Human-readable phase name
- `--description`: Optional description of the phase scope
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)

**Options for `plan phase update`:**
- `phase_id`: The ID of the phase to update
- `--status`, `-s`: New status (pending, in_progress, completed, blocked)
- `--name`, `-n`: New name for the phase
- `--plan`, `-p`: Path to plan folder

#### Orchestration Management

Generate and validate Mermaid flowchart diagrams that define the execution order of plan phases:

```bash
# Generate orchestration MMD from plan YAML files
agentic plan orchestration generate --plan docs/plans/live/260128AB_feature

# Generate with custom output filename
agentic plan orchestration generate --output orchestration_custom.mmd --force

# Validate that MMD matches plan YAML structure
agentic plan orchestration validate --plan docs/plans/live/260128AB_feature

# Strict validation: treat warnings as errors
agentic plan orchestration validate --strict
```

**Options for `plan orchestration generate`:**
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)
- `--output`, `-o`: Output filename (default: `orchestration_<plan_name>.mmd`)
- `--force`, `-f`: Overwrite existing MMD file if present

**Options for `plan orchestration validate`:**
- `--plan`, `-p`: Path to plan folder
- `--strict`: Treat warnings as errors (exit code 1 on warnings)

The generated MMD includes:
- Phase nodes from YAML with agent routing
- Test-fix loop structure for test phases
- Feedback triggers for failures
- CLI commands in comments for agent execution

#### User Stories Management

List and test user stories defined in plan YAML files:

```bash
# List all user stories in a plan
agentic plan stories list --plan docs/plans/live/260128AB_feature

# Generate blind test scenarios from user stories
agentic plan stories test --plan docs/plans/live/260128AB_feature

# Output test cases to a file
agentic plan stories test --output tests/story_tests.yml --format yaml
agentic plan stories test --output tests/story_tests.json --format json
```

**Options for `plan stories list`:**
- `--plan`, `-p`: Path to plan folder (auto-detected if omitted)

**Options for `plan stories test`:**
- `--plan`, `-p`: Path to plan folder
- `--output`, `-o`: Output file path (default: stdout)
- `--format`, `-f`: Output format - `yaml` (default) or `json`

### langsmith (ls) - LangSmith Integration

Query LangSmith traces, runs, and project statistics with advanced forensic analysis capabilities.

```bash
# List recent runs
agentic langsmith runs [--project <name>] [--limit <n>] [--type llm|chain|tool|retriever] [--error]
agentic ls runs -p my-project -l 50

# Get details for a specific run (enhanced with hierarchy and timing)
agentic langsmith run <run-id> [--url] [--tree] [--full] [--format json|yaml|table] [--timing]
agentic ls run abc123 --url --tree --timing       # Show hierarchy and timing breakdown
agentic ls run abc123 --full --format yaml        # Full inputs/outputs in YAML
agentic ls run abc123 --tree                      # Show parent/child hierarchy

# List all projects
agentic langsmith projects [--detail]
agentic ls projects -d

# Show project statistics
agentic langsmith stats --project <name> [--since YYYY-MM-DD] [--until YYYY-MM-DD]
agentic ls stats -p my-project --since 2026-01-01

# Analyze friction patterns (enhanced with export and grouping)
agentic langsmith friction --project <name> [--sessions <n>] [--since YYYY-MM-DD] [--limit <n>] [--lookback-days <n>] [--min-affected <n>] [--recommend] [--validate|--no-validate] [--export json|markdown|yaml] [--group-by severity|type|session] [--json]
agentic ls friction -p my-project -r                                    # With recommendations
agentic ls friction -p my-project --sessions 5 --min-affected 2         # Session-based filtering
agentic ls friction -p my-project --export markdown --group-by severity # Export to markdown
agentic ls friction -p my-project --export yaml --group-by type         # Export grouped by type

# List recent sessions with run counts
agentic langsmith sessions --project <name> [--limit <n>] [--since YYYY-MM-DD] [--json]
agentic ls sessions -p my-project -l 20

# Analyze a specific session (NEW)
agentic langsmith session-analyze <session-id> [--project <name>] [--export json|csv|markdown]
agentic ls session-analyze abc123 --export csv     # Export session timeline to CSV
agentic ls session-analyze abc123 --export markdown # Export session report to markdown
agentic ls session-analyze abc123 -p my-project   # Analyze with project validation

# Search runs by pattern (NEW)
agentic langsmith batch-search <pattern> --project <name> [--field inputs|outputs|error|all] [--type llm|chain|tool|retriever] [--status success|error|running] [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--limit <n>] [--group-by session|type|status|none] [--export json|csv]
agentic ls batch-search "timeout.*exceeded" -p my-project                        # Search for timeout errors
agentic ls batch-search "retry" -p my-project --field error --export csv         # Search errors, export CSV
agentic ls batch-search "user_id" -p my-project --field inputs --group-by session # Group by session
```

**Enhanced Features:**

- **Run Inspection**: `--tree` shows parent/child hierarchy, `--full` displays complete inputs/outputs, `--timing` provides detailed timing breakdown
- **Friction Analysis**: Export to markdown/YAML/JSON, group patterns by severity/type/session for better organization
- **Session Analysis**: Dedicated command to analyze individual sessions with timeline and statistics
- **Batch Search**: Regex-based search across runs with flexible filtering and grouping

**Environment Variables:**
- `LANGSMITH_API_KEY` - Required for all LangSmith commands
- `CC_LANGSMITH_PROJECT` - Default project for friction analysis

**Troubleshooting:**

If you encounter "LANGSMITH_API_KEY not found":
```bash
# Set API key in environment
export LANGSMITH_API_KEY=your_key_here

# Or configure in CLI config
agentic config set langsmith.api_key your_key_here
```

If commands fail with "agenticlangsmith package not installed":
```bash
cd modules/AgenticLangSmith
uv pip install -e .
```

### question - Question Queue Management

Manage questions that arise during agent workflows. Questions are stored in a plan's `questions/` directory with pending and answered status tracking.

```bash
# List questions
agentic question list [--plan <path>] [--status pending|answered|deferred|all]
agentic question list --status pending              # List pending questions (default)
agentic question list --status answered             # List answered questions
agentic question list --status all                  # List all questions

# Show question details
agentic question show <question_id> [--plan <path>]
agentic question show Q-20260203-143022-a1b2

# Create a new question
agentic question ask <text> [--plan <path>] [--severity blocking|high|medium|low] [--context <text>]
agentic question ask "What testing framework should we use?" --severity high
agentic question ask "Should we add this feature?" --severity medium --context "Feature request from user"

# Answer a question
agentic question answer <question_id> [--plan <path>] [--text <answer>] [--confidence high|medium|low]
agentic question answer Q-20260203-143022-a1b2 --text "Use pytest for testing" --confidence high
agentic question answer Q-20260203-143022-a1b2   # Prompt for answer text

# Defer a question
agentic question defer <question_id> [--plan <path>]
agentic question defer Q-20260203-143022-a1b2
```

**Question ID Format:**
- `Q-YYYYMMDD-HHMMSS-XXXX` (e.g., `Q-20260203-143022-a1b2`)
- Timestamp provides chronological ordering
- Random suffix ensures uniqueness

**Directory Structure:**
```
plan_folder/
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

**Plan Path Detection:**
- Auto-detects from Main-First plan resolver (current branch's active plan)
- Override with `--plan <path>` flag
- Useful for working across multiple plans

**JSON Output:**
All commands support `--json` flag for structured output:
```bash
agentic --json question list --status pending
agentic --json question show Q-20260203-143022-a1b2
```

**Tmux Integration:**
For remote/SSH scenarios, see the [Tmux HITL Workflow Guide](../../docs/plans/live/260203QT_question_tmux/WORKFLOW.md) for setting up automatic question notifications in tmux panes.

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

### context (ctx) - CCI Context Injection

CLI Context Injection (CCI) commands for agents to fetch exactly what they need via CLI instead of loading large static files. The context command is the primary mechanism for agents to self-initialize with the right context for their role and current task.

```bash
# Primary entrypoint - aggregates task, role guidance, and essential inputs
agentic context bootstrap [--role <role-id>]
agentic ctx bootstrap --role build-python

# Get role-specific process.yml and manifest.yml content
agentic context role <role-id> [--format yaml|json]
agentic ctx role planner-build
agentic ctx role build-python --format json

# Get active task from Main-First plan (crawls docs/plans/live/)
agentic context task [--all]
agentic ctx task
agentic ctx task --all

# Get input files for a role with path resolution
agentic context inputs --role <role-id> [--resolve]
agentic ctx inputs --role build-python
agentic ctx inputs --role planner-build --resolve

# Generate thin-client agent file from bootstrap template
agentic context generate-agent <role-id> [--output <file>]
agentic ctx generate-agent build-python
agentic ctx generate-agent planner-build --output agent.md
```

#### Subcommand Details

**bootstrap** - Primary entrypoint for agents to self-initialize

Returns a combined context bundle containing:
- Active Task from the current plan (from docs/plans/live/)
- Role-specific process guidance (process.yml)
- Essential input file references

```bash
# Auto-detect role from context
agentic context bootstrap

# Specify role explicitly
agentic ctx bootstrap --role build-python

# Preview first 50 lines of bootstrap output
agentic ctx bootstrap | head -50
```

**role** - Returns process.yml and manifest.yml content for a role

Retrieves the process guidance and manifest definition from the AgenticGuidance module for the specified role ID.

```bash
# Get role guidance as YAML (default)
agentic ctx role planner-build

# Get role guidance as JSON
agentic ctx role build-python --format json
```

**task** - Crawls docs/plans/live/ to find active task

Searches plan YAML files for the first in_progress task, or the first pending task if none are in progress. Returns task details including ID, description, and guidance.

```bash
# Get current/next task to work on
agentic ctx task

# Show all tasks in the plan
agentic ctx task --all
```

**inputs** - Returns input files for a role with path resolution

Retrieves the inputs.yml file for the specified role and resolves all file paths, layer references, and existence checks. Provides a manifest of relevant project files.

```bash
# Get inputs for a role
agentic ctx inputs --role build-python

# Get inputs with layer expansion
agentic ctx inputs --role planner-build --resolve
```

**generate-agent** - Generate thin-client agent file from bootstrap template

Creates a minimal agent markdown file that uses the CCI bootstrap protocol to self-initialize at runtime rather than embedding static context.

```bash
# Output to stdout
agentic ctx generate-agent build-python

# Save to file
agentic ctx generate-agent planner-build --output agent.md
```

### entrypoint (ep) - Workflow Entrypoints

Discover and execute workflow entrypoints that define starting points for orchestration and planning. Entrypoint files are named with an underscore prefix (e.g., `_plan_build.yml`) and are located in `.claude/entrypoints/` or `modules/AgenticGuidance/entrypoints/`.

```bash
# List all available entrypoints
agentic entrypoint list
agentic ep list

# Show the full contents of an entrypoint file
agentic entrypoint show plan_build
agentic ep show _orchestrate

# Execute entrypoint with variable substitution
agentic entrypoint execute plan_build
agentic ep execute orchestrate --context "Additional context here"

# Execute with custom variables
agentic ep execute plan_build --vars TASK_ID=build_01 --vars BRANCH=feature-auth

# Compile complete context bundle (includes orchestration, inputs, and references)
agentic ep execute plan_build --compile
agentic ep execute orchestrate --compile --context "My context"
```

#### Subcommand Details

**list** - Display all available entrypoints

Searches for entrypoint files in two locations (in priority order):
1. `.claude/entrypoints/` in the current working directory
2. `modules/AgenticGuidance/entrypoints/` in the project root

```bash
# List all entrypoints with their descriptions
agentic ep list

# JSON output for scripting
agentic -j ep list
```

**show** - Show the full contents of an entrypoint file

Retrieves and displays the raw content of an entrypoint file by name. The underscore prefix is optional.

```bash
# Show entrypoint content (underscore optional)
agentic ep show plan_build
agentic ep show _plan_build

# JSON output includes path and type
agentic -j ep show orchestrate
```

**execute** - Execute entrypoint with variable substitution

Reads the entrypoint file, applies variable substitution using `{{VAR}}` syntax, and outputs the processed content. Supports custom variables, context prepending, and full context compilation.

```bash
# Basic execution with variable substitution
agentic ep execute plan_build

# Add custom variables (KEY=VALUE format)
agentic ep execute plan_build --vars TASK_ID=build_01
agentic ep execute orchestrate --vars BRANCH=main --vars PHASE=P1

# Prepend context text to output
agentic ep execute orchestrate --context "Working on feature authentication"

# Compile complete context bundle
agentic ep execute plan_build --compile
```

**Options for `entrypoint execute`:**
- `name` (required): Entrypoint name (with or without underscore prefix)
- `--vars`: Variable substitution pairs in KEY=VALUE format (can be repeated)
- `--context`: Additional context text to prepend to the entrypoint content
- `--compile`, `-c`: Compile complete context bundle including orchestration file, inputs.yml, and all referenced files

**Compile Mode:**

When `--compile` is specified, the command builds a complete context bundle by:
1. Reading and processing the entrypoint file with variable substitution
2. Finding and including the orchestration file (process.mmd) referenced by the entrypoint
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

### session - Claude Code Session Management

Spawn, monitor, and manage Claude Code sessions. Sessions can run in the foreground or background, with full tracking of status, output logs, and process lifecycle.

```bash
# Spawn a new Claude Code session
agentic session spawn --prompt "Implement the feature"
agentic session spawn -p "Fix the bug in auth.py" --max-turns 10

# Spawn in background mode (returns immediately)
agentic session spawn --prompt "Run tests" --background
agentic session spawn -p "Build docs" --background --directory /path/to/project

# List all sessions
agentic session list
agentic session list --active  # Only show running sessions

# Get detailed status of a session
agentic session status <session-id>
agentic session status abc123 --show-output  # Include log contents

# Stop a running session
agentic session stop <session-id>
agentic session stop abc123 --force  # Force kill (SIGKILL)
```

#### Subcommand Details

**spawn** - Start a new Claude Code session

Launches the `claude` CLI with the specified prompt. In foreground mode, waits for completion and displays output. In background mode, returns immediately and logs output to files.

```bash
# Basic foreground session
agentic session spawn --prompt "Analyze the codebase and suggest improvements"

# Background session with turn limit
agentic session spawn -p "Refactor the utils module" --max-turns 5 --background

# Session in a specific directory
agentic session spawn -p "Fix failing tests" --directory /home/code/project
```

**Options for `session spawn`:**
- `--prompt`, `-p` (required): The prompt to send to Claude Code
- `--max-turns`: Maximum number of conversation turns (passed to claude CLI)
- `--background`: Run session in background, return immediately
- `--directory`: Working directory for the session (default: current directory)

**list** - Display all Claude Code sessions

Shows a table of all tracked sessions with their status, PID, start time, and prompt summary.

```bash
# List all sessions
agentic session list

# List only running sessions
agentic session list --active

# JSON output for scripting
agentic -j session list
```

**Options for `session list`:**
- `--active`: Filter to show only running sessions

**stop** - Stop a running session

Sends a termination signal to the session process. By default uses SIGTERM for graceful shutdown.

```bash
# Graceful stop (SIGTERM)
agentic session stop abc123

# Force kill (SIGKILL)
agentic session stop abc123 --force
```

**Options for `session stop`:**
- `session_id` (required): Full or partial session UUID
- `--force`: Use SIGKILL instead of SIGTERM

**status** - Get detailed session information

Displays comprehensive information about a session including status, timing, logs, and output.

```bash
# Get session status
agentic session status abc123

# Include output log contents
agentic session status abc123 --show-output

# JSON output
agentic -j session status abc123
```

**Options for `session status`:**
- `session_id` (required): Full or partial session UUID
- `--show-output`: Display contents of stdout and stderr logs

**Session Storage:**

Sessions are tracked in `~/.agentic/sessions/`:
- Session metadata: `~/.agentic/sessions/<session-id>.json`
- Output logs: `~/.agentic/sessions/logs/<session-id>.stdout.log`
- Error logs: `~/.agentic/sessions/logs/<session-id>.stderr.log`

### loop - Ralph Loop Management

Start, stop, and monitor Ralph Loop executions. A Ralph Loop is an iterative execution cycle where an agent repeatedly processes a prompt until a completion condition is met or max iterations are reached.

```bash
# Start a Ralph Loop with inline prompt
agentic loop start --prompt "Fix all failing tests"
agentic loop start -p "Implement the feature" --max-iterations 20

# Start from entrypoint or file
agentic loop start --entrypoint _orchestrate
agentic loop start --prompt-file task.txt --background

# Stop a running loop
agentic loop stop <loop-id>
agentic loop stop abc123 --force

# Get detailed loop status
agentic loop status <loop-id>

# Show loop execution history
agentic loop history
agentic loop history --active
agentic loop history --status completed --limit 50
```

#### Subcommand Details

**start** - Start a new Ralph Loop

Launches a Ralph Loop that iteratively executes a prompt until completion. Prompts can be provided inline, from a file, or via an entrypoint reference.

```bash
# Basic loop with inline prompt
agentic loop start --prompt "Run tests and fix any failures"

# From entrypoint with custom max iterations
agentic loop start -e _orchestrate -m 20

# From file, background mode, with completion detection
agentic loop start -f prompt.txt -b -c "All done"

# With specific working directory and output file
agentic loop start -p "Build feature" -d /path/to/project -o results.txt
```

**Options for `loop start`:**
- `--prompt`, `-p`: Direct prompt string to execute in the loop
- `--prompt-file`, `-f`: Path to file containing the prompt (supports .txt and .md)
- `--entrypoint`, `-e`: Entrypoint reference to load as the prompt (e.g., `_orchestrate`, `plan_build`)
- `--max-iterations`, `-m`: Maximum number of loop iterations before automatic termination (default: 10)
- `--completion-promise`, `-c`: Text pattern that signals loop completion (e.g., "All tasks complete")
- `--background`, `-b`: Run the loop in the background with output logged to files
- `--directory`, `-d`: Working directory for the loop (default: current directory)
- `--output`, `-o`: Output file path to write loop results

**Prompt Source Priority:**
1. `--entrypoint` - Loads and executes an entrypoint file
2. `--prompt-file` - Reads prompt content from a file
3. `--prompt` - Uses the inline prompt string

**stop** - Stop a running Ralph Loop

Sends a termination signal to the loop process. By default uses SIGTERM for graceful shutdown.

```bash
# Graceful stop (allows current iteration to complete)
agentic loop stop abc123

# Force kill (immediate termination)
agentic loop stop abc123 --force

# Stop using partial ID match
agentic loop stop abc
```

**Options for `loop stop`:**
- `loop_id` (required): Full or partial loop UUID
- `--force`, `-f`: Use SIGKILL instead of SIGTERM for immediate termination

**status** - Display detailed loop information

Shows comprehensive information about a loop including status, iteration progress, timing, and any errors.

```bash
# Get loop status
agentic loop status abc123

# Use partial ID match
agentic loop status abc

# JSON output for scripting
agentic -j loop status abc123
```

**Options for `loop status`:**
- `loop_id` (required): Full or partial loop UUID

**Status Information Displayed:**
- Loop ID and creation timestamp
- Current iteration / max iterations
- Runtime duration
- Status (running, completed, failed, stopped)
- Prompt source (inline, file, or entrypoint)
- Completion promise if set
- Iteration history table

**history** - Show past loop executions

Lists all Ralph Loop executions with their status, sorted by start time (most recent first).

```bash
# Show all recent loops
agentic loop history

# Show only running loops
agentic loop history --active

# Filter by status
agentic loop history --status running
agentic loop history --status completed

# Increase result limit
agentic loop history --limit 50

# JSON output for scripting
agentic -j loop history
```

**Options for `loop history`:**
- `--active`, `-a`: Show only active (running) loops
- `--status`, `-s`: Filter by status (running, completed, failed, stopped)
- `--limit`, `-l`: Maximum number of loops to show (default: 20)

**Loop Storage:**

Loops are tracked in `~/.agentic/loops/`:
- Loop metadata: `~/.agentic/loops/<loop-id>.json`

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
agentic stories find [--project <name>] [--changes <files>]
agentic st find -p my-project

# Manage agent manifests
agentic manifest show <path>
agentic manifest list [<path>]
agentic manifest validate <path>
agentic mf show ./agents/my-agent

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

### template (tpl) - Plan Template Generation

Generate plan YAML files from templates with optional customization:

```bash
# List available template types
agentic template list

# Generate a build plan to stdout
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
| `build` | Implementation plan for building new features with phased tasks |
| `test` | Test plan with unit, integration, and e2e test phases |
| `cleanup` | Audit and cleanup plan for code review and documentation |
| `guidance` | Guidance improvement plan for agent friction analysis |

**Options for `template generate`:**
- `type` (required): Template type (build, test, cleanup, guidance)
- `--output`, `-o`: Output file path (default: stdout)
- `--objective`: Objective description to inject into the template (replaces placeholder text)
- `--phases`: Comma-separated list of `ID:Name` pairs (e.g., `P1:Build,P2:Test`)
- `--success-criteria`: Comma-separated or newline-separated list of success criteria

## Command Categories

| Category | Scope | Commands |
|----------|-------|----------|
| **Global** | Any directory | setup, health, config, prefs, update, rebuild, state, env, session, loop |
| **Project** | Requires .git or .agenticcli.yml | worktree, plan, context, entrypoint, langsmith, inputs, template, stories, manifest |

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
│   │   ├── context.py      # CCI context injection
│   │   ├── entrypoint.py   # Workflow entrypoints
│   │   ├── langsmith.py    # LangSmith integration
│   │   ├── session.py      # Session management
│   │   ├── loop.py         # Ralph Loop management
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
