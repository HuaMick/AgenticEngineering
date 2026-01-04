"""Stability decorators and command metadata for AgenticCLI.

Provides mechanisms to mark commands with stability levels (ALPHA, BETA, etc.)
and display appropriate warnings to users.
"""

from enum import Enum


class StabilityLevel(str, Enum):
    """Command stability levels."""

    ALPHA = "ALPHA"
    BETA = "BETA"
    EXPERIMENTAL = "EXPERIMENTAL"
    STABLE = "STABLE"


# Mapping of commands to their stability levels
# Commands not listed are assumed to be STABLE
# All commands are now STABLE as of iteration-28
COMMAND_STABILITY: dict[str, StabilityLevel] = {
    # "cicd": StabilityLevel.STABLE,  # Matured in iteration-28
    # "manifest": StabilityLevel.STABLE,  # Matured in iteration-28
}


# Stability level descriptions for banners
STABILITY_MESSAGES: dict[StabilityLevel, str] = {
    StabilityLevel.ALPHA: "This command is experimental and may change without notice.",
    StabilityLevel.BETA: "This command is in beta testing. Please report any issues.",
    StabilityLevel.EXPERIMENTAL: "This command is experimental. Use with caution.",
}


# Stability level colors for console output
STABILITY_COLORS: dict[StabilityLevel, str] = {
    StabilityLevel.ALPHA: "red",
    StabilityLevel.BETA: "yellow",
    StabilityLevel.EXPERIMENTAL: "magenta",
}


def get_command_stability(command: str) -> StabilityLevel:
    """Get the stability level for a command.

    Args:
        command: Command name (e.g., "cicd", "plan")

    Returns:
        StabilityLevel for the command, defaults to STABLE if not specified.
    """
    return COMMAND_STABILITY.get(command, StabilityLevel.STABLE)


def get_stability_banner_text(level: StabilityLevel, command: str) -> str | None:
    """Get the banner text for a stability level.

    Args:
        level: The stability level
        command: The command name for context

    Returns:
        Banner text or None for STABLE commands.
    """
    if level == StabilityLevel.STABLE:
        return None

    message = STABILITY_MESSAGES.get(level, "")
    return f"[{level.value}] {message}"


def get_stability_color(level: StabilityLevel) -> str:
    """Get the color for a stability level.

    Args:
        level: The stability level

    Returns:
        Rich color string for the level.
    """
    return STABILITY_COLORS.get(level, "white")
