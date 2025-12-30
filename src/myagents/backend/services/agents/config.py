"""
Configuration settings for the agents service.

This module provides centralized configuration for agent behavior,
including strict mode settings for external service integrations.

Environment Variables:
    GEMINI_MODEL: Gemini model to use (default: gemini-2.5-flash)
    LANGSMITH_PROJECT: LangSmith project name (default: myagents-echo)
    LANGSMITH_STRICT_MODE: Fail on LangSmith errors (default: false)
    MYAGENTS_LOG_DIR: Directory for agent logs (default: /home/code/myagents/docs/agent_logs)
    GCP_SECRET_TIMEOUT: Timeout for GCP secret fetching in seconds (default: 30)
"""

import os
from pathlib import Path


def get_config_bool(key: str, default: bool = False) -> bool:
    """
    Get a boolean configuration value from environment variables.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        Boolean value
    """
    value = os.environ.get(key, "").lower()
    if value in ("true", "1", "yes", "on"):
        return True
    elif value in ("false", "0", "no", "off"):
        return False
    return default


# LangSmith Configuration
# When LANGSMITH_STRICT_MODE is enabled, invalid API keys will raise errors
# When disabled, validation failures will log warnings and continue execution
LANGSMITH_STRICT_MODE = get_config_bool("LANGSMITH_STRICT_MODE", default=False)

# Valid LangSmith API key prefixes
LANGSMITH_API_KEY_PREFIXES = ("ls__", "lsv2_")

# LangSmith project name
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "myagents-echo")

# LLM Configuration
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Logging Configuration
LOG_DIR = Path(os.getenv("MYAGENTS_LOG_DIR", "/home/code/myagents/docs/agent_logs"))

# GCP Configuration
GCP_SECRET_TIMEOUT = int(os.getenv("GCP_SECRET_TIMEOUT", "30"))


def ensure_log_dir() -> Path:
    """
    Ensure LOG_DIR exists, creating it if necessary.

    Returns:
        Path object for the log directory

    Raises:
        OSError: If directory creation fails due to permissions or other errors
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR
