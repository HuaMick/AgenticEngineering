"""Question management commands.

Handles question queue operations for agent workflows.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _get_repo_root() -> Path:
    """Get the git repository root."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def _launch_tui_in_tmux_window(repo_root: Path, refresh: int) -> None:
    """Launch or focus the 'questions' tmux window with the TUI inside."""
    import subprocess

    WINDOW_NAME = "questions"

    # Check if 'questions' window already exists
    result = subprocess.run(
        ["tmux", "list-windows", "-F", "#{window_name}"],
        capture_output=True, text=True,
    )
    existing = result.stdout.strip().split("\n") if result.returncode == 0 else []

    if WINDOW_NAME in existing:
        # Switch to existing window
        subprocess.run(["tmux", "select-window", "-t", WINDOW_NAME])
    else:
        # Create new window running the TUI (with --no-tmux-window to avoid recursion)
        subprocess.run([
            "tmux", "new-window", "-n", WINDOW_NAME,
            f"agentic plan question dashboard --no-tmux-window --refresh {refresh}",
        ])


def cmd_dashboard(args, ctx=None):
    """Launch the interactive Question TUI dashboard.

    If running in tmux, opens a dedicated 'questions' window.
    Otherwise, runs the TUI directly in the current terminal.
    """
    import subprocess
    from agenticcli.tui.question_tui import QuestionTUI

    refresh_seconds = getattr(args, "refresh", 5)
    no_tmux_window = getattr(args, "no_tmux_window", False)
    repo_root = _get_repo_root()

    # Check if we should launch in a tmux window
    try:
        from agenticcli.utils.tmux import is_in_tmux
        in_tmux = is_in_tmux()
    except ImportError:
        in_tmux = False

    if in_tmux and not no_tmux_window:
        _launch_tui_in_tmux_window(repo_root, refresh_seconds)
    else:
        tui = QuestionTUI(repo_root=repo_root, refresh_seconds=refresh_seconds)
        tui.run()


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
    elif args.question_command == "dashboard":
        cmd_dashboard(args, ctx)
    else:
        print("Usage: agentic question <list|show|answer|ask|defer|watch|watch-daemon|watch-stop|dashboard>", file=sys.stderr)
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


