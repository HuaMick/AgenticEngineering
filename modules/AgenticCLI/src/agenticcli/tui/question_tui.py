"""QuestionTUI - navigable terminal UI for answering agent questions.

This module provides a persistent, interactive terminal UI for managing
questions raised by agent workflows. It runs inside a dedicated tmux
window named 'questions', giving the user maximum screen space on small
Termux/Android screens while keeping the agent's main pane uncluttered.

Rich was chosen over Textual because Textual requires a proper TTY with
full terminal control sequences. In some Termux + tmux configurations
the PTY handling is limited, causing Textual apps to render incorrectly
or fail to accept keyboard input. Rich works over any terminal that
supports ANSI escape codes, including Termux on Android and SSH sessions,
and it is already a project dependency so no additional install is needed.

The rendering pattern uses tty.setcbreak() for single-keypress navigation
(arrow keys, j/k, Tab, Enter, d, m, s, q) combined with Rich Console for
output (console.clear() + console.print()). select.select() on stdin with
a configurable timeout provides auto-refresh of the questions list. This
avoids Rich Live entirely because Live and stdin input cannot coexist in
the same thread. The alternative of a background refresh thread with a
main-thread input loop introduces race conditions on some terminals.

When the user answers a question (Enter) or requests more info (m), the
terminal temporarily switches from cbreak mode back to line mode so that
input() can capture freeform text. After submission the terminal returns
to cbreak mode and the cursor auto-advances to the next pending question.
Suggested answers, when present, are navigated with arrow keys without
leaving cbreak mode. All terminal settings are restored in a finally
block so Ctrl-C never leaves the terminal in a broken state.
"""

import select
import sys
import time
import termios
import tty
import yaml
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


# Severity sort order (lower = higher priority)
_SEVERITY_ORDER = {
    "blocking": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}

# Normal row severity styles
_SEVERITY_STYLE = {
    "blocking": "[red bold]",
    "high": "[red]",
    "medium": "[yellow]",
    "low": "[dim]",
}
_SEVERITY_STYLE_CLOSE = {
    "blocking": "[/red bold]",
    "high": "[/red]",
    "medium": "[/yellow]",
    "low": "[/dim]",
}

# Cursor row severity styles (inverted)
_SEVERITY_CURSOR_STYLE = {
    "blocking": "[red bold reverse]",
    "high": "[red reverse]",
    "medium": "[yellow reverse]",
    "low": "[reverse]",
}
_SEVERITY_CURSOR_STYLE_CLOSE = {
    "blocking": "[/red bold reverse]",
    "high": "[/red reverse]",
    "medium": "[/yellow reverse]",
    "low": "[/reverse]",
}

# Abbreviated severity labels for narrow terminals
_SEVERITY_ABBREV = {
    "blocking": "BLK",
    "high": "HI",
    "medium": "MED",
    "low": "LO",
}


