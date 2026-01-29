#!/usr/bin/env python3
"""AgenticCLI main command structure.

Defines the argparse parser and command routing.
"""

import argparse
import sys

from agenticcli import __version__


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with all subcommands.

    Returns:
        Configured ArgumentParser with all command groups.
    """
    parser = argparse.ArgumentParser(
        prog="agentic",
        description="AgenticCLI - Command-line interface for AgenticEngineering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
================================================================================
                              COMMAND REFERENCE
================================================================================

GLOBAL COMMANDS (work from any directory)
-----------------------------------------
  setup            Interactive setup wizard for initial configuration
  health           Check CLI health, dependencies, and configuration status
  prefs            Manage user preferences (aliases: preferences, pref)
  config (cfg)     Configuration management (show, init, get, set, list, delete)
  update           Reinstall AgenticCLI from source using uv sync
  rebuild          Full rebuild: clean artifacts, rebuild package, reinstall
  state            Manage process state registry for tracking CLI operations
  session          Manage Claude Code sessions (spawn, list, stop, status)
  loop             Manage Ralph Loops (start, stop, status, history)
  env              Environment variable injection (show, export, run)
  langsmith (ls)   Query LangSmith traces, runs, projects, and statistics

PROJECT COMMANDS (require .git or .agenticcli.yml)
--------------------------------------------------
  worktree (wt)    Manage git worktrees with planning folder integration
  plan             Manage planning folders, tasks, phases, and orchestration
  inputs           Validate and resolve inputs.yml file references
  template (tpl)   Generate plan files from templates (build, test, cleanup)
  stories (st)     Find and filter user stories for testing
  manifest (mf)    Display, list, and validate agent manifests
  cicd             CI/CD configuration management and auditing

CONTEXT COMMANDS - CCI (CLI Context Injection)
----------------------------------------------
  context (ctx)    CCI context retrieval for agents to self-initialize

  Subcommands:
    bootstrap      Get Seed Context: Active Task + Role Guidance + Essential Inputs
    role           Get role-specific process.yml and manifest.yml content
    task           Get active task from Main-First plan (crawls docs/plans/live/)
    inputs         Get CCI manifest of relevant project files for a role
    generate-agent Generate thin-client agent file from bootstrap template

  Examples:
    agentic context bootstrap --role build    # Primary agent initialization
    agentic context role planner-build        # Get role-specific guidance
    agentic context task                      # Get current task from plan
    agentic context inputs --role build       # Get input file manifest
    agentic ctx task --all                    # Show all tasks, not just current

PLAN TASK COMMANDS (task list management)
-----------------------------------------
  agentic plan task list                      # List all tasks with status
  agentic plan task list --status pending     # Filter by status
  agentic plan task current                   # Get current/next task to work on
  agentic plan task status build_01_001       # Show details for specific task
  agentic plan task add "Description" --phase P1  # Add new task
  agentic plan task update 01.1 --status completed  # Update task status
  agentic plan task prefill --preset planner-build  # Load preset task template

PLAN PHASE COMMANDS (phase management)
--------------------------------------
  agentic plan phase list                     # Show all phases with task counts
  agentic plan phase add --id P3 --name "Integration Tests"
  agentic plan phase update P1 --status completed

PLAN ORCHESTRATION COMMANDS (workflow automation)
-------------------------------------------------
  agentic plan orchestration generate         # Generate MMD from plan YAML
  agentic plan orchestration validate         # Check MMD matches plan YAML
  agentic plan orchestration validate --strict  # Fail on any warnings

AGENT BOOTSTRAP (full context with file paths)
----------------------------------------------
  agentic planner-guidance --bootstrap        # Full bootstrap context
  agentic build-python --bootstrap            # Full bootstrap context
  agentic test-runner --bootstrap             # Full bootstrap context
  agentic orchestration-executor --bootstrap  # Full bootstrap context
  agentic <agent-name> --bootstrap            # Works for all 26 agents

ENTRYPOINT COMMANDS (workflow starting points)
----------------------------------------------
  entrypoint (ep)  Discover and execute workflow entrypoints

  Subcommands:
    list           List all available entrypoints from .claude/entrypoints/
    show           Display contents of an entrypoint file by name
    execute        Execute entrypoint with variable substitution

  Examples:
    agentic entrypoint list                   # List available entrypoints
    agentic ep show plan_build                # Show entrypoint contents
    agentic ep execute orchestrate --context "My context"
    agentic ep execute plan_build --compile   # Compile with all dependencies

SESSION COMMANDS (Claude Code session management)
-------------------------------------------------
  agentic session spawn --prompt "Task description"  # Start new session
  agentic session spawn -p "Task" --background       # Run in background
  agentic session list                        # List all sessions
  agentic session list --active               # Show only running sessions
  agentic session status <session_id>         # Get detailed status
  agentic session stop <session_id>           # Stop a running session

LOOP COMMANDS (Ralph Loop management)
-------------------------------------
  agentic loop start --prompt "Task"          # Start a new Ralph Loop
  agentic loop start -e _orchestrate          # Start from entrypoint
  agentic loop start -f prompt.txt --background  # Background with file input
  agentic loop status <loop_id>               # Get loop status and progress
  agentic loop stop <loop_id>                 # Stop a running loop
  agentic loop history                        # Show past loop executions
  agentic loop history --status running       # Filter by status

GLOBAL FLAGS
------------
  -j, --json       Output in JSON format for scripting/automation
  -d, --debug      Enable debug logging to console
  -v, --version    Show version information
  -h, --help       Show help message

QUICK START EXAMPLES
--------------------
  agentic setup                               # First-time setup wizard
  agentic health                              # Verify installation
  agentic wt create feature-auth              # Create new worktree
  agentic plan init feature-auth              # Initialize plan folder
  agentic plan task list                      # See available tasks
  agentic context bootstrap --role build      # Get agent context

For detailed help on any command, use: agentic <command> --help
""",
    )

    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"agentic {__version__}",
    )

    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output in JSON format for scripting/automation",
    )

    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug logging to console",
    )

    # Create subparsers for command groups
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Global commands (work from any directory)
    _add_setup_parser(subparsers)
    _add_preferences_parser(subparsers)
    _add_health_parser(subparsers)

    # Worktree commands
    _add_worktree_parser(subparsers)

    # Plan commands
    _add_plan_parser(subparsers)

    # Config commands
    _add_config_parser(subparsers)

    # Package management commands
    _add_update_parser(subparsers)
    _add_rebuild_parser(subparsers)

    # LangSmith commands
    _add_langsmith_parser(subparsers)

    # Feature 06: CLI Extensions
    _add_inputs_parser(subparsers)
    _add_template_parser(subparsers)
    _add_stories_parser(subparsers)
    _add_manifest_parser(subparsers)
    _add_cicd_parser(subparsers)

    # State management
    _add_state_parser(subparsers)

    # Session management (Claude Code sessions)
    _add_session_parser(subparsers)

    # Loop management (Ralph Loops)
    _add_loop_parser(subparsers)

    # Environment management
    _add_env_parser(subparsers)

    # CCI Context commands
    _add_context_parser(subparsers)

    # Entrypoint commands
    _add_entrypoint_parser(subparsers)

    # Note: LangSmith parser already added at line 101
    # Duplicate call removed during Phase 5 integration

    return parser


def _add_setup_parser(subparsers):
    """Add setup command parser."""
    setup_parser = subparsers.add_parser(
        "setup",
        help="Interactive setup wizard",
        description="Initialize AgenticCLI configuration with guided prompts.",
    )
    setup_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing configuration without prompting",
    )


