"""Tests for token estimation utilities."""
import pytest

pytestmark = pytest.mark.story("US-SET-008")

from agenticcli.utils.tokens import (
    estimate_tokens,
    context_usage_percent,
    get_usage_color,
    MAX_CONTEXT_TOKENS,
    RECOMMENDED_MAX_TOKENS,
    CRITICAL_THRESHOLD_TOKENS,
    CHARS_PER_TOKEN,
)


class TestEstimateTokens:
    def test_empty_string_returns_zero(self):
        assert estimate_tokens("") == 0

    def test_none_returns_zero(self):
        assert estimate_tokens(None) == 0

    def test_short_string_returns_minimum_one(self):
        assert estimate_tokens("Hi") >= 1

    def test_1000_chars_approximately_250_tokens(self):
        text = "a" * 1000
        tokens = estimate_tokens(text)
        assert 200 <= tokens <= 300

    def test_heuristic_ratio(self):
        text = "a" * 400
        assert estimate_tokens(text) == 100  # 400 / 4


class TestContextUsagePercent:
    def test_zero_tokens(self):
        assert context_usage_percent(0) == 0.0

    def test_half_usage(self):
        half = MAX_CONTEXT_TOKENS // 2
        pct = context_usage_percent(half)
        assert 49.0 <= pct <= 51.0

    def test_full_usage(self):
        assert context_usage_percent(MAX_CONTEXT_TOKENS) == 100.0

    def test_over_limit_capped(self):
        assert context_usage_percent(MAX_CONTEXT_TOKENS * 2) == 100.0


class TestGetUsageColor:
    def test_safe_range(self):
        assert get_usage_color(50) == "cyan"

    def test_warning_threshold(self):
        assert get_usage_color(75) == "yellow"
        assert get_usage_color(80) == "yellow"

    def test_critical_threshold(self):
        assert get_usage_color(90) == "red"
        assert get_usage_color(95) == "red"

    def test_zero_is_safe(self):
        assert get_usage_color(0) == "cyan"


class TestConstants:
    def test_max_context(self):
        assert MAX_CONTEXT_TOKENS == 200_000

    def test_recommended_max(self):
        assert RECOMMENDED_MAX_TOKENS == 150_000

    def test_critical_threshold(self):
        assert CRITICAL_THRESHOLD_TOKENS == 180_000

    def test_chars_per_token(self):
        assert CHARS_PER_TOKEN == 4
