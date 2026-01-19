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
Global Commands (work from any directory):
  setup           Interactive setup wizard
  health          Check CLI health and dependencies
  prefs           Manage preferences (alias: preferences)
  config (cfg)    Configuration and preferences management
  update          Reinstall AgenticCLI from source
  rebuild         Full rebuild and reinstall
  langsmith (ls)  Query LangSmith traces and projects

Project Commands (require .git or .agenticcli.yml):
  worktree (wt)   Manage git worktrees with planning folder integration
  plan            Manage planning folders and track task status
  langsmith (ls)  Query LangSmith traces and runs
  inputs          Validate and resolve inputs.yml references
  template (tpl)  Generate plan files from templates
  stories (st)    Find user stories for testing
  manifest (mf)   Manage agent manifests
  cicd            CI/CD configuration management

Flags:
  -j, --json      Output in JSON format
  -d, --debug     Enable debug logging to console
  -v, --version   Show version
  -h, --help      Show help

Examples:
  agentic setup
  agentic health
  agentic prefs set editor.theme dark
  agentic wt create feature-auth
  agentic -j plan status
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

    # Environment management
    _add_env_parser(subparsers)

    # LangSmith integration
    _add_langsmith_parser(subparsers)

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
        help="Manage preferences",
        description="Get, set, list, and delete user preferences.",
    )
    prefs_subparsers = prefs_parser.add_subparsers(dest="prefs_command", help="Preference commands")

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
        help="Run health checks",
        description="Check CLI installation, configuration, and dependencies.",
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
        dest="worktree_command", help="Worktree commands"
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
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command", help="Plan commands")

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

    # plan task
    task_parser = plan_subparsers.add_parser(
        "task",
        help="Update task status",
        description="Start or complete tasks in plan files.",
    )
    task_subparsers = task_parser.add_subparsers(dest="task_action", help="Task actions")

    start_parser = task_subparsers.add_parser("start", help="Mark task as in_progress")
    start_parser.add_argument("task_id", help="Task ID (e.g., 01.1)")
    start_parser.add_argument("--plan", "-p", help="Plan path (default: auto-detect)")

    complete_parser = task_subparsers.add_parser("complete", help="Mark task as completed")
    complete_parser.add_argument("task_id", help="Task ID (e.g., 01.1)")
    complete_parser.add_argument("--plan", "-p", help="Plan path (default: auto-detect)")

    # plan archive
    archive_parser = plan_subparsers.add_parser(
        "archive",
        help="Copy plan to completed folder",
        description="Copy the plan folder to docs/plans/completed/.",
    )
    archive_parser.add_argument("path", help="Path to plan folder to archive")

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
    move_subparsers = move_parser.add_subparsers(dest="move_type", help="Move commands")

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


def _add_langsmith_parser(subparsers):
    """Add langsmith subcommand parser."""
    langsmith_parser = subparsers.add_parser(
        "langsmith",
        aliases=["ls"],
        help="Query LangSmith traces and runs",
        description="Query LangSmith traces, runs, and project statistics.",
    )
    langsmith_subparsers = langsmith_parser.add_subparsers(
        dest="langsmith_command", help="LangSmith commands"
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
        help="Project name (defaults to CC_LANGSMITH_PROJECT env var)",
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
        "--recommend", "-r",
        action="store_true",
        help="Include resolution recommendations in output",
    )


def _add_config_parser(subparsers):
    """Add config subcommand parser."""
    config_parser = subparsers.add_parser(
        "config",
        aliases=["cfg"],
        help="Configuration and preferences management",
        description="Manage AgenticCLI configuration stored in ~/.config/agenticcli/.",
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command", help="Config commands")

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
    inputs_subparsers = inputs_parser.add_subparsers(dest="inputs_command", help="Inputs commands")

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
        dest="template_command", help="Template commands"
    )

    # template generate
    generate_parser = template_subparsers.add_parser(
        "generate",
        help="Generate a plan file from template",
        description="Generate a plan file with injected context.",
    )
    generate_parser.add_argument(
        "type", choices=["build", "test", "cleanup", "guidance"], help="Template type"
    )
    generate_parser.add_argument("--output", "-o", help="Output file path (default: stdout)")

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
        dest="stories_command", help="Stories commands"
    )

    # stories find
    find_parser = stories_subparsers.add_parser(
        "find",
        help="Find relevant user stories",
        description="Scan and filter user stories.",
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
        dest="manifest_command", help="Manifest commands"
    )

    # manifest show
    show_parser = manifest_subparsers.add_parser(
        "show",
        help="Display formatted agent manifest",
        description="Show triggers, patterns, and capabilities.",
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
    cicd_subparsers = cicd_parser.add_subparsers(dest="cicd_command", help="CI/CD commands")

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
    state_subparsers = state_parser.add_subparsers(dest="state_command", help="State commands")

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


def _add_env_parser(subparsers):
    """Add env subcommand parser."""
    env_parser = subparsers.add_parser(
        "env",
        help="Manage environment variable injection",
        description="View and manage environment variables for subprocess execution.",
    )
    env_subparsers = env_parser.add_subparsers(dest="env_command", help="Environment commands")

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


def _add_langsmith_parser(subparsers):
    """Add langsmith subcommand parser."""
    langsmith_parser = subparsers.add_parser(
        "langsmith",
        aliases=["ls"],
        help="Query LangSmith traces and projects",
        description="Query and analyze LangSmith traces for agent introspection and debugging.",
    )
    langsmith_subparsers = langsmith_parser.add_subparsers(
        dest="langsmith_command", help="LangSmith commands"
    )

    # langsmith runs
    runs_parser = langsmith_subparsers.add_parser(
        "runs",
        help="List recent runs",
        description="Query and display recent runs with optional filtering.",
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

    # langsmith run
    run_parser = langsmith_subparsers.add_parser(
        "run",
        help="Show details for a specific run",
        description="Display detailed information for a single run by ID.",
    )
    run_parser.add_argument(
        "run_id",
        help="Run ID (UUID) to display",
    )
    run_parser.add_argument(
        "--url", "-u",
        action="store_true",
        help="Generate shareable URL for the run",
    )

    # langsmith projects
    projects_parser = langsmith_subparsers.add_parser(
        "projects",
        help="List all projects",
        description="Display all projects in the LangSmith workspace.",
    )
    projects_parser.add_argument(
        "--detail", "-d",
        action="store_true",
        help="Show additional details (created date, description)",
    )

    # langsmith stats
    stats_parser = langsmith_subparsers.add_parser(
        "stats",
        help="Show project statistics",
        description="Display aggregated usage statistics for a project.",
    )
    stats_parser.add_argument(
        "--project", "-p",
        required=True,
        help="Project name to get stats for",
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
    elif args.command == "env":
        from agenticcli.commands import env

        env.handle(args, ctx=ctx)
    elif args.command in ("langsmith", "ls"):
        from agenticcli.commands import langsmith

        langsmith.handle(args, ctx=ctx)
    else:
        parser.print_help()
        sys.exit(1)
