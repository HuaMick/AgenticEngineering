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
Commands:
  worktree    Manage git worktrees with planning folder integration
  plan        Manage planning folders and track task status
  config      Configuration and preferences management
  inputs      Validate and resolve inputs.yml references
  template    Generate plan files from templates
  stories     Find user stories for testing
  manifest    Display agent manifests
  cicd        Audit CI/CD configuration
  update      Reinstall AgenticCLI from source
  rebuild     Full rebuild and reinstall

Examples:
  agentic worktree create feature-auth
  agentic plan status
  agentic config show
  agentic inputs validate path/to/inputs.yml
  agentic template generate build --output plan.yml
""",
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"agentic {__version__}",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format for scripting/automation",
    )

    # Create subparsers for command groups
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Worktree commands
    _add_worktree_parser(subparsers)

    # Plan commands
    _add_plan_parser(subparsers)

    # Config commands
    _add_config_parser(subparsers)

    # Package management commands
    _add_update_parser(subparsers)
    _add_rebuild_parser(subparsers)

    # Feature 06: CLI Extensions
    _add_inputs_parser(subparsers)
    _add_template_parser(subparsers)
    _add_stories_parser(subparsers)
    _add_manifest_parser(subparsers)
    _add_cicd_parser(subparsers)

    return parser


def _add_worktree_parser(subparsers):
    """Add worktree subcommand parser."""
    worktree_parser = subparsers.add_parser(
        "worktree",
        help="Manage git worktrees with planning folder integration",
        description="Create, list, and remove git worktrees with automatic planning folder scaffolding.",
    )
    worktree_subparsers = worktree_parser.add_subparsers(dest="worktree_command", help="Worktree commands")

    # worktree create
    create_parser = worktree_subparsers.add_parser(
        "create",
        help="Create a new worktree with planning folder",
        description="Create a git worktree and scaffold a planning folder.",
    )
    create_parser.add_argument("branch", help="Branch name for the new worktree")
    create_parser.add_argument("--base", "-b", default="main", help="Base branch to create from (default: main)")
    create_parser.add_argument("--no-plan", action="store_true", help="Skip planning folder creation")

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
    remove_parser.add_argument("--force", "-f", action="store_true", help="Force removal without confirmation")

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

    # plan scaffold
    scaffold_parser = plan_subparsers.add_parser(
        "scaffold",
        help="Create planning folder structure",
        description="Create a new planning folder with proper structure and placeholder files.",
    )
    scaffold_parser.add_argument("name", help="Folder name (e.g., 260103AE_feature)")
    scaffold_parser.add_argument("--worktree", "-w", help="Worktree path (default: current directory)")

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


def _add_config_parser(subparsers):
    """Add config subcommand parser."""
    config_parser = subparsers.add_parser(
        "config",
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
        help="Generate plan files from templates",
        description="Generate properly formatted plan files from templates.",
    )
    template_subparsers = template_parser.add_subparsers(dest="template_command", help="Template commands")

    # template generate
    generate_parser = template_subparsers.add_parser(
        "generate",
        help="Generate a plan file from template",
        description="Generate a plan file with injected context.",
    )
    generate_parser.add_argument("type", choices=["build", "test", "cleanup", "guidance"],
                                  help="Template type")
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
        help="Find user stories for testing",
        description="Find and filter user stories from the userstories directory.",
    )
    stories_subparsers = stories_parser.add_subparsers(dest="stories_command", help="Stories commands")

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
        help="Display agent manifests",
        description="Show formatted agent manifest information.",
    )
    manifest_subparsers = manifest_parser.add_subparsers(dest="manifest_command", help="Manifest commands")

    # manifest show
    show_parser = manifest_subparsers.add_parser(
        "show",
        help="Display formatted agent manifest",
        description="Show triggers, patterns, and capabilities.",
    )
    show_parser.add_argument("path", help="Path to agent directory or manifest file")


def _add_cicd_parser(subparsers):
    """Add cicd subcommand parser."""
    cicd_parser = subparsers.add_parser(
        "cicd",
        help="Audit CI/CD configuration",
        description="Audit CI/CD configuration against codebase.",
    )
    cicd_subparsers = cicd_parser.add_subparsers(dest="cicd_command", help="CI/CD commands")

    # cicd audit
    cicd_subparsers.add_parser(
        "audit",
        help="Audit CI/CD configuration",
        description="Compare CI/CD test configuration with actual test directories.",
    )


def run_cli():
    """Main CLI entry point.

    Parses arguments and routes to appropriate command handlers.
    """
    parser = create_parser()
    args = parser.parse_args()

    # Set JSON output mode if requested
    if getattr(args, "json", False):
        from agenticcli.console import set_json_output
        set_json_output(True)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Route to command handlers
    if args.command == "worktree":
        from agenticcli.commands import worktree
        worktree.handle(args)
    elif args.command == "plan":
        from agenticcli.commands import plan
        plan.handle(args)
    elif args.command == "config":
        from agenticcli.commands import config
        config.handle(args)
    elif args.command == "update":
        from agenticcli.commands import package
        package.handle_update(args)
    elif args.command == "rebuild":
        from agenticcli.commands import package
        package.handle_rebuild(args)
    elif args.command == "inputs":
        from agenticcli.commands import inputs
        inputs.handle(args)
    elif args.command == "template":
        from agenticcli.commands import template
        template.handle(args)
    elif args.command == "stories":
        from agenticcli.commands import stories
        stories.handle(args)
    elif args.command == "manifest":
        from agenticcli.commands import manifest
        manifest.handle(args)
    elif args.command == "cicd":
        from agenticcli.commands import cicd
        cicd.handle(args)
    else:
        parser.print_help()
        sys.exit(1)