def _add_preferences_parser(subparsers):
    """Add preferences command parser with aliases."""
    prefs_parser = subparsers.add_parser(
        "preferences",
        aliases=["prefs", "pref"],
        help="Manage user preferences for CLI behavior and defaults",
        description="Get, set, list, and delete user preferences stored in ~/.config/agenticcli/.",
    )
    prefs_subparsers = prefs_parser.add_subparsers(
        dest="prefs_command", help="get, set, list, delete, or clear preferences"
    )

    # prefs get
    get_parser = prefs_subparsers.add_parser(
        "get",
        help="Get a preference value",
        description="Get a specific preference value (supports dot notation).",
    )
    get_parser.add_argument("key", help="Preference key (e.g., editor.theme)")

    # prefs set
    set_parser = prefs_subparsers.add_parser(
        "set",
        help="Set a preference value",
        description="Set a preference value (supports dot notation).",
    )
    set_parser.add_argument("key", help="Preference key")
    set_parser.add_argument("value", help="Value to set")

    # prefs list
    prefs_subparsers.add_parser(
        "list",
        help="List all preferences",
        description="Display all stored preferences.",
    )

    # prefs delete
    delete_parser = prefs_subparsers.add_parser(
        "delete",
        help="Delete a preference",
        description="Delete a specific preference key.",
    )
    delete_parser.add_argument("key", help="Preference key to delete")

    # prefs clear
    clear_parser = prefs_subparsers.add_parser(
        "clear",
        help="Clear all preferences",
        description="Remove all preferences (with confirmation).",
    )
    clear_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Clear without confirmation",
    )


def _add_health_parser(subparsers):
    """Add health command parser."""
    subparsers.add_parser(
        "health",
        help="Verify CLI installation, dependencies, and configuration status",
        description="Run comprehensive health checks on CLI installation, configuration files, "
        "required dependencies, and external service connectivity.",
    )


def _add_worktree_parser(subparsers):
    """Add worktree subcommand parser."""
    worktree_parser = subparsers.add_parser(
        "worktree",
        aliases=["wt"],
        help="Manage git worktrees with planning folder integration",
        description="Create, list, and remove git worktrees with automatic planning folder scaffolding.",
    )
    worktree_subparsers = worktree_parser.add_subparsers(
        dest="worktree_command", help="create, list, remove, or show status of worktrees"
    )

    # worktree create
    create_parser = worktree_subparsers.add_parser(
        "create",
        help="Create a new worktree with planning folder",
        description="Create a git worktree and scaffold a planning folder.",
    )
    create_parser.add_argument("branch", help="Branch name for the new worktree")
    create_parser.add_argument(
        "--base", "-b", default="main", help="Base branch to create from (default: main)"
    )
    create_parser.add_argument(
        "--no-plan", action="store_true", help="Skip planning folder creation"
    )

    # worktree list
    worktree_subparsers.add_parser(
        "list",
        help="List all worktrees with their planning folders",
        description="Display all git worktrees and their associated planning folders.",
    )

    # worktree remove
    remove_parser = worktree_subparsers.add_parser(
        "remove",
        help="Remove a worktree",
        description="Remove a git worktree and optionally archive its planning folder.",
    )
    remove_parser.add_argument("branch", help="Branch name of the worktree to remove")
    remove_parser.add_argument(
        "--force", "-f", action="store_true", help="Force removal without confirmation"
    )

    # worktree status
    worktree_subparsers.add_parser(
        "status",
        help="Show detailed status of current worktree",
        description="Display git status, branch info, and active plans for the current worktree.",
    )


