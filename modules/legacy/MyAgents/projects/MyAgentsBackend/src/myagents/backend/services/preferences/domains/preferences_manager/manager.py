"""User preferences management domain logic."""

import json
from pathlib import Path
from typing import Optional, Any


class PreferencesManager:
    """Manages user preferences for MyAgents."""

    def __init__(self, preferences_file: Optional[Path] = None):
        """Initialize preferences manager.

        Args:
            preferences_file: Path to preferences JSON file
                             (defaults to ~/.myagents/preferences.json)
        """
        if preferences_file is None:
            self.preferences_file = Path.home() / ".myagents" / "preferences.json"
        else:
            self.preferences_file = preferences_file

        # Ensure preferences directory exists
        self.preferences_file.parent.mkdir(parents=True, exist_ok=True)

        # Load or initialize preferences
        self._preferences = self._load_preferences()

    def _load_preferences(self) -> dict:
        """Load preferences from file.

        Returns:
            Dict with preferences, or empty dict if file doesn't exist
        """
        if self.preferences_file.exists():
            try:
                with open(self.preferences_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return self._get_default_preferences()
        # File doesn't exist - create with defaults
        defaults = self._get_default_preferences()
        self._preferences = defaults
        self._save_preferences()
        return defaults

    def _get_default_preferences(self) -> dict:
        """Get default preferences structure."""
        return {
            "cli": {
                "default_project": None,
                "editor": "vim",
                "auto_update": False
            },
            "studio": {
                "auto_start": False,
                "default_port": 2024
            },
            "agents": {
                "default_model": "gemini-2.0-flash-exp",
                "enable_tracing": True
            }
        }

    def _save_preferences(self) -> None:
        """Save preferences to file."""
        with open(self.preferences_file, 'w') as f:
            json.dump(self._preferences, f, indent=2)
            # Ensure data is written to disk immediately
            # This prevents race conditions in cross-process scenarios
            f.flush()
            import os
            os.fsync(f.fileno())

    def get(self, key: str) -> Optional[Any]:
        """Get a preference value.

        Args:
            key: Preference key (supports dot notation like 'agent.default')

        Returns:
            Preference value or None if not found
        """
        # Support dot notation for nested keys
        keys = key.split('.')
        value = self._preferences

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None

        return value

    def set(self, key: str, value: Any) -> None:
        """Set a preference value.

        Args:
            key: Preference key (supports dot notation like 'agent.default')
            value: Preference value (must be JSON serializable)
        """
        # Support dot notation for nested keys
        keys = key.split('.')
        current = self._preferences

        # Navigate to the parent dict, creating nested dicts as needed
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            elif not isinstance(current[k], dict):
                # If intermediate key exists but is not a dict, replace it
                current[k] = {}
            current = current[k]

        # Set the final value
        current[keys[-1]] = value

        # Save to disk
        self._save_preferences()

    def delete(self, key: str) -> bool:
        """Delete a preference.

        Args:
            key: Preference key (supports dot notation like 'agent.default')

        Returns:
            True if key was deleted, False if key didn't exist
        """
        # Support dot notation for nested keys
        keys = key.split('.')
        current = self._preferences

        # Navigate to parent dict
        for k in keys[:-1]:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return False

        # Delete the final key
        if isinstance(current, dict) and keys[-1] in current:
            del current[keys[-1]]
            self._save_preferences()
            return True

        return False

    def list_all(self) -> dict:
        """List all preferences.

        Returns:
            Dict with all preferences
        """
        return self._preferences.copy()

    def clear_all(self) -> None:
        """Clear all preferences."""
        self._preferences = {}
        self._save_preferences()
