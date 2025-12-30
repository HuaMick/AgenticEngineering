"""Comprehensive test suite for config management functionality.

This test suite validates:
- Preferences module functionality
- Config loader functionality
- Dynamic config path resolution (no module-level caching)
- CLI commands for config management
"""
import json
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from agent_gcptoolkit.secrets.domains import preferences
from agent_gcptoolkit.secrets.domains import config_loader
from agent_gcptoolkit.secrets.domains.config_loader import ConfigError


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Fixture to create a temporary home directory for testing."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Mock the preferences module paths
    fake_config_dir = fake_home / ".config" / "agent-gcptoolkit"
    fake_preferences_file = fake_config_dir / "preferences.json"
    monkeypatch.setattr(preferences, "PREFERENCES_DIR", fake_config_dir)
    monkeypatch.setattr(preferences, "PREFERENCES_FILE", fake_preferences_file)

    return fake_home


@pytest.fixture
def temp_config_dir(temp_home):
    """Fixture to create temporary config directory."""
    config_dir = temp_home / ".config" / "agent-gcptoolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def temp_preferences_file(temp_config_dir):
    """Fixture that returns the path to temporary preferences file."""
    return temp_config_dir / "preferences.json"


@pytest.fixture
def sample_config_content():
    """Sample valid config content."""
    return {
        "authentication": {
            "type": "service_account",
            "service_account_path": "/tmp/test-sa.json"
        },
        "gcp": {
            "project_id": "test-project"
        }
    }


@pytest.fixture
def temp_config_file(temp_config_dir, sample_config_content, tmp_path):
    """Fixture to create a temporary config file with valid content."""
    # Create a dummy service account file
    sa_file = tmp_path / "test-sa.json"
    sa_file.write_text(json.dumps({"type": "service_account"}))

    # Update config to point to the real service account file
    sample_config_content["authentication"]["service_account_path"] = str(sa_file)

    config_file = temp_config_dir / "config.yml"
    with open(config_file, 'w') as f:
        yaml.dump(sample_config_content, f)
    return config_file


class TestPreferencesModule:
    """Test suite for preferences module."""

    def test_get_preference_returns_none_when_not_set(self, temp_home):
        """Test that get_preference returns None when preference is not set."""
        result = preferences.get_preference("config_path")
        assert result is None

    def test_set_preference_stores_value(self, temp_home):
        """Test that set_preference stores a value."""
        test_path = "/path/to/config.yml"
        preferences.set_preference("config_path", test_path)

        # Verify the preference was stored
        result = preferences.get_preference("config_path")
        assert result == test_path

    def test_get_preference_returns_stored_value(self, temp_home):
        """Test that get_preference returns the stored value."""
        test_path = "/another/path/config.yml"
        preferences.set_preference("config_path", test_path)

        result = preferences.get_preference("config_path")
        assert result == test_path

    def test_clear_preference_removes_value(self, temp_home):
        """Test that clear_preference removes a value."""
        test_path = "/path/to/config.yml"
        preferences.set_preference("config_path", test_path)

        # Verify it was set
        assert preferences.get_preference("config_path") == test_path

        # Clear it
        preferences.clear_preference("config_path")

        # Verify it's gone
        assert preferences.get_preference("config_path") is None

    def test_preferences_persisted_to_json_file(self, temp_home, temp_preferences_file):
        """Test that preferences are persisted to the JSON file."""
        test_path = "/path/to/config.yml"
        preferences.set_preference("config_path", test_path)

        # Read the file directly
        with open(temp_preferences_file, 'r') as f:
            data = json.load(f)

        assert data["config_path"] == test_path

    def test_preferences_handle_missing_file(self, temp_home):
        """Test that preferences handle missing file gracefully."""
        # Try to get a preference when file doesn't exist
        result = preferences.get_preference("config_path")
        assert result is None

    def test_get_all_preferences(self, temp_home):
        """Test getting all preferences."""
        preferences.set_preference("config_path", "/path/to/config.yml")
        preferences.set_preference("another_key", "another_value")

        all_prefs = preferences.get_all_preferences()
        assert all_prefs["config_path"] == "/path/to/config.yml"
        assert all_prefs["another_key"] == "another_value"

    def test_clear_nonexistent_preference(self, temp_home):
        """Test clearing a preference that doesn't exist."""
        # Should not raise an error
        preferences.clear_preference("nonexistent_key")


