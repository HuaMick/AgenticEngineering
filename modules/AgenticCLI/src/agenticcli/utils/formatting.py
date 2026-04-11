# story: US-PLN-001
"""String formatting utilities.

Pure functions for formatting and truncating display strings.
"""


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate a string to a maximum length, appending a suffix if truncated.

    Args:
        text: The string to truncate.
        max_length: Maximum allowed length of the returned string (including suffix).
        suffix: String appended when truncation occurs. Defaults to '...'.

    Returns:
        The original string if it fits within max_length, otherwise a truncated
        version ending with the suffix. Returns '' for empty strings or when
        max_length <= 0.

    Examples:
        >>> truncate_string('Hello World', 8)
        'Hello...'
        >>> truncate_string('Hi', 10)
        'Hi'
        >>> truncate_string('', 5)
        ''
        >>> truncate_string('Hello', 0)
        ''
        >>> truncate_string('Hello', -1)
        ''
        >>> truncate_string('Hello World', 14)
        'Hello World...'
        >>> truncate_string('Hello World', 2, suffix='...')
        'He'
    """
    if not text or max_length <= 0:
        return ""

    if len(text) <= max_length:
        return text

    # If max_length is shorter than the suffix, truncate without suffix
    if max_length < len(suffix):
        return text[:max_length]

    return text[: max_length - len(suffix)] + suffix
