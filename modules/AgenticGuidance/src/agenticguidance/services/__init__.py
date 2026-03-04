"""
AgenticGuidance Services

This package contains the business logic services extracted from AgenticCLI workflows.
Each module provides a specific domain of functionality:

- config: Configuration management with tiered loading
- state: Process state registry and file locking
- context: Epic resolution and role context loading
- epic: Epic movement and archival workflows + CRUD operations (EpicService)
- epic_repository: TinyDB-backed storage repository for epics and tickets
- environment: Environment variable management
- template: Jinja2 template rendering
- preset: Ticket preset loading
- session: Tmux session lifecycle management
- claude_session: Claude Code session state management
- ralph: Ralph Loop epic discovery and prioritization
- ticket: Ticket CRUD operations (TicketService)
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
from .epic import (
    EpicCreateResult,
    EpicData,
    EpicDeleteResult,
    EpicMetadata,
    EpicMovementWorkflow,
    EpicService,
    EpicUpdateResult,
    FolderMoveResult,
    GitSafetyChecker,
    MoveResult,
    PhaseData,
    TicketData,
    TicketMoveResult,
    ValidationResult,
)
from .epic_repository import EpicRepository
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
    EpicAction,
    EpicInfo,
    PlanAction,
    PlanInfo,
    RalphLoopService,
)
from .ticket import (
    Ticket,
    TicketService,
    TicketStatus,
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
    # Epic services (new canonical names)
    "EpicCreateResult",
    "EpicData",
    "EpicDeleteResult",
    "EpicMetadata",
    "EpicMovementWorkflow",
    "EpicService",
    "EpicUpdateResult",
    "EpicRepository",
    # Shared movement types (used by both epic and plan modules)
    "FolderMoveResult",
    "GitSafetyChecker",
    "MoveResult",
    "PhaseData",
    "TicketData",
    "TicketMoveResult",
    "ValidationResult",
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
    "EpicAction",
    "EpicInfo",
    "PlanAction",  # backward-compat alias for EpicAction
    "PlanInfo",    # backward-compat alias for EpicInfo
    "RalphLoopService",
    # Ticket services (new canonical names)
    "Ticket",
    "TicketService",
    "TicketStatus",
]
