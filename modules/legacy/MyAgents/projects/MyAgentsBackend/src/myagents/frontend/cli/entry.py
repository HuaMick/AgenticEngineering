#!/usr/bin/env python3
"""Entry point for MyAgents CLI - detects project root and configuration.

This entry point has been refactored to use HealthCheckWorkflow from Phase 1
of the CLI Workflow Refactoring plan. All detection logic is now delegated
to the workflow layer.
"""

import sys
from pathlib import Path

from myagents.frontend.cli.myagents_cli import run_cli
from myagents.backend.services.agents.workflows.health_check_workflow import HealthCheckWorkflow
from myagents.backend.services.agents.workflows.help_workflow import HelpWorkflow


def main():
    """Entry point for CLI.

    All commands now work from any directory using home directory configuration
    (~/.config/myagents/) as the single source of truth.

    This function uses HealthCheckWorkflow and HelpWorkflow.
    """
    # Initialize workflows
    health_workflow = HealthCheckWorkflow()
    help_workflow = HelpWorkflow()

    # Handle --version flag before project detection
    if "--version" in sys.argv or "-v" in sys.argv:
        print(help_workflow.show_version())
        sys.exit(0)

    # Handle --help flag before project detection
    # Only handle top-level help (no command specified)
    if len(sys.argv) == 2 and sys.argv[1] in ("--help", "-h"):
        # Show main help without needing project detection
        from myagents.frontend.cli import myagents_cli
        myagents_cli.project_dir = Path.cwd()
        myagents_cli.config_path = None
        myagents_cli.main()
        sys.exit(0)

    # Handle no arguments - show help
    if len(sys.argv) == 1:
        from myagents.frontend.cli import myagents_cli
        myagents_cli.project_dir = Path.cwd()
        myagents_cli.config_path = None
        myagents_cli.main()
        sys.exit(0)

    # Parse command from argv (first non-flag argument)
    command = None
    for arg in sys.argv[1:]:
        if not arg.startswith("-"):
            command = arg
            break

    # Check if --help flag is present (for any command)
    is_help = "--help" in sys.argv or "-h" in sys.argv

    # Handle subcommand help (e.g., myagents chat --help) without project detection
    if command and is_help:
        from myagents.frontend.cli import myagents_cli
        myagents_cli.project_dir = Path.cwd()
        myagents_cli.config_path = None
        myagents_cli.main()
        sys.exit(0)

    # Define global commands that work from any directory

    # All commands (including project commands with --help) go through normal routing
    # Only exception is top-level help which was already handled above
    try:
        # Use HealthCheckWorkflow to detect context and route command
        # Pass is_help flag to allow permissive routing for help requests
        context = health_workflow.detect_context(command=command, is_help=is_help)

        # Handle both global and project contexts
        # Global commands return source_root, project commands return project_root
        if context.get("is_global_command"):
            # Global command: use source_root
            project_root = context["source_root"]
            config_path = context["config_path"]
            run_cli(project_root, config_path, is_global=True)
        else:
            # Project command: use project_root
            project_root = context["project_root"]
            config_path = context["config_path"]
            run_cli(project_root, config_path, is_global=False)

    except RuntimeError as e:
        # Check if this is a project detection error but the command might be invalid
        # In that case, try to run with cwd so argparse can show proper error
        error_msg = str(e)
        if "No langgraph.json found" in error_msg:
            # Try running anyway - if command is invalid, argparse will show proper error
            # This prevents masking invalid command errors with project detection errors
            try:
                from myagents.frontend.cli import myagents_cli
                myagents_cli.project_dir = Path.cwd()
                myagents_cli.config_path = None
                myagents_cli.main()
            except SystemExit:
                # argparse handled it (e.g., invalid command)
                raise
            except Exception:
                # Not an argparse error - original project detection error was correct
                print(f"Error: {error_msg}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
