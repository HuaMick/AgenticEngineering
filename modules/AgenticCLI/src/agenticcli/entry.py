#!/usr/bin/env python3
"""Entry point for AgenticCLI.

Handles --help, --version, and agent names before importing heavier modules.
"""

import sys


def main():
    """Entry point for CLI.

    Handles --version, --help, and agent names early for fast response.
    All other commands are delegated to the Typer-based CLI in cli.py.
    """
    # Handle --version flag early (before any heavy imports)
    # Note: Only handle --version (long form), not -v short form
    # -v is used by subcommands for --verbose and --vars
    if "--version" in sys.argv:
        from agenticcli import __version__

        print(f"agentic {__version__}")
        sys.exit(0)

    # Handle agent names as first positional argument early (before any heavy imports)
    # Pattern: agentic <agent-name> [--bootstrap] [-j]
    if len(sys.argv) >= 2:
        first_arg = sys.argv[1]
        # Skip if it's a flag (starts with -)
        if not first_arg.startswith("-"):
            from agenticcli.commands.agent_help import is_agent_name, get_agent_name, show_agent_help

            if is_agent_name(first_arg):
                agent_name = get_agent_name(first_arg)
                if agent_name:
                    # Check for JSON flag
                    json_output = "-j" in sys.argv or "--json" in sys.argv
                    # Check for bootstrap flag (full context mode)
                    bootstrap = "--bootstrap" in sys.argv
                    show_agent_help(agent_name, json_output=json_output, bootstrap=bootstrap)
                    sys.exit(0)

    # Handle -h alias for --help
    if len(sys.argv) >= 2 and sys.argv[1] == "-h":
        sys.argv[1] = "--help"

    from agenticcli.cli import run_cli
    run_cli()


if __name__ == "__main__":
    main()
