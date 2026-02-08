"""Question management commands.

Handles question queue operations for agent workflows.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Track question IDs already notified via ntfy (dedup across callback invocations)
_ntfy_seen_question_ids: set[str] = set()


def handle(args, ctx=None):
    """Route question subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.question_command == "list":
        cmd_list(args, ctx)
    elif args.question_command == "show":
        cmd_show(args, ctx)
    elif args.question_command == "answer":
        cmd_answer(args, ctx)
    elif args.question_command == "ask":
        cmd_ask(args, ctx)
    elif args.question_command == "defer":
        cmd_defer(args, ctx)
    elif args.question_command == "watch":
        cmd_watch(args, ctx)
    elif args.question_command == "watch-daemon":
        cmd_watch_daemon(args, ctx)
    elif args.question_command == "watch-stop":
        cmd_watch_stop(args, ctx)
    else:
        print("Usage: agentic question <list|show|answer|ask|defer|watch|watch-daemon|watch-stop>", file=sys.stderr)
        sys.exit(1)


def _get_service(plan_path: Path):
    """Get QuestionQueue service instance.

    Args:
        plan_path: Path to plan folder.

    Returns:
        QuestionQueue instance.

    Raises:
        SystemExit: If service cannot be initialized.
    """
    from agenticcli.console import print_error

    try:
        from agenticguidance.services.question import QuestionQueue

        return QuestionQueue(plan_path)
    except ImportError:
        print_error(
            "agenticguidance package not installed. "
            "Install it with: pip install -e modules/AgenticGuidance"
        )
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to initialize QuestionQueue: {e}")
        sys.exit(1)


def _get_plan_path(args, ctx=None) -> Path:
    """Detect or validate plan path from args or context.

    Args:
        args: Parsed arguments with optional --plan flag.
        ctx: Optional CLI context.

    Returns:
        Path to plan folder.

    Raises:
        SystemExit: If plan path cannot be determined or doesn't exist.
    """
    from agenticcli.console import print_error, print_warning

    # Check if --plan flag was provided
    plan_arg = getattr(args, "plan", None)

    if plan_arg:
        plan_path = Path(plan_arg).resolve()
        if not plan_path.exists():
            print_error(f"Plan path does not exist: {plan_path}")
            sys.exit(1)
        if not plan_path.is_dir():
            print_error(f"Plan path is not a directory: {plan_path}")
            sys.exit(1)
        return plan_path

    # Auto-detect from Main-First plan resolver
    try:
        from agenticguidance.services import MainFirstPlanResolver

        resolver = MainFirstPlanResolver()
        plan_info = resolver.resolve_active_plan()

        if plan_info and plan_info.get("plan_folder"):
            plan_path = Path(plan_info["plan_folder"])
            if plan_path.exists():
                return plan_path

    except Exception as e:
        print_warning(f"Failed to auto-detect plan path: {e}")

    # No plan path found
    print_error(
        "Could not determine plan path. "
        "Either use --plan <path> or run from a directory with an active plan."
    )
    print(
        "Hint: Use 'agentic plan init <name>' to create a plan or "
        "'agentic context bootstrap' to see active plans.",
        file=sys.stderr,
    )
    sys.exit(1)


