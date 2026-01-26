"""Session management commands for agentic-tmux.

Commands for creating, attaching, listing, and managing tmux sessions
with integration to AgenticGuidance services.
"""

import json
import os
import sys
from datetime import datetime


def handle(args):
    """Route session subcommands.

    Args:
        args: Parsed command arguments.
    """
    if args.session_command == "create":
        cmd_create(args)
    elif args.session_command == "attach":
        cmd_attach(args)
    elif args.session_command == "list":
        cmd_list(args)
    elif args.session_command == "kill":
        cmd_kill(args)
    elif args.session_command == "status":
        cmd_status(args)
    else:
        print("Usage: agentic-tmux session <create|attach|list|kill|status>", file=sys.stderr)
        sys.exit(1)


def _is_json_output(args) -> bool:
    """Check if JSON output is requested."""
    return getattr(args, "json", False)


def _print_json(data: dict):
    """Print data as JSON."""
    print(json.dumps(data, indent=2))


def _print_error(message: str):
    """Print error message."""
    print(f"Error: {message}", file=sys.stderr)


def _print_success(message: str):
    """Print success message."""
    print(f"✓ {message}")


def cmd_create(args):
    """Create a new tmux session.

    Args:
        args: Parsed arguments with name, optional worktree and plan.
    """
    from agenticguidance.services import SessionService

    service = SessionService()
    result = service.create(
        name=args.name,
        worktree=getattr(args, "worktree", None),
        plan_folder=getattr(args, "plan", None),
    )

    if _is_json_output(args):
        _print_json({
            "success": result.success,
            "message": result.message,
            "session": result.session.to_dict() if result.session else None,
        })
    else:
        if result.success:
            _print_success(result.message)
            if result.session:
                print(f"  Name: {result.session.name}")
                if result.session.worktree:
                    print(f"  Worktree: {result.session.worktree}")
                if result.session.plan_folder:
                    print(f"  Plan: {result.session.plan_folder}")
            print(f"\nAttach with: agentic-tmux session attach {args.name}")
        else:
            _print_error(result.message)
            sys.exit(1)


def cmd_attach(args):
    """Attach to an existing tmux session.

    Args:
        args: Parsed arguments with session name.
    """
    from agenticguidance.services import SessionService

    service = SessionService()
    result = service.attach(args.name)

    if _is_json_output(args):
        _print_json({
            "success": result.success,
            "message": result.message,
            "command": result.data.get("command") if result.data else None,
        })
    else:
        if result.success:
            # Execute tmux attach
            if result.data and "command" in result.data:
                cmd = result.data["command"]
                os.execvp(cmd[0], cmd)
        else:
            _print_error(result.message)
            sys.exit(1)


def cmd_list(args):
    """List all tmux sessions.

    Args:
        args: Parsed arguments.
    """
    from agenticguidance.services import SessionService, SessionState

    service = SessionService()
    sessions = service.list()

    if _is_json_output(args):
        _print_json({
            "sessions": [s.to_dict() for s in sessions],
            "count": len(sessions),
        })
        return

    if not sessions:
        print("No sessions found.")
        return

    # Print as table
    print(f"{'Name':<20} {'State':<10} {'Attached':<10} {'Worktree':<30}")
    print("-" * 70)

    for session in sessions:
        state = session.state.value
        if session.state == SessionState.RUNNING:
            state = f"\033[32m{state}\033[0m"  # Green
        elif session.state == SessionState.DEAD:
            state = f"\033[31m{state}\033[0m"  # Red

        attached = "Yes" if session.attached else "No"
        worktree = session.worktree or "-"
        if len(worktree) > 28:
            worktree = "..." + worktree[-25:]

        print(f"{session.name:<20} {state:<19} {attached:<10} {worktree:<30}")

    print(f"\nTotal: {len(sessions)} session(s)")


def cmd_kill(args):
    """Kill a tmux session.

    Args:
        args: Parsed arguments with session name and optional force flag.
    """
    from agenticguidance.services import SessionService

    service = SessionService()
    result = service.kill(args.name, force=getattr(args, "force", False))

    if _is_json_output(args):
        _print_json({
            "success": result.success,
            "message": result.message,
        })
    else:
        if result.success:
            _print_success(result.message)
        else:
            _print_error(result.message)
            sys.exit(1)


def cmd_status(args):
    """Show session status.

    Args:
        args: Parsed arguments with optional session name.
    """
    from agenticguidance.services import SessionService

    service = SessionService()
    name = getattr(args, "name", None)

    if name:
        # Show single session
        session = service.get(name)
        if not session:
            if _is_json_output(args):
                _print_json({"error": f"Session '{name}' not found"})
            else:
                _print_error(f"Session '{name}' not found")
            sys.exit(1)

        if _is_json_output(args):
            _print_json({"session": session.to_dict()})
        else:
            print(f"Session: {session.name}")
            print(f"  State: {session.state.value}")
            print(f"  Attached: {'Yes' if session.attached else 'No'}")
            print(f"  Windows: {session.windows}")
            if session.created_at:
                created = datetime.fromtimestamp(session.created_at)
                print(f"  Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")
            if session.worktree:
                print(f"  Worktree: {session.worktree}")
            if session.plan_folder:
                print(f"  Plan: {session.plan_folder}")
            if session.metadata:
                print("  Metadata:")
                for key, value in session.metadata.items():
                    print(f"    {key}: {value}")
    else:
        # Show summary
        sessions = service.list()
        running = sum(1 for s in sessions if s.state.value == "running")
        attached = sum(1 for s in sessions if s.attached)

        if _is_json_output(args):
            _print_json({
                "total": len(sessions),
                "running": running,
                "attached": attached,
            })
        else:
            print(f"Sessions: {len(sessions)} total, {running} running, {attached} attached")
