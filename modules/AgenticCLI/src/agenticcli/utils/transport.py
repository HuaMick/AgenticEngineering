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
) -> str:
    """Determine the best available transport for agent spawning.

    Priority: sdk-tmux > tmux > subprocess
    """
    tmux_exists = bool(shutil.which("tmux"))

    if sdk_available and tmux_exists and tmux_requested:
        return SDK_TMUX
    elif tmux_exists and tmux_requested:
        return TMUX
    else:
        return SUBPROCESS
