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

from .config import (
    ConfigResult,
    ConfigSource,
    ConfigValue,
    ConfigWorkflow,
    DEFAULT_CONFIG,
    ENV_VAR_MAPPING,
    TieredConfigLoader,
)
from .context import (
    MainFirstPlanResolver,
    generate_agent_bootstrap,
    get_role_inputs_manifest,
    get_role_process,
)
from .environment import (
    EnvironmentProvider,
    EnvVar,
    SecretSource,
    is_secret_name,
)
from .plan import (
    FolderMoveResult,
    GitSafetyChecker,
    MoveResult,
    PlanMovementWorkflow,
    TaskMoveResult,
)
from .preset import (
    PresetLoadResult,
    TaskPresetWorkflow,
)
from .state import (
    FileLock,
    ProcessEntry,
    ProcessState,
    StateRegistry,
)
from .template import (
    TemplateContext,
    TemplateWorkflow,
    create_template_context_from_project,
)

__all__ = [
    # Config services
    "ConfigResult",
    "ConfigSource",
    "ConfigValue",
    "ConfigWorkflow",
    "DEFAULT_CONFIG",
    "ENV_VAR_MAPPING",
    "TieredConfigLoader",
    # Context services
    "MainFirstPlanResolver",
    "generate_agent_bootstrap",
    "get_role_inputs_manifest",
    "get_role_process",
    # Environment services
    "EnvironmentProvider",
    "EnvVar",
    "SecretSource",
    "is_secret_name",
    # Plan services
    "FolderMoveResult",
    "GitSafetyChecker",
    "MoveResult",
    "PlanMovementWorkflow",
    "TaskMoveResult",
    # Preset services
    "PresetLoadResult",
    "TaskPresetWorkflow",
    # State services
    "FileLock",
    "ProcessEntry",
    "ProcessState",
    "StateRegistry",
    # Template services
    "TemplateContext",
    "TemplateWorkflow",
    "create_template_context_from_project",
]