def cmd_list(args, ctx=None):
    """List questions with optional status filter.

    Implements: agentic question list [--plan PATH] [--status STATUS] [--tmux-refresh]
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_header,
        print_json,
    )
    from rich.table import Table

    plan_path = _get_plan_path(args, ctx)
    service = _get_service(plan_path)

    status_filter = getattr(args, "status", "pending")
    tmux_refresh = getattr(args, "tmux_refresh", False)

    # Get questions based on status filter
    if status_filter == "pending":
        questions = service.list_pending_questions()
    elif status_filter == "answered":
        # List answered questions (read from answered/ directory)
        questions = []
        answered_dir = plan_path / "questions" / "answered"
        if answered_dir.exists():
            for yml_file in answered_dir.glob("*_question.yml"):
                try:
                    from agenticguidance.models.question import yaml_to_question

                    yaml_content = yml_file.read_text(encoding="utf-8")
                    question = yaml_to_question(yaml_content)
                    questions.append(question)
                except Exception:
                    continue
        questions.sort(key=lambda q: q.created_at)
    elif status_filter == "deferred":
        # Deferred questions would be in pending/ with status="deferred"
        all_questions = service.list_pending_questions()
        questions = [q for q in all_questions if q.status == "deferred"]
    elif status_filter == "all":
        # All questions from both pending and answered
        questions = service.list_pending_questions()
        answered_dir = plan_path / "questions" / "answered"
        if answered_dir.exists():
            for yml_file in answered_dir.glob("*_question.yml"):
                try:
                    from agenticguidance.models.question import yaml_to_question

                    yaml_content = yml_file.read_text(encoding="utf-8")
                    question = yaml_to_question(yaml_content)
                    questions.append(question)
                except Exception:
                    continue
        questions.sort(key=lambda q: q.created_at)
    else:
        from agenticcli.console import print_error

        print_error(f"Invalid status filter: {status_filter}")
        print("Valid options: pending, answered, deferred, all", file=sys.stderr)
        sys.exit(1)

    # JSON output
    if is_json_output():
        print_json({
            "plan_path": str(plan_path),
            "status_filter": status_filter,
            "count": len(questions),
            "questions": [q.to_dict() for q in questions],
        })
        return

    # Rich table output
    print_header(f"Questions - {status_filter.capitalize()}")

    if not questions:
        console.print(f"[dim]No {status_filter} questions found[/dim]")
        return

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", max_width=20)
    table.add_column("Text", max_width=50)
    table.add_column("Severity")
    table.add_column("Status")
    table.add_column("Asked By")

    for question in questions:
        # Format ID (truncate for display)
        q_id = question.id[:20] if len(question.id) > 20 else question.id

        # Truncate text
        text = question.text[:48] + "..." if len(question.text) > 50 else question.text

        # Format severity with color
        severity = question.severity
        if severity == "blocking":
            severity_str = "[red bold]BLOCKING[/red bold]"
        elif severity == "high":
            severity_str = "[red]HIGH[/red]"
        elif severity == "medium":
            severity_str = "[yellow]MEDIUM[/yellow]"
        else:
            severity_str = "[dim]LOW[/dim]"

        # Format status
        status = question.status
        if status == "pending":
            status_str = "[yellow]pending[/yellow]"
        elif status == "answered":
            status_str = "[green]answered[/green]"
        elif status == "deferred":
            status_str = "[dim]deferred[/dim]"
        else:
            status_str = status

        table.add_row(
            q_id,
            text,
            severity_str,
            status_str,
            question.asked_by,
        )

    console.print(table)
    console.print(f"\n[dim]Showing {len(questions)} questions from {plan_path}[/dim]")

    # Auto-refresh tmux if --tmux-refresh flag is set
    if tmux_refresh:
        _auto_refresh_tmux_notifications(plan_path)


def cmd_show(args, ctx=None):
    """Show detailed information for a specific question.

    Implements: agentic question show <question_id> [--plan PATH]
    """
    from datetime import datetime

    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )
    from rich.panel import Panel

    plan_path = _get_plan_path(args, ctx)
    service = _get_service(plan_path)

    question_id = args.question_id

    # Get question
    question = service.get_question(question_id)

    if not question:
        print_error(f"Question not found: {question_id}")
        sys.exit(1)

    # JSON output
    if is_json_output():
        print_json(question.to_dict())
        return

    # Rich panel output
    print_header(f"Question: {question_id}")

    # Basic info
    console.print(f"\n[bold]ID:[/bold] [cyan]{question.id}[/cyan]")
    console.print(f"[bold]Status:[/bold] {question.status}")

    # Severity with color
    severity = question.severity
    if severity == "blocking":
        severity_str = "[red bold]BLOCKING[/red bold]"
    elif severity == "high":
        severity_str = "[red]HIGH[/red]"
    elif severity == "medium":
        severity_str = "[yellow]MEDIUM[/yellow]"
    else:
        severity_str = "[dim]LOW[/dim]"
    console.print(f"[bold]Severity:[/bold] {severity_str}")

    # Timestamps
    created_dt = datetime.fromtimestamp(question.created_at)
    console.print(f"\n[bold]Created:[/bold] {created_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"[bold]Asked by:[/bold] {question.asked_by}")

    # Question text
    console.print(Panel(question.text, title="Question", border_style="blue"))

    # Context
    if question.context:
        console.print(Panel(question.context, title="Context", border_style="cyan"))

    # Answer info (if answered)
    if question.status == "answered" and question.answer:
        if question.answered_at:
            answered_dt = datetime.fromtimestamp(question.answered_at)
            console.print(f"\n[bold]Answered:[/bold] {answered_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        if question.answered_by:
            console.print(f"[bold]Answered by:[/bold] {question.answered_by}")
        console.print(Panel(question.answer, title="Answer", border_style="green"))

    console.print()


def cmd_answer(args, ctx=None):
    """Answer a pending question.

    Implements: agentic question answer <question_id> --text "answer" [--plan PATH] [--interactive]
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_json,
        print_success,
    )

    plan_path = _get_plan_path(args, ctx)
    service = _get_service(plan_path)

    # Check for interactive mode
    interactive = getattr(args, "interactive", False)

    # If interactive mode and no question_id, list pending questions for selection
    if interactive and not hasattr(args, "question_id"):
        # List pending questions and prompt for selection
        pending = service.list_pending_questions()
        if not pending:
            print_error("No pending questions to answer")
            sys.exit(1)

        console.print("[bold]Pending Questions:[/bold]\n")
        for i, q in enumerate(pending, start=1):
            severity = q.severity.upper()
            # Add [S] indicator if question has suggested answers
            suggest_indicator = " [S]" if q.suggested_answers else ""
            console.print(f"  [{i}] {q.id[:20]} - {q.text[:50]}{'...' if len(q.text) > 50 else ''} [{severity}]{suggest_indicator}")

        console.print()
        try:
            choice = input("Select question number: ").strip()
            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(pending):
                print_error("Invalid selection")
                sys.exit(1)
            question_id = pending[int(choice) - 1].id
        except (EOFError, KeyboardInterrupt):
            print_error("\nCancelled")
            sys.exit(1)
    elif hasattr(args, "question_id"):
        question_id = args.question_id
    else:
        print_error("question_id is required when not using --interactive")
        sys.exit(1)

    # If interactive mode, use the wizard
    if interactive:
        from agenticcli.utils.interactive_answer import (
            DEFER_SENTINEL,
            interactive_answer_wizard,
        )

        # Load the question
        question = service.get_question(question_id)
        if not question:
            print_error(f"Question not found: {question_id}")
            sys.exit(1)

        # Load suggested answers from question if available
        suggested_answers = question.suggested_answers

        # Launch wizard
        answer_text, confidence = interactive_answer_wizard(question, suggested_answers)

        # Handle deferral
        if answer_text == DEFER_SENTINEL:
            # Defer the question
            question.mark_deferred()
            try:
                from agenticguidance.models.question import question_to_yaml

                yaml_content = question_to_yaml(question)
                question_path = plan_path / "questions" / "pending" / f"{question_id}.yml"
                question_path.write_text(yaml_content, encoding="utf-8")
            except Exception as e:
                print_error(f"Failed to defer question: {e}")
                sys.exit(1)

            # Auto-refresh tmux notifications
            _auto_refresh_tmux_notifications(plan_path)

            print_success(f"Question deferred: {question_id}")
            console.print(f"[dim]Status updated in: {plan_path}/questions/pending/[/dim]")
            return

    else:
        # Non-interactive mode: get text from args
        answer_text = getattr(args, "text", None)

        # If --text not provided, prompt for input
        if not answer_text:
            console.print(f"[bold]Answering question:[/bold] {question_id}")
            console.print("[dim]Enter answer (Ctrl+D when done):[/dim]")
            try:
                lines = []
                while True:
                    try:
                        line = input()
                        lines.append(line)
                    except EOFError:
                        break
                answer_text = "\n".join(lines).strip()
            except KeyboardInterrupt:
                print_error("\nAnswer cancelled")
                sys.exit(1)

            if not answer_text:
                print_error("Answer cannot be empty")
                sys.exit(1)

        # Get confidence if provided
        confidence = getattr(args, "confidence", None)

    # Answer the question
    try:
        question, answer = service.answer_question(
            question_id,
            answer_text,
            answered_by="human",
            confidence=confidence,
        )
    except FileNotFoundError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to answer question: {e}")
        sys.exit(1)

    # Auto-refresh tmux notifications after answering
    _auto_refresh_tmux_notifications(plan_path)

    # Output
    if is_json_output():
        print_json({
            "question": question.to_dict(),
            "answer": answer.to_dict(),
        })
    else:
        print_success(f"Question answered: {question_id}")
        console.print(f"[dim]Answer moved to: {plan_path}/questions/answered/[/dim]")


