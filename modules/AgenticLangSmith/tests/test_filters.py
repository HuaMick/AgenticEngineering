"""Unit tests for filter builder functions."""

from datetime import datetime, timezone

import pytest

from agenticlangsmith.filters import (
    build_time_filter,
    build_type_filter,
    build_error_filter,
    combine_filters,
)


class TestBuildTimeFilter:
    """Tests for build_time_filter function."""

    def test_build_time_filter_with_start(self):
        """Test that start time filter is formatted correctly."""
        start = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        result = build_time_filter(start=start)

        assert result is not None
        assert "gte(start_time" in result
        assert "2024-01-15" in result
        assert "10:00:00" in result

    def test_build_time_filter_with_end(self):
        """Test that end time filter is formatted correctly."""
        end = datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        result = build_time_filter(end=end)

        assert result is not None
        assert "lte(start_time" in result
        assert "2024-01-31" in result
        assert "23:59:59" in result

    def test_build_time_filter_with_both(self):
        """Test combined start+end time filter."""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc)
        result = build_time_filter(start=start, end=end)

        assert result is not None
        assert "and(" in result
        assert "gte(start_time" in result
        assert "lte(start_time" in result
        assert "2024-01-01" in result
        assert "2024-01-31" in result

    def test_build_time_filter_no_params(self):
        """Test that None is returned when no time bounds specified."""
        result = build_time_filter()

        assert result is None

    def test_build_time_filter_without_timezone(self):
        """Test filter with naive datetime (no timezone)."""
        start = datetime(2024, 6, 15, 12, 30, 0)
        result = build_time_filter(start=start)

        assert result is not None
        assert "2024-06-15" in result
        assert "12:30:00" in result


class TestBuildTypeFilter:
    """Tests for build_type_filter function."""

    def test_build_type_filter(self):
        """Test that run type filter is formatted correctly."""
        result = build_type_filter("llm")

        assert result == "eq(run_type, 'llm')"

    def test_build_type_filter_chain(self):
        """Test chain type filter."""
        result = build_type_filter("chain")

        assert result == "eq(run_type, 'chain')"

    def test_build_type_filter_tool(self):
        """Test tool type filter."""
        result = build_type_filter("tool")

        assert result == "eq(run_type, 'tool')"

    def test_build_type_filter_retriever(self):
        """Test retriever type filter."""
        result = build_type_filter("retriever")

        assert result == "eq(run_type, 'retriever')"

    def test_build_type_filter_case_insensitive(self):
        """Test that type filter is case insensitive."""
        result = build_type_filter("LLM")

        assert result == "eq(run_type, 'llm')"

    def test_build_type_filter_invalid_type(self):
        """Test that invalid type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            build_type_filter("invalid_type")

        assert "Invalid run_type" in str(exc_info.value)
        assert "invalid_type" in str(exc_info.value)


class TestBuildErrorFilter:
    """Tests for build_error_filter function."""

    def test_build_error_filter_true(self):
        """Test error=true filter format."""
        result = build_error_filter(has_error=True)

        assert result == "eq(status, 'error')"

    def test_build_error_filter_false(self):
        """Test error=false filter format."""
        result = build_error_filter(has_error=False)

        assert result == "ne(status, 'error')"

    def test_build_error_filter_default(self):
        """Test default behavior (has_error=True)."""
        result = build_error_filter()

        assert result == "eq(status, 'error')"


class TestCombineFilters:
    """Tests for combine_filters function."""

    def test_combine_filters_single(self):
        """Test single filter passthrough."""
        result = combine_filters("eq(run_type, 'llm')")

        assert result == "eq(run_type, 'llm')"

    def test_combine_filters_multiple(self):
        """Test AND combination of multiple filters."""
        result = combine_filters(
            "eq(run_type, 'llm')",
            "eq(status, 'error')"
        )

        assert result is not None
        assert "and(" in result
        assert "eq(run_type, 'llm')" in result
        assert "eq(status, 'error')" in result

    def test_combine_filters_with_none(self):
        """Test that None values are filtered out."""
        result = combine_filters(
            "eq(run_type, 'llm')",
            None,
            "eq(status, 'error')"
        )

        assert result is not None
        assert "and(" in result
        assert "eq(run_type, 'llm')" in result
        assert "eq(status, 'error')" in result

    def test_combine_filters_all_none(self):
        """Test that all None returns None."""
        result = combine_filters(None, None, None)

        assert result is None

    def test_combine_filters_three_filters(self):
        """Test combining three filters."""
        result = combine_filters(
            "eq(run_type, 'llm')",
            "eq(status, 'error')",
            "gte(latency, 1.0)"
        )

        assert result is not None
        assert "and(" in result
        # All three filters should be present
        assert "eq(run_type, 'llm')" in result
        assert "eq(status, 'error')" in result
        assert "gte(latency, 1.0)" in result

    def test_combine_filters_empty_args(self):
        """Test with no arguments."""
        result = combine_filters()

        assert result is None

    def test_combine_filters_single_none(self):
        """Test single None argument."""
        result = combine_filters(None)

        assert result is None

    def test_combine_filters_with_time_filter(self):
        """Test combining time filter with other filters."""
        time_filter = build_time_filter(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc)
        )
        type_filter = build_type_filter("llm")

        result = combine_filters(time_filter, type_filter)

        assert result is not None
        assert "and(" in result
        assert "gte(start_time" in result
        assert "eq(run_type, 'llm')" in result