class TestConfigLoader:
    """Test suite for config_loader module."""

    def test_get_config_path_with_preference_set(self, temp_home, temp_config_file):
        """Test _get_config_path returns preference path when set."""
        # Set a preference
        preferences.set_preference("config_path", str(temp_config_file))

        # Get config path
        result = config_loader._get_config_path()

        assert result == str(temp_config_file)

    def test_get_config_path_with_no_preference(self, temp_home, temp_config_file):
        """Test _get_config_path returns default path when no preference."""
        # Ensure no preference is set
        preferences.clear_preference("config_path")

        # Create config at default location
        default_config = temp_home / ".config" / "agent-gcptoolkit" / "config.yml"
        default_config.parent.mkdir(parents=True, exist_ok=True)
        default_config.write_text(temp_config_file.read_text())

        result = config_loader._get_config_path()

        assert result == str(default_config)

    def test_get_config_path_returns_default_location(self, temp_home, temp_config_dir):
        """Test _get_config_path returns default location."""
        preferences.clear_preference("config_path")

        # Create default config
        default_config = temp_config_dir / "config.yml"
        default_config.write_text("test: data")

        result = config_loader._get_config_path()

        assert result == str(default_config)

    def test_get_config_path_raises_when_file_missing(self, temp_home):
        """Test _get_config_path raises FileNotFoundError when config missing."""
        preferences.clear_preference("config_path")

        with pytest.raises(FileNotFoundError) as exc_info:
            config_loader._get_config_path()

        assert "Configuration file not found" in str(exc_info.value)

    def test_load_config_raises_error_when_file_missing(self, temp_home):
        """Test load_config raises ConfigError when file doesn't exist."""
        preferences.clear_preference("config_path")

        # Ensure no default config exists
        with pytest.raises(FileNotFoundError):
            config_loader.load_config()

    def test_config_path_not_cached_at_module_level(self, temp_home, temp_config_file, tmp_path):
        """CRITICAL: Test that config path is not cached at module level.

        This test validates that changing preferences takes effect immediately
        without requiring a Python restart.
        """
        # Create two different config files
        config1 = tmp_path / "config1.yml"
        config2 = tmp_path / "config2.yml"

        # Create service account files
        sa1 = tmp_path / "sa1.json"
        sa2 = tmp_path / "sa2.json"
        sa1.write_text(json.dumps({"type": "service_account"}))
        sa2.write_text(json.dumps({"type": "service_account"}))

        # Create two different configs with unique project IDs
        config1_content = {
            "authentication": {
                "type": "service_account",
                "service_account_path": str(sa1)
            },
            "gcp": {
                "project_id": "project-one"
            }
        }
        config2_content = {
            "authentication": {
                "type": "service_account",
                "service_account_path": str(sa2)
            },
            "gcp": {
                "project_id": "project-two"
            }
        }

        with open(config1, 'w') as f:
            yaml.dump(config1_content, f)
        with open(config2, 'w') as f:
            yaml.dump(config2_content, f)

        # Set preference to config1
        preferences.set_preference("config_path", str(config1))

        # Load config - should load config1
        cfg1 = config_loader.load_config()
        assert cfg1["gcp"]["project_id"] == "project-one"

        # Change preference to config2
        preferences.set_preference("config_path", str(config2))

        # Load config again - should load config2 WITHOUT Python restart
        cfg2 = config_loader.load_config()
        assert cfg2["gcp"]["project_id"] == "project-two"

        # This proves the config path is determined dynamically, not cached

    def test_preference_change_reflected_immediately(self, temp_home, tmp_path):
        """CRITICAL: Test that preference changes are reflected immediately.

        This validates the core requirement: no Python restart needed.
        """
        # Create service account file
        sa_file = tmp_path / "sa.json"
        sa_file.write_text(json.dumps({"type": "service_account"}))

        # Create custom config
        custom_config = tmp_path / "custom.yml"
        custom_content = {
            "authentication": {
                "type": "service_account",
                "service_account_path": str(sa_file)
            },
            "gcp": {
                "project_id": "custom-project"
            }
        }
        with open(custom_config, 'w') as f:
            yaml.dump(custom_content, f)

        # Set preference
        preferences.set_preference("config_path", str(custom_config))

        # Get config path - should return custom path
        path1 = config_loader._get_config_path()
        assert path1 == str(custom_config)

        # Clear preference
        preferences.clear_preference("config_path")

        # Create default config
        default_config = temp_home / ".config" / "agent-gcptoolkit" / "config.yml"
        default_config.parent.mkdir(parents=True, exist_ok=True)
        default_content = {
            "authentication": {
                "type": "service_account",
                "service_account_path": str(sa_file)
            },
            "gcp": {
                "project_id": "default-project"
            }
        }
        with open(default_config, 'w') as f:
            yaml.dump(default_content, f)

        # Get config path again - should return default path
        path2 = config_loader._get_config_path()
        assert path2 == str(default_config)

        # This proves preferences are checked dynamically each time

    def test_load_config_validates_missing_authentication(self, temp_home, temp_config_dir):
        """Test load_config validates missing authentication section."""
        config_file = temp_config_dir / "config.yml"
        with open(config_file, 'w') as f:
            yaml.dump({"gcp": {"project_id": "test"}}, f)

        preferences.set_preference("config_path", str(config_file))

        with pytest.raises(ConfigError) as exc_info:
            config_loader.load_config()

        assert "authentication" in str(exc_info.value)

    def test_load_config_validates_missing_gcp_section(self, temp_home, temp_config_dir, tmp_path):
        """Test load_config validates missing GCP section."""
        sa_file = tmp_path / "sa.json"
        sa_file.write_text(json.dumps({"type": "service_account"}))

        config_file = temp_config_dir / "config.yml"
        config_content = {
            "authentication": {
                "type": "service_account",
                "service_account_path": str(sa_file)
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_content, f)

        preferences.set_preference("config_path", str(config_file))

        with pytest.raises(ConfigError) as exc_info:
            config_loader.load_config()

        assert "gcp" in str(exc_info.value)

    def test_load_config_validates_service_account_file_exists(self, temp_home, temp_config_dir):
        """Test load_config validates service account file exists."""
        config_file = temp_config_dir / "config.yml"
        config_content = {
            "authentication": {
                "type": "service_account",
                "service_account_path": "/nonexistent/sa.json"
            },
            "gcp": {
                "project_id": "test-project"
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_content, f)

        preferences.set_preference("config_path", str(config_file))

        with pytest.raises(ConfigError) as exc_info:
            config_loader.load_config()

        assert "Service account file not found" in str(exc_info.value)

    def test_load_config_success(self, temp_home, temp_config_file):
        """Test load_config succeeds with valid config."""
        preferences.set_preference("config_path", str(temp_config_file))

        config = config_loader.load_config()

        assert config["authentication"]["type"] == "service_account"
        assert config["gcp"]["project_id"] == "test-project"
        assert "service_account_path" in config["authentication"]


class TestCLICommands:
    """Test suite for CLI commands (if possible without full CLI execution)."""

    def test_config_set_path_validates_file_exists(self, temp_home, tmp_path, capsys):
        """Test that config set-path validates file exists."""
        from agent_gcptoolkit.cli.main import cmd_config_set_path
        from argparse import Namespace

        # Try to set path to nonexistent file
        nonexistent = tmp_path / "nonexistent.yml"
        args = Namespace(path=str(nonexistent))

        with pytest.raises(SystemExit) as exc_info:
            cmd_config_set_path(args)

        assert exc_info.value.code == 1

    def test_config_set_path_stores_absolute_path(self, temp_home, temp_config_file):
        """Test that config set-path stores absolute path."""
        from agent_gcptoolkit.cli.main import cmd_config_set_path
        from argparse import Namespace

        args = Namespace(path=str(temp_config_file))
        cmd_config_set_path(args)

        # Verify preference was set
        stored_path = preferences.get_preference("config_path")
        assert stored_path == str(temp_config_file.resolve())

    def test_config_show_with_preference(self, temp_home, temp_config_file, capsys):
        """Test config show command with preference set."""
        from agent_gcptoolkit.cli.main import cmd_config_show
        from argparse import Namespace

        preferences.set_preference("config_path", str(temp_config_file))

        args = Namespace()
        cmd_config_show(args)

        captured = capsys.readouterr()
        assert str(temp_config_file) in captured.out
        assert "preference" in captured.out.lower()

    def test_config_show_without_preference(self, temp_home, temp_config_file, capsys):
        """Test config show command without preference."""
        from agent_gcptoolkit.cli.main import cmd_config_show
        from argparse import Namespace

        # Ensure no preference
        preferences.clear_preference("config_path")

        # Create default config
        default_config = temp_home / ".config" / "agent-gcptoolkit" / "config.yml"
        default_config.parent.mkdir(parents=True, exist_ok=True)
        default_config.write_text(temp_config_file.read_text())

        args = Namespace()
        cmd_config_show(args)

        captured = capsys.readouterr()
        assert str(default_config) in captured.out
        assert "default" in captured.out.lower()

    def test_config_clear_removes_preference(self, temp_home, temp_config_file, capsys):
        """Test config clear command removes preference."""
        from agent_gcptoolkit.cli.main import cmd_config_clear
        from argparse import Namespace

        # Set a preference first
        preferences.set_preference("config_path", str(temp_config_file))
        assert preferences.get_preference("config_path") is not None

        # Clear it
        args = Namespace()
        cmd_config_clear(args)

        # Verify it's gone
        assert preferences.get_preference("config_path") is None

        captured = capsys.readouterr()
        assert "cleared" in captured.out.lower()


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_config_file(self, temp_home, temp_config_dir):
        """Test handling of empty config file."""
        config_file = temp_config_dir / "config.yml"
        config_file.write_text("")

        preferences.set_preference("config_path", str(config_file))

        with pytest.raises(ConfigError) as exc_info:
            config_loader.load_config()

        assert "empty" in str(exc_info.value).lower()

    def test_invalid_yaml_config(self, temp_home, temp_config_dir):
        """Test handling of invalid YAML."""
        config_file = temp_config_dir / "config.yml"
        config_file.write_text("invalid: yaml: content: [")

        preferences.set_preference("config_path", str(config_file))

        with pytest.raises(ConfigError) as exc_info:
            config_loader.load_config()

        assert "parse" in str(exc_info.value).lower() or "YAML" in str(exc_info.value)

    def test_preference_with_nonexistent_path(self, temp_home, tmp_path):
        """Test _get_config_path when preference points to nonexistent file."""
        nonexistent = tmp_path / "nonexistent.yml"
        preferences.set_preference("config_path", str(nonexistent))

        # Should fall back to default location
        default_config = temp_home / ".config" / "agent-gcptoolkit" / "config.yml"
        default_config.parent.mkdir(parents=True, exist_ok=True)
        default_config.write_text("test: data")

        result = config_loader._get_config_path()
        assert result == str(default_config)

    def test_unsupported_auth_type(self, temp_home, temp_config_dir, tmp_path):
        """Test handling of unsupported authentication type."""
        sa_file = tmp_path / "sa.json"
        sa_file.write_text(json.dumps({"type": "service_account"}))

        config_file = temp_config_dir / "config.yml"
        config_content = {
            "authentication": {
                "type": "oauth2",
                "service_account_path": str(sa_file)
            },
            "gcp": {
                "project_id": "test-project"
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(config_content, f)

        preferences.set_preference("config_path", str(config_file))

        with pytest.raises(ConfigError) as exc_info:
            config_loader.load_config()

        assert "Unsupported authentication type" in str(exc_info.value)
