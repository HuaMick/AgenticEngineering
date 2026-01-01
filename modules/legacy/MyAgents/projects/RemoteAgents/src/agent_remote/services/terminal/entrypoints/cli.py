"""Terminal service CLI entrypoint.

Provides command-line interface for starting remote terminal sessions.
Invoked by: agent-remote-terminal --relay-url <url>
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

import click

from agent_remote.services.terminal.domains.pty_manager import TerminalDimensions
from agent_remote.services.terminal.workflows.session_workflow import (
    SessionWorkflow,
    SessionWorkflowError,
)


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,  # Log to stderr, not stdout (PTY uses stdout)
    )


@click.command("agent-remote-terminal")
@click.option(
    "--relay-url",
    required=True,
    help="Relay service URL (e.g., http://localhost:8000)",
)
@click.option(
    "--session-id",
    default=None,
    help="Existing session ID to reconnect to (optional)",
)
@click.option(
    "--command",
    default="claude",
    help="Command to run in PTY (default: claude)",
)
@click.option(
    "--rows",
    default=24,
    type=int,
    help="Terminal rows (default: 24)",
)
@click.option(
    "--cols",
    default=80,
    type=int,
    help="Terminal columns (default: 80)",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def main(
    relay_url: str,
    session_id: Optional[str],
    command: str,
    rows: int,
    cols: int,
    verbose: bool,
) -> None:
    """Start a remote terminal session.

    Creates a new session with the relay service, spawns Claude Code CLI
    in a PTY, and bridges I/O between the PTY and relay WebSocket.

    The pairing code is displayed for sharing with the web client.
    Press Ctrl+C to stop the session.
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    # Parse command into list
    command_list = command.split()
    dimensions = TerminalDimensions(rows=rows, cols=cols)

    # Create session workflow
    workflow = SessionWorkflow(
        relay_url=relay_url,
        command=command_list,
        dimensions=dimensions,
    )

    async def run_session() -> int:
        """Run the terminal session."""
        try:
            # Create session with relay
            session_id, pairing_code = await workflow.create_session()

            # Display pairing code prominently
            click.echo("=" * 50, err=True)
            click.echo(f"Session ID: {session_id}", err=True)
            click.echo(f"PAIRING CODE: {pairing_code}", err=True)
            click.echo("Share this code with the web client to connect.", err=True)
            click.echo("=" * 50, err=True)
            click.echo("Press Ctrl+C to stop the session.", err=True)
            click.echo("", err=True)

            # Start PTY session
            await workflow.start()

            # Wait until interrupted or process exits
            while workflow.is_running:
                await asyncio.sleep(0.1)

            return 0

        except SessionWorkflowError as e:
            logger.error(f"Session error: {e}")
            return 1
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            return 1
        finally:
            # Cleanup
            try:
                await workflow.stop()
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")

    def signal_handler(sig, frame):
        """Handle Ctrl+C."""
        click.echo("\nStopping session...", err=True)
        # Will be cleaned up by finally block
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run async session
    try:
        exit_code = asyncio.run(run_session())
        sys.exit(exit_code)
    except SystemExit:
        pass
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
