"""Centralized spawn command builder for agent sessions."""
from typing import Optional


def build_spawn_command(
    role: str,
    epic_folder: str,
    max_turns: Optional[int] = None,
    skip_permissions: bool = False,
    background: bool = True,
    use_tmux: bool = True,
    json_output: bool = True,
) -> list[str]:
    """Build a normalized 'agentic orchestrate session spawn' command.

    All callers should use this to ensure consistent flag handling.
    """
    cmd = ["agentic"]
    if json_output:
        cmd.append("-j")
    cmd.extend(["orchestrate", "session", "spawn", "--role", role, "--epic", epic_folder])
    if background:
        cmd.append("-b")
    if use_tmux:
        cmd.append("--tmux")
    if max_turns is not None:
        cmd.extend(["--max-turns", str(max_turns)])
    if skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    return cmd