def _add_plan_parser(subparsers):
    """Add plan subcommand parser."""
    plan_parser = subparsers.add_parser(
        "plan",
        help="Manage planning folders and track task status",
        description="Create, validate, and manage planning folders for tracking implementation tasks.",
    )
    plan_subparsers = plan_parser.add_subparsers(
        dest="plan_command", help="init, scaffold, status, validate, task, phase, orchestration, archive, or unarchive plans"
    )

    # plan init - combines worktree creation + plan folder scaffolding
    init_parser = plan_subparsers.add_parser(
        "init",
        help="Initialize worktree and plan folder with proper naming",
        description=(
            "Create worktree if needed and scaffold plan folder with YYMMDDXX_description naming. "
            "Enforces naming convention programmatically, eliminating agent interpretation errors."
        ),
    )
    init_parser.add_argument("branch", help="Branch name for worktree")
    init_parser.add_argument(
        "--description", "-d",
        help="Plan description (used in folder name, defaults to branch name)",
    )
    init_parser.add_argument(
        "--base", "-b",
        default="main",
        help="Base branch to create worktree from (default: main)",
    )

    # plan scaffold
    scaffold_parser = plan_subparsers.add_parser(
        "scaffold",
        help="Create planning folder structure",
        description="Create a new planning folder with proper structure and placeholder files.",
    )
    scaffold_parser.add_argument("name", help="Folder name (e.g., 260103AE_feature)")
    scaffold_parser.add_argument(
        "--worktree", "-w", help="Worktree path (default: current directory)"
    )

    # plan status
    status_parser = plan_subparsers.add_parser(
        "status",
        help="Show plan status and task summary",
        description="Display task completion summary for a planning folder.",
    )
    status_parser.add_argument("path", nargs="?", help="Path to plan folder (default: auto-detect)")

    # plan validate
    validate_parser = plan_subparsers.add_parser(
        "validate",
        help="Validate plan folder structure and YAML",
        description="Check folder structure, file presence, and YAML syntax.",
    )
    validate_parser.add_argument("path", help="Path to plan folder to validate")
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail validation on stub templates (default: warn only)",
    )

    # plan task
    task_parser = plan_subparsers.add_parser(
        "task",
        help="Manage tasks in plan files",
        description="Manage tasks in plan files: list, add, update status, and track progress.",
    )
    task_subparsers = task_parser.add_subparsers(
        dest="task_action", help="list, current, start, complete, add, update, status, or prefill"
    )

    start_parser = task_subparsers.add_parser(
        "start",
        help="Mark task as in_progress",
        description="Set a task's status to in_progress to indicate active work.",
    )
    start_parser.add_argument("task_id", help="Task ID (e.g., 01.1)")
    start_parser.add_argument("--plan", "-p", help="Plan path (default: auto-detect)")
    start_parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Suppress auto-archival even if all tasks are completed",
    )

    complete_parser = task_subparsers.add_parser(
        "complete",
        help="Mark task as completed",
        description="Set a task's status to completed when work is finished.",
    )
    complete_parser.add_argument("task_id", help="Task ID (e.g., 01.1)")
    complete_parser.add_argument("--plan", "-p", help="Plan path (default: auto-detect)")
    complete_parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Suppress auto-archival even if all tasks are completed",
    )

    # task prefill
    prefill_parser = task_subparsers.add_parser(
        "prefill",
        help="Load preset task list from template",
        description="Prefill tasks from a named preset template (e.g., planner-build, builder).",
    )
    prefill_parser.add_argument(
        "--preset", "-t",
        required=True,
        help="Preset name (e.g., planner-build, planner-teach, builder)",
    )
    prefill_parser.add_argument(
        "--plan", "-p",
        help="Plan path (default: auto-detect)",
    )
    prefill_parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show tasks that would be added without making changes",
    )

    # task list
    list_parser = task_subparsers.add_parser(
        "list",
        help="Show all tasks in current plan folder",
        description="Display all tasks with their current status from plan files.",
    )
    list_parser.add_argument(
        "--plan", "-p",
        help="Plan path (default: auto-detect)",
    )
    list_parser.add_argument(
        "--status", "-s",
        choices=["all", "pending", "in_progress", "completed"],
        default="all",
        help="Filter by task status (default: all)",
    )
    list_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full task details including guidance",
    )

    # task status
    status_parser = task_subparsers.add_parser(
        "status",
        help="Show detailed status for a specific task",
        description="Display detailed information about a task by ID.",
    )
    status_parser.add_argument(
        "task_id",
        help="Task ID (e.g., build_01_001, 01.1)",
    )
    status_parser.add_argument(
        "--plan", "-p",
        help="Plan path (default: auto-detect)",
    )

    # task add
    add_parser = task_subparsers.add_parser(
        "add",
        help="Add new task to plan",
        description="Add a new task to the active plan file.",
    )
    add_parser.add_argument(
        "description",
        help="Task description",
    )
    add_parser.add_argument(
        "--plan", "-p",
        help="Plan path (default: auto-detect)",
    )
    add_parser.add_argument(
        "--phase", "-ph",
        help="Phase ID to add task to (e.g., build_01)",
    )
    add_parser.add_argument(
        "--id",
        help="Custom task ID (auto-generated if not specified)",
    )
    add_parser.add_argument(
        "--priority",
        choices=["low", "medium", "high"],
        default="medium",
        help="Task priority (default: medium)",
    )

    # task update
    update_parser = task_subparsers.add_parser(
        "update",
        help="Update task status in plan file",
        description="Mark a task as in_progress, completed, or blocked.",
    )
    update_parser.add_argument(
        "task_id",
        help="Task ID (e.g., 01.1, build_01_001)",
    )
    update_parser.add_argument(
        "--status", "-s",
        required=True,
        choices=["pending", "in_progress", "completed", "blocked"],
        help="New status for the task",
    )
    update_parser.add_argument(
        "--plan", "-p",
        help="Plan path (default: auto-detect)",
    )
    update_parser.add_argument(
        "--note", "-n",
        help="Add a completion note to the task",
    )
    update_parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Suppress auto-archival even if all tasks are completed",
    )

    # task current
    current_parser = task_subparsers.add_parser(
        "current",
        help="Get the current task to work on",
        description="Returns the first in_progress task, or first pending if none in progress.",
    )
    current_parser.add_argument(
        "--plan", "-p",
        help="Plan path (default: auto-detect)",
    )

    # plan archive
    archive_parser = plan_subparsers.add_parser(
        "archive",
        help="Copy plan to completed folder",
        description="Copy the plan folder to docs/plans/completed/.",
    )
    archive_parser.add_argument("path", help="Path to plan folder to archive")

    # plan unarchive
    unarchive_parser = plan_subparsers.add_parser(
        "unarchive",
        help="Move plan from completed back to live",
        description="Move a plan folder from docs/plans/completed/ back to docs/plans/live/. "
        "Useful when a plan was archived prematurely or needs to be resumed.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentic plan unarchive --plan 260103AE_feature
  agentic plan unarchive --plan feature --force  # Partial match, skip confirmation
  agentic plan unarchive -p 260103AE_feature -f
""",
    )
    unarchive_parser.add_argument(
        "--plan", "-p",
        required=True,
        help="Plan folder name (exact match or partial match in completed/)",
    )
    unarchive_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Skip confirmation prompt",
    )

    # plan list
    plan_subparsers.add_parser(
        "list",
        help="List all plans in the repository",
        description="Display all plans in docs/plans/live with status summary.",
    )

    # plan move
    move_parser = plan_subparsers.add_parser(
        "move",
        help="Move completed tasks or archive folder",
        description="Move completed tasks to plan_completed.yml or archive the entire folder.",
    )
    move_subparsers = move_parser.add_subparsers(
        dest="move_type", help="move task, tasks, or folder to completed"
    )

    # plan move task <id>
    move_task_parser = move_subparsers.add_parser(
        "task",
        help="Move a single completed task",
        description="Move a specific completed task to plan_completed.yml.",
    )
    move_task_parser.add_argument("task_id", help="Task ID to move (e.g., 12.7)")
    move_task_parser.add_argument("--plan", "-p", help="Plan path (default: auto-detect)")
    move_task_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )
    move_task_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Move even if there are uncommitted changes",
    )

    # plan move tasks
    move_tasks_parser = move_subparsers.add_parser(
        "tasks",
        help="Move all completed tasks",
        description="Move all completed tasks to plan_completed.yml.",
    )
    move_tasks_parser.add_argument("--plan", "-p", help="Plan path (default: auto-detect)")
    move_tasks_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )
    move_tasks_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Move even if there are uncommitted changes",
    )

    # plan move folder
    move_folder_parser = move_subparsers.add_parser(
        "folder",
        help="Archive the plan folder",
        description="Move the entire plan folder to docs/plans/completed/.",
    )
    move_folder_parser.add_argument("--plan", "-p", help="Plan path (default: auto-detect)")
    move_folder_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be done without making changes",
    )
    move_folder_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Archive even if there are uncommitted changes",
    )

    # plan orchestration
    orchestration_parser = plan_subparsers.add_parser(
        "orchestration",
        help="Manage plan orchestration MMD files",
        description="Generate and validate Mermaid orchestration diagrams that define "
        "the agent workflow for a plan. MMD files encode phase transitions, agent "
        "routing, test-fix loops, and CLI commands agents should execute.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Orchestration MMD files are the source of truth for agent workflows:
  - Define which agents handle each phase
  - Specify test-fix loop patterns
  - Include CLI commands for task updates
  - Enable automated plan execution

Examples:
  agentic plan orchestration generate           # Generate MMD for current plan
  agentic plan orchestration validate           # Check MMD matches plan YAML
  agentic plan orchestration validate --strict  # Fail on any warnings
""",
    )
    orchestration_subparsers = orchestration_parser.add_subparsers(
        dest="orchestration_action", help="generate or validate orchestration MMD files"
    )

    # plan orchestration generate
    orch_generate_parser = orchestration_subparsers.add_parser(
        "generate",
        help="Generate orchestration MMD from plan YAML",
        description="Reads plan_*.yml files and generates a Mermaid flowchart (.mmd) that "
        "defines the complete agent workflow. Output includes phase nodes with agent "
        "assignments, test-fix loops, task status commands, and decision points.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The generated MMD includes:
  - Phase nodes mapped to specific agents (build-python, test-runner, etc.)
  - Test-fix loop patterns with retry logic
  - CLI commands for updating task status
  - Decision nodes for conditional branching

Examples:
  agentic plan orchestration generate                    # Auto-detect plan, create MMD
  agentic plan orchestration generate -p ./my_plan/      # Specify plan path
  agentic plan orchestration generate -o custom.mmd      # Custom output filename
  agentic plan orchestration generate --force            # Overwrite existing MMD
""",
    )
    orch_generate_parser.add_argument(
        "--plan", "-p",
        help="Path to plan folder. Auto-detects from current worktree if not specified.",
    )
    orch_generate_parser.add_argument(
        "--output", "-o",
        help="Output filename. Default: orchestration_<plan_name>.mmd in the plan folder.",
    )
    orch_generate_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing MMD file without prompting",
    )

    # plan orchestration validate
    orch_validate_parser = orchestration_subparsers.add_parser(
        "validate",
        help="Validate orchestration MMD against plan YAML",
        description="Compares orchestration_*.mmd against plan_*.yml files to detect drift. "
        "Checks that all phases exist in the MMD, task IDs are correctly referenced, "
        "and agent routing follows the expected patterns defined in the plan.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Validation checks:
  - All YAML phases have corresponding MMD nodes
  - Task IDs in MMD match those in plan_*.yml files
  - Agent assignments follow naming conventions
  - No orphaned nodes or broken transitions

Examples:
  agentic plan orchestration validate              # Validate current plan
  agentic plan orchestration validate --strict     # Treat warnings as errors
  agentic plan orchestration validate -p ./plan/   # Validate specific plan
""",
    )
    orch_validate_parser.add_argument(
        "--plan", "-p",
        help="Path to plan folder. Auto-detects from current worktree if not specified.",
    )
    orch_validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors and exit with code 1 if any warnings found",
    )

    # plan phase
    phase_parser = plan_subparsers.add_parser(
        "phase",
        help="Manage plan phases",
        description="Add, list, and update phases in plan_build.yml files. "
        "Phases group related tasks and define implementation stages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentic plan phase list                     # Show all phases with task counts
  agentic plan phase add --id P3 --name "Integration Tests"
  agentic plan phase update P1 --status completed
""",
    )
    phase_subparsers = phase_parser.add_subparsers(
        dest="phase_action", help="add, list, or update plan phases"
    )

    # plan phase add
    phase_add_parser = phase_subparsers.add_parser(
        "add",
        help="Add a new phase to plan_build.yml",
        description="Add a new phase with ID, name, and optional description. "
        "The phase is added to the end of the phases list in plan_build.yml.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentic plan phase add --id P1 --name "Initial Setup"
  agentic plan phase add --id build_02 --name "Core Logic" --description "Main implementation work"
  agentic plan phase add --id P3 --name "Testing" -p ./docs/plans/live/my_plan/
""",
    )
    phase_add_parser.add_argument(
        "--id",
        required=True,
        help="Unique phase ID. Convention: P1, P2, P3... or build_01, build_02...",
    )
    phase_add_parser.add_argument(
        "--name",
        required=True,
        help="Human-readable phase name (e.g., 'Initial Setup', 'Core Implementation')",
    )
    phase_add_parser.add_argument(
        "--description",
        help="Optional longer description explaining the phase scope and goals",
    )
    phase_add_parser.add_argument(
        "--plan", "-p",
        help="Path to plan folder. Auto-detects from current worktree if not specified.",
    )

    # plan phase list
    phase_list_parser = phase_subparsers.add_parser(
        "list",
        help="List all phases in the plan",
        description="Display phases from plan_build.yml in a table format showing "
        "ID, name, status, and count of tasks in each phase.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example output:
  ID    Name              Status       Tasks
  P1    Initial Setup     completed    3/3
  P2    Core Logic        in_progress  2/5
  P3    Testing           pending      0/4
""",
    )
    phase_list_parser.add_argument(
        "--plan", "-p",
        help="Path to plan folder. Auto-detects from current worktree if not specified.",
    )

    # plan phase update
    phase_update_parser = phase_subparsers.add_parser(
        "update",
        help="Update a phase in plan_build.yml",
        description="Update the status or name of an existing phase. "
        "At least one of --status or --name must be provided.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentic plan phase update P1 --status completed
  agentic plan phase update P2 --status in_progress --name "Revised Core Logic"
  agentic plan phase update build_01 --name "Setup and Config" -p ./my_plan/
""",
    )
    phase_update_parser.add_argument(
        "phase_id",
        help="ID of the phase to update (e.g., P1, build_01)",
    )
    phase_update_parser.add_argument(
        "--status", "-s",
        choices=["pending", "in_progress", "completed", "blocked"],
        help="New status: pending, in_progress, completed, or blocked",
    )
    phase_update_parser.add_argument(
        "--name", "-n",
        help="New display name for the phase",
    )
    phase_update_parser.add_argument(
        "--plan", "-p",
        help="Path to plan folder. Auto-detects from current worktree if not specified.",
    )

    # plan stories
    stories_parser = plan_subparsers.add_parser(
        "stories",
        help="Manage user stories in plan files",
        description="List and generate tests from user stories defined in plan YAML files. "
        "User stories capture the intended behavior from an end-user perspective and "
        "can be converted to executable test scenarios.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
User stories in plan YAML follow this format:
  user_stories:
    - id: US001
      persona: developer
      action: "run agentic plan task list"
      outcome: "see all tasks with status"

Examples:
  agentic plan stories list                  # Display stories in table format
  agentic plan stories test                  # Generate test scenarios to stdout
  agentic plan stories test -o tests.yml     # Save test scenarios to file
""",
    )
    stories_subparsers = stories_parser.add_subparsers(
        dest="stories_action", help="list or generate tests from user stories"
    )

    # plan stories list
    stories_list_parser = stories_subparsers.add_parser(
        "list",
        help="List user stories from plan YAML",
        description="Display all user stories from the plan in a formatted table. "
        "Shows ID, persona, action, and expected outcome for each story.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example output:
  ID      Persona     Action                        Outcome
  US001   developer   run agentic plan task list    see all tasks with status
  US002   operator    run agentic plan validate     get validation errors

Examples:
  agentic plan stories list                  # List stories from auto-detected plan
  agentic plan stories list -p ./my_plan/    # List stories from specific plan
""",
    )
    stories_list_parser.add_argument(
        "--plan", "-p",
        help="Path to plan folder. Auto-detects from current worktree if not specified.",
    )

    # plan stories test
    stories_test_parser = stories_subparsers.add_parser(
        "test",
        help="Generate blind test scenarios from user stories",
        description="Converts user_stories from plan YAML into executable test cases. "
        "Each story becomes a test with: command to run, expected outcome, and "
        "validation type (exit_code, output_contains, etc.).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Generated test format (YAML):
  tests:
    - id: US001
      command: "agentic plan task list"
      expected:
        validation: output_contains
        pattern: "pending|completed|in_progress"
      story_ref: "As a developer, I want to see all tasks"

Examples:
  agentic plan stories test                       # Print test YAML to stdout
  agentic plan stories test -o blind_tests.yml   # Save to file
  agentic plan stories test --format json        # Output as JSON
  agentic plan stories test -p ./plan/ -o t.yml  # Specify plan and output
""",
    )
    stories_test_parser.add_argument(
        "--plan", "-p",
        help="Path to plan folder. Auto-detects from current worktree if not specified.",
    )
    stories_test_parser.add_argument(
        "--output", "-o",
        help="Output file path. If not specified, prints to stdout.",
    )
    stories_test_parser.add_argument(
        "--format", "-f",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format: yaml (default, human-readable) or json (for programmatic use)",
    )


def _add_langsmith_parser(subparsers):
    """Add langsmith subcommand parser."""
    langsmith_parser = subparsers.add_parser(
        "langsmith",
        aliases=["ls"],
        help="Query LangSmith traces and runs",
        description="Query LangSmith traces, runs, and project statistics.",
    )
    langsmith_subparsers = langsmith_parser.add_subparsers(
        dest="langsmith_command", help="runs, run, projects, stats, friction, or sessions"
    )

    # langsmith runs
    runs_parser = langsmith_subparsers.add_parser(
        "runs",
        help="List recent runs with filtering",
        description="Query and display recent LangSmith runs with optional filters.",
    )
    runs_parser.add_argument(
        "--project", "-p",
        help="Filter by project name",
    )
    runs_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=20,
        help="Maximum number of runs to return (default: 20)",
    )
    runs_parser.add_argument(
        "--type", "-t",
        choices=["llm", "chain", "tool", "retriever"],
        help="Filter by run type",
    )
    runs_parser.add_argument(
        "--error", "-e",
        action="store_true",
        help="Show only runs with errors",
    )

    # langsmith run <run-id>
    run_parser = langsmith_subparsers.add_parser(
        "run",
        help="Show detailed info for a single run",
        description="Display full details for a specific run by ID.",
    )
    run_parser.add_argument(
        "run_id",
        help="The run ID to fetch details for",
    )
    run_parser.add_argument(
        "--url", "-u",
        action="store_true",
        help="Generate a shareable URL for the run",
    )

    # langsmith projects
    projects_parser = langsmith_subparsers.add_parser(
        "projects",
        help="List all projects",
        description="List all LangSmith projects in the workspace.",
    )
    projects_parser.add_argument(
        "--detail", "-d",
        action="store_true",
        help="Show additional project details",
    )

    # langsmith stats
    stats_parser = langsmith_subparsers.add_parser(
        "stats",
        help="Show usage statistics for a project",
        description="Display aggregated statistics for a LangSmith project.",
    )
    stats_parser.add_argument(
        "--project", "-p",
        required=True,
        help="Project name (required)",
    )
    stats_parser.add_argument(
        "--since",
        help="Start date for statistics (YYYY-MM-DD)",
    )
    stats_parser.add_argument(
        "--until",
        help="End date for statistics (YYYY-MM-DD)",
    )

    # langsmith friction
    friction_parser = langsmith_subparsers.add_parser(
        "friction",
        help="Analyze traces for friction patterns",
        description="Detect friction patterns like excessive retries, exploration drift, "
        "missing context, schema violations, and automatable patterns.",
    )
    friction_parser.add_argument(
        "--project", "-p",
        required=True,
        help="Project name (required)",
    )
    friction_parser.add_argument(
        "--sessions",
        type=int,
        help="Number of recent sessions to analyze (overrides --lookback-days)",
    )
    friction_parser.add_argument(
        "--since",
        help="Start date for analysis (ISO format, e.g., 2026-01-01)",
    )
    friction_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=100,
        help="Maximum number of runs to analyze (default: 100)",
    )
    friction_parser.add_argument(
        "--lookback-days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)",
    )
    friction_parser.add_argument(
        "--min-affected",
        type=int,
        default=2,
        help="Only show patterns affecting N+ sessions (default: 2)",
    )
    friction_parser.add_argument(
        "--recommend", "-r",
        action="store_true",
        help="Include resolution recommendations in output",
    )
    friction_parser.add_argument(
        "--validate",
        dest="validate",
        action="store_true",
        default=True,
        help="Validate recommendations against existing guidance (default: True)",
    )
    friction_parser.add_argument(
        "--no-validate",
        dest="validate",
        action="store_false",
        help="Skip validation of recommendations against existing guidance",
    )
    friction_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    # langsmith sessions
    sessions_parser = langsmith_subparsers.add_parser(
        "sessions",
        help="List recent sessions with run counts",
        description="List recent LangSmith sessions grouped by session ID with run counts.",
    )
    sessions_parser.add_argument(
        "--project", "-p",
        required=True,
        help="Project name (required)",
    )
    sessions_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Number of sessions to show (default: 10)",
    )
    sessions_parser.add_argument(
        "--since",
        help="Start date for session listing (ISO format, e.g., 2026-01-01)",
    )
    sessions_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )


def _add_config_parser(subparsers):
    """Add config subcommand parser."""
    config_parser = subparsers.add_parser(
        "config",
        aliases=["cfg"],
        help="Configuration and preferences management",
        description="Manage AgenticCLI configuration stored in ~/.config/agenticcli/.",
    )
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", help="show, init, get, set, list, delete, show-path, set-path, or clear"
    )

    # config show
    config_subparsers.add_parser(
        "show",
        help="Display current configuration",
        description="Show all configuration settings.",
    )

    # config init
    config_subparsers.add_parser(
        "init",
        help="Initialize configuration",
        description="Create configuration directory and default settings.",
    )

    # prefs get
    get_parser = config_subparsers.add_parser(
        "get",
        help="Get a preference value",
        description="Get a specific preference value (supports dot notation).",
    )
    get_parser.add_argument("key", help="Preference key (e.g., worktree.default_base)")

    # prefs set
    set_parser = config_subparsers.add_parser(
        "set",
        help="Set a preference value",
        description="Set a preference value (supports dot notation).",
    )
    set_parser.add_argument("key", help="Preference key")
    set_parser.add_argument("value", help="Value to set")

    # prefs list
    config_subparsers.add_parser(
        "list",
        help="List all preferences",
        description="Display all stored preferences.",
    )

    # prefs delete
    delete_parser = config_subparsers.add_parser(
        "delete",
        help="Delete a preference value",
        description="Delete a specific preference key (supports dot notation).",
    )
    delete_parser.add_argument("key", help="Preference key to delete (e.g., worktree.default_base)")

    # config show-path
    config_subparsers.add_parser(
        "show-path",
        help="Show all config file paths",
        description="Display config file paths with existence status.",
    )

    # config set-path
    set_path_parser = config_subparsers.add_parser(
        "set-path",
        help="Set custom config file path",
        description="Set a custom config file path (persisted in config directory).",
    )
    set_path_parser.add_argument("path", help="Path to custom config file")

    # config clear
    clear_parser = config_subparsers.add_parser(
        "clear",
        help="Clear configuration",
        description="Clear all configuration (requires --force).",
    )
    clear_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Confirm clearing configuration",
    )


def _add_update_parser(subparsers):
    """Add update command parser."""
    subparsers.add_parser(
        "update",
        help="Reinstall AgenticCLI from source",
        description="Run uv sync to reinstall the package from source.",
    )


def _add_rebuild_parser(subparsers):
    """Add rebuild command parser."""
    subparsers.add_parser(
        "rebuild",
        help="Full rebuild and reinstall",
        description="Clean build artifacts, rebuild package, and reinstall.",
    )


def _add_inputs_parser(subparsers):
    """Add inputs subcommand parser."""
    inputs_parser = subparsers.add_parser(
        "inputs",
        help="Validate and resolve inputs.yml references",
        description="Validate input file references and resolve layer paths.",
    )
    inputs_subparsers = inputs_parser.add_subparsers(
        dest="inputs_command", help="validate or resolve input file references"
    )

    # inputs validate
    validate_parser = inputs_subparsers.add_parser(
        "validate",
        help="Validate all input references",
        description="Check if all referenced files and layers exist.",
    )
    validate_parser.add_argument("file", help="Path to inputs.yml file")

    # inputs resolve
    resolve_parser = inputs_subparsers.add_parser(
        "resolve",
        help="Show resolved paths for all inputs",
        description="Display the full input tree with resolved paths.",
    )
    resolve_parser.add_argument("file", help="Path to inputs.yml file")


def _add_template_parser(subparsers):
    """Add template subcommand parser."""
    template_parser = subparsers.add_parser(
        "template",
        aliases=["tpl"],
        help="Generate plan files from templates",
        description="Generate properly formatted plan files from templates.",
    )
    template_subparsers = template_parser.add_subparsers(
        dest="template_command", help="generate plan files or list available templates"
    )

    # template generate
    generate_parser = template_subparsers.add_parser(
        "generate",
        help="Generate a plan file from template",
        description="Generate a plan YAML file from a template with injected context. "
        "Supports build, test, cleanup, and guidance templates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a build plan with objective
  agentic template generate build --objective "Add user authentication"

  # Generate with phases and success criteria
  agentic template generate build \\
    --objective "Implement REST API" \\
    --phases "P1:Setup,P2:Implementation,P3:Testing" \\
    --success-criteria "All endpoints return JSON,Tests pass,Documentation complete"

  # Save to file
  agentic template generate build -o plan_build.yml --objective "Add logging"
""",
    )
    generate_parser.add_argument(
        "type", choices=["build", "test", "cleanup", "guidance"],
        help="Template type: build (implementation tasks), test (test plan), cleanup (post-impl), guidance (process docs)"
    )
    generate_parser.add_argument(
        "--output", "-o",
        help="Output file path. If not specified, outputs to stdout for piping or review."
    )
    generate_parser.add_argument(
        "--objective",
        help="Main objective/goal for the plan. Injected into template header. "
        "Example: 'Implement OAuth2 authentication flow'"
    )
    generate_parser.add_argument(
        "--phases",
        help="Comma-separated ID:Name pairs defining plan phases. "
        "Example: 'P1:Setup,P2:Core,P3:Tests' creates 3 phases with those IDs and names."
    )
    generate_parser.add_argument(
        "--success-criteria",
        help="Comma-separated list of success criteria. "
        "Example: 'Tests pass,Docs updated,No lint errors'"
    )

    # template list
    template_subparsers.add_parser(
        "list",
        help="List available template types",
        description="Show all available template types with descriptions.",
    )


