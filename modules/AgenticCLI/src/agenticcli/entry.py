#!/usr/bin/env python3
"""Entry point for AgenticCLI.

Handles --help, --version, and agent names before importing heavier modules.
Supports both argparse (legacy) and Typer (new) backends.

Set AGENTIC_USE_TYPER=1 to enable the Typer-based CLI.
"""

import os
import sys


def _use_typer() -> bool:
    """Check if Typer backend should be used.

    Returns:
        True if AGENTIC_USE_TYPER environment variable is set to "1".
    """
    return os.environ.get("AGENTIC_USE_TYPER", "0") == "1"


def main():
    """Entry point for CLI.

    Handles --version, --help, and agent names early for fast response.
    All other commands are delegated to the appropriate backend:
    - Typer (new): when AGENTIC_USE_TYPER=1
    - Argparse (legacy): default

    The Typer backend automatically handles global flags (--json, --debug)
    in any position, solving the flag ordering issue.
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

    # Route to appropriate backend
    if _use_typer():
        # Handle -h alias: Typer only recognizes --help, so translate -h for users
        if len(sys.argv) >= 2 and sys.argv[1] == "-h":
            sys.argv[1] = "--help"

        # Handle no-args: Typer shows help via no_args_is_help but exits with code 0
        if len(sys.argv) == 1:
            from agenticcli.cli import run_cli
            run_cli()
            sys.exit(0)

        # Typer backend - handles global flags automatically
        from agenticcli.cli_typer import main_typer
        main_typer()
    else:
        # Legacy argparse backend
        # Handle --help flag at top level early
        if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ("--help", "-h")):
            from agenticcli.cli import run_cli
            run_cli()
            sys.exit(0)

        # All other commands go through normal CLI processing
        from agenticcli.cli import run_cli
        run_cli()


if __name__ == "__main__":
    main()