def _search_completed_plans(name: str) -> Path | None:
    """Search docs/plans/completed/ for a plan matching *name*.

    Uses the same prefix-match logic as ``find_plan_folder`` uses for
    ``live/``: exact match wins, otherwise the first alphabetical prefix
    match is returned.

    Args:
        name: Folder name or prefix to search for.

    Returns:
        Path to the matching completed plan folder, or ``None``.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    completed_dir = repo_root / "docs" / "plans" / "completed"
    if not completed_dir.exists():
        return None

    search_name = Path(name).name or name
    exact_match = None
    partial_matches: list[Path] = []

    for item in completed_dir.iterdir():
        if item.is_dir():
            if item.name == search_name:
                exact_match = item
                break
            elif item.name.startswith(search_name):
                partial_matches.append(item)

    if exact_match:
        return exact_match
    if partial_matches:
        partial_matches.sort(key=lambda p: p.name)
        return partial_matches[0]
    return None


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
            # Try find_plan_folder (searches live/)
            try:
                from agenticcli.commands.plan import find_plan_folder

                plan_path = find_plan_folder(plan_arg)
            except SystemExit:
                # find_plan_folder exits on not found; search completed/ too
                plan_path = _search_completed_plans(plan_arg)
                if not plan_path:
                    print_error(f"Plan path not found in live or completed: {plan_arg}")
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
        # list_pending_questions() returns all files in pending/ including
        # deferred ones (status="deferred"). Filter to truly pending only.
        questions = [q for q in questions if q.status == "pending"]
        _SEVERITY_ORDER = {"blocking": 0, "high": 1, "medium": 2, "low": 3}
        questions.sort(key=lambda q: (_SEVERITY_ORDER.get(q.severity, 9), q.created_at))
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
        _SEVERITY_ORDER = {"blocking": 0, "high": 1, "medium": 2, "low": 3}
        questions.sort(key=lambda q: (_SEVERITY_ORDER.get(q.severity, 9), q.created_at))
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
    table.add_column("Created", style="dim")

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

        from datetime import datetime

        created_str = datetime.fromtimestamp(question.created_at).strftime("%Y-%m-%d %H:%M")
        table.add_row(
            q_id,
            text,
            severity_str,
            status_str,
            question.asked_by,
            created_str,
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

    # Load companion answer record to get confidence
    answer_confidence = None
    if question.status == "answered":
        try:
            from agenticguidance.models.question import yaml_to_answer

            answer_file = plan_path / "questions" / "answered" / f"{question_id}.yml"
            if answer_file.exists():
                answer_obj = yaml_to_answer(answer_file.read_text(encoding="utf-8"))
                answer_confidence = answer_obj.confidence
        except Exception:
            pass

    # JSON output
    if is_json_output():
        data = question.to_dict()
        data["confidence"] = answer_confidence
        print_json(data)
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
        if answer_confidence:
            console.print(f"[bold]Confidence:[/bold] {answer_confidence}")

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
            asked_by="agent",
            suggested_answers=suggested_answers,
        )
    except ValueError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to create question: {e}")
        sys.exit(1)

    # Auto-notify via ntfy (fire-and-forget, errors logged but not raised)
    try:
        _send_ntfy_if_configured(plan_path, [question])
    except Exception as e:
        logger.debug("Auto-notify on ask failed: %s", e)

    # Notify tmux question window that a new question is waiting
    try:
        from agenticcli.utils.tmux_notify import notify_question_window
        notify_question_window(question_count=1)
    except Exception:
        pass

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

            # Notify tmux question window and send ntfy push notification
            try:
                from agenticcli.utils.tmux_notify import notify_question_window
                notify_question_window(len(pending))
            except Exception as e:
                logger.debug("notify_question_window error: %s", e)

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


def _get_watcher_pidfile(plan_path: Path) -> Path:
    """Get pidfile path for a plan's question watcher daemon.

    Args:
        plan_path: Path to plan folder.

    Returns:
        Path to the pidfile (e.g. ~/.config/agenticguidance/watchers/<plan_name>.pid).
    """
    import os as _os

    xdg_config = _os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        config_dir = Path(xdg_config) / "agenticguidance"
    else:
        config_dir = Path.home() / ".config" / "agenticguidance"
    piddir = config_dir / "watchers"
    piddir.mkdir(parents=True, exist_ok=True)
    return piddir / f"{plan_path.name}.pid"


def cmd_watch_daemon(args, ctx=None):
    """Start question watcher in background as daemon.

    Implements: agentic question watch-daemon [--plan PATH]

    Delegates to _ensure_watch_daemon for the actual daemon start logic.
    """
    from agenticcli.console import print_error, print_success, print_warning

    plan_path = _get_plan_path(args, ctx)

    started, reason = _ensure_watch_daemon(plan_path)

    if started:
        pidfile = _get_watcher_pidfile(plan_path)
        pid = pidfile.read_text().strip() if pidfile.exists() else "unknown"
        print_success(f"Question watcher started in background (PID: {pid})")
        print(f"Plan: {plan_path}")
        print("Use 'agentic question watch-stop' to stop the watcher")

    elif reason == "already_running":
        pidfile = _get_watcher_pidfile(plan_path)
        pid = pidfile.read_text().strip() if pidfile.exists() else "unknown"
        print_warning(f"Question watcher already running for {plan_path.name} (PID: {pid})")
        print("Use 'agentic question watch-stop' to stop the existing watcher first.")
        sys.exit(1)

    else:
        print_error("Failed to start daemon. Check logs for details.")
        sys.exit(1)


def cmd_watch_stop(args, ctx=None):
    """Stop running question watcher daemon.

    Implements: agentic question watch-stop
    """
    import os
    import signal

    from agenticcli.console import print_error, print_success, print_warning

    # Find all watcher pidfiles
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        config_dir = Path(xdg_config) / "agenticguidance"
    else:
        config_dir = Path.home() / ".config" / "agenticguidance"
    piddir = config_dir / "watchers"

    if not piddir.exists():
        print_warning("No question watcher daemons are running")
        sys.exit(0)

    pidfiles = list(piddir.glob("*.pid"))
    if not pidfiles:
        print_warning("No question watcher daemons are running")
        sys.exit(0)

    # Stop all watchers
    stopped_count = 0
    for pidfile in pidfiles:
        plan_name = pidfile.stem

        try:
            pid = int(pidfile.read_text().strip())
        except (ValueError, OSError):
            pidfile.unlink(missing_ok=True)
            continue

        try:
            os.kill(pid, signal.SIGTERM)
            print_success(f"Stopped watcher for {plan_name} (PID: {pid})")
            stopped_count += 1
        except ProcessLookupError:
            print_warning(f"Watcher for {plan_name} (PID: {pid}) was not running")
        except PermissionError:
            print_error(f"Permission denied to stop PID {pid} for {plan_name}")
        except Exception as e:
            print_error(f"Failed to stop watcher for {plan_name}: {e}")
        finally:
            pidfile.unlink(missing_ok=True)

    if stopped_count == 0:
        print_warning("No running watchers were stopped")
    else:
        print_success(f"Stopped {stopped_count} watcher(s)")


def _ensure_watch_daemon(plan_path: Path) -> tuple[bool, str]:
    """Idempotently ensure a question watch-daemon is running for a plan.

    Verifies no existing daemon is alive, and starts a background watcher
    process if needed. Uses PID files for daemon tracking. Safe to call
    from any context — never raises to the caller.

    Args:
        plan_path: Path to plan folder.

    Returns:
        Tuple of (started, reason) where reason is one of:
        "started", "already_running", "error".
    """
    import os
    import subprocess

    try:
        pidfile = _get_watcher_pidfile(plan_path)

        # Check for existing running watcher
        if pidfile.exists():
            try:
                pid = int(pidfile.read_text().strip())
                os.kill(pid, 0)
                # PID is alive — daemon already running
                logger.debug(
                    "_ensure_watch_daemon: already running for %s (PID %d)",
                    plan_path.name,
                    pid,
                )
                return (False, "already_running")
            except (ProcessLookupError, OSError, ValueError):
                # PID is dead or invalid — clean up stale pidfile
                logger.info(
                    "_ensure_watch_daemon: stale pidfile for %s, cleaning up",
                    plan_path.name,
                )
                pidfile.unlink(missing_ok=True)

        # Start daemon via subprocess
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

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Write pidfile for daemon tracking
        pidfile.write_text(str(process.pid))

        logger.info(
            "_ensure_watch_daemon: started for %s (PID %d)",
            plan_path.name,
            process.pid,
        )
        return (True, "started")

    except Exception as e:
        logger.debug("_ensure_watch_daemon: error: %s", e)
        return (False, "error")


def _get_ntfy_config() -> dict | None:
    """Read ntfy configuration from user preferences.

    Returns dict with 'topic' and 'server' keys, or None if ntfy
    is not configured or disabled.
    """
    try:
        from agenticcli.commands.config import get_config_dir

        config_dir = get_config_dir()
        prefs_file = config_dir / "preferences.yml"

        if not prefs_file.exists():
            return None

        import yaml

        prefs = yaml.safe_load(prefs_file.read_text()) or {}
        ntfy_config = prefs.get("ntfy", {})

        topic = ntfy_config.get("topic", "")
        if not topic:
            return None

        if not ntfy_config.get("enabled", True):
            return None

        return {
            "topic": topic,
            "server": ntfy_config.get("server", "https://ntfy.sh"),
        }
    except Exception:
        return None


def _send_ntfy_if_configured(plan_path: Path, questions: list) -> None:
    """Send a simple ntfy push notification for pending questions.

    Notification-only: tells the user questions are waiting. The user
    answers questions in the TUI, not via ntfy replies.

    Args:
        plan_path: Path to plan folder.
        questions: List of Question objects (pending).
    """
    try:
        config = _get_ntfy_config()
        if not config:
            return

        from agenticcli.utils.ntfy import send_ntfy

        pending = [q for q in questions if getattr(q, "status", "") == "pending"]
        if not pending:
            return

        count = len(pending)
        plan_name = plan_path.name if plan_path else "unknown"
        title = f"{count} question{'s' if count > 1 else ''} pending"
        body = f"Plan: {plan_name} — open TUI to answer"

        send_ntfy(
            topic=config["topic"],
            title=title,
            message=body,
            server=config.get("server", "https://ntfy.sh"),
        )
    except Exception as e:
        logger.debug("ntfy notification error: %s", e)


def _auto_refresh_tmux_notifications(plan_path: Path):
    """Notify user about pending questions via tmux status bar."""
    try:
        service = _get_service(plan_path)
        pending = service.list_pending_questions()
        from agenticcli.utils.tmux_notify import notify_question_window
        notify_question_window(question_count=len(pending))
    except Exception:
        pass
