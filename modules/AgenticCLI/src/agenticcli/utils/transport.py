"""Centralized transport selection for agent spawning."""
import shutil
from typing import Optional

# Standard transport values
SDK_TMUX = "sdk-tmux"
TMUX = "tmux"
SUBPROCESS = "subprocess"
SDK_DIRECT = "sdk"


def determine_transport(
    sdk_available: bool = False,
    tmux_requested: bool = True,
    force_sdk_direct: bool = False,
) -> str:
    """Determine the best available transport for agent spawning.

    Priority: SDK_DIRECT (if forced) > sdk-tmux > tmux > subprocess

    Args:
        sdk_available: Whether the Claude Agent SDK is importable.
        tmux_requested: Whether tmux-based transport is desired.
        force_sdk_direct: When True and sdk_available, return SDK_DIRECT
            before other checks. The env var check stays at the call site.
    """
    if force_sdk_direct and sdk_available:
        return SDK_DIRECT

    tmux_exists = bool(shutil.which("tmux"))

    if sdk_available and tmux_exists and tmux_requested:
        return SDK_TMUX
    elif tmux_exists and tmux_requested:
        return TMUX
    else:
        return SUBPROCESS
