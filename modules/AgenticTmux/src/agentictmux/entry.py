"""Entry point for agentic-tmux CLI."""

import argparse
import sys


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for agentic-tmux.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="agentic-tmux",
        description="Terminal session management for AgenticEngineering workflows",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Session commands
    session_parser = subparsers.add_parser("session", help="Manage tmux sessions")
    session_subparsers = session_parser.add_subparsers(
        dest="session_command", help="Session operations"
    )

    # session create
    create_parser = session_subparsers.add_parser("create", help="Create a new session")
    create_parser.add_argument("name", help="Session name")
    create_parser.add_argument("--worktree", "-w", help="Link to worktree path")
    create_parser.add_argument("--plan", "-p", help="Link to plan folder")

    # session attach
    attach_parser = session_subparsers.add_parser("attach", help="Attach to session")
    attach_parser.add_argument("name", help="Session name")

    # session list
    session_subparsers.add_parser("list", help="List all sessions")

    # session kill
    kill_parser = session_subparsers.add_parser("kill", help="Kill a session")
    kill_parser.add_argument("name", help="Session name")
    kill_parser.add_argument("--force", "-f", action="store_true", help="Force kill")

    # session status
    status_parser = session_subparsers.add_parser("status", help="Show session status")
    status_parser.add_argument("name", nargs="?", help="Session name (optional)")

    return parser


def main():
    """Main entry point for agentic-tmux CLI."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "session":
        from agentictmux.commands.session import handle

        handle(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
