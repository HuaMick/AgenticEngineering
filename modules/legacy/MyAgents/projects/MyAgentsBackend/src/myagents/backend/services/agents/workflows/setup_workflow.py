"""Setup Workflow

Handles initial system setup and configuration management.
Includes preference management (get/set/delete/list/clear) and
config initialization for home directory setup.
"""

from pathlib import Path
from typing import Optional, Any, Tuple


class SetupWorkflow:
    """Workflow for system setup and preference management.

    This workflow provides multiple entrypoints for:
    - Initializing system configuration
    - Getting preference values
    - Setting preference values
    - Deleting preferences
    - Listing all preferences
    - Clearing all preferences

    Supports dot notation for nested keys (e.g., 'agent.default').
    """

    def __init__(self, preferences_file: Optional[Path] = None):
        """Initialize the preferences workflow.

        Args:
            preferences_file: Optional path to preferences file.
                            If None, uses default location.
        """
        self.preferences_file = preferences_file

    def get_preference(self, key: str) -> Tuple[bool, str, Any]:
        """Retrieve a preference value.

        Args:
            key: Preference key (supports dot notation like 'agent.default')

        Returns:
            Tuple of (success: bool, message: str, value: Any)
        """
        from myagents.backend.services.preferences.domains.preferences_manager.manager import PreferencesManager

        try:
            manager = PreferencesManager(preferences_file=self.preferences_file)
            value = manager.get(key)

            if value is None:
                return False, f"Preference '{key}' not found", None
            else:
                return True, f"Preference '{key}' = {value}", value
        except PermissionError as e:
            return False, f"Permission denied accessing preferences file: {e}", None
        except Exception as e:
            return False, f"Failed to read preferences: {e}", None

    def set_preference(self, key: str, value: Any) -> Tuple[bool, str]:
        """Set a preference value.

        Args:
            key: Preference key (supports dot notation like 'agent.default')
            value: Preference value (must be JSON serializable)

        Returns:
            Tuple of (success: bool, message: str)
        """
        from myagents.backend.services.preferences.domains.preferences_manager.manager import PreferencesManager

        try:
            manager = PreferencesManager(preferences_file=self.preferences_file)
            manager.set(key, value)
            return True, f"Preference '{key}' set to '{value}'"
        except Exception as e:
            return False, f"Failed to set preference: {e}"

    def delete_preference(self, key: str) -> Tuple[bool, str]:
        """Delete a preference.

        Args:
            key: Preference key (supports dot notation like 'agent.default')

        Returns:
            Tuple of (success: bool, message: str)
        """
        from myagents.backend.services.preferences.domains.preferences_manager.manager import PreferencesManager

        try:
            manager = PreferencesManager(preferences_file=self.preferences_file)
            deleted = manager.delete(key)

            if deleted:
                return True, f"Preference '{key}' deleted"
            else:
                return False, f"Preference '{key}' not found"
        except PermissionError as e:
            return False, f"Permission denied accessing preferences file: {e}"
        except Exception as e:
            return False, f"Failed to delete preference: {e}"

    def list_preferences(self) -> Tuple[bool, str, dict]:
        """List all preferences.

        Returns:
            Tuple of (success: bool, message: str, preferences: dict)
        """
        from myagents.backend.services.preferences.domains.preferences_manager.manager import PreferencesManager

        try:
            manager = PreferencesManager(preferences_file=self.preferences_file)
            prefs = manager.list_all()

            if prefs:
                return True, f"Found {len(prefs)} preference(s)", prefs
            else:
                return True, "No preferences set", {}
        except PermissionError as e:
            return False, f"Permission denied accessing preferences file: {e}", {}
        except Exception as e:
            return False, f"Failed to list preferences: {e}", {}

    def clear_preferences(self) -> Tuple[bool, str]:
        """Clear all preferences.

        Returns:
            Tuple of (success: bool, message: str)
        """
        from myagents.backend.services.preferences.domains.preferences_manager.manager import PreferencesManager

        try:
            manager = PreferencesManager(preferences_file=self.preferences_file)
            manager.clear_all()
            return True, "All preferences cleared"
        except Exception as e:
            return False, f"Failed to clear preferences: {e}"

    def initialize_config(self, overwrite: bool = False) -> Tuple[bool, str]:
        """Initialize config.yml with proper schema in home directory.

        Creates ~/.config/myagents/config.yml with:
        - server section (host, port, allow_blocking)
        - runtime section (pid_file, log_dir, checkpoint_dir)
        - langgraph section (project_name)

        Args:
            overwrite: Force overwrite existing config

        Returns:
            Tuple of (success: bool, message: str)
        """
        import yaml  # type: ignore[import-untyped]
        from pathlib import Path

        config_dir = Path.home() / ".config" / "myagents"
        config_file = config_dir / "config.yml"

        # Check if exists
        if config_file.exists() and not overwrite:
            return True, f"Config already exists at {config_file}"

        # Create directory
        config_dir.mkdir(parents=True, exist_ok=True)

        # Create config with proper schema
        # Use Path.home() to get absolute paths instead of literal ~ strings
        home_dir = Path.home()
        config_data = {
            "server": {
                "host": "127.0.0.1",
                "port": 2024,
                "allow_blocking": True
            },
            "runtime": {
                "pid_file": str(home_dir / ".config" / "myagents" / "runtime" / "studio.pid"),
                "log_dir": str(home_dir / ".config" / "myagents" / "runtime" / "studio" / "logs"),
                "checkpoint_dir": str(home_dir / ".config" / "myagents" / "runtime" / "studio" / "checkpoints")
            },
            "langgraph": {
                "project_name": "myagents-default"
            }
        }

        # Write config
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        return True, f"Config created at {config_file}"

    def initialize_langgraph_config(self, overwrite: bool = False) -> Tuple[bool, str]:
        """Initialize langgraph.json with absolute paths in home directory.

        Creates ~/.config/myagents/langgraph.json with:
        - dependencies list
        - graphs pointing to installed package workflows
        - env file path

        Args:
            overwrite: Force overwrite existing config

        Returns:
            Tuple of (success: bool, message: str)
        """
        import json
        from pathlib import Path

        config_dir = Path.home() / ".config" / "myagents"
        langgraph_file = config_dir / "langgraph.json"

        # Check if exists
        if langgraph_file.exists() and not overwrite:
            return True, f"LangGraph config already exists at {langgraph_file}"

        # Create directory
        config_dir.mkdir(parents=True, exist_ok=True)

        # Get absolute path to installed package
        try:
            import myagents
            import os
            package_root = Path(os.path.dirname(myagents.__file__))
        except ImportError:
            return False, "myagents package not installed"

        # Build absolute paths to agent workflows
        builder_agent_path = package_root / "backend" / "services" / "agents" / "workflows" / "builder_agent.py"

        # Verify paths exist
        if not builder_agent_path.exists():
            return False, f"Builder agent not found at {builder_agent_path}"

        # Create langgraph.json with absolute paths
        langgraph_data = {
            "dependencies": [
                "langgraph>=0.2.0",
                "langchain-core",
                "langchain-google-genai>=2.0.5",
                "google-generativeai>=0.8.5",
                "langsmith>=0.1.0"
            ],
            "graphs": {
                "builder": f"{builder_agent_path}:create_builder_agent",
                "coding": f"{builder_agent_path}:create_builder_agent"  # Backward compatibility alias
            },
            "env": str(config_dir / ".env")
        }

        # Write config
        with open(langgraph_file, 'w') as f:
            json.dump(langgraph_data, f, indent=2)

        # FIX-002: Verify file was written correctly
        if not langgraph_file.exists():
            return False, f"Failed to write langgraph.json to {langgraph_file}"

        # Verify referenced files exist
        for graph_name, graph_path in langgraph_data["graphs"].items():
            file_path, entry_point = graph_path.split(":")
            if not Path(file_path).exists():
                return False, (
                    f"langgraph.json references {file_path} which doesn't exist. "
                    f"This may indicate a package installation issue."
                )

        return True, f"LangGraph config created at {langgraph_file}"

    def run_setup(self) -> Tuple[bool, str]:
        """Run interactive setup workflow.

        Returns:
            Tuple of (success: bool, message: str)
        """
        messages = []

        # Initialize config.yml
        success, message = self.initialize_config()
        if not success:
            return False, f"Setup failed: {message}"
        messages.append(message)

        # Initialize langgraph.json
        success, message = self.initialize_langgraph_config()
        if not success:
            return False, f"Setup failed: {message}"
        messages.append(message)

        return True, f"Setup complete.\n" + "\n".join(messages)


