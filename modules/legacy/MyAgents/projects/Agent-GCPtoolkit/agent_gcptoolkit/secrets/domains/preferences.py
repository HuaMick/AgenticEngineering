"""Preferences manager for Agent-GCPtoolkit.

Manages persistent user preferences stored in XDG Base Directory standard location:
~/.config/agent-gcptoolkit/preferences.json
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# XDG Base Directory standard location
PREFERENCES_DIR = Path.home() / ".config" / "agent-gcptoolkit"
PREFERENCES_FILE = PREFERENCES_DIR / "preferences.json"


def _ensure_preferences_dir() -> None:
    """Create preferences directory if it doesn't exist."""
    try:
        PREFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create preferences directory {PREFERENCES_DIR}: {e}")
        raise


def _load_preferences() -> Dict[str, Any]:
    """
    Load preferences from JSON file.

    Returns:
        Dictionary of preferences, or empty dict if file doesn't exist
    """
    if not PREFERENCES_FILE.exists():
        return {}

    try:
        with open(PREFERENCES_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse preferences file {PREFERENCES_FILE}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to read preferences file {PREFERENCES_FILE}: {e}")
        return {}


def _save_preferences(preferences: Dict[str, Any]) -> None:
    """
    Save preferences to JSON file.

    Args:
        preferences: Dictionary of preferences to save
    """
    _ensure_preferences_dir()

    try:
        with open(PREFERENCES_FILE, 'w') as f:
            json.dump(preferences, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save preferences to {PREFERENCES_FILE}: {e}")
        raise


def get_preference(key: str) -> Optional[str]:
    """
    Get preference value by key.

    Args:
        key: Preference key

    Returns:
        Preference value if found, None otherwise
    """
    preferences = _load_preferences()
    return preferences.get(key)


def set_preference(key: str, value: str) -> None:
    """
    Set preference value.

    Args:
        key: Preference key
        value: Preference value
    """
    preferences = _load_preferences()
    preferences[key] = value
    _save_preferences(preferences)
    logger.info(f"Preference '{key}' set to: {value}")


def clear_preference(key: str) -> None:
    """
    Clear/remove preference by key.

    Args:
        key: Preference key to remove
    """
    preferences = _load_preferences()
    if key in preferences:
        del preferences[key]
        _save_preferences(preferences)
        logger.info(f"Preference '{key}' cleared")
    else:
        logger.debug(f"Preference '{key}' not found, nothing to clear")


def get_all_preferences() -> Dict[str, Any]:
    """
    Get all preferences.

    Returns:
        Dictionary of all preferences
    """
    return _load_preferences()
