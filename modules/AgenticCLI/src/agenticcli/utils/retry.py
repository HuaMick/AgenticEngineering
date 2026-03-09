"""Centralized retry utilities with configurable backoff."""
import logging
import time
from typing import Callable, TypeVar, Optional, Sequence

logger = logging.getLogger(__name__)
T = TypeVar("T")

# Centralized retry constants
DEFAULT_MAX_RETRIES = 3
SPAWN_RETRY_BACKOFF = [5, 15]  # For orchestration quick-exit retries
SDK_RETRY_BASE_DELAY = 2  # For SDK/tmux spawn retries (2^n)


def exponential_backoff(attempt: int, base: int = 2) -> int:
    """Calculate exponential backoff delay: base^attempt seconds."""
    return base ** attempt


def static_backoff(attempt: int, delays: Sequence[int] = (5, 15)) -> int:
    """Get delay from static backoff schedule."""
    return delays[min(attempt, len(delays) - 1)]
