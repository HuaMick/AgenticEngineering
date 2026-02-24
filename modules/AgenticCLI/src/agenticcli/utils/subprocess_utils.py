"""Subprocess utilities for AgenticCLI.

Provides helpers for spawning subprocesses that strip Claude Code
internal environment variables to prevent nested-session errors.
"""

import os
from typing import Optional

# Environment variables set by Claude Code that must not be inherited
# by child claude processes (causes nested-session rejection).
_CLAUDECODE_ENV_VARS = (
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
)


def get_clean_env(base_env: Optional[dict] = None) -> dict:
    """Return a copy of the environment with Claude Code internal vars removed.

    Call this whenever spawning a `claude` subprocess from within an
    existing Claude Code session to prevent the nested-session error:
        "Claude Code cannot be launched inside another Claude Code session."

    Args:
        base_env: Base environment dict to copy and strip. Defaults to
                  os.environ if not provided.

    Returns:
        A new dict with CLAUDECODE and CLAUDE_CODE_ENTRYPOINT removed.
    """
    env = dict(base_env if base_env is not None else os.environ)
    for var in _CLAUDECODE_ENV_VARS:
        env.pop(var, None)
    return env
