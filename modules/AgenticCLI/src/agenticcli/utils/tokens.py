"""Token estimation utilities for context window metrics."""

# Claude context window limits
MAX_CONTEXT_TOKENS = 200_000
RECOMMENDED_MAX_TOKENS = 150_000  # 75% warning threshold
CRITICAL_THRESHOLD_TOKENS = 180_000  # 90% critical threshold

# Heuristic: ~4 characters per token (English text average)
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string."""
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def context_usage_percent(tokens: int) -> float:
    """Calculate context window usage as a percentage."""
    return min(100.0, (tokens / MAX_CONTEXT_TOKENS) * 100)


def get_usage_color(percent: float) -> str:
    """Get the appropriate color for the given usage percentage."""
    if percent >= 90:
        return "red"
    elif percent >= 75:
        return "yellow"
    return "cyan"