def cmd_ask(args, ctx=None):
    """Create a new question.

    Implements: agentic question ask <text> [--severity LEVEL] [--plan PATH] [--suggest "option"]
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_json,
        print_success,
    )

    plan_path = _get_plan_path(args, ctx)
    service = _get_service(plan_path)

    text = args.text
    severity = getattr(args, "severity", "medium")

    # Get context from args or use default
    context = getattr(args, "context", "Created via CLI")

    # Get suggested answers from args
    suggested_answers = getattr(args, "suggest", None)

    # Create question
    try:
        question = service.create_question(
            text=text,
            context=context,
            severity=severity,
            asked_by="human",
            suggested_answers=suggested_answers,
        )
    except ValueError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to create question: {e}")
        sys.exit(1)

    # Output
    if is_json_output():
        print_json(question.to_dict())
    else:
        print_success(f"Question created: {question.id}")
        console.print(f"[bold]Text:[/bold] {text}")
        console.print(f"[bold]Severity:[/bold] {severity}")
        if suggested_answers:
            console.print(f"[bold]Suggested answers:[/bold] {len(suggested_answers)} options")
        console.print(f"[dim]Question saved to: {plan_path}/questions/pending/[/dim]")


def cmd_defer(args, ctx=None):
    """Defer a pending question.

    Implements: agentic question defer <question_id> [--plan PATH]
    """
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_json,
        print_success,
    )

    plan_path = _get_plan_path(args, ctx)
    service = _get_service(plan_path)

    question_id = args.question_id

    # Get question
    question = service.get_question(question_id)

    if not question:
        print_error(f"Question not found: {question_id}")
        sys.exit(1)

    if question.status != "pending":
        print_error(f"Question is not pending (status: {question.status})")
        sys.exit(1)

    # Defer the question (update status in place)
    question.mark_deferred()

    # Write back to file
    try:
        from agenticguidance.models.question import question_to_yaml

        yaml_content = question_to_yaml(question)
        question_path = plan_path / "questions" / "pending" / f"{question_id}.yml"
        question_path.write_text(yaml_content, encoding="utf-8")
    except Exception as e:
        print_error(f"Failed to defer question: {e}")
        sys.exit(1)

    # Auto-refresh tmux notifications after deferring
    _auto_refresh_tmux_notifications(plan_path)

    # Output
    if is_json_output():
        print_json(question.to_dict())
    else:
        print_success(f"Question deferred: {question_id}")
        console.print(f"[dim]Status updated in: {plan_path}/questions/pending/[/dim]")


def cmd_watch(args, ctx=None):
    """Watch question folders and display updates in foreground.

    Implements: agentic question watch [--plan PATH]
    """
    import signal
    import time

    from agenticcli.console import console, print_error, print_header, print_success

    plan_path = _get_plan_path(args, ctx)

    # Try to import watcher service
    try:
        from agenticcli.services.question_watcher import (
            start_question_watcher,
            stop_question_watcher,
        )
    except ImportError as e:
        print_error(
            "Failed to import question watcher service. "
            "Ensure watchdog is installed: pip install watchdog>=3.0"
        )
        print_error(f"Error: {e}")
        sys.exit(1)

    print_header("Question Watcher - Foreground Mode")
    console.print(f"[bold]Plan:[/bold] {plan_path}")
    console.print(f"[bold]Watching:[/bold] questions/pending/ and questions/answered/")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    # Define callback for question changes
    def on_questions_changed():
        """Reload questions and display notification."""
        try:
            from rich.panel import Panel

            service = _get_service(plan_path)
            pending = service.list_pending_questions()
            blocking = [q for q in pending if q.severity == "blocking"]

            timestamp = time.strftime("%H:%M:%S")
            console.print(
                Panel(
                    f"[yellow]Questions updated at {timestamp}[/yellow]\n"
                    f"Pending: {len(pending)} | Blocking: {len(blocking)}",
                    title="Question Change Detected",
                    border_style="yellow",
                )
            )

            # Auto-refresh tmux if available
            try:
                from agenticcli.utils.tmux import is_in_tmux

                if is_in_tmux():
                    from agenticcli.commands.question import _auto_refresh_tmux_notifications

                    _auto_refresh_tmux_notifications(plan_path)
            except Exception as e:
                console.print(f"[dim]Could not refresh tmux: {e}[/dim]")

            # Send ntfy push notifications for new questions
            try:
                _send_ntfy_if_configured(plan_path, pending)
            except Exception as e:
                logger.debug("ntfy hook error in watcher callback: %s", e)

        except Exception as e:
            console.print(f"[red]Error processing question change: {e}[/red]")

    # Start watcher
    try:
        observer = start_question_watcher(plan_path, on_questions_changed, daemon=False)
        print_success("Watcher started successfully")

        # Set up signal handler for clean shutdown
        def signal_handler(sig, frame):
            console.print("\n[yellow]Stopping watcher...[/yellow]")
            stop_question_watcher(observer)
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Keep running until interrupted
        while observer.is_alive():
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping watcher...[/yellow]")
        stop_question_watcher(observer)
    except Exception as e:
        print_error(f"Watcher error: {e}")
        sys.exit(1)


def cmd_watch_daemon(args, ctx=None):
    """Start question watcher in background as daemon.

    Implements: agentic question watch-daemon [--plan PATH]
    """
    import json
    import subprocess

    from agenticcli.console import print_error, print_success, print_warning

    plan_path = _get_plan_path(args, ctx)

    # Check if state tracking is available
    try:
        from agenticcli.services.state import ProcessStateRegistry
    except ImportError:
        print_error(
            "ProcessStateRegistry not available. "
            "Cannot track daemon state without state service."
        )
        sys.exit(1)

    # Initialize state registry
    registry = ProcessStateRegistry()

    # Check if watcher is already running for this plan
    state_key = f"question_watcher_{plan_path.name}"
    existing_state = registry.get_state(state_key)

    if existing_state and existing_state.get("status") == "running":
        pid = existing_state.get("pid")
        print_warning(f"Question watcher already running for {plan_path.name} (PID: {pid})")
        print("Use 'agentic question watch-stop' to stop the existing watcher first.")
        sys.exit(1)

    # Start watcher in background using subprocess
    try:
        # Use nohup to detach from terminal
        cmd = [
            "nohup",
            "python3",
            "-c",
            f"from pathlib import Path; "
            f"from agenticcli.services.question_watcher import start_question_watcher, stop_question_watcher; "
            f"import time; "
            f"plan_path = Path('{plan_path}'); "
            f"def callback(): pass; "
            f"observer = start_question_watcher(plan_path, callback, daemon=False); "
            f"try:\n"
            f"    while True: time.sleep(1)\n"
            f"except KeyboardInterrupt:\n"
            f"    stop_question_watcher(observer)",
        ]

        # Start process in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Register in state
        registry.register_process(
            state_key,
            process.pid,
            metadata={
                "plan_path": str(plan_path),
                "plan_name": plan_path.name,
                "command": "question watch-daemon",
            },
        )

        print_success(f"Question watcher started in background (PID: {process.pid})")
        print(f"Plan: {plan_path}")
        print("Use 'agentic question watch-stop' to stop the watcher")

    except Exception as e:
        print_error(f"Failed to start daemon: {e}")
        sys.exit(1)


def cmd_watch_stop(args, ctx=None):
    """Stop running question watcher daemon.

    Implements: agentic question watch-stop
    """
    import os
    import signal

    from agenticcli.console import print_error, print_success, print_warning

    # Check if state tracking is available
    try:
        from agenticcli.services.state import ProcessStateRegistry
    except ImportError:
        print_error(
            "ProcessStateRegistry not available. "
            "Cannot stop daemon without state service."
        )
        sys.exit(1)

    # Initialize state registry
    registry = ProcessStateRegistry()

    # List all question watcher processes
    all_states = registry.list_processes()
    watcher_states = [
        (key, state)
        for key, state in all_states.items()
        if key.startswith("question_watcher_")
    ]

    if not watcher_states:
        print_warning("No question watcher daemons are running")
        sys.exit(0)

    # Stop all watchers
    stopped_count = 0
    for state_key, state in watcher_states:
        if state.get("status") != "running":
            continue

        pid = state.get("pid")
        plan_name = state.get("metadata", {}).get("plan_name", "unknown")

        try:
            # Send SIGTERM to process
            os.kill(pid, signal.SIGTERM)
            registry.mark_stopped(state_key)
            print_success(f"Stopped watcher for {plan_name} (PID: {pid})")
            stopped_count += 1
        except ProcessLookupError:
            # Process already dead, just clean up state
            registry.mark_stopped(state_key)
            print_warning(f"Watcher for {plan_name} (PID: {pid}) was not running")
        except PermissionError:
            print_error(f"Permission denied to stop PID {pid} for {plan_name}")
        except Exception as e:
            print_error(f"Failed to stop watcher for {plan_name}: {e}")

    if stopped_count == 0:
        print_warning("No running watchers were stopped")
    else:
        print_success(f"Stopped {stopped_count} watcher(s)")


def _send_ntfy_if_configured(plan_path: Path, questions: list) -> None:
    """Send ntfy push notifications for NEW pending questions.

    Reads ntfy.topic from user preferences. If not configured, returns
    silently (ntfy is opt-in). Deduplicates by tracking previously-seen
    question IDs in the module-level _ntfy_seen_question_ids set.

    Args:
        plan_path: Path to plan folder.
        questions: List of Question objects (pending).
    """
    global _ntfy_seen_question_ids

    try:
        from agenticcli.commands.config import get_config_dir

        config_dir = get_config_dir()
        prefs_file = config_dir / "preferences.yml"

        if not prefs_file.exists():
            return

        import yaml

        prefs = yaml.safe_load(prefs_file.read_text()) or {}
        ntfy_config = prefs.get("ntfy", {})

        topic = ntfy_config.get("topic", "")
        if not topic:
            return

        # Check enabled flag (default True if absent)
        if not ntfy_config.get("enabled", True):
            return

        server = ntfy_config.get("server", "https://ntfy.sh")

        from agenticcli.utils.ntfy import notify_new_question

        for q in questions:
            q_id = q.id if hasattr(q, "id") else q.get("id", "")
            if not q_id or q_id in _ntfy_seen_question_ids:
                continue

            _ntfy_seen_question_ids.add(q_id)
            success = notify_new_question(topic, q, server)
            logger.debug(
                "ntfy notification for %s: %s", q_id, "sent" if success else "failed"
            )

    except Exception as e:
        logger.debug("ntfy notification error: %s", e)


def _auto_refresh_tmux_notifications(plan_path: Path):
    """Helper to auto-refresh tmux notifications after question changes.

    Loads current pending questions and updates the tmux notification pane
    if running in a tmux session.

    Args:
        plan_path: Path to plan folder.
    """
    try:
        from agenticcli.utils.tmux import is_in_tmux

        if not is_in_tmux():
            return

        # Load current pending questions
        service = _get_service(plan_path)
        pending_questions = service.list_pending_questions()

        # Convert to dict format expected by notify function
        questions_data = [q.to_dict() for q in pending_questions]

        # Import notify function
        try:
            from agenticcli.utils.tmux_notify import notify_questions_in_tmux

            # Call notification function
            success = notify_questions_in_tmux(plan_path, questions_data)

            if not success:
                # Notification failed but don't raise error
                import logging
                logger = logging.getLogger(__name__)
                logger.debug("Failed to update tmux notification (not in tmux or error)")

        except ImportError:
            # tmux_notify module not available, skip silently
            pass
        except Exception as e:
            # Log but don't fail on notification errors
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to refresh tmux notifications: {e}")

    except Exception as e:
        # Silently ignore if tmux utils not available or other errors
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Could not auto-refresh tmux notifications: {e}")
