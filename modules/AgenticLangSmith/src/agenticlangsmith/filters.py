"""Filter builders for LangSmith queries.

LangSmith uses a filter expression language for querying runs. This module
provides builder functions to construct valid filter expressions.

Filter Expression Syntax:
- Comparisons: eq, ne, gt, gte, lt, lte, like, ilike
- Logical: and, or, not
- Field access: dot notation (e.g., run.status)
- String literals: single quotes (e.g., 'error')

Examples:
    - eq(status, 'error')
    - and(eq(run_type, 'llm'), gt(latency, 1.0))
    - gte(start_time, '2024-01-01T00:00:00Z')
"""

from datetime import datetime
from typing import Optional


def build_time_filter(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None
) -> Optional[str]:
    """Build time range filter expression.

    Args:
        start: Start of time range (inclusive). Filter runs that started at or after.
        end: End of time range (inclusive). Filter runs that started at or before.

    Returns:
        Filter expression string, or None if no time bounds specified.

    Examples:
        >>> build_time_filter(start=datetime(2024, 1, 1))
        "gte(start_time, '2024-01-01T00:00:00')"

        >>> build_time_filter(start=datetime(2024, 1, 1), end=datetime(2024, 1, 31))
        "and(gte(start_time, '2024-01-01T00:00:00'), lte(start_time, '2024-01-31T00:00:00'))"
    """
    filters = []

    if start:
        start_iso = start.isoformat()
        filters.append(f"gte(start_time, '{start_iso}')")

    if end:
        end_iso = end.isoformat()
        filters.append(f"lte(start_time, '{end_iso}')")

    if not filters:
        return None

    if len(filters) == 1:
        return filters[0]

    return f"and({filters[0]}, {filters[1]})"


def build_type_filter(run_type: str) -> str:
    """Build run type filter.

    Args:
        run_type: The run type to filter by. Valid values:
            - 'llm': LLM calls
            - 'chain': Chain executions
            - 'tool': Tool invocations
            - 'retriever': Retriever calls

    Returns:
        Filter expression string.

    Raises:
        ValueError: If run_type is not a valid type.

    Examples:
        >>> build_type_filter('llm')
        "eq(run_type, 'llm')"
    """
    valid_types = {'llm', 'chain', 'tool', 'retriever', 'prompt', 'parser'}

    if run_type.lower() not in valid_types:
        raise ValueError(
            f"Invalid run_type '{run_type}'. Must be one of: {', '.join(sorted(valid_types))}"
        )

    return f"eq(run_type, '{run_type.lower()}')"


def build_error_filter(has_error: bool = True) -> str:
    """Build error status filter.

    Args:
        has_error: If True, filter for runs with errors.
                   If False, filter for runs without errors.

    Returns:
        Filter expression string.

    Examples:
        >>> build_error_filter(True)
        "eq(status, 'error')"

        >>> build_error_filter(False)
        "ne(status, 'error')"
    """
    if has_error:
        return "eq(status, 'error')"
    else:
        return "ne(status, 'error')"


def build_tag_filter(tag: str) -> str:
    """Build tag filter expression.

    Args:
        tag: The tag to filter by. Runs must have this tag.

    Returns:
        Filter expression string.

    Examples:
        >>> build_tag_filter('production')
        "has(tags, 'production')"
    """
    # Escape single quotes in the tag value
    escaped_tag = tag.replace("'", "\\'")
    return f"has(tags, '{escaped_tag}')"


def build_name_filter(name: str, exact: bool = False) -> str:
    """Build name filter expression.

    Args:
        name: The name or pattern to filter by.
        exact: If True, match exactly. If False, use case-insensitive contains.

    Returns:
        Filter expression string.

    Examples:
        >>> build_name_filter('ChatBot')
        "ilike(name, '%ChatBot%')"

        >>> build_name_filter('ChatBot', exact=True)
        "eq(name, 'ChatBot')"
    """
    escaped_name = name.replace("'", "\\'")

    if exact:
        return f"eq(name, '{escaped_name}')"
    else:
        return f"ilike(name, '%{escaped_name}%')"


