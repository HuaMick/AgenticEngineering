"""
AgenticGuidance Services Layer

This package provides the business logic for agentic workflows, including:
- Configuration management (TieredConfigLoader, ConfigWorkflow)
- State management (StateRegistry, FileLock)
- Environment variable handling (EnvironmentProvider)
- Context resolution (MainFirstPlanResolver)
- Template rendering (TemplateWorkflow)
- Plan management (PlanMovementWorkflow, GitSafetyChecker)
- Task presets (TaskPresetWorkflow)

These services are designed to be consumed by presentation layers such as:
- AgenticCLI (command-line interface)
- AgenticTmux (terminal session management)
- AgenticVoice (voice interface)
"""

__version__ = "0.1.0"

# Services will be exported as they are implemented
# from .services.config import ConfigWorkflow, TieredConfigLoader, ConfigResult
# from .services.state import StateRegistry, FileLock, ProcessState
# from .services.context import MainFirstPlanResolver
# from .services.plan import PlanMovementWorkflow, GitSafetyChecker
# from .services.environment import EnvironmentProvider
# from .services.template import TemplateWorkflow
# from .services.preset import TaskPresetWorkflow

__all__ = [
    "__version__",
    # Exports will be added as services are implemented
]
