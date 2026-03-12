"""Centralized session ID generation and tmux session naming."""
import re
import uuid
from pathlib import Path
from typing import Optional


def generate_session_id() -> str:
    """Generate a new session UUID string."""
    return str(uuid.uuid4())


def generate_loop_id(prefix: str = "loop") -> str:
    """Generate a prefixed loop ID (e.g., 'orch-abc123def456')."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def short_id(session_id: str) -> str:
    """Get short display form (first 8 chars) of a session ID."""
    return session_id[:8]


def tmux_session_name(
    session_id: str,
    epic_folder: Optional[Path] = None,
    role: Optional[str] = None,
) -> str:
    """Generate a descriptive tmux session name.

    Naming convention:
    - With epic + role: agentic-{epic_short}-{role_short}-{session_id[:6]}
    - With epic only:   agentic-{epic_short}-{session_id[:8]}
    - Without epic:     agentic-spawn-{session_id[:8]}

    Names are sanitized to valid tmux identifiers (alphanumeric + hyphens).

    Args:
        session_id: Session UUID.
        epic_folder: Optional epic folder path.
        role: Optional agent role.

    Returns:
        A valid tmux session name string.
    """
    if epic_folder:
        epic_short = epic_folder.name[:8] if isinstance(epic_folder, Path) else str(epic_folder)[:8]
        if role:
            role_short = role[:8]
            sid_short = session_id[:6]
            name = f"agentic-{epic_short}-{role_short}-{sid_short}"
        else:
            name = f"agentic-{epic_short}-{session_id[:8]}"
    else:
        name = f"agentic-spawn-{session_id[:8]}"

    # Sanitize: replace invalid chars with hyphens, collapse multiples
    name = re.sub(r"[^a-zA-Z0-9_-]", "-", name)
    name = re.sub(r"-{2,}", "-", name)
    return name.strip("-")
