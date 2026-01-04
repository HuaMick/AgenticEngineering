"""Environment Workflow - secure environment injection for subprocesses.

Provides context-aware environment variable injection without creating
.env files on disk. Secrets remain in memory only.
"""

import os
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class SecretSource(Enum):
    """Source of a secret/environment variable."""

    CONFIG = "config"  # From config files
    ENV = "env"  # From environment
    PREFS = "prefs"  # From preferences
    RUNTIME = "runtime"  # Injected at runtime


@dataclass
class EnvVar:
    """Environment variable with source tracking."""

    name: str
    value: str
    source: SecretSource
    is_secret: bool = False
    masked_value: Optional[str] = None

    def __post_init__(self):
        """Set masked value for secrets."""
        if self.is_secret and self.masked_value is None:
            if len(self.value) > 4:
                self.masked_value = self.value[:2] + "*" * (len(self.value) - 4) + self.value[-2:]
            else:
                self.masked_value = "****"

    def display_value(self) -> str:
        """Get value for display (masked if secret)."""
        if self.is_secret:
            return self.masked_value or "****"
        return self.value


# Patterns that indicate a variable contains sensitive data
SECRET_PATTERNS = [
    r".*PASSWORD.*",
    r".*SECRET.*",
    r".*TOKEN.*",
    r".*KEY.*",
    r".*API_KEY.*",
    r".*PRIVATE.*",
    r".*CREDENTIAL.*",
    r".*AUTH.*",
]


def is_secret_name(name: str) -> bool:
    """Check if a variable name suggests it contains sensitive data.

    Args:
        name: Environment variable name.

    Returns:
        True if name matches secret patterns.
    """
    name_upper = name.upper()
    for pattern in SECRET_PATTERNS:
        if re.match(pattern, name_upper):
            return True
    return False


@dataclass
class EnvironmentProvider:
    """Provides environment variables for subprocess execution.

    Merges configuration from multiple sources with proper precedence:
    1. Runtime overrides (highest)
    2. Environment variables
    3. Preferences
    4. Config files (lowest)

    Secrets are never written to disk and are masked in logs.
    """

    config_dir: Optional[Path] = None
    project_root: Optional[Path] = None
    runtime_overrides: dict = field(default_factory=dict)
    _cache: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        """Initialize default paths if not provided."""
        if self.config_dir is None:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                self.config_dir = Path(xdg_config) / "agenticcli"
            else:
                self.config_dir = Path.home() / ".config" / "agenticcli"

    def get_all(self) -> dict[str, EnvVar]:
        """Get all environment variables with sources.

        Returns:
            Dictionary mapping variable names to EnvVar objects.
        """
        env_vars = {}

        # 1. Load from config files (lowest priority)
        env_vars.update(self._load_from_config())

        # 2. Load from preferences
        env_vars.update(self._load_from_prefs())

        # 3. Load from environment (existing env vars)
        env_vars.update(self._load_from_env())

        # 4. Apply runtime overrides (highest priority)
        for name, value in self.runtime_overrides.items():
            env_vars[name] = EnvVar(
                name=name,
                value=str(value),
                source=SecretSource.RUNTIME,
                is_secret=is_secret_name(name),
            )

        return env_vars

    def _load_from_config(self) -> dict[str, EnvVar]:
        """Load environment variables from config files."""
        env_vars = {}

        if self.config_dir:
            config_file = self.config_dir / "config.yml"
            if config_file.exists():
                try:
                    data = yaml.safe_load(config_file.read_text())
                    if data and "environment" in data:
                        for name, value in data["environment"].items():
                            env_vars[name] = EnvVar(
                                name=name,
                                value=str(value),
                                source=SecretSource.CONFIG,
                                is_secret=is_secret_name(name),
                            )
                except yaml.YAMLError:
                    pass

        # Check project-level config
        if self.project_root:
            project_config = self.project_root / ".agenticcli.yml"
            if project_config.exists():
                try:
                    data = yaml.safe_load(project_config.read_text())
                    if data and "environment" in data:
                        for name, value in data["environment"].items():
                            env_vars[name] = EnvVar(
                                name=name,
                                value=str(value),
                                source=SecretSource.CONFIG,
                                is_secret=is_secret_name(name),
                            )
                except yaml.YAMLError:
                    pass

        return env_vars

    def _load_from_prefs(self) -> dict[str, EnvVar]:
        """Load environment variables from preferences."""
        env_vars = {}

        if self.config_dir:
            prefs_file = self.config_dir / "preferences.yml"
            if prefs_file.exists():
                try:
                    data = yaml.safe_load(prefs_file.read_text())
                    if data and "environment" in data:
                        for name, value in data["environment"].items():
                            env_vars[name] = EnvVar(
                                name=name,
                                value=str(value),
                                source=SecretSource.PREFS,
                                is_secret=is_secret_name(name),
                            )
                except yaml.YAMLError:
                    pass

        return env_vars

    def _load_from_env(self) -> dict[str, EnvVar]:
        """Load relevant environment variables from current environment.

        Only loads AGENTIC_* prefixed variables.
        """
        env_vars = {}

        for name, value in os.environ.items():
            if name.startswith("AGENTIC_"):
                env_vars[name] = EnvVar(
                    name=name,
                    value=value,
                    source=SecretSource.ENV,
                    is_secret=is_secret_name(name),
                )

        return env_vars

    def get_subprocess_env(self) -> dict[str, str]:
        """Get environment dictionary for subprocess execution.

        Merges current environment with configured variables.

        Returns:
            Dictionary suitable for subprocess.run(env=...).
        """
        # Start with current environment
        env = os.environ.copy()

        # Add configured variables
        for name, var in self.get_all().items():
            env[name] = var.value

        return env

    def run_with_env(
        self,
        command: list[str],
        cwd: Optional[Path] = None,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a command with injected environment.

        Args:
            command: Command and arguments to run.
            cwd: Working directory.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            CompletedProcess result.
        """
        env = self.get_subprocess_env()

        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=capture_output,
            text=True,
        )

    def set_runtime(self, name: str, value: str) -> None:
        """Set a runtime environment variable.

        Args:
            name: Variable name.
            value: Variable value.
        """
        self.runtime_overrides[name] = value

    def clear_runtime(self, name: Optional[str] = None) -> None:
        """Clear runtime environment variables.

        Args:
            name: Specific variable to clear, or None for all.
        """
        if name is None:
            self.runtime_overrides.clear()
        elif name in self.runtime_overrides:
            del self.runtime_overrides[name]

    def export_shell(self) -> str:
        """Export environment variables in shell format.

        Returns:
            String of export statements for shell sourcing.
        """
        lines = []
        for name, var in sorted(self.get_all().items()):
            # Escape single quotes in value
            escaped = var.value.replace("'", "'\"'\"'")
            lines.append(f"export {name}='{escaped}'")
        return "\n".join(lines)

    def export_json(self) -> dict:
        """Export environment variables as JSON-serializable dict.

        Secrets are masked in the output.

        Returns:
            Dictionary with variable info.
        """
        result = {}
        for name, var in self.get_all().items():
            result[name] = {
                "value": var.display_value(),
                "source": var.source.value,
                "is_secret": var.is_secret,
            }
        return result
