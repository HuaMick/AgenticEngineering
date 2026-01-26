"""
AgenticGuidance Services

This package contains the business logic services extracted from AgenticCLI workflows.
Each module provides a specific domain of functionality:

- config: Configuration management with tiered loading
- state: Process state registry and file locking
- context: Plan resolution and role context loading
- plan: Plan movement and archival workflows
- environment: Environment variable management
- template: Jinja2 template rendering
- preset: Task preset loading
"""

from .context import (
    MainFirstPlanResolver,
    get_role_process,
    get_role_inputs_manifest,
    generate_agent_bootstrap,
)
from .state import (
    FileLock,
    ProcessEntry,
    ProcessState,
    StateRegistry,
)

__all__ = [
    # Context services
    "MainFirstPlanResolver",
    "get_role_process",
    "get_role_inputs_manifest",
    "generate_agent_bootstrap",
    # State services
    "FileLock",
    "ProcessEntry",
    "ProcessState",
    "StateRegistry",
]
