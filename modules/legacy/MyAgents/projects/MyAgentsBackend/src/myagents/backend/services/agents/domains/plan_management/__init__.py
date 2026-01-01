"""Plan management domain for reading/writing live plan YAML files.

This domain provides utilities for managing execution plans,
particularly for multi-agent orchestration scenarios.
"""

from .plan_manager import PlanManager

__all__ = ["PlanManager"]
