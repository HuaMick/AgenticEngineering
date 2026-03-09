"""Centralized context file utilities for agent session spawning."""
from pathlib import Path


def get_context_dir() -> Path:
    """Get the context directory for session context files."""
    context_dir = Path.home() / ".agentic" / "sessions" / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    return context_dir


def write_context_file(session_id: str, content: str) -> Path:
    """Write compiled context to file and return path."""
    context_dir = get_context_dir()
    context_file = context_dir / f"{session_id}.md"
    context_file.write_text(content)
    return context_file
