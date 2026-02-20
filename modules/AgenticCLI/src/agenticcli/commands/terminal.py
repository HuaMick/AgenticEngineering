"""Terminal command group for AgenticCLI.

`agentic terminal serve` — starts the AgenticFrontend web terminal server.
"""

import logging
import sys

logger = logging.getLogger(__name__)


def cmd_serve(args, ctx=None):
    """Start the AgenticFrontend web terminal server.

    Args:
        args: Parsed arguments with port, open flags.
        ctx: Optional CLIContext.
    """
    port = getattr(args, "port", 8765)
    open_browser = getattr(args, "open_browser", False)

    try:
        from agenticfrontend.server import main as serve_main
    except ImportError:
        from agenticcli.console import print_error
        print_error(
            "AgenticFrontend is not installed. Install it with:\n"
            "  pip install -e modules/AgenticFrontend"
        )
        sys.exit(1)

    serve_main(port=port, open_browser=open_browser)


def handle(args, ctx=None):
    """Route terminal subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext.
    """
    terminal_command = getattr(args, "terminal_command", None)
    if terminal_command == "serve":
        cmd_serve(args, ctx)
    else:
        print(
            "Usage: agentic session terminal <serve>",
            file=sys.stderr,
        )
        sys.exit(1)