def _add_stories_parser(subparsers):
    """Add stories subcommand parser."""
    stories_parser = subparsers.add_parser(
        "stories",
        aliases=["st"],
        help="Find user stories for testing",
        description="Find and filter user stories from the userstories directory.",
    )
    stories_subparsers = stories_parser.add_subparsers(
        dest="stories_command", help="find user stories matching specified criteria"
    )

    # stories find
    find_parser = stories_subparsers.add_parser(
        "find",
        help="Find user stories matching project or changed files",
        description="Scan userstories directory and filter by project name or changed files.",
    )
    find_parser.add_argument("--project", "-p", help="Filter by project name")
    find_parser.add_argument("--changes", "-c", nargs="*", help="Filter by changed files")


def _add_manifest_parser(subparsers):
    """Add manifest subcommand parser."""
    manifest_parser = subparsers.add_parser(
        "manifest",
        aliases=["mf"],
        help="Manage agent manifests",
        description="Display, list, and validate agent manifests.",
    )
    manifest_subparsers = manifest_parser.add_subparsers(
        dest="manifest_command", help="show, list, or validate agent manifests"
    )

    # manifest show
    show_parser = manifest_subparsers.add_parser(
        "show",
        help="Display formatted agent manifest with triggers and capabilities",
        description="Show agent manifest details including triggers, patterns, capabilities, and metadata.",
    )
    show_parser.add_argument("path", help="Path to agent directory or manifest file")

    # manifest list
    list_parser = manifest_subparsers.add_parser(
        "list",
        help="List all manifests in the project",
        description="Find and list all agent manifests.",
    )
    list_parser.add_argument(
        "path",
        nargs="?",
        help="Base path to search (defaults to current directory)",
    )

    # manifest validate
    validate_parser = manifest_subparsers.add_parser(
        "validate",
        help="Validate a manifest file",
        description="Check manifest for required fields and correct structure.",
    )
    validate_parser.add_argument("path", help="Path to agent directory or manifest file")


