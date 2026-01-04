#!/usr/bin/env python3
"""CLI Context - shared context passed through command hierarchy.

Provides a centralized context object that avoids global state and enables
clean dependency injection for command handlers.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CLIContext:
    """Shared context passed through command hierarchy.

    Attributes:
        cwd: Current working directory when CLI was invoked.
        config_dir: Path to configuration directory (~/.config/agenticcli/).
        project_root: Path to project root (contains .git or .agenticcli.yml).
        json_output: Whether to output in JSON format.
        verbose: Whether verbose output is enabled.
    """

    cwd: Path = field(default_factory=Path.cwd)
    config_dir: Optional[Path] = None
    project_root: Optional[Path] = None
    json_output: bool = False
    verbose: bool = False

    @classmethod
    def discover(cls, json_output: bool = False, verbose: bool = False) -> "CLIContext":
        """Create context with auto-discovered paths.

        Args:
            json_output: Whether to output in JSON format.
            verbose: Whether verbose output is enabled.

        Returns:
            CLIContext with discovered config_dir and project_root.
        """
        ctx = cls(
            cwd=Path.cwd(),
            json_output=json_output,
            verbose=verbose,
        )
        ctx.config_dir = cls._get_config_dir()
        ctx.project_root = cls._find_project_root(ctx.cwd)
        return ctx

    @staticmethod
    def _get_config_dir() -> Path:
        """Get the configuration directory path.

        Uses XDG_CONFIG_HOME if set, otherwise ~/.config/agenticcli/.

        Returns:
            Path to configuration directory.
        """
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / "agenticcli"
        return Path.home() / ".config" / "agenticcli"

    @staticmethod
    def _find_project_root(start: Path) -> Optional[Path]:
        """Find the project root by walking up the directory tree.

        Looks for .git directory or .agenticcli.yml file.

        Args:
            start: Starting directory for the search.

        Returns:
            Path to project root, or None if not found.
        """
        current = start.resolve()

        # Walk up to find .git or .agenticcli.yml
        while current != current.parent:
            if (current / ".git").exists():
                return current
            if (current / ".agenticcli.yml").exists():
                return current
            current = current.parent

        # Check root directory
        if (current / ".git").exists():
            return current
        if (current / ".agenticcli.yml").exists():
            return current

        return None

    @property
    def is_in_project(self) -> bool:
        """Check if we're inside a recognized project.

        Returns:
            True if project_root was discovered.
        """
        return self.project_root is not None

    @property
    def config_file(self) -> Path:
        """Get path to main config file.

        Returns:
            Path to config.yml in config_dir.
        """
        return self.config_dir / "config.yml" if self.config_dir else Path("config.yml")

    @property
    def prefs_file(self) -> Path:
        """Get path to preferences file.

        Returns:
            Path to preferences.yml in config_dir.
        """
        return self.config_dir / "preferences.yml" if self.config_dir else Path("preferences.yml")

    @property
    def logs_dir(self) -> Path:
        """Get path to logs directory.

        Returns:
            Path to logs/ in config_dir.
        """
        return self.config_dir / "logs" if self.config_dir else Path("logs")

    @property
    def state_file(self) -> Path:
        """Get path to state registry file.

        Returns:
            Path to state.json in config_dir.
        """
        return self.config_dir / "state.json" if self.config_dir else Path("state.json")

    @property
    def project_config_file(self) -> Optional[Path]:
        """Get path to project-level config file.

        Returns:
            Path to .agenticcli.yml in project root, or None if not in a project.
        """
        if self.project_root:
            return self.project_root / ".agenticcli.yml"
        return None

    def get_tiered_config(self):
        """Get a TieredConfigLoader instance for this context.

        Returns:
            TieredConfigLoader configured with global and project paths.
        """
        from agenticcli.workflows.config_workflow import TieredConfigLoader

        return TieredConfigLoader(
            global_config_path=self.config_file,
            project_config_path=self.project_config_file,
        )

    def ensure_config_dir(self) -> Path:
        """Ensure the config directory exists.

        Creates the directory if it doesn't exist.

        Returns:
            Path to configuration directory.
        """
        if self.config_dir:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        return self.config_dir

    def require_project(self, command: str) -> None:
        """Raise error if not in a project directory.

        Args:
            command: Name of command requiring project context.

        Raises:
            SystemExit: If not in a project directory.
        """
        import sys

        if not self.is_in_project:
            from agenticcli.console import console

            console.print(f"[red]Error: Command '{command}' requires a project directory.[/red]")
            console.print(
                "[dim]No .git or .agenticcli.yml found in current or parent directories.[/dim]"
            )
            sys.exit(1)

    def __str__(self) -> str:
        """Return a string representation of the context."""
        return (
            f"CLIContext(\n"
            f"  cwd={self.cwd},\n"
            f"  config_dir={self.config_dir},\n"
            f"  project_root={self.project_root},\n"
            f"  json_output={self.json_output},\n"
            f"  verbose={self.verbose}\n"
            f")"
        )
