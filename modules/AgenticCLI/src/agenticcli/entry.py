#!/usr/bin/env python3
"""Entry point for AgenticCLI.

Handles --help and --version flags before importing heavier modules.
All routing is delegated to cli.run_cli().
"""

import sys


def main():
    """Entry point for CLI.

    Handles --version and --help early for fast response.
    All other commands are delegated to run_cli().
    """
    # Handle --version flag early (before any heavy imports)
    if "--version" in sys.argv or "-v" in sys.argv:
        from agenticcli import __version__

        print(f"agentic {__version__}")
        sys.exit(0)

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