def _add_cicd_parser(subparsers):
    """Add cicd subcommand parser."""
    cicd_parser = subparsers.add_parser(
        "cicd",
        help="CI/CD configuration management",
        description="Manage and audit CI/CD configurations.",
    )
    cicd_subparsers = cicd_parser.add_subparsers(
        dest="cicd_command", help="audit, list, or show CI/CD configurations"
    )

    # cicd audit
    cicd_subparsers.add_parser(
        "audit",
        help="Audit CI/CD configuration",
        description="Compare CI/CD test configuration with actual test directories.",
    )

    # cicd list
    cicd_subparsers.add_parser(
        "list",
        help="List all CI/CD configurations",
        description="Find and list all CI/CD configuration files in the project.",
    )

    # cicd show
    show_parser = cicd_subparsers.add_parser(
        "show",
        help="Show CI/CD configuration details",
        description="Display details of a specific CI/CD configuration.",
    )
    show_parser.add_argument(
        "path",
        nargs="?",
        help="Path to CI/CD configuration file (auto-detects if not specified)",
    )


def _add_state_parser(subparsers):
    """Add state subcommand parser."""
    state_parser = subparsers.add_parser(
        "state",
        help="Manage process state registry",
        description="View and manage the process state registry for tracking active CLI operations.",
    )
    state_subparsers = state_parser.add_subparsers(
        dest="state_command", help="list, show, clear, or cleanup process entries"
    )

    # state list
    list_parser = state_subparsers.add_parser(
        "list",
        help="List registered processes",
        description="Display all processes in the state registry.",
    )
    list_parser.add_argument(
        "--active",
        "-a",
        action="store_true",
        help="Show only active (running) processes",
    )

    # state show
    show_parser = state_subparsers.add_parser(
        "show",
        help="Show details of a specific process",
        description="Display detailed information about a registered process.",
    )
    show_parser.add_argument("pid", type=int, help="Process ID to show")

    # state clear
    clear_parser = state_subparsers.add_parser(
        "clear",
        help="Clear entries from the registry",
        description="Remove completed/failed/stale entries from the registry.",
    )
    clear_parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Clear all entries (including running)",
    )
    clear_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force clear (required with --all)",
    )

    # state cleanup
    state_subparsers.add_parser(
        "cleanup",
        help="Clean up stale processes",
        description="Mark processes that are no longer running as stale.",
    )


