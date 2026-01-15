"""AgenticLangSmith - LangSmith API wrapper for AgenticCLI."""

__version__ = "0.1.0"

# Service classes and exceptions
from agenticlangsmith.service import (
    LangSmithService,
    LangSmithConfigError,
    LangSmithAPIError,
)

# Filter builder functions
from agenticlangsmith.filters import (
    build_time_filter,
    build_type_filter,
    build_error_filter,
    build_tag_filter,
    build_name_filter,
    build_latency_filter,
    build_token_filter,
    combine_filters,
    combine_filters_or,
)

__all__ = [
    "__version__",
    # Service
    "LangSmithService",
    "LangSmithConfigError",
    "LangSmithAPIError",
    # Filters
    "build_time_filter",
    "build_type_filter",
    "build_error_filter",
    "build_tag_filter",
    "build_name_filter",
    "build_latency_filter",
    "build_token_filter",
    "combine_filters",
    "combine_filters_or",
]
