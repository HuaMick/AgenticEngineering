"""Health Check Workflow for MyAgents CLI.

This workflow provides health checking and context detection for the CLI.
Extracted from myagents.frontend/cli/entry.py to follow the Domain → Workflow → Entrypoint pattern.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml  # type: ignore[import-untyped]


class HealthCheckWorkflow:
    """Workflow for CLI and project health checks and context detection.

    This workflow provides multiple entrypoints for:
    - Detecting CLI installation location
    - Detecting project root and configuration
    - Validating environment prerequisites
    - Combined context detection for routing
    """

    def __init__(self):
        """Initialize the health check workflow."""
        pass

    def check_cli_health(self) -> Dict[str, Any]:
        """Verify CLI installation and return health status.

        Returns:
            Dict with CLI health information:
                - installed: bool - Whether CLI is properly installed
                - source_root: Path - CLI installation location
                - version: str - CLI version (if available)
                - python_version: str - Python version being used
        """
        try:
            source_root = self.detect_cli_source_root()

            # Try to get version
            version = "unknown"
            try:
                from importlib.metadata import version as get_version
                version = get_version("myagents")
            except Exception:
                version = "development"

            return {
                "installed": True,
                "source_root": source_root,
                "version": version,
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            }
        except Exception as e:
            return {
                "installed": False,
                "error": str(e),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            }

    def check_project_health(self, project_root: Optional[Path] = None) -> Dict[str, Any]:
        """Verify project context and return health status.

        Args:
            project_root: Optional project root path. If None, will use home directory.

        Returns:
            Dict with project health information:
                - valid: bool - Whether project context is valid
                - project_root: Path - Project root location (home directory)
                - has_langgraph_json: bool - Whether langgraph.json exists
                - config_path: Path - Configuration file path (if found)
                - error: str - Error message (if validation failed)
        """
        try:
            if project_root is None:
                # Use home directory as single source of truth
                langgraph_dir = self.detect_langgraph_path()
                if langgraph_dir is None:
                    raise RuntimeError(
                        "No langgraph.json found in ~/.config/myagents/. "
                        "Run 'myagents setup' to configure."
                    )
                project_root = langgraph_dir

            langgraph_json = project_root / "langgraph.json"
            has_langgraph = langgraph_json.exists()

            config_path = None
            if has_langgraph:
                config_path = self.detect_config_path()

            return {
                "valid": has_langgraph,
                "project_root": project_root,
                "has_langgraph_json": has_langgraph,
                "config_path": config_path
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }

    def detect_context(self, command: Optional[str] = None, is_help: bool = False) -> Dict[str, Any]:
        """Combined detection for routing commands to appropriate context.

        This is the main entrypoint for CLI routing logic. Uses only home directory
        configuration (~/.config/myagents/) as the single source of truth.

        Args:
            command: Optional command name to determine context requirements
            is_help: Deprecated - kept for backward compatibility but no longer used

        Returns:
            Dict with context information:
                - context_type: str - "global" or "project"
                - source_root: Path - CLI installation location (for global commands)
                - project_root: Path - Home directory config location (for project commands)
                - config_path: Path - Configuration file path (for project commands)
                - is_global_command: bool - Whether this is a global command
        """
        # Define global commands that work from any directory
        global_commands = {"update", "rebuild", "preferences", "config", "setup", "gcptoolkit", "relay", "remote"}

        is_global = command in global_commands if command else False

        if is_global:
            # Global command context
            source_root = self.detect_cli_source_root()
            return {
                "context_type": "global",
                "source_root": source_root,
                "config_path": None,
                "is_global_command": True
            }
        else:
            # Project command context - use home directory
            langgraph_dir = self.detect_langgraph_path()
            if langgraph_dir is None:
                raise RuntimeError(
                    "No langgraph.json found in ~/.config/myagents/. "
                    "Run 'myagents setup' to configure."
                )

            config_path = self.detect_config_path()
            return {
                "context_type": "project",
                "project_root": langgraph_dir,
                "config_path": config_path,
                "is_global_command": False
            }

    def validate_environment(self) -> Dict[str, Any]:
        """Check prerequisites and environment setup.

        Returns:
            Dict with environment validation results:
                - valid: bool - Whether environment is valid
                - python_version_ok: bool - Whether Python version is acceptable
                - venv_active: bool - Whether virtual environment is active
                - issues: List[str] - List of any issues found
                - warnings: List[str] - List of non-critical warnings
        """
        issues = []
        warnings = []

        # Check Python version (require 3.11+)
        python_ok = sys.version_info >= (3, 11)
        if not python_ok:
            issues.append(
                f"Python 3.11+ required, found {sys.version_info.major}.{sys.version_info.minor}"
            )

        # Check if in virtual environment
        venv_active = (
            hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        )
        if not venv_active:
            warnings.append("Not running in a virtual environment")

        return {
            "valid": len(issues) == 0,
            "python_version_ok": python_ok,
            "venv_active": venv_active,
            "issues": issues,
            "warnings": warnings
        }

    # Core detection functions (extracted from myagents.frontend/cli/entry.py)

    def detect_cli_source_root(self) -> Path:
        """Detect CLI installation location via __file__.

        This finds where the CLI is installed, not where a project is located.
        Used for update and rebuild commands.

        Returns:
            Path: Absolute path to CLI source root (where pyproject.toml is)
        """
        # __file__ points to src/myagents/backend/services/agents/workflows/health_check_workflow.py
        # Navigate up to project root:
        # workflows -> agents -> services -> backend -> myagents -> src -> project_root
        workflow_file = Path(__file__).resolve()
        return workflow_file.parent.parent.parent.parent.parent.parent.parent


    def detect_config_path(self) -> Optional[Path]:
        """Detect config path from canonical home directory location.

        Checks only the canonical location: ~/.config/myagents/config.yml
        Agents use 'myagents preferences' CLI command to modify this config.

        Returns:
            Path: Absolute path to config file if found, None if missing
        """
        # Check home directory config (XDG Base Directory standard)
        home_config = Path.home() / ".config" / "myagents" / "config.yml"
        if home_config.exists():
            return home_config

        # Config not found - user should run 'myagents preferences'
        return None

    def detect_langgraph_path(self) -> Optional[Path]:
        """Detect langgraph.json in home directory only.

        Checks only ~/.config/myagents/langgraph.json as the single source of truth.
        Never creates files or directories. Never checks local project directories.

        Returns:
            Path: Directory containing langgraph.json (~/.config/myagents/) if found, None otherwise
        """
        # Check home directory only (XDG Base Directory standard)
        home_langgraph_dir = Path.home() / ".config" / "myagents"
        home_langgraph_file = home_langgraph_dir / "langgraph.json"

        if home_langgraph_file.exists():
            # File exists - return home directory
            return home_langgraph_dir

        # File doesn't exist - return None (never create)
        return None



