"""
Session configuration schema and validation for AgenticTmux.

Provides configuration management and naming conventions for tmux sessions.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class SessionConfig:
    """Configuration for session management.

    Attributes:
        default_shell: Default shell for new sessions.
        auto_attach: Whether to auto-attach after create.
        naming_pattern: Regex pattern for valid session names.
        max_sessions: Maximum number of concurrent sessions (0 = unlimited).
        auto_cleanup: Whether to auto-cleanup dead sessions.
        persist_registry: Whether to persist session registry.
        worktree_auto_link: Auto-link sessions to worktrees.
        plan_auto_link: Auto-link sessions to plan folders.
    """

    default_shell: str = "/bin/bash"
    auto_attach: bool = False
    naming_pattern: str = r"^[a-zA-Z][a-zA-Z0-9_-]{0,49}$"
    max_sessions: int = 0
    auto_cleanup: bool = True
    persist_registry: bool = True
    worktree_auto_link: bool = True
    plan_auto_link: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "default_shell": self.default_shell,
            "auto_attach": self.auto_attach,
            "naming_pattern": self.naming_pattern,
            "max_sessions": self.max_sessions,
            "auto_cleanup": self.auto_cleanup,
            "persist_registry": self.persist_registry,
            "worktree_auto_link": self.worktree_auto_link,
            "plan_auto_link": self.plan_auto_link,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionConfig":
        """Create from dictionary."""
        return cls(
            default_shell=data.get("default_shell", "/bin/bash"),
            auto_attach=data.get("auto_attach", False),
            naming_pattern=data.get("naming_pattern", r"^[a-zA-Z][a-zA-Z0-9_-]{0,49}$"),
            max_sessions=data.get("max_sessions", 0),
            auto_cleanup=data.get("auto_cleanup", True),
            persist_registry=data.get("persist_registry", True),
            worktree_auto_link=data.get("worktree_auto_link", True),
            plan_auto_link=data.get("plan_auto_link", True),
        )


@dataclass
class SessionNamingResult:
    """Result of session name validation."""

    valid: bool
    name: str
    message: str
    suggested: Optional[str] = None


class SessionNamingConvention:
    """Session naming conventions and validation.

    Naming conventions:
    - Must start with a letter
    - Can contain letters, numbers, underscores, hyphens
    - Max 50 characters
    - No spaces or special characters
    - Reserved names: main, master, default, all

    Recommended patterns:
    - worktree-based: {repo}-{branch} e.g., "myproject-feature-auth"
    - plan-based: {plan_id} e.g., "260126AT"
    - task-based: {plan_id}-{task_id} e.g., "260126AT-AT-005"
    """

    RESERVED_NAMES = {"main", "master", "default", "all", "new", "list", "kill"}
    DEFAULT_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_-]{0,49}$"
    MAX_LENGTH = 50

    def __init__(self, pattern: Optional[str] = None):
        """Initialize naming convention.

        Args:
            pattern: Custom regex pattern for validation.
        """
        self.pattern = re.compile(pattern or self.DEFAULT_PATTERN)

    def validate(self, name: str) -> SessionNamingResult:
        """Validate a session name.

        Args:
            name: Session name to validate.

        Returns:
            SessionNamingResult with validation status.
        """
        if not name:
            return SessionNamingResult(
                valid=False,
                name=name,
                message="Session name cannot be empty",
            )

        if len(name) > self.MAX_LENGTH:
            suggested = name[:self.MAX_LENGTH]
            return SessionNamingResult(
                valid=False,
                name=name,
                message=f"Session name too long (max {self.MAX_LENGTH} chars)",
                suggested=suggested,
            )

        if name.lower() in self.RESERVED_NAMES:
            return SessionNamingResult(
                valid=False,
                name=name,
                message=f"'{name}' is a reserved name",
                suggested=f"{name}-session",
            )

        if not self.pattern.match(name):
            # Generate a suggested valid name
            suggested = self._sanitize_name(name)
            return SessionNamingResult(
                valid=False,
                name=name,
                message="Invalid session name. Must start with letter, contain only letters, numbers, underscores, hyphens",
                suggested=suggested,
            )

        return SessionNamingResult(
            valid=True,
            name=name,
            message="Valid session name",
        )

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name to make it valid.

        Args:
            name: Name to sanitize.

        Returns:
            Sanitized name.
        """
        # Replace spaces and invalid chars with hyphens
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "-", name)
        # Remove consecutive hyphens
        sanitized = re.sub(r"-+", "-", sanitized)
        # Remove leading/trailing hyphens
        sanitized = sanitized.strip("-")
        # Ensure starts with letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "s-" + sanitized
        # Truncate to max length
        sanitized = sanitized[:self.MAX_LENGTH]
        # Handle empty result
        if not sanitized:
            sanitized = "session"
        return sanitized

    def generate_from_worktree(self, worktree_path: str) -> str:
        """Generate session name from worktree path.

        Args:
            worktree_path: Path to worktree.

        Returns:
            Generated session name.
        """
        path = Path(worktree_path)
        name = path.name

        # Common pattern: repo-branch (e.g., AgenticEngineering-feature)
        if "-" in name:
            # Keep the branch part
            parts = name.split("-", 1)
            if len(parts) > 1:
                name = parts[1]  # Use branch name

        return self._sanitize_name(name)

    def generate_from_plan(self, plan_folder: str) -> str:
        """Generate session name from plan folder.

        Args:
            plan_folder: Plan folder name (e.g., 260126AT_agentictmux).

        Returns:
            Generated session name.
        """
        # Extract plan ID (first part before underscore)
        if "_" in plan_folder:
            plan_id = plan_folder.split("_")[0]
            return self._sanitize_name(plan_id)
        return self._sanitize_name(plan_folder)