class QuestionTUI:
    """Navigable terminal UI for pending agent questions.

    Uses tty.setcbreak() for single-keypress input and Rich Console for
    rendering. Auto-refreshes every refresh_seconds between keypresses.

    Usage:
        tui = QuestionTUI(repo_root=Path("/path/to/repo"))
        tui.run()  # blocks until user quits with q or Ctrl-C
    """

    def __init__(self, repo_root: Path, refresh_seconds: int = 5):
        """Initialise the TUI.

        Args:
            repo_root: Root of the git repository (used to find pending questions).
            refresh_seconds: How often to auto-refresh the question list.
        """
        self.console = Console()
        self.repo_root = repo_root
        self.refresh_seconds = refresh_seconds
        self.cursor = 0
        self.questions: list[dict] = []  # list of {plan_name, question_data, plan_path}
        self._old_settings = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main loop in cbreak mode. Blocks until user quits with q or Ctrl-C."""
        self._old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            while True:
                self._refresh_questions()
                self._render()
                key = self._read_key_with_timeout(self.refresh_seconds)

                if key is None:
                    # Timeout - auto-refresh on next iteration
                    continue
                elif key == "q" or key == "\x03":
                    # q or Ctrl-C
                    break
                elif key in ("\x1b[A", "k"):
                    # Up arrow or vim k
                    self.cursor = max(0, self.cursor - 1)
                elif key in ("\x1b[B", "j"):
                    # Down arrow or vim j
                    self.cursor = min(len(self.questions) - 1, self.cursor + 1)
                elif key == "\t":
                    # Tab - cycle forward, wrapping
                    self.cursor = (self.cursor + 1) % max(1, len(self.questions))
                elif key == "\r" or key == "\n":
                    # Enter - answer selected question
                    self._handle_answer()
                elif key == "d":
                    self._handle_defer()
                elif key == "m":
                    self._handle_more_info()
                elif key == "s":
                    self._handle_show()
        except KeyboardInterrupt:
            # Ctrl-C can also arrive as a signal rather than \x03
            pass
        finally:
            if self._old_settings is not None:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
            # Print a blank line so the prompt appears cleanly after exit
            print()

    # ------------------------------------------------------------------
    # Data refresh
    # ------------------------------------------------------------------

    def _get_repo_db_path(self) -> Path:
        """Derive the repo-local TinyDB path (.agentic/epics.db under repo root)."""
        current = self.repo_root
        while current != current.parent:
            if (current / ".git").exists():
                return current / ".agentic" / "epics.db"
            current = current.parent
        return Path.home() / ".agentic" / "epics.db"

    def _get_live_epic_dirs(self) -> list[Path]:
        """Return live epic folder paths from TinyDB, sorted by name."""
        try:
            from agenticguidance.services.epic_repository import EpicRepository
            repo = EpicRepository(db_path=self._get_repo_db_path(), auto_bootstrap=False)
            metas = repo.list_epics(status="live")
            dirs = [m.epic_folder for m in metas if m.epic_folder.is_dir()]
            return sorted(dirs, key=lambda p: p.name)
        except Exception:
            return []

    def _refresh_questions(self) -> None:
        """Query TinyDB for live epics, scan their questions/pending/*.yml files,
        and populate self.questions.

        Reads each YAML file, builds a list of question dicts, sorts by severity
        (blocking > high > medium > low) then by created_at timestamp.
        """
        found: list[dict] = []

        for plan_dir in self._get_live_epic_dirs():
            pending_dir = plan_dir / "questions" / "pending"
            if not pending_dir.exists():
                continue

            for question_file in pending_dir.glob("*.yml"):
                try:
                    with open(question_file, encoding="utf-8") as fh:
                        question_data = yaml.safe_load(fh)

                    if not question_data or not isinstance(question_data, dict):
                        continue

                    # Only show pending questions (not deferred)
                    status = question_data.get("status", "pending")
                    if status not in ("pending",):
                        continue

                    found.append({
                        "plan_name": plan_dir.name,
                        "plan_path": plan_dir,
                        "question_data": question_data,
                        "file_path": question_file,
                    })
                except Exception:
                    # Skip files that can't be read or parsed
                    continue

        # Sort: severity priority first, then created_at ascending
        found.sort(
            key=lambda q: (
                _SEVERITY_ORDER.get(
                    q["question_data"].get("severity", "low"), 99
                ),
                q["question_data"].get("created_at", 0),
            )
        )

        # Preserve cursor position by matching question IDs when possible
        if self.questions and found:
            old_id = None
            if 0 <= self.cursor < len(self.questions):
                old_id = self.questions[self.cursor]["question_data"].get("id")
            if old_id:
                for i, q in enumerate(found):
                    if q["question_data"].get("id") == old_id:
                        self.cursor = i
                        break
                else:
                    # Previously selected question no longer present
                    self.cursor = min(self.cursor, max(0, len(found) - 1))
            else:
                self.cursor = min(self.cursor, max(0, len(found) - 1))
        else:
            self.cursor = 0

        self.questions = found

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _build_questions_table(self, width: int = 80) -> Table:
        """Build and return a Rich Table for the current questions list.

        When there are no pending questions, returns a single-row table with
        a "No pending questions" message spanning the question column. When
        questions are present, each row represents one pending question with
        severity-based style markup applied.

        Args:
            width: Terminal width used to size columns. Defaults to 80.

        Returns:
            A Rich Table ready to be printed to the console.
        """
        # --- Determine column widths based on terminal width ---
        if width < 65:
            plan_width = 10
            sev_width = 3
            show_full_severity = False
        elif width <= 80:
            plan_width = 14
            sev_width = 8
            show_full_severity = True
        else:
            plan_width = 16
            sev_width = 8
            show_full_severity = True

        # Question column gets remaining space (minus separators/padding)
        # Table borders take ~3 chars per column separator in Rich
        q_width = max(20, width - plan_width - sev_width - 10)

        table = Table(
            show_header=True,
            header_style="bold",
            show_edge=False,
            pad_edge=True,
            box=None,
        )
        table.add_column("Plan", width=plan_width, no_wrap=True)
        table.add_column("Severity", width=sev_width, no_wrap=True)
        table.add_column("Question", width=q_width, no_wrap=True)

        if not self.questions:
            table.add_row("", "", "[dim]No pending questions[/dim]")
            return table

        for i, entry in enumerate(self.questions):
            q = entry["question_data"]
            plan_name = entry["plan_name"]
            severity = q.get("severity", "low").lower()
            question_text = q.get("text", q.get("question", "")).replace("\n", " ")
            is_cursor = i == self.cursor

            # Truncate plan name
            if len(plan_name) > plan_width - 2:
                plan_display = plan_name[: plan_width - 2] + ".."
            else:
                plan_display = plan_name

            # Severity label
            if show_full_severity:
                sev_label = severity.upper()
            else:
                sev_label = _SEVERITY_ABBREV.get(severity, severity.upper())

            # Truncate question text
            if len(question_text) > q_width - 2:
                q_display = question_text[: q_width - 5] + "..."
            else:
                q_display = question_text

            # Apply styles
            if is_cursor:
                open_tag = _SEVERITY_CURSOR_STYLE.get(severity, "[reverse]")
                close_tag = _SEVERITY_CURSOR_STYLE_CLOSE.get(severity, "[/reverse]")
            else:
                open_tag = _SEVERITY_STYLE.get(severity, "")
                close_tag = _SEVERITY_STYLE_CLOSE.get(severity, "")

            table.add_row(
                f"{open_tag}{plan_display}{close_tag}",
                f"{open_tag}{sev_label}{close_tag}",
                f"{open_tag}{q_display}{close_tag}",
            )

        return table

    def _render(self) -> None:
        """Clear screen and print question table with cursor highlight."""
        self.console.clear()
        width = self.console.width or 80

        # --- Header line ---
        count = len(self.questions)
        header_left = f"PENDING QUESTIONS ({count})"
        header_right = f"Auto-refresh: {self.refresh_seconds}s"
        padding = max(1, width - len(header_left) - len(header_right))
        self.console.print(
            f"[bold]{header_left}[/bold]" + " " * padding + f"[dim]{header_right}[/dim]"
        )
        self.console.print()

        if not self.questions:
            self._render_empty_state()
            return

        table = self._build_questions_table(width=width)
        self.console.print(table)

        # --- Status bar ---
        divider = "[dim]" + "-" * min(width, 60) + "[/dim]"
        self.console.print()
        self.console.print(divider)

        if width < 65:
            status_bar = "[dim]↑↓/Tab nav  Enter ans  m info  d defer  q quit[/dim]"
        else:
            status_bar = (
                "[dim]↑↓/Tab navigate  Enter answer  m more info  d defer  s show  q quit[/dim]"
            )
        self.console.print(status_bar)

    def _render_empty_state(self) -> None:
        """Render the empty state when there are no pending questions."""
        self.console.print("[green]No pending questions. All clear.[/green]")
        self.console.print()
        self.console.print("[dim]Waiting for new questions...[/dim]")
        self.console.print("[dim]Press q to quit.[/dim]")

    # ------------------------------------------------------------------
    # Key input
    # ------------------------------------------------------------------

    def _read_key_with_timeout(self, timeout: float) -> "str | None":
        """Read a keypress with timeout. Returns None on timeout.

        Uses select.select() for the wait. Escape sequences for arrow keys
        (ESC [ A/B) are read in full as a single logical key string.

        Args:
            timeout: Seconds to wait before returning None.

        Returns:
            Key string (possibly multi-char for arrow keys), or None on timeout.
        """
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            return None

        ch = sys.stdin.read(1)

        if ch == "\x1b":
            # Possible escape sequence - read the bracket and letter
            ready2, _, _ = select.select([sys.stdin], [], [], 0.05)
            if ready2:
                ch2 = sys.stdin.read(1)
                ch += ch2
                if ch2 == "[":
                    ready3, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if ready3:
                        ch += sys.stdin.read(1)

        return ch

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _handle_answer(self) -> None:
        """Answer the selected question.

        Restores line mode for text input, shows question detail, collects
        the user's answer (with optional suggested-answer menu), confirms,
        submits via QuestionQueue, then re-enters cbreak mode.
        """
        if not self.questions or self.cursor >= len(self.questions):
            return

        entry = self.questions[self.cursor]
        q = entry["question_data"]
        plan_path = entry["plan_path"]
        question_id = q.get("id", "")

        # Restore line mode for text input
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
        try:
            self.console.clear()
            self._render_question_detail(entry)

            suggested = q.get("suggested_answers") or []
            answer_text = None

            if suggested:
                # Numbered suggestion menu
                self.console.print()
                self.console.print("[bold]Select an answer:[/bold]")
                for i, opt in enumerate(suggested, start=1):
                    self.console.print(f"  [{i}] {opt}")
                self.console.print("  [C] Custom answer")
                self.console.print("  [D] Defer")
                self.console.print()

                while True:
                    try:
                        choice = input("Your choice: ").strip().upper()
                    except (EOFError, KeyboardInterrupt):
                        self.console.print("\n[yellow]Cancelled[/yellow]")
                        return

                    if choice == "D":
                        self.console.print("[yellow]Deferred.[/yellow]")
                        return
                    elif choice == "C":
                        self.console.print()
                        self.console.print("[bold]Enter your custom answer:[/bold]")
                        try:
                            answer_text = input("> ").strip()
                        except (EOFError, KeyboardInterrupt):
                            self.console.print("\n[yellow]Cancelled[/yellow]")
                            return
                        if not answer_text:
                            self.console.print("[yellow]Empty answer - cancelled.[/yellow]")
                            return
                        break
                    elif choice.isdigit():
                        idx = int(choice) - 1
                        if 0 <= idx < len(suggested):
                            answer_text = suggested[idx]
                            break
                        else:
                            self.console.print("[red]Invalid choice. Try again.[/red]")
                    else:
                        self.console.print("[red]Invalid choice. Try again.[/red]")
            else:
                # Freeform input
                self.console.print()
                self.console.print("[bold]Your answer (leave blank to cancel):[/bold]")
                try:
                    answer_text = input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    self.console.print("\n[yellow]Cancelled[/yellow]")
                    return
                if not answer_text:
                    self.console.print("[yellow]Cancelled.[/yellow]")
                    return

            # Confirmation prompt
            self.console.print()
            self.console.print(f"[bold]Your answer:[/bold] {answer_text}")
            self.console.print()
            self.console.print("[bold]Submit? [Y/n/e][/bold]  Y=submit  n=cancel  e=edit")

            # Re-enter cbreak briefly for the single confirmation keypress
            tty.setcbreak(sys.stdin.fileno())
            try:
                confirm_key = self._read_key_with_timeout(30)
            finally:
                # Restore line mode again in case we need to loop back
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)

            if confirm_key is None or confirm_key.lower() == "n":
                self.console.print("[yellow]Cancelled.[/yellow]")
                time.sleep(0.5)
                return
            elif confirm_key.lower() == "e":
                # Re-prompt freeform edit
                self.console.print()
                self.console.print("[bold]Edit your answer:[/bold]")
                try:
                    answer_text = input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    self.console.print("\n[yellow]Cancelled[/yellow]")
                    return
                if not answer_text:
                    self.console.print("[yellow]Cancelled.[/yellow]")
                    return
            # y, Enter, or any other key => submit

            # Submit via QuestionQueue
            try:
                from agenticguidance.services.question import QuestionQueue
                QuestionQueue(plan_path).answer_question(
                    question_id,
                    answer_text,
                    answered_by="human",
                )
                self.console.print()
                self.console.print("[green]Answer submitted.[/green]")
                time.sleep(0.5)
            except Exception as e:
                self.console.print(f"\n[red]Error submitting answer: {e}[/red]")
                time.sleep(2)
                return

            # Auto-advance cursor
            self.cursor = min(self.cursor, max(0, len(self.questions) - 2))

        except (EOFError, KeyboardInterrupt):
            self.console.print("\n[yellow]Cancelled[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")
            time.sleep(1)
        finally:
            # Always re-enter cbreak
            tty.setcbreak(sys.stdin.fileno())

    def _handle_defer(self) -> None:
        """Defer the selected question.

        Stays in cbreak mode and reads a single Y/n keypress for confirmation.
        On confirmation, marks the question deferred and writes it back to YAML.
        """
        if not self.questions or self.cursor >= len(self.questions):
            return

        entry = self.questions[self.cursor]
        q = entry["question_data"]
        question_text = q.get("text", q.get("question", ""))
        file_path = entry["file_path"]

        # Brief inline prompt (stay in cbreak mode)
        self.console.print()
        self.console.print("[bold]Defer this question?[/bold]")
        # Truncate for display
        display_text = question_text[:60] + "..." if len(question_text) > 60 else question_text
        self.console.print(f'[dim]"{display_text}"[/dim]')
        self.console.print()
        self.console.print("[bold][Y/n][/bold]", end=" ")

        key = self._read_key_with_timeout(15)

        if key is None or key.lower() == "n":
            self.console.print("[yellow]Cancelled.[/yellow]")
            time.sleep(0.5)
            return

        # y or Enter => defer
        try:
            from agenticguidance.models.question import yaml_to_question, question_to_yaml

            yaml_content = file_path.read_text(encoding="utf-8")
            question_obj = yaml_to_question(yaml_content)
            question_obj.mark_deferred()
            new_yaml = question_to_yaml(question_obj)
            file_path.write_text(new_yaml, encoding="utf-8")

            self.console.print()
            self.console.print("[green]Question deferred.[/green]")
            time.sleep(0.5)
        except Exception as e:
            self.console.print(f"\n[red]Error deferring question: {e}[/red]")
            time.sleep(2)
            return

        # Auto-advance cursor
        self.cursor = min(self.cursor, max(0, len(self.questions) - 2))

    def _handle_more_info(self) -> None:
        """Request more information on the selected question.

        Restores line mode for freeform input, then submits the request as
        a special answer with a 'Need more info: ' prefix. The agent sees
        this and provides clarification via a follow-up question.
        """
        if not self.questions or self.cursor >= len(self.questions):
            return

        entry = self.questions[self.cursor]
        q = entry["question_data"]
        plan_path = entry["plan_path"]
        question_id = q.get("id", "")
        question_text = q.get("text", q.get("question", ""))

        # Restore line mode for text input
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
        try:
            self.console.clear()

            # Show brief question context
            self.console.print("[bold]REQUEST MORE INFO[/bold]")
            self.console.print("[dim]" + "-" * 60 + "[/dim]")
            self.console.print()
            display_text = question_text[:80] + "..." if len(question_text) > 80 else question_text
            self.console.print(display_text)
            self.console.print()
            self.console.print("[bold]What info do you need? (leave blank to cancel):[/bold]")

            try:
                info_text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[yellow]Cancelled[/yellow]")
                return

            if not info_text:
                self.console.print("[yellow]Cancelled.[/yellow]")
                time.sleep(0.5)
                return

            # Submit as special answer
            try:
                from agenticguidance.services.question import QuestionQueue
                QuestionQueue(plan_path).answer_question(
                    question_id,
                    f"Need more info: {info_text}",
                    answered_by="human",
                )
                self.console.print()
                self.console.print("[green]Info requested. Waiting for agent follow-up...[/green]")
                time.sleep(1)
            except Exception as e:
                self.console.print(f"\n[red]Error requesting info: {e}[/red]")
                time.sleep(2)
                return

        except (EOFError, KeyboardInterrupt):
            self.console.print("\n[yellow]Cancelled[/yellow]")
        except Exception as e:
            self.console.print(f"\n[red]Error: {e}[/red]")
            time.sleep(1)
        finally:
            # Always re-enter cbreak
            tty.setcbreak(sys.stdin.fileno())

    def _handle_show(self) -> None:
        """Show full detail for the selected question (read-only).

        Stays in cbreak mode. Clears screen, prints full question detail,
        then waits for any keypress before returning to the main list.
        """
        if not self.questions or self.cursor >= len(self.questions):
            return

        entry = self.questions[self.cursor]

        self.console.clear()
        self._render_question_detail(entry)
        self.console.print()
        self.console.print("[dim]Press any key to return...[/dim]")

        # Wait for any keypress (already in cbreak mode)
        self._read_key_with_timeout(60)

    # ------------------------------------------------------------------
    # Detail rendering helper
    # ------------------------------------------------------------------

    def _render_question_detail(self, entry: dict) -> None:
        """Print full question detail to the console.

        Renders a header block with plan name, severity, asked_by and
        timestamp, followed by the full question text and context. If
        the question has suggested_answers they are listed at the end.

        Args:
            entry: Question entry dict as returned by _refresh_questions,
                   with keys: plan_name, plan_path, question_data, file_path.
        """
        q = entry["question_data"]
        plan_name = entry["plan_name"]

        severity = q.get("severity", "low").upper()
        asked_by = q.get("asked_by", "unknown")
        question_text = q.get("text", q.get("question", ""))
        context_text = q.get("context", "")
        suggested = q.get("suggested_answers") or []

        # Format timestamp
        created_at = q.get("created_at")
        if created_at:
            try:
                ts = datetime.fromtimestamp(float(created_at))
                time_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, OSError, OverflowError):
                time_str = str(created_at)
        else:
            time_str = "unknown"

        # Truncate plan name for header display
        plan_display = plan_name[:20] + ".." if len(plan_name) > 22 else plan_name

        divider = "[dim]" + "-" * 60 + "[/dim]"

        self.console.print(divider)
        self.console.print(
            f"[bold]QUESTION[/bold]"
            f"{'':>30}"
            f"[dim]Plan: {plan_display}[/dim]"
        )
        self.console.print(
            f"Severity: [bold]{severity}[/bold]"
            f"{'':>8}"
            f"[dim]Asked by: {asked_by}[/dim]"
        )
        self.console.print(f"[dim]Time: {time_str}[/dim]")
        self.console.print(divider)
        self.console.print()
        self.console.print(question_text)
        self.console.print()

        if context_text:
            self.console.print("[bold]Context:[/bold]")
            self.console.print(context_text)
            self.console.print()

        self.console.print(divider)

        if suggested:
            self.console.print()
            self.console.print("[bold]Suggested answers:[/bold]")
            for i, opt in enumerate(suggested, start=1):
                self.console.print(f"  {i}. {opt}")
