"""Tests for config service."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from agenticguidance.services.config import (
    ConfigResult,
    ConfigSource,
    ConfigValue,
    ConfigWorkflow,
    DEFAULT_CONFIG,
    TieredConfigLoader,
)


class TestConfigSource:
    """Tests for ConfigSource enum."""

    def test_source_values(self):
        """Test config source enum values."""
        assert ConfigSource.DEFAULT.value == "default"
        assert ConfigSource.GLOBAL.value == "global"
        assert ConfigSource.PROJECT.value == "project"
        assert ConfigSource.ENV.value == "environment"
        assert ConfigSource.CLI.value == "cli"


class TestConfigValue:
    """Tests for ConfigValue dataclass."""

    def test_create_value_with_source(self):
        """Test creating a config value with source."""
        value = ConfigValue(value="test", source=ConfigSource.DEFAULT)

        assert value.value == "test"
        assert value.source == ConfigSource.DEFAULT
        assert value.path is None

    def test_create_value_with_path(self):
        """Test creating a config value with file path."""
        value = ConfigValue(
            value="test",
            source=ConfigSource.GLOBAL,
            path="/home/user/.config/config.yml",
        )

        assert value.path == "/home/user/.config/config.yml"


class TestTieredConfigLoader:
    """Tests for TieredConfigLoader class."""

    def test_load_returns_defaults_when_no_files(self, tmp_path):
        """Test returns default config when no config files exist."""
        loader = TieredConfigLoader(
            global_config_path=tmp_path / "global.yml",
            project_config_path=tmp_path / "project.yml",
        )

        config = loader.load()

        assert config["version"] == DEFAULT_CONFIG["version"]
        assert "defaults" in config

    def test_load_merges_global_config(self, tmp_path):
        """Test global config is merged with defaults."""
        global_config = tmp_path / "global.yml"
        global_config.write_text("custom_key: custom_value\n")

        loader = TieredConfigLoader(global_config_path=global_config)
        config = loader.load()

        assert config["custom_key"] == "custom_value"
        assert "defaults" in config  # Defaults still present

    def test_load_project_overrides_global(self, tmp_path):
        """Test project config overrides global config."""
        global_config = tmp_path / "global.yml"
        global_config.write_text("shared_key: global_value\n")

        project_config = tmp_path / "project.yml"
        project_config.write_text("shared_key: project_value\n")

        loader = TieredConfigLoader(
            global_config_path=global_config,
            project_config_path=project_config,
        )
        config = loader.load()

        assert config["shared_key"] == "project_value"

    def test_load_cli_overrides_all(self, tmp_path):
        """Test CLI overrides take highest precedence."""
        global_config = tmp_path / "global.yml"
        global_config.write_text("key: global\n")

        loader = TieredConfigLoader(
            global_config_path=global_config,
            cli_overrides={"key": "cli"},
        )
        config = loader.load()

        assert config["key"] == "cli"

    @patch.dict(os.environ, {"AGENTIC_BASE_BRANCH": "develop"})
    def test_load_env_vars(self, tmp_path):
        """Test environment variables are loaded."""
        loader = TieredConfigLoader()
        config = loader.load()

        assert config["defaults"]["base_branch"] == "develop"

    def test_get_returns_value_with_source(self, tmp_path):
        """Test get returns ConfigValue with source attribution."""
        global_config = tmp_path / "global.yml"
        global_config.write_text("custom: value\n")

        loader = TieredConfigLoader(global_config_path=global_config)
        result = loader.get("custom")

        assert isinstance(result, ConfigValue)
        assert result.value == "value"
        assert result.source == ConfigSource.GLOBAL
        assert result.path == str(global_config)

    def test_get_returns_default_source(self):
        """Test get returns DEFAULT source for default values."""
        loader = TieredConfigLoader()
        result = loader.get("defaults.base_branch")

        assert result.source == ConfigSource.DEFAULT
        assert result.value == "main"

    def test_get_nested_key(self):
        """Test getting nested key with dot notation."""
        loader = TieredConfigLoader()
        result = loader.get("defaults.repo_abbreviation")

        assert result.value == "AE"


class TestConfigWorkflow:
    """Tests for ConfigWorkflow class."""

    def test_ensure_dir_creates_directory(self, tmp_path):
        """Test ensure_dir creates config directory."""
        config_dir = tmp_path / "subdir" / "config"
        workflow = ConfigWorkflow(config_dir=config_dir)

        result = workflow.ensure_dir()

        assert result == config_dir
        assert config_dir.exists()

    def test_show_returns_error_when_no_config(self, tmp_path):
        """Test show returns error when config doesn't exist."""
        workflow = ConfigWorkflow(config_dir=tmp_path)

        result = workflow.show()

        assert result.success is False
        assert "No configuration found" in result.message

    def test_show_returns_config_content(self, tmp_path):
        """Test show returns config file content."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("version: 1\nkey: value\n")

        workflow = ConfigWorkflow(config_dir=tmp_path)
        result = workflow.show()

        assert result.success is True
        assert result.data["config"]["key"] == "value"

    def test_init_creates_config_file(self, tmp_path):
        """Test init creates default config file."""
        workflow = ConfigWorkflow(config_dir=tmp_path)

        result = workflow.init()

        assert result.success is True
        assert workflow.config_file.exists()

    def test_init_fails_if_exists_without_overwrite(self, tmp_path):
        """Test init fails if config exists and overwrite=False."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("existing: config\n")

        workflow = ConfigWorkflow(config_dir=tmp_path)
        result = workflow.init(overwrite=False)

        assert result.success is False
        assert "already exists" in result.message

    def test_init_overwrites_when_flag_set(self, tmp_path):
        """Test init overwrites existing config when overwrite=True."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("old: config\n")

        workflow = ConfigWorkflow(config_dir=tmp_path)
        result = workflow.init(overwrite=True)

        assert result.success is True

    def test_set_pref_creates_preference(self, tmp_path):
        """Test set_pref creates or updates preference."""
        workflow = ConfigWorkflow(config_dir=tmp_path)

        result = workflow.set_pref("test.key", "test_value")

        assert result.success is True
        assert result.data["key"] == "test.key"
        assert result.data["value"] == "test_value"

    def test_get_pref_retrieves_value(self, tmp_path):
        """Test get_pref retrieves stored preference."""
        prefs_file = tmp_path / "preferences.yml"
        prefs_file.write_text("test:\n  key: stored_value\n")

        workflow = ConfigWorkflow(config_dir=tmp_path)
        result = workflow.get_pref("test.key")

        assert result.success is True
        assert result.data["value"] == "stored_value"

    def test_get_pref_returns_error_for_missing_key(self, tmp_path):
        """Test get_pref returns error for non-existent key."""
        prefs_file = tmp_path / "preferences.yml"
        prefs_file.write_text("existing: value\n")

        workflow = ConfigWorkflow(config_dir=tmp_path)
        result = workflow.get_pref("nonexistent.key")

        assert result.success is False
        assert "not found" in result.message

    def test_delete_pref_removes_value(self, tmp_path):
        """Test delete_pref removes preference."""
        prefs_file = tmp_path / "preferences.yml"
        prefs_file.write_text("test:\n  key: value\n")

        workflow = ConfigWorkflow(config_dir=tmp_path)
        result = workflow.delete_pref("test.key")

        assert result.success is True

    def test_clear_prefs_removes_all(self, tmp_path):
        """Test clear_prefs removes all preferences."""
        prefs_file = tmp_path / "preferences.yml"
        prefs_file.write_text("key1: value1\nkey2: value2\n")

        workflow = ConfigWorkflow(config_dir=tmp_path)
        result = workflow.clear_prefs()

        assert result.success is True
