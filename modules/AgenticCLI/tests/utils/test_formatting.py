# story: US-PLN-001
"""Unit tests for agenticcli.utils.formatting.truncate_string.

truncate_string is the helper used by cmd_list (Epic Lifecycle / US-PLN-001)
to keep long epic names inside the terminal table width. Covered behaviors:
  - String longer than max_length is truncated with suffix
  - String shorter/equal to max_length returns unchanged
  - Custom suffix works
  - Empty string returns ''
  - Zero/negative max_length returns ''
  - max_length shorter than suffix → truncate without suffix
"""

import pytest

pytestmark = pytest.mark.story("US-PLN-001")

from agenticcli.utils.formatting import truncate_string


# --- Step 1: String longer than max_length is truncated with suffix ---


def test_truncate_long_string_with_default_suffix():
    """String longer than max_length is truncated and '...' suffix appended."""
    result = truncate_string("Hello World", 8)
    assert result == "Hello..."
    assert len(result) <= 8


def test_truncated_string_never_exceeds_max_length():
    """Returned string length must never exceed max_length."""
    result = truncate_string("A very long string that goes on and on", 15)
    assert len(result) <= 15
    assert result.endswith("...")


def test_truncate_at_exact_boundary():
    """When max_length == len(text) + 1, still truncates correctly."""
    # "Hello World" is 11 chars, with suffix "..." (3), max_length=10 → "Hello W..."
    result = truncate_string("Hello World", 10)
    assert len(result) <= 10
    assert result == "Hello W..."


# --- Step 2: String shorter than or equal to max_length returns unchanged ---


def test_string_shorter_than_max_length_unchanged():
    """String shorter than max_length returns the original string."""
    result = truncate_string("Hi", 10)
    assert result == "Hi"


def test_string_equal_to_max_length_unchanged():
    """String with length == max_length returns unchanged (no truncation needed)."""
    result = truncate_string("Hello", 5)
    assert result == "Hello"


def test_single_char_within_max_length():
    """Single character string within max_length returns unchanged."""
    result = truncate_string("X", 5)
    assert result == "X"


# --- Step 3: Custom suffix ---


def test_custom_suffix_single_char():
    """Custom single-char suffix replaces the default '...'."""
    result = truncate_string("Hello World", 8, suffix="…")
    assert len(result) <= 8
    assert result.endswith("…")


def test_custom_suffix_two_chars():
    """Custom two-char suffix works correctly."""
    result = truncate_string("Hello World", 8, suffix="--")
    assert len(result) <= 8
    assert result.endswith("--")
    assert result == "Hello ---"[: 8]  # "Hello ---" → "Hello --" won't fit, let's compute
    # "Hello World"[:8-2] + "--" = "Hello " + "--" = "Hello --"
    assert result == "Hello --"


def test_custom_suffix_empty_string():
    """Empty suffix means no suffix appended, just truncation."""
    result = truncate_string("Hello World", 5, suffix="")
    assert result == "Hello"
    assert len(result) == 5


# --- Step 4: Empty string returns '' ---


def test_empty_string_returns_empty():
    """Empty input string always returns empty string."""
    result = truncate_string("", 5)
    assert result == ""


def test_empty_string_with_zero_max_length():
    """Empty string with zero max_length returns empty."""
    result = truncate_string("", 0)
    assert result == ""


# --- Step 5: Zero/negative max_length returns '' ---


def test_zero_max_length_returns_empty():
    """max_length of 0 returns empty string without exception."""
    result = truncate_string("Hello", 0)
    assert result == ""


def test_negative_max_length_returns_empty():
    """Negative max_length returns empty string without exception."""
    result = truncate_string("Hello", -1)
    assert result == ""


def test_large_negative_max_length_returns_empty():
    """Very large negative max_length still returns empty string."""
    result = truncate_string("Hello World", -1000)
    assert result == ""


# --- Step 6: max_length shorter than suffix length → truncate without suffix ---


def test_max_length_shorter_than_suffix_truncates_without_suffix():
    """When max_length < len(suffix), truncate without appending suffix."""
    # Default suffix "..." is 3 chars, max_length=2 → just first 2 chars
    result = truncate_string("Hello World", 2)
    assert result == "He"
    assert len(result) <= 2


def test_max_length_equal_to_suffix_length():
    """When max_length == len(suffix), suffix fits so it's used."""
    # Default suffix "..." is 3 chars, max_length=3 → "..."
    result = truncate_string("Hello World", 3)
    assert result == "..."
    assert len(result) <= 3


def test_max_length_one_with_default_suffix():
    """max_length=1 with 3-char suffix → just first char, no suffix."""
    result = truncate_string("Hello World", 1)
    assert result == "H"
    assert len(result) <= 1
