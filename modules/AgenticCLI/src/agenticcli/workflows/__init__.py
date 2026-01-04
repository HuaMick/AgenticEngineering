"""Workflow layer for AgenticCLI.

This package separates core business logic from CLI handlers.
Each workflow encapsulates operations that may be invoked from
multiple entrypoints (CLI, scripts, tests).
"""

from agenticcli.workflows.config_workflow import ConfigResult, ConfigWorkflow

__all__ = ["ConfigWorkflow", "ConfigResult"]
