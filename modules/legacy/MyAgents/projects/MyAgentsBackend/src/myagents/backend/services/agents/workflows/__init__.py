"""Workflows package for agents.

This module contains workflow orchestration logic that coordinates
between domains and provides clean entrypoints for CLI commands.

Available workflows:
- HealthCheckWorkflow: CLI and project health checks, context detection
- HelpWorkflow: Help, version, and documentation display
- SetupWorkflow: Initial setup and configuration management
- StudioWorkflow: LangGraph Studio lifecycle management
- secrets_workflow: Secret management (function-based)
- builder_agent: Builder agent workflow (LangGraph-based)
"""

# Export function-based workflows (backward compatibility)
from .secrets_workflow import get_secret, clear_secret_cache

# Export class-based workflows
from .health_check_workflow import HealthCheckWorkflow
from .help_workflow import HelpWorkflow
from .setup_workflow import SetupWorkflow
# Backward compatibility alias
from .setup_workflow import PreferencesWorkflow
from .studio_workflow import StudioWorkflow

__all__ = [
    # Function-based workflows
    "get_secret",
    "clear_secret_cache",
    # Class-based workflows
    "HealthCheckWorkflow",
    "HelpWorkflow",
    "SetupWorkflow",
    "PreferencesWorkflow",  # Backward compatibility
    "StudioWorkflow",
]
