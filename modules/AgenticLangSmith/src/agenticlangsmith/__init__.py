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

# Friction analysis
from agenticlangsmith.friction import (
    FrictionAnalyzer,
    FrictionReport,
    FrictionPattern,
    FrictionPatternType,
    Severity,
)

# Resolution recommendations
from agenticlangsmith.resolution import (
    ResolutionRecommender,
    ResolutionPlan,
    ResolutionRecommendation,
    ResolutionType,
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
    # Friction analysis
    "FrictionAnalyzer",
    "FrictionReport",
    "FrictionPattern",
    "FrictionPatternType",
    "Severity",
    # Resolution
    "ResolutionRecommender",
    "ResolutionPlan",
    "ResolutionRecommendation",
    "ResolutionType",
]