def build_latency_filter(
    min_seconds: Optional[float] = None,
    max_seconds: Optional[float] = None
) -> Optional[str]:
    """Build latency filter expression.

    Args:
        min_seconds: Minimum latency threshold (inclusive).
        max_seconds: Maximum latency threshold (inclusive).

    Returns:
        Filter expression string, or None if no bounds specified.

    Examples:
        >>> build_latency_filter(min_seconds=1.0)
        "gte(latency, 1.0)"

        >>> build_latency_filter(min_seconds=0.5, max_seconds=2.0)
        "and(gte(latency, 0.5), lte(latency, 2.0))"
    """
    filters = []

    if min_seconds is not None:
        filters.append(f"gte(latency, {min_seconds})")

    if max_seconds is not None:
        filters.append(f"lte(latency, {max_seconds})")

    if not filters:
        return None

    if len(filters) == 1:
        return filters[0]

    return f"and({filters[0]}, {filters[1]})"


def build_token_filter(
    min_tokens: Optional[int] = None,
    max_tokens: Optional[int] = None
) -> Optional[str]:
    """Build token count filter expression.

    Args:
        min_tokens: Minimum token count threshold (inclusive).
        max_tokens: Maximum token count threshold (inclusive).

    Returns:
        Filter expression string, or None if no bounds specified.

    Examples:
        >>> build_token_filter(min_tokens=100)
        "gte(total_tokens, 100)"
    """
    filters = []

    if min_tokens is not None:
        filters.append(f"gte(total_tokens, {min_tokens})")

    if max_tokens is not None:
        filters.append(f"lte(total_tokens, {max_tokens})")

    if not filters:
        return None

    if len(filters) == 1:
        return filters[0]

    return f"and({filters[0]}, {filters[1]})"


def combine_filters(*filters: Optional[str]) -> Optional[str]:
    """Combine multiple filters with AND logic.

    Args:
        *filters: Variable number of filter expressions to combine.
                  None values are filtered out.

    Returns:
        Combined filter expression with AND logic, or None if no valid filters.

    Examples:
        >>> combine_filters("eq(run_type, 'llm')", "eq(status, 'error')")
        "and(eq(run_type, 'llm'), eq(status, 'error'))"

        >>> combine_filters("eq(run_type, 'llm')", None, "eq(status, 'error')")
        "and(eq(run_type, 'llm'), eq(status, 'error'))"

        >>> combine_filters("eq(run_type, 'llm')")
        "eq(run_type, 'llm')"

        >>> combine_filters(None, None)
        None
    """
    # Filter out None values
    valid_filters = [f for f in filters if f is not None]

    if not valid_filters:
        return None

    if len(valid_filters) == 1:
        return valid_filters[0]

    # Build nested AND expression
    # LangSmith filter syntax uses: and(expr1, and(expr2, expr3))
    result = valid_filters[-1]
    for f in reversed(valid_filters[:-1]):
        result = f"and({f}, {result})"

    return result


def combine_filters_or(*filters: Optional[str]) -> Optional[str]:
    """Combine multiple filters with OR logic.

    Args:
        *filters: Variable number of filter expressions to combine.
                  None values are filtered out.

    Returns:
        Combined filter expression with OR logic, or None if no valid filters.

    Examples:
        >>> combine_filters_or("eq(run_type, 'llm')", "eq(run_type, 'chain')")
        "or(eq(run_type, 'llm'), eq(run_type, 'chain'))"
    """
    # Filter out None values
    valid_filters = [f for f in filters if f is not None]

    if not valid_filters:
        return None

    if len(valid_filters) == 1:
        return valid_filters[0]

    # Build nested OR expression
    result = valid_filters[-1]
    for f in reversed(valid_filters[:-1]):
        result = f"or({f}, {result})"

    return result
