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
- story: User story data model and service (StoryService)
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
    EPIC_STATUS_MIGRATION,
    EpicCreateResult,
    EpicData,
    EpicDeleteResult,
    EpicMetadata,
    EpicMovementWorkflow,
    EpicService,
    EpicStatus,
    EpicUpdateResult,
    FolderMoveResult,
    GitSafetyChecker,
    MoveResult,
    PhaseData,
    TicketData,
    TicketMoveResult,
    ValidationResult,
    normalize_epic_status,
)
from .epic_repository import EpicRepository, DEFAULT_PRIORITY, normalize_priority
from .dependency import DependencyService
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
from .story import Story, StoryService
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
    "EPIC_STATUS_MIGRATION",
    "EpicCreateResult",
    "EpicData",
    "EpicDeleteResult",
    "EpicMetadata",
    "EpicMovementWorkflow",
    "EpicService",
    "EpicStatus",
    "EpicUpdateResult",
    "EpicRepository",
    "DEFAULT_PRIORITY",
    "normalize_priority",
    "DependencyService",
    "normalize_epic_status",
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
    # Story services
    "Story",
    "StoryService",
    # Ticket services (new canonical names)
    "Ticket",
    "TicketService",
    "TicketStatus",
]