# Backward-compatible function-based API
# These functions maintain the existing API for current CLI commands


def get_preference(key: str, preferences_file: Optional[Path] = None) -> Tuple[bool, str, Any]:
    """Workflow function for getting a preference value.

    This is a backward-compatible wrapper around SetupWorkflow.get_preference().

    Args:
        key: Preference key (supports dot notation like 'agent.default')
        preferences_file: Optional path to preferences file

    Returns:
        Tuple of (success: bool, message: str, value: Any)
    """
    workflow = SetupWorkflow(preferences_file=preferences_file)
    return workflow.get_preference(key)


def set_preference(
    key: str,
    value: Any,
    preferences_file: Optional[Path] = None
) -> Tuple[bool, str]:
    """Workflow function for setting a preference value.

    This is a backward-compatible wrapper around SetupWorkflow.set_preference().

    Args:
        key: Preference key (supports dot notation like 'agent.default')
        value: Preference value (must be JSON serializable)
        preferences_file: Optional path to preferences file

    Returns:
        Tuple of (success: bool, message: str)
    """
    workflow = SetupWorkflow(preferences_file=preferences_file)
    return workflow.set_preference(key, value)


def delete_preference(key: str, preferences_file: Optional[Path] = None) -> Tuple[bool, str]:
    """Workflow function for deleting a preference.

    This is a backward-compatible wrapper around SetupWorkflow.delete_preference().

    Args:
        key: Preference key (supports dot notation like 'agent.default')
        preferences_file: Optional path to preferences file

    Returns:
        Tuple of (success: bool, message: str)
    """
    workflow = SetupWorkflow(preferences_file=preferences_file)
    return workflow.delete_preference(key)


def list_preferences(preferences_file: Optional[Path] = None) -> Tuple[bool, str, dict]:
    """Workflow function for listing all preferences.

    This is a backward-compatible wrapper around SetupWorkflow.list_preferences().

    Args:
        preferences_file: Optional path to preferences file

    Returns:
        Tuple of (success: bool, message: str, preferences: dict)
    """
    workflow = SetupWorkflow(preferences_file=preferences_file)
    return workflow.list_preferences()


def clear_preferences(preferences_file: Optional[Path] = None) -> Tuple[bool, str]:
    """Workflow function for clearing all preferences.

    This is a backward-compatible wrapper around SetupWorkflow.clear_preferences().

    Args:
        preferences_file: Optional path to preferences file

    Returns:
        Tuple of (success: bool, message: str)
    """
    workflow = SetupWorkflow(preferences_file=preferences_file)
    return workflow.clear_preferences()


# Backward-compatible class alias
PreferencesWorkflow = SetupWorkflow
