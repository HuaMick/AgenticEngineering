"""
AgenticGuidance Services

This package contains the business logic services extracted from AgenticCLI workflows.
Each module provides a specific domain of functionality:

- config: Configuration management with tiered loading
- state: Process state registry and file locking
- context: Plan resolution and role context loading
- plan: Plan movement and archival workflows + CRUD operations (PlanService)
- plan_repository: TinyDB-backed storage repository for plans and tasks
- environment: Environment variable management
- template: Jinja2 template rendering
- preset: Task preset loading
- session: Tmux session lifecycle management
- claude_session: Claude Code session state management
- ralph: Ralph Loop plan discovery and prioritization
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
    PhaseData,
    PlanCreateResult,
    PlanData,
    PlanDeleteResult,
    PlanMetadata,
    PlanMovementWorkflow,
    PlanService,
    PlanUpdateResult,
    TaskData,
    TaskMoveResult,
    ValidationResult,
)
from .plan_repository import PlanRepository
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
from .claude_session import (
    ClaudeSessionStatus,
    SessionEntry,
    SessionStateService,
)
from .session import (
    SessionInfo,
    SessionResult,
    SessionService,
    SessionState,
)
from .session_config import (
    SessionConfig,
    SessionConfigLoader,
    SessionNamingConvention,
    SessionNamingResult,
    session_lifecycle_create,
)
from .template import (
    TemplateContext,
    TemplateWorkflow,
    create_template_context_from_project,
)
from .ralph import (
    PlanAction,
    PlanInfo,
    RalphLoopService,
)
from .task import (
    Task,
    TaskService,
    TaskStatus,
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
    "PhaseData",
    "PlanCreateResult",
    "PlanData",
    "PlanDeleteResult",
    "PlanMetadata",
    "PlanMovementWorkflow",
    "PlanService",
    "PlanUpdateResult",
    "TaskData",
    "TaskMoveResult",
    "ValidationResult",
    "PlanRepository",
    # Preset services
    "PresetLoadResult",
    "TaskPresetWorkflow",
    # State services
    "FileLock",
    "ProcessEntry",
    "ProcessState",
    "StateRegistry",
    # Claude session services
    "ClaudeSessionStatus",
    "SessionEntry",
    "SessionStateService",
    # Session services
    "SessionConfig",
    "SessionConfigLoader",
    "SessionInfo",
    "SessionNamingConvention",
    "SessionNamingResult",
    "SessionResult",
    "SessionService",
    "SessionState",
    "session_lifecycle_create",
    # Template services
    "TemplateContext",
    "TemplateWorkflow",
    "create_template_context_from_project",
    # Ralph Loop services
    "PlanAction",
    "PlanInfo",
    "RalphLoopService",
    # Task services
    "Task",
    "TaskService",
    "TaskStatus",
]
