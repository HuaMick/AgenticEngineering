"""Configuration workflow - core logic for configuration management.

Separates business logic from CLI handlers, enabling testability
and reuse across different entrypoints.
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml


class ConfigSource(Enum):
    """Configuration source layer in the onion model.

    Precedence (highest to lowest): CLI > ENV > PROJECT > GLOBAL > DEFAULT
    """

    DEFAULT = "default"
    GLOBAL = "global"  # ~/.config/agenticcli/config.yml
    PROJECT = "project"  # .agenticcli.yml in project root
    ENV = "environment"  # AGENTIC_* environment variables
    CLI = "cli"  # Command-line flags


@dataclass
class ConfigValue:
    """A configuration value with its source attribution.

    Attributes:
        value: The configuration value.
        source: Where the value came from.
        path: File path if source is file-based.
    """

    value: Any
    source: ConfigSource
    path: Optional[str] = None


# Default configuration values
DEFAULT_CONFIG = {
    "version": 1,
    "defaults": {
        "repo_abbreviation": "AE",
        "base_branch": "main",
    },
    "worktree": {
        "default_base": "main",
    },
    "plan": {
        "auto_scaffold": True,
    },
}

# Environment variable to config key mapping
ENV_VAR_MAPPING = {
    "AGENTIC_BASE_BRANCH": "defaults.base_branch",
    "AGENTIC_REPO_ABBREVIATION": "defaults.repo_abbreviation",
    "AGENTIC_WORKTREE_BASE": "worktree.default_base",
    "AGENTIC_PLAN_AUTO_SCAFFOLD": "plan.auto_scaffold",
}


@dataclass
class TieredConfigLoader:
    """Multi-layer configuration loader implementing the onion model.

    Layer precedence (highest to lowest):
    1. CLI flags (--config-key=value)
    2. Environment variables (AGENTIC_*)
    3. Project config (.agenticcli.yml)
    4. Global config (~/.config/agenticcli/config.yml)
    5. Defaults (hardcoded)

    Attributes:
        global_config_path: Path to global config file.
        project_config_path: Path to project config file.
        cli_overrides: CLI flag overrides.
    """

    global_config_path: Optional[Path] = None
    project_config_path: Optional[Path] = None
    cli_overrides: dict = field(default_factory=dict)

    def load(self) -> dict:
        """Load merged configuration from all layers.

        Returns:
            Merged configuration dictionary.
        """
        # Start with defaults
        merged = self._deep_copy(DEFAULT_CONFIG)

        # Layer 1: Global config
        if self.global_config_path and self.global_config_path.exists():
            global_config = self._load_yaml(self.global_config_path)
            if global_config:
                merged = self._deep_merge(merged, global_config)

        # Layer 2: Project config
        if self.project_config_path and self.project_config_path.exists():
            project_config = self._load_yaml(self.project_config_path)
            if project_config:
                merged = self._deep_merge(merged, project_config)

        # Layer 3: Environment variables
        env_config = self._load_env()
        if env_config:
            merged = self._deep_merge(merged, env_config)

        # Layer 4: CLI overrides
        if self.cli_overrides:
            merged = self._deep_merge(merged, self.cli_overrides)

        return merged

    def get(self, key: str) -> ConfigValue:
        """Get a specific config value with source attribution.

        Args:
            key: Config key in dot notation (e.g., "defaults.base_branch").

        Returns:
            ConfigValue with value and source information.
        """
        # Check CLI overrides first (highest precedence)
        cli_value = self._get_nested(self.cli_overrides, key)
        if cli_value is not None:
            return ConfigValue(value=cli_value, source=ConfigSource.CLI)

        # Check environment variables
        env_config = self._load_env()
        env_value = self._get_nested(env_config, key)
        if env_value is not None:
            return ConfigValue(value=env_value, source=ConfigSource.ENV)

        # Check project config
        if self.project_config_path and self.project_config_path.exists():
            project_config = self._load_yaml(self.project_config_path)
            if project_config:
                project_value = self._get_nested(project_config, key)
                if project_value is not None:
                    return ConfigValue(
                        value=project_value,
                        source=ConfigSource.PROJECT,
                        path=str(self.project_config_path),
                    )

        # Check global config
        if self.global_config_path and self.global_config_path.exists():
            global_config = self._load_yaml(self.global_config_path)
            if global_config:
                global_value = self._get_nested(global_config, key)
                if global_value is not None:
                    return ConfigValue(
                        value=global_value,
                        source=ConfigSource.GLOBAL,
                        path=str(self.global_config_path),
                    )

        # Fall back to defaults
        default_value = self._get_nested(DEFAULT_CONFIG, key)
        return ConfigValue(value=default_value, source=ConfigSource.DEFAULT)

    def get_merged_with_sources(self) -> dict:
        """Get full config with source attribution for each value.

        Returns:
            Dictionary where each leaf value is a ConfigValue object.
        """
        result = {}
        merged = self.load()
        self._add_sources_recursive(merged, result, "")
        return result

    def _add_sources_recursive(self, data: dict, result: dict, prefix: str) -> None:
        """Recursively add source attribution to config values."""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result[key] = {}
                self._add_sources_recursive(value, result[key], full_key)
            else:
                config_value = self.get(full_key)
                result[key] = {
                    "value": config_value.value,
                    "source": config_value.source.value,
                    "path": config_value.path,
                }

    def _load_yaml(self, path: Path) -> Optional[dict]:
        """Load YAML file safely."""
        try:
            return yaml.safe_load(path.read_text()) or {}
        except (yaml.YAMLError, OSError):
            return None

    def _load_env(self) -> dict:
        """Load configuration from environment variables."""
        result = {}
        for env_var, config_key in ENV_VAR_MAPPING.items():
            value = os.environ.get(env_var)
            if value is not None:
                # Parse boolean values
                if value.lower() in ("true", "1", "yes"):
                    value = True
                elif value.lower() in ("false", "0", "no"):
                    value = False
                self._set_nested(result, config_key, value)
        return result

    @staticmethod
    def _get_nested(data: dict, key: str) -> Any:
        """Get a value using dot notation."""
        if not data:
            return None
        keys = key.split(".")
        value = data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value

    @staticmethod
    def _set_nested(data: dict, key: str, value: Any) -> None:
        """Set a value using dot notation."""
        keys = key.split(".")
        target = data
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    @staticmethod
    def _deep_copy(data: dict) -> dict:
        """Create a deep copy of a dictionary."""
        import copy

        return copy.deepcopy(data)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = TieredConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


@dataclass
class ConfigResult:
    """Result from a configuration operation.

    Attributes:
        success: Whether the operation succeeded.
        message: Human-readable result message.
        data: Optional data payload (config values, etc.).
    """

    success: bool
    message: str
    data: Optional[dict] = None


@dataclass
class ConfigWorkflow:
    """Core logic for configuration management.

    Separates config operations from CLI handlers for testability.
    All file I/O and validation happens here.
    """

    config_dir: Path
    config_file: Path = field(init=False)
    prefs_file: Path = field(init=False)

    def __post_init__(self):
        """Initialize derived paths."""
        self.config_file = self.config_dir / "config.yml"
        self.prefs_file = self.config_dir / "preferences.yml"

    def ensure_dir(self) -> Path:
        """Ensure the config directory exists.

        Returns:
            Path to config directory.
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)
        return self.config_dir

    def show(self) -> ConfigResult:
        """Get current configuration.

        Returns:
            ConfigResult with config data or error.
        """
        if not self.config_file.exists():
            return ConfigResult(
                success=False,
                message="No configuration found. Run 'agentic config init' to create one.",
                data=None,
            )

        try:
            content = yaml.safe_load(self.config_file.read_text())
            return ConfigResult(
                success=True,
                message=f"Configuration loaded from {self.config_file}",
                data={"path": str(self.config_file), "config": content or {}},
            )
        except yaml.YAMLError as e:
            return ConfigResult(
                success=False,
                message=f"Error parsing config file: {e}",
                data=None,
            )

    def init(self, overwrite: bool = False, defaults: Optional[dict] = None) -> ConfigResult:
        """Initialize configuration.

        Args:
            overwrite: Whether to overwrite existing config.
            defaults: Optional defaults to merge into config.

        Returns:
            ConfigResult with creation status.
        """
        self.ensure_dir()

        if self.config_file.exists() and not overwrite:
            return ConfigResult(
                success=False,
                message=f"Configuration already exists: {self.config_file}",
                data={"path": str(self.config_file)},
            )

        # Create default config
        default_config = {
            "version": 1,
            "defaults": {
                "repo_abbreviation": "AE",
                "base_branch": "main",
            },
        }

        # Merge custom defaults
        if defaults:
            default_config["defaults"].update(defaults)

        with open(self.config_file, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False)

        # Create empty preferences if not exists
        created_prefs = False
        if not self.prefs_file.exists():
            default_prefs = {
                "worktree": {
                    "default_base": "main",
                },
                "plan": {
                    "auto_scaffold": True,
                },
            }
            with open(self.prefs_file, "w") as f:
                yaml.dump(default_prefs, f, default_flow_style=False)
            created_prefs = True

        return ConfigResult(
            success=True,
            message=f"Created configuration: {self.config_file}",
            data={
                "config_file": str(self.config_file),
                "prefs_file": str(self.prefs_file) if created_prefs else None,
                "created_prefs": created_prefs,
            },
        )

    def get_pref(self, key: str) -> ConfigResult:
        """Get a preference value.

        Args:
            key: Preference key (supports dot notation).

        Returns:
            ConfigResult with value or error.
        """
        if not self.prefs_file.exists():
            return ConfigResult(
                success=False,
                message="No preferences found. Run 'agentic config init' to create them.",
                data=None,
            )

        try:
            prefs = yaml.safe_load(self.prefs_file.read_text())
            if not prefs:
                prefs = {}

            value = self._get_nested_value(prefs, key)
            if value is None:
                return ConfigResult(
                    success=False,
                    message=f"Key not found: {key}",
                    data=None,
                )

            return ConfigResult(
                success=True,
                message=f"Found {key}",
                data={"key": key, "value": value},
            )
        except yaml.YAMLError as e:
            return ConfigResult(
                success=False,
                message=f"Error parsing preferences file: {e}",
                data=None,
            )

    def set_pref(self, key: str, value: Any) -> ConfigResult:
        """Set a preference value.

        Args:
            key: Preference key (supports dot notation).
            value: Value to set (will be JSON-parsed if possible).

        Returns:
            ConfigResult with set status.
        """
        self.ensure_dir()

        if self.prefs_file.exists():
            try:
                prefs = yaml.safe_load(self.prefs_file.read_text())
                if not prefs:
                    prefs = {}
            except yaml.YAMLError:
                prefs = {}
        else:
            prefs = {}

        # Parse value (try JSON first, then use as string)
        if isinstance(value, str):
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value
        else:
            parsed_value = value

        self._set_nested_value(prefs, key, parsed_value)

        with open(self.prefs_file, "w") as f:
            yaml.dump(prefs, f, default_flow_style=False)

        return ConfigResult(
            success=True,
            message=f"Set {key} = {parsed_value}",
            data={"key": key, "value": parsed_value},
        )

    def list_prefs(self) -> ConfigResult:
        """List all preferences.

        Returns:
            ConfigResult with all preferences.
        """
        if not self.prefs_file.exists():
            return ConfigResult(
                success=False,
                message="No preferences found. Run 'agentic config init' to create them.",
                data=None,
            )

        try:
            prefs = yaml.safe_load(self.prefs_file.read_text())
            return ConfigResult(
                success=True,
                message=f"Preferences loaded from {self.prefs_file}",
                data={"path": str(self.prefs_file), "preferences": prefs or {}},
            )
        except yaml.YAMLError as e:
            return ConfigResult(
                success=False,
                message=f"Error parsing preferences file: {e}",
                data=None,
            )

    def delete_pref(self, key: str) -> ConfigResult:
        """Delete a preference value.

        Args:
            key: Preference key (supports dot notation).

        Returns:
            ConfigResult with deletion status.
        """
        if not self.prefs_file.exists():
            return ConfigResult(
                success=False,
                message="No preferences found. Run 'agentic config init' to create them.",
                data=None,
            )

        try:
            prefs = yaml.safe_load(self.prefs_file.read_text())
            if not prefs:
                prefs = {}

            if not self._delete_nested_value(prefs, key):
                return ConfigResult(
                    success=False,
                    message=f"Key not found: {key}",
                    data=None,
                )

            with open(self.prefs_file, "w") as f:
                yaml.dump(prefs, f, default_flow_style=False)

            return ConfigResult(
                success=True,
                message=f"Deleted {key}",
                data={"key": key, "deleted": True},
            )
        except yaml.YAMLError as e:
            return ConfigResult(
                success=False,
                message=f"Error parsing preferences file: {e}",
                data=None,
            )

    def clear_prefs(self) -> ConfigResult:
        """Clear all preferences.

        Returns:
            ConfigResult with clear status.
        """
        if not self.prefs_file.exists():
            return ConfigResult(
                success=False,
                message="No preferences found. Nothing to clear.",
                data=None,
            )

        with open(self.prefs_file, "w") as f:
            yaml.dump({}, f, default_flow_style=False)

        return ConfigResult(
            success=True,
            message="All preferences cleared.",
            data={"cleared": True},
        )

    @staticmethod
    def _get_nested_value(data: dict, key: str) -> Any:
        """Get a value using dot notation."""
        keys = key.split(".")
        value = data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value

    @staticmethod
    def _set_nested_value(data: dict, key: str, value: Any) -> None:
        """Set a value using dot notation."""
        keys = key.split(".")
        target = data
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    @staticmethod
    def _delete_nested_value(data: dict, key: str) -> bool:
        """Delete a value using dot notation. Returns True if deleted."""
        keys = key.split(".")
        target = data
        for k in keys[:-1]:
            if isinstance(target, dict) and k in target:
                target = target[k]
            else:
                return False

        if isinstance(target, dict) and keys[-1] in target:
            del target[keys[-1]]
            return True
        return False
