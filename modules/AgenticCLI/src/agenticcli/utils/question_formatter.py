"""Question notification formatting utilities.

Provides formatters for rendering pending questions in tmux notification panes
and terminal output.
"""

import textwrap
from typing import Any


# ANSI color codes for severity levels
COLOR_HIGH = "\033[31m"     # Red
COLOR_MEDIUM = "\033[33m"   # Yellow
COLOR_LOW = "\033[32m"      # Green
COLOR_RESET = "\033[0m"     # Reset to default


def format_question_notification(questions: list[dict]) -> str:
    """Format a list of pending questions for notification display.

    Creates a formatted text output suitable for tmux notification panes,
    including ASCII art borders, severity colors, and CLI command hints.

    Args:
        questions: List of question dictionaries with fields:
            - question_id: Unique identifier
            - severity: "high", "medium", or "low"
            - module: Module/agent that generated the question
            - question: The question text
            - context: Additional context (optional)

    Returns:
        Formatted string with bordered notification, ready for display.

    Example:
        >>> questions = [
        ...     {"question_id": "Q001", "severity": "high", "module": "builder",
        ...      "question": "Should I proceed?", "context": "Building feature X"}
        ... ]
        >>> print(format_question_notification(questions))
    """
    if not questions:
        return _format_no_questions()

    lines = []

    # Header with border
    lines.append("=" * 78)
    lines.append("PENDING QUESTIONS".center(78))
    lines.append("=" * 78)
    lines.append("")

    # List each question
    for idx, q in enumerate(questions, start=1):
        question_id = q.get("question_id", "UNKNOWN")
        severity = q.get("severity", "medium").lower()
        module = q.get("module", "unknown")
        question_text = q.get("question", "No question text")

        # Truncate question text to 100 characters
        if len(question_text) > 100:
            question_text = question_text[:97] + "..."

        # Apply color based on severity
        color_code = _get_severity_color(severity)

        # Format: [1] Q001 (high) - builder
        header = f"[{idx}] {question_id} ({severity}) - {module}"
        lines.append(f"{color_code}{header}{COLOR_RESET}")

        # Wrap question text to fit within 78 characters with indent
        wrapped = textwrap.fill(
            question_text,
            width=74,
            initial_indent="  ",
            subsequent_indent="  "
        )
        lines.append(wrapped)
        lines.append("")

    # Footer with CLI command hints
    lines.append("-" * 78)
    lines.append("COMMANDS:")
    lines.append("  To answer:  agentic question answer <question-id>")
    lines.append("  To list:    agentic question list")
    lines.append("  To defer:   agentic question defer <question-id>")
    lines.append("=" * 78)

    return "\n".join(lines)


def format_question_summary(question: dict) -> str:
    """Format a single question summary with all details.

    Creates a detailed view of a single question including all fields
    and the CLI command to answer it.

    Args:
        question: Question dictionary with fields:
            - question_id: Unique identifier
            - severity: "high", "medium", or "low"
            - module: Module/agent that generated the question
            - question: The question text
            - context: Additional context (optional)
            - created_at: Timestamp (optional)

    Returns:
        Formatted string with complete question details.

    Example:
        >>> question = {
        ...     "question_id": "Q001",
        ...     "severity": "high",
        ...     "module": "builder",
        ...     "question": "Should I proceed with this approach?",
        ...     "context": "Building feature X requires dependency Y"
        ... }
        >>> print(format_question_summary(question))
    """
    question_id = question.get("question_id", "UNKNOWN")
    severity = question.get("severity", "medium").lower()
    module = question.get("module", "unknown")
    question_text = question.get("question", "No question text")
    context = question.get("context", "")
    created_at = question.get("created_at", "")

    lines = []

    # Header
    lines.append("=" * 78)
    color_code = _get_severity_color(severity)
    lines.append(f"{color_code}QUESTION: {question_id} ({severity}){COLOR_RESET}")
    lines.append("=" * 78)
    lines.append("")

    # Fields
    lines.append(f"Module:   {module}")
    if created_at:
        lines.append(f"Created:  {created_at}")
    lines.append("")

    # Question text (wrapped)
    lines.append("Question:")
    wrapped_question = textwrap.fill(
        question_text,
        width=74,
        initial_indent="  ",
        subsequent_indent="  "
    )
    lines.append(wrapped_question)
    lines.append("")

    # Context (if provided)
    if context:
        lines.append("Context:")
        wrapped_context = textwrap.fill(
            context,
            width=74,
            initial_indent="  ",
            subsequent_indent="  "
        )
        lines.append(wrapped_context)
        lines.append("")

    # Command to answer
    lines.append("-" * 78)
    lines.append(f"To answer: agentic question answer {question_id}")
    lines.append("=" * 78)

    return "\n".join(lines)


def _get_severity_color(severity: str) -> str:
    """Get ANSI color code for severity level.

    Args:
        severity: Severity level ("high", "medium", "low")

    Returns:
        ANSI color code string.
    """
    severity_lower = severity.lower()
    if severity_lower == "high":
        return COLOR_HIGH
    elif severity_lower == "medium":
        return COLOR_MEDIUM
    elif severity_lower == "low":
        return COLOR_LOW
    else:
        return COLOR_RESET


def _format_no_questions() -> str:
    """Format a message when there are no pending questions.

    Returns:
        Formatted string indicating no questions.
    """
    lines = []
    lines.append("=" * 78)
    lines.append("NO PENDING QUESTIONS".center(78))
    lines.append("=" * 78)
    lines.append("")
    lines.append("All questions have been answered or deferred.".center(78))
    lines.append("")
    lines.append("=" * 78)
    return "\n".join(lines)