class SessionConfigLoader:
    """Loader for session configuration from files."""

    DEFAULT_CONFIG_PATH = Path.home() / ".config" / "agenticcli" / "session_config.yml"

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize config loader.

        Args:
            config_path: Path to config file.
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH

    def load(self) -> SessionConfig:
        """Load configuration from file.

        Returns:
            SessionConfig with loaded or default values.
        """
        if not self.config_path.exists():
            return SessionConfig()

        try:
            data = yaml.safe_load(self.config_path.read_text())
            if data and isinstance(data, dict):
                return SessionConfig.from_dict(data.get("session", data))
        except (yaml.YAMLError, IOError):
            pass

        return SessionConfig()

    def save(self, config: SessionConfig) -> bool:
        """Save configuration to file.

        Args:
            config: Configuration to save.

        Returns:
            True if saved successfully.
        """
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"session": config.to_dict()}
            self.config_path.write_text(yaml.dump(data, default_flow_style=False))
            return True
        except IOError:
            return False


# Lifecycle patterns as documented helpers

def session_lifecycle_create(
    service,
    name: str,
    worktree: Optional[str] = None,
    plan_folder: Optional[str] = None,
    config: Optional[SessionConfig] = None,
):
    """Standard lifecycle pattern for session creation.

    1. Validate name
    2. Check max sessions limit
    3. Auto-cleanup dead sessions
    4. Create session
    5. Auto-link worktree/plan if configured

    Args:
        service: SessionService instance.
        name: Session name.
        worktree: Optional worktree path.
        plan_folder: Optional plan folder.
        config: Optional configuration.

    Returns:
        SessionResult from service.create().
    """
    if config is None:
        config = SessionConfigLoader().load()

    # Validate name
    naming = SessionNamingConvention(config.naming_pattern)
    validation = naming.validate(name)
    if not validation.valid:
        from agenticguidance.services.session import SessionResult
        return SessionResult(
            success=False,
            message=validation.message,
            data={"suggested": validation.suggested} if validation.suggested else None,
        )

    # Auto-cleanup if configured
    if config.auto_cleanup:
        service.cleanup_dead()

    # Check max sessions
    if config.max_sessions > 0:
        active = len([s for s in service.list() if s.state.value == "running"])
        if active >= config.max_sessions:
            from agenticguidance.services.session import SessionResult
            return SessionResult(
                success=False,
                message=f"Max sessions ({config.max_sessions}) reached. Kill a session first.",
            )

    # Create session
    return service.create(
        name=name,
        worktree=worktree if config.worktree_auto_link else None,
        plan_folder=plan_folder if config.plan_auto_link else None,
    )