def _add_session_parser(subparsers):
    """Add session subcommand parser for Claude Code session management."""
    session_parser = subparsers.add_parser(
        "session",
        help="Manage Claude Code sessions",
        description="Spawn, list, stop, and monitor Claude Code sessions programmatically. "
        "Sessions are individual Claude Code invocations that can run interactively or in the background.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentic session spawn -p "Implement the login feature"
  agentic session spawn -p "Fix bug #123" --background --max-turns 5
  agentic session list --active
  agentic session status abc123
  agentic session stop abc123

Claude Code Integration:
  Sessions wrap the 'claude' CLI command, providing:
  - Background execution with output logging
  - Session tracking via state registry
  - Graceful termination support
""",
    )
    session_subparsers = session_parser.add_subparsers(
        dest="session_command", help="spawn, list, stop, or check status of sessions"
    )

    # session spawn
    spawn_parser = session_subparsers.add_parser(
        "spawn",
        help="Spawn a new Claude Code session with a prompt",
        description="Spawn a new Claude Code session with a prompt. "
        "The session invokes the 'claude' CLI with the specified prompt and options. "
        "Sessions can run in the foreground (default) or background mode.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple foreground session
  agentic session spawn -p "Explain this codebase"

  # Background session with turn limit
  agentic session spawn -p "Run all tests and fix failures" -b -m 10

  # Session in specific directory
  agentic session spawn -p "Review code" -d /path/to/project
""",
    )
    spawn_parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="The prompt to send to Claude Code. This is the task description or question.",
    )
    spawn_parser.add_argument(
        "--max-turns", "-m",
        type=int,
        help="Maximum number of agentic turns (tool uses) for the session. "
        "Limits how many actions Claude can take. Useful for bounded tasks.",
    )
    spawn_parser.add_argument(
        "--background", "-b",
        action="store_true",
        help="Run the session in the background. Output is logged to files. "
        "Use 'agentic session status' to check progress.",
    )
    spawn_parser.add_argument(
        "--directory", "-d",
        help="Working directory for the Claude Code session. "
        "Defaults to current directory. Claude will have access to files in this directory.",
    )

    # session list
    list_parser = session_subparsers.add_parser(
        "list",
        help="Display all Claude Code sessions with their status",
        description="Display all Claude Code sessions with their status. "
        "Shows session ID, status (running/completed/failed), start time, and prompt preview.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all sessions
  agentic session list

  # List only running sessions
  agentic session list --active
""",
    )
    list_parser.add_argument(
        "--active", "-a",
        action="store_true",
        help="Show only active (running) sessions. Filters out completed and failed sessions.",
    )

    # session stop
    stop_parser = session_subparsers.add_parser(
        "stop",
        help="Stop a running Claude Code session",
        description="Stop a running Claude Code session. "
        "Sends SIGTERM by default for graceful shutdown. Use --force for immediate termination.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Graceful stop
  agentic session stop abc123

  # Force kill (immediate)
  agentic session stop abc123 --force
""",
    )
    stop_parser.add_argument(
        "session_id",
        help="Session ID (or partial ID prefix) to stop. Partial IDs are matched against registered sessions.",
    )
    stop_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force kill the session using SIGKILL instead of SIGTERM. "
        "Use when graceful shutdown is not responding.",
    )

    # session status
    status_parser = session_subparsers.add_parser(
        "status",
        help="Get detailed status of a Claude Code session",
        description="Get detailed status of a Claude Code session. "
        "Shows session metadata, runtime duration, and optionally the captured output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get status
  agentic session status abc123

  # Get status with output logs
  agentic session status abc123 --show-output
""",
    )
    status_parser.add_argument(
        "session_id",
        help="Session ID (or partial ID prefix) to check. Partial IDs are matched against registered sessions.",
    )
    status_parser.add_argument(
        "--show-output", "-o",
        action="store_true",
        help="Display the captured stdout and stderr from the session log files.",
    )


def _add_loop_parser(subparsers):
    """Add loop subcommand parser for Ralph Loop management."""
    loop_parser = subparsers.add_parser(
        "loop",
        help="Manage Ralph Loops (iterative agent execution cycles)",
        description=(
            "Start, stop, and monitor Ralph Loop executions. "
            "A Ralph Loop is an iterative execution cycle where an agent repeatedly processes "
            "a prompt until a completion condition is met or max iterations are reached. "
            "Ralph Loops enable autonomous task completion with built-in termination controls."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ralph Loop Concepts:
  - Loops execute a prompt repeatedly until completion or max iterations
  - Completion is detected via --completion-promise text matching
  - Loops can run in foreground (interactive) or background mode
  - Each iteration spawns a Claude Code session with the prompt

Prompt Sources (mutually exclusive):
  --prompt, -p        Direct inline prompt string
  --prompt-file, -f   Read prompt from a file
  --entrypoint, -e    Use an entrypoint file (e.g., _orchestrate)

Examples:
  agentic loop start -p "Fix all failing tests"
  agentic loop start -e _orchestrate --max-iterations 20
  agentic loop start -f task.txt --background --completion-promise "All tasks complete"
  agentic loop status abc123
  agentic loop stop abc123
  agentic loop history --status running
""",
    )
    loop_subparsers = loop_parser.add_subparsers(
        dest="loop_command", help="start, stop, status, or history of Ralph Loops"
    )

    # loop start
    start_parser = loop_subparsers.add_parser(
        "start",
        help="Start a Ralph Loop with a prompt from various sources",
        description=(
            "Start a Ralph Loop with a prompt from various sources. "
            "A Ralph Loop iteratively executes the prompt until the completion promise is found "
            "in the output or max iterations are reached. Prompts can be provided inline, "
            "from a file, or via an entrypoint reference."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Prompt Source Priority:
  1. --entrypoint (-e) - Loads and executes an entrypoint file
  2. --prompt-file (-f) - Reads prompt content from a file
  3. --prompt (-p) - Uses the inline prompt string

Completion Detection:
  The loop monitors output for the --completion-promise text.
  When found, the loop terminates gracefully. Use phrases like:
  - "All tasks complete"
  - "No more work to do"
  - "LOOP_COMPLETE"

Examples:
  # Simple inline prompt
  agentic loop start -p "Run tests and fix any failures"

  # From entrypoint with custom max iterations
  agentic loop start -e _orchestrate -m 20

  # From file, background mode, with completion detection
  agentic loop start -f prompt.txt -b -c "All done"

  # With specific working directory
  agentic loop start -p "Build feature" -d /path/to/project
""",
    )
    start_parser.add_argument(
        "--prompt", "-p",
        help="Direct prompt string to execute in the loop. "
        "The prompt is sent to Claude Code on each iteration.",
    )
    start_parser.add_argument(
        "--prompt-file", "-f",
        help="Path to file containing the prompt. The file contents are read and used "
        "as the prompt for each loop iteration. Supports .txt and .md files.",
    )
    start_parser.add_argument(
        "--entrypoint", "-e",
        help="Entrypoint reference to load as the prompt (e.g., _orchestrate, plan_build). "
        "Entrypoints are workflow templates from .claude/entrypoints/ that can include "
        "variable substitution and context compilation.",
    )
    start_parser.add_argument(
        "--max-iterations", "-m",
        type=int,
        default=10,
        help="Maximum number of loop iterations before automatic termination (default: 10). "
        "Each iteration runs the full prompt through Claude Code.",
    )
    start_parser.add_argument(
        "--completion-promise", "-c",
        help="Text pattern that signals loop completion. When this text appears in the "
        "Claude Code output, the loop terminates successfully. "
        "Example: 'All tasks complete' or 'DONE'.",
    )
    start_parser.add_argument(
        "--background", "-b",
        action="store_true",
        help="Run the loop in the background. Output is logged to files. "
        "Use 'agentic loop status' to monitor progress.",
    )
    start_parser.add_argument(
        "--directory", "-d",
        help="Working directory for the loop (default: current directory). "
        "Claude Code will operate within this directory for file access.",
    )
    start_parser.add_argument(
        "--output", "-o",
        help="Output file path to write loop results. Captures the final state "
        "and iteration summary.",
    )

    # loop stop
    stop_parser = loop_subparsers.add_parser(
        "stop",
        help="Stop a running loop",
        description=(
            "Stop a running Ralph Loop. By default, sends SIGTERM for graceful termination. "
            "The loop will complete its current iteration before stopping. "
            "Use --force for immediate termination via SIGKILL."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Graceful stop (allows current iteration to complete)
  agentic loop stop abc123

  # Force kill (immediate termination)
  agentic loop stop abc123 --force

  # Stop using partial ID match
  agentic loop stop abc
""",
    )
    stop_parser.add_argument(
        "loop_id",
        help="Loop ID (or partial ID prefix) to stop. Partial IDs are matched against "
        "registered loops. Use 'agentic loop history' to find loop IDs.",
    )
    stop_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force kill the loop immediately using SIGKILL instead of SIGTERM. "
        "Use when graceful shutdown is not responding.",
    )

    # loop status
    status_parser = loop_subparsers.add_parser(
        "status",
        help="Display detailed status of a loop including iteration progress",
        description=(
            "Display detailed status of a specific loop including iteration progress. "
            "Shows current iteration number, total iterations allowed, runtime duration, "
            "completion status, and any captured output or errors."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Status Information:
  - Loop ID and creation timestamp
  - Current iteration / max iterations
  - Runtime duration
  - Status (running, completed, failed, stopped)
  - Prompt source (inline, file, or entrypoint)
  - Completion promise if set

Examples:
  agentic loop status abc123
  agentic loop status abc  # Partial ID match
""",
    )
    status_parser.add_argument(
        "loop_id",
        help="Loop ID (or partial ID prefix) to check. Use 'agentic loop history' "
        "to list all loop IDs.",
    )

    # loop history
    history_parser = loop_subparsers.add_parser(
        "history",
        help="Show past loop executions",
        description=(
            "Show past Ralph Loop executions with their status. "
            "Lists loops in reverse chronological order with ID, status, iteration count, "
            "start time, and prompt preview."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show all recent loops
  agentic loop history

  # Show only running loops
  agentic loop history --active
  agentic loop history -s running

  # Show completed loops with higher limit
  agentic loop history --status completed --limit 50
""",
    )
    history_parser.add_argument(
        "--active", "-a",
        action="store_true",
        help="Show only active (running) loops. Equivalent to --status running.",
    )
    history_parser.add_argument(
        "--status", "-s",
        choices=["running", "completed", "failed", "stopped"],
        help="Filter loops by status. Options: running, completed, failed, stopped.",
    )
    history_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=20,
        help="Maximum number of loops to show (default: 20). "
        "Loops are listed in reverse chronological order.",
    )


