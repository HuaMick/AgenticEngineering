"""Workflow layer for AgenticCLI.

This package separates core business logic from CLI handlers.
Each workflow encapsulates operations that may be invoked from
multiple entrypoints (CLI, scripts, tests).
"""

from agenticcli.workflows.config_workflow import ConfigResult, ConfigWorkflow
from agenticcli.workflows.context_workflow import MainFirstPlanResolver
from agenticcli.workflows.task_workflow import PresetLoadResult, TaskPresetWorkflow

__all__ = [
    "ConfigWorkflow",
    "ConfigResult",
    "TaskPresetWorkflow",
    "PresetLoadResult",
    "MainFirstPlanResolver",
]
