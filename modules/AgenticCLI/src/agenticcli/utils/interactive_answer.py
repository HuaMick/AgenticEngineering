"""Interactive answer wizard for question answering via SSH/Termux.

Provides a mobile-friendly, SSH-compatible interface for answering agent questions
with optional suggested answers, confirmation prompts, and defer capability.
"""

from typing import Optional

from rich.console import Console

# Sentinel value to signal question deferral
DEFER_SENTINEL = "__DEFER__"


def interactive_answer_wizard(
    question: "Question",
    suggested_answers: Optional[list[str]] = None,
) -> tuple[str, Optional[str]]:
    """Interactive wizard for answering a question.

    Displays the question with severity badge and prompts for an answer.
    If suggested answers are provided, shows numbered menu with custom/defer options.
    Otherwise, shows free-text input with defer option.

    Mobile-friendly: uses max width of 60 chars for display.
    SSH-compatible: uses plain input() instead of rich prompts.

    Args:
        question: Question object with text and severity attributes.
        suggested_answers: Optional list of suggested answer strings.

    Returns:
        Tuple of (answer_text, confidence_level).
        - If user selects suggested answer: (answer_text, "high")
        - If user provides custom answer: (answer_text, None)
        - If user defers: (DEFER_SENTINEL, None)

    Example:
        >>> question = Question(text="Use pytest?", severity="medium")
        >>> answer, confidence = interactive_answer_wizard(question, ["Yes", "No"])
        >>> if answer == DEFER_SENTINEL:
        ...     print("Question deferred")
        >>> else:
        ...     print(f"Answer: {answer}, Confidence: {confidence}")
    """
    console = Console(width=60, force_terminal=True)

    # Display question header with severity badge
    severity = getattr(question, "severity", "medium").upper()
    if severity == "BLOCKING":
        badge = "[red bold]BLOCKING[/red bold]"
    elif severity == "HIGH":
        badge = "[red]HIGH[/red]"
    elif severity == "MEDIUM":
        badge = "[yellow]MEDIUM[/yellow]"
    else:
        badge = "[dim]LOW[/dim]"

    console.print()
    console.print(f"[bold]Question [{badge}]:[/bold]")
    console.print()

    # Word-wrap question text to 60 chars
    question_text = getattr(question, "text", "")
    console.print(question_text)
    console.print()

    # Branch based on whether suggested answers are provided
    if suggested_answers:
        return _answer_with_suggestions(console, suggested_answers)
    else:
        return _answer_freeform(console)


def _answer_with_suggestions(
    console: Console,
    suggested_answers: list[str],
) -> tuple[str, Optional[str]]:
    """Handle answering with suggested options menu.

    Args:
        console: Rich console for output.
        suggested_answers: List of suggested answer strings.

    Returns:
        Tuple of (answer_text, confidence_level).
    """
    # Display numbered options
    console.print("[bold]Select an answer:[/bold]")
    for i, answer in enumerate(suggested_answers, start=1):
        console.print(f"  [{i}] {answer}")
    console.print(f"  [C] Custom answer")
    console.print(f"  [D] Defer question")
    console.print()

    # Get selection
    while True:
        try:
            choice = input("Your choice: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Cancelled[/yellow]")
            return (DEFER_SENTINEL, None)

        # Handle defer
        if choice == "D":
            if _confirm(console, "Defer this question?"):
                return (DEFER_SENTINEL, None)
            else:
                continue

        # Handle custom
        if choice == "C":
            return _prompt_custom_answer(console)

        # Handle numbered selection
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(suggested_answers):
                selected = suggested_answers[index]
                if _confirm(console, f"Your answer: {selected} - Submit?"):
                    return (selected, "high")
                else:
                    continue

        # Invalid input
        console.print("[red]Invalid choice. Please try again.[/red]")


def _answer_freeform(console: Console) -> tuple[str, Optional[str]]:
    """Handle freeform text answer input.

    Args:
        console: Rich console for output.

    Returns:
        Tuple of (answer_text, confidence_level).
    """
    console.print("[bold]Enter your answer (or [D] to defer):[/bold]")
    console.print("[dim](Press Enter when done)[/dim]")
    console.print()

    while True:
        try:
            answer = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Cancelled[/yellow]")
            return (DEFER_SENTINEL, None)

        if not answer:
            console.print("[red]Answer cannot be empty[/red]")
            continue

        # Check for defer
        if answer.upper() == "D":
            if _confirm(console, "Defer this question?"):
                return (DEFER_SENTINEL, None)
            else:
                continue

        # Confirm answer
        if _confirm(console, f"Your answer: {answer} - Submit?"):
            return (answer, None)


def _prompt_custom_answer(console: Console) -> tuple[str, Optional[str]]:
    """Prompt for custom answer text.

    Args:
        console: Rich console for output.

    Returns:
        Tuple of (answer_text, confidence_level).
    """
    console.print()
    console.print("[bold]Enter your custom answer:[/bold]")
    console.print()

    while True:
        try:
            answer = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Cancelled[/yellow]")
            return (DEFER_SENTINEL, None)

        if not answer:
            console.print("[red]Answer cannot be empty[/red]")
            continue

        if _confirm(console, f"Your answer: {answer} - Submit?"):
            return (answer, None)


def _confirm(console: Console, prompt: str) -> bool:
    """Prompt for yes/no confirmation.

    Args:
        console: Rich console for output.
        prompt: Confirmation prompt text.

    Returns:
        True if user confirms (Y), False otherwise.
    """
    console.print()
    console.print(f"[bold]{prompt}[/bold] [Y/n]")

    while True:
        try:
            response = input().strip().upper()
        except (EOFError, KeyboardInterrupt):
            return False

        if response in ("Y", "YES", ""):
            return True
        elif response in ("N", "NO"):
            return False
        else:
            console.print("[red]Please enter Y or N[/red]")