def _add_env_parser(subparsers):
    """Add env subcommand parser."""
    env_parser = subparsers.add_parser(
        "env",
        help="Manage environment variable injection",
        description="View and manage environment variables for subprocess execution.",
    )
    env_subparsers = env_parser.add_subparsers(
        dest="env_command", help="show, export, or run commands with environment variables"
    )

    # env show
    env_subparsers.add_parser(
        "show",
        help="Show environment configuration",
        description="Display all configured environment variables with sources (secrets masked).",
    )

    # env export
    export_parser = env_subparsers.add_parser(
        "export",
        help="Export environment variables",
        description="Export environment variables in shell or JSON format.",
    )
    export_parser.add_argument(
        "--format",
        "-f",
        choices=["shell", "json"],
        default="shell",
        help="Output format (default: shell)",
    )

    # env run
    run_parser = env_subparsers.add_parser(
        "run",
        help="Run command with injected environment",
        description="Execute a command with configured environment variables.",
    )
    run_parser.add_argument(
        "cmd_args",
        nargs="+",
        metavar="COMMAND",
        help="Command and arguments to run",
    )


# Note: Duplicate _add_langsmith_parser removed during Phase 5 integration.
# The complete implementation is at line 498 with friction subcommand.


def _add_context_parser(subparsers):
    """Add context subcommand parser for CCI (CLI Context Injection) context retrieval."""
    context_parser = subparsers.add_parser(
        "context",
        aliases=["ctx"],
        help="CCI context retrieval for agents",
        description=(
            "CLI Context Injection (CCI) commands for agents to fetch exactly what they need "
            "via CLI instead of loading large static files."
        ),
    )
    context_subparsers = context_parser.add_subparsers(
        dest="context_command", help="bootstrap, role, task, inputs, or generate-agent"
    )

    # context bootstrap
    bootstrap_parser = context_subparsers.add_parser(
        "bootstrap",
        help="Primary entrypoint for agents to self-initialize. Aggregates: Active Task + Role Guidance + Essential Inputs.",
        description=(
            "Primary entrypoint for agents to self-initialize. "
            "Aggregates: Active Task + Role Guidance + Essential Inputs. "
            "Returns a combined context bundle containing the current task from the plan, "
            "role-specific process guidance (process.yml), and essential input file references."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Bootstrap with specific role
  agentic ctx bootstrap --role build-python

  # Preview first 50 lines of bootstrap output
  agentic ctx bootstrap | head -50

  # Bootstrap for planner role
  agentic ctx bootstrap --role planner-build

  # Auto-detect role from context
  agentic context bootstrap
""",
    )
    bootstrap_parser.add_argument(
        "--role", "-r",
        help="Role ID (e.g., planner-build, build-python). Auto-detected if not specified.",
    )

    # context role
    role_parser = context_subparsers.add_parser(
        "role",
        help="Returns process.yml and manifest.yml content for a specific role.",
        description=(
            "Returns process.yml and manifest.yml content for a specific role. "
            "Retrieves the process guidance and manifest definition from the AgenticGuidance "
            "module for the specified role ID (e.g., planner-build, build-python)."
        ),
    )
    role_parser.add_argument(
        "role_id",
        help="Role ID (e.g., planner-build, build-python)",
    )
    role_parser.add_argument(
        "--format", "-f",
        choices=["yaml", "json"],
        default="yaml",
        help="Output format (default: yaml)",
    )

    # context task
    task_parser = context_subparsers.add_parser(
        "task",
        help="Crawls the main worktree's docs/plans/live/ to find active task.",
        description=(
            "Crawls the main worktree's docs/plans/live/ to find active task. "
            "Searches plan YAML files for the first in_progress task, or the first pending "
            "task if none are in progress. Returns task details including ID, description, "
            "and guidance for the current branch."
        ),
    )
    task_parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Show all tasks instead of just current task",
    )

    # context inputs
    inputs_parser = context_subparsers.add_parser(
        "inputs",
        help="Returns input files for a role with path resolution.",
        description=(
            "Returns input files for a role with path resolution. "
            "Retrieves the inputs.yml file for the specified role and resolves all file paths, "
            "layer references, and existence checks. Provides a manifest of relevant project files "
            "that the agent should have access to."
        ),
    )
    inputs_parser.add_argument(
        "--role", "-r",
        required=True,
        help="Role ID (e.g., planner-build, build-python)",
    )
    inputs_parser.add_argument(
        "--resolve",
        action="store_true",
        help="Expand layer references",
    )

    # context generate-agent
    generate_parser = context_subparsers.add_parser(
        "generate-agent",
        help="Generate thin-client agent file from bootstrap template.",
        description=(
            "Generate thin-client agent file from bootstrap template. "
            "Creates a minimal agent markdown file that uses the CCI bootstrap protocol "
            "to self-initialize at runtime rather than embedding static context."
        ),
    )
    generate_parser.add_argument(
        "role_id",
        help="Role ID (e.g., planner-build, build-python)",
    )
    generate_parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)",
    )


def _add_entrypoint_parser(subparsers):
    """Add entrypoint subcommand parser for workflow entrypoints."""
    entrypoint_parser = subparsers.add_parser(
        "entrypoint",
        aliases=["ep"],
        help="Discover and execute workflow entrypoints",
        description="List, show, and execute entrypoint files that define workflow starting points.",
    )
    entrypoint_subparsers = entrypoint_parser.add_subparsers(
        dest="entrypoint_command", help="list, show, or execute workflow entrypoints"
    )

    # entrypoint list
    entrypoint_subparsers.add_parser(
        "list",
        help="Display all entrypoints from .claude/entrypoints/ and modules/AgenticGuidance/entrypoints/",
        description="Display all entrypoints from .claude/entrypoints/ and modules/AgenticGuidance/entrypoints/.",
    )

    # entrypoint show
    show_parser = entrypoint_subparsers.add_parser(
        "show",
        help="Show the full contents of an entrypoint file by name",
        description="Show the full contents of an entrypoint file by name.",
    )
    show_parser.add_argument(
        "name",
        help="Entrypoint name (with or without underscore prefix, e.g., 'plan_build' or '_plan_build')",
    )

    # entrypoint execute
    execute_parser = entrypoint_subparsers.add_parser(
        "execute",
        help="Read entrypoint, apply variable substitution, and output",
        description=(
            "Read entrypoint, apply variable substitution, and output. "
            "Use --compile to bundle orchestration, inputs.yml, and all referenced files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Execute with compile flag to bundle all dependencies
  agentic ep execute _plan_build --compile

  # Execute with variable substitution
  agentic ep execute orchestrate --vars PLAN_PATH=/path/to/plan

  # Multiple variables
  agentic ep execute _plan_build --vars PLAN_PATH=./docs/plans/live/my_plan --vars WORKTREE=feature-branch

  # Add context prefix
  agentic ep execute _orchestrate --context "Focus on test failures first"
""",
    )
    execute_parser.add_argument(
        "name",
        help="Entrypoint name (with or without underscore prefix)",
    )
    execute_parser.add_argument(
        "--vars", "-v",
        action="append",
        metavar="KEY=VALUE",
        help="Variable substitution (can be used multiple times). Supports: PLAN_PATH, WORKTREE, and custom vars.",
    )
    execute_parser.add_argument(
        "--context",
        help="Additional context text to prepend to the entrypoint content",
    )
    execute_parser.add_argument(
        "--compile", "-c",
        action="store_true",
        help="Compile complete context bundle including orchestration, inputs.yml, and all referenced files",
    )


# Command categories for project requirement checking
# Includes aliases for each command
GLOBAL_COMMANDS = {
    "setup",
    "config",
    "cfg",  # alias for config
    "preferences",
    "prefs",
    "pref",
    "update",
    "rebuild",
    "health",
    "state",
    "session",
    "loop",
    "env",
    "langsmith",
    "ls",  # alias for langsmith
}
PROJECT_COMMANDS = {
    "worktree",
    "wt",  # alias for worktree
    "plan",
    "langsmith",
    "ls",  # alias for langsmith
    "inputs",
    "template",
    "tpl",  # alias for template
    "stories",
    "st",  # alias for stories
    "manifest",
    "mf",  # alias for manifest
    "cicd",
    "context",
    "ctx",  # alias for context
    "entrypoint",
    "ep",  # alias for entrypoint
}


def run_cli():
    """Main CLI entry point.

    Parses arguments and routes to appropriate command handlers.
    Global commands work from any directory.
    Project commands require a .git or .agenticcli.yml in the directory tree.
    """
    parser = create_parser()
    args = parser.parse_args()

    # Set JSON output mode if requested
    json_output = getattr(args, "json", False)
    if json_output:
        from agenticcli.console import set_json_output

        set_json_output(True)

    # Create context for command handlers
    from agenticcli.context import CLIContext

    debug_mode = getattr(args, "debug", False)
    ctx = CLIContext.discover(json_output=json_output)

    # Initialize logging
    from agenticcli.logging import setup_logging

    logger = setup_logging(
        log_dir=ctx.logs_dir,
        level="DEBUG" if debug_mode else None,
        debug_to_console=debug_mode,
    )

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Log command invocation
    logger.info(f"Command: {args.command}")

    # Check project requirement for project-specific commands
    if args.command in PROJECT_COMMANDS:
        ctx.require_project(args.command)

    # Display stability banner for non-stable commands
    from agenticcli.console import print_stability_banner

    print_stability_banner(args.command)

    # Route to command handlers - ctx passed as optional param for gradual migration
    # Global commands (work from any directory)
    if args.command == "setup":
        from agenticcli.commands import setup

        setup.handle(args, ctx=ctx)
    elif args.command in ("preferences", "prefs", "pref"):
        from agenticcli.commands import preferences

        preferences.handle(args, ctx=ctx)
    elif args.command == "health":
        from agenticcli.commands import health

        health.handle(args, ctx=ctx)
    elif args.command in ("worktree", "wt"):
        from agenticcli.commands import worktree

        worktree.handle(args, ctx=ctx)
    elif args.command == "plan":
        from agenticcli.commands import plan

        plan.handle(args, ctx=ctx)
    elif args.command in ("langsmith", "ls"):
        from agenticcli.commands import langsmith

        langsmith.handle(args, ctx=ctx)
    elif args.command in ("config", "cfg"):
        from agenticcli.commands import config

        config.handle(args, ctx=ctx)
    elif args.command == "update":
        from agenticcli.commands import package

        package.handle_update(args, ctx=ctx)
    elif args.command == "rebuild":
        from agenticcli.commands import package

        package.handle_rebuild(args, ctx=ctx)
    elif args.command == "inputs":
        from agenticcli.commands import inputs

        inputs.handle(args, ctx=ctx)
    elif args.command in ("template", "tpl"):
        from agenticcli.commands import template

        template.handle(args, ctx=ctx)
    elif args.command in ("stories", "st"):
        from agenticcli.commands import stories

        stories.handle(args, ctx=ctx)
    elif args.command in ("manifest", "mf"):
        from agenticcli.commands import manifest

        manifest.handle(args, ctx=ctx)
    elif args.command == "cicd":
        from agenticcli.commands import cicd

        cicd.handle(args, ctx=ctx)
    elif args.command == "state":
        from agenticcli.commands import state

        state.handle(args, ctx=ctx)
    elif args.command == "session":
        from agenticcli.commands import session

        session.handle(args, ctx=ctx)
    elif args.command == "loop":
        from agenticcli.commands import loop

        loop.handle(args, ctx=ctx)
    elif args.command == "env":
        from agenticcli.commands import env

        env.handle(args, ctx=ctx)
    elif args.command in ("langsmith", "ls"):
        from agenticcli.commands import langsmith

        langsmith.handle(args, ctx=ctx)
    elif args.command in ("context", "ctx"):
        from agenticcli.commands import context

        context.handle(args, ctx=ctx)
    elif args.command in ("entrypoint", "ep"):
        from agenticcli.commands import entrypoint

        entrypoint.handle(args, ctx=ctx)
    else:
        parser.print_help()
        sys.exit(1)
