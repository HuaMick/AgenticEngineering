"""Tests for config commands."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


class TestConfigShow:
    """Tests for 'agentic config show' command."""

    def test_show_no_config(self, cli_runner, temp_config_dir):
        """Test show when no config exists."""
        stdout, stderr, code = cli_runner(["config", "show"])
        assert "No configuration found" in stdout
        assert code == 0

    def test_show_with_config(self, cli_runner, temp_config_dir):
        """Test show when config exists."""
        config = {"version": 1, "defaults": {"base_branch": "main"}}
        config_file = temp_config_dir / "config.yml"
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        stdout, stderr, code = cli_runner(["config", "show"])
        assert "Configuration:" in stdout
        assert "version: 1" in stdout
        assert code == 0


class TestConfigGet:
    """Tests for 'agentic config get' command."""

    def test_get_existing_key(self, cli_runner, sample_prefs):
        """Test getting an existing preference."""
        stdout, stderr, code = cli_runner(["config", "get", "worktree.default_base"])
        assert "main" in stdout
        assert "worktree.default_base" in stdout
        assert code == 0

    def test_get_nested_key(self, cli_runner, sample_prefs):
        """Test getting a nested preference."""
        stdout, stderr, code = cli_runner(["config", "get", "test.nested.value"])
        assert "test_value" in stdout
        assert code == 0

    def test_get_missing_key(self, cli_runner, sample_prefs):
        """Test getting a non-existent key."""
        stdout, stderr, code = cli_runner(["config", "get", "nonexistent.key"])
        assert "Key not found" in stderr
        assert code == 1


class TestConfigSet:
    """Tests for 'agentic config set' command."""

    def test_set_simple_value(self, cli_runner, temp_config_dir):
        """Test setting a simple value."""
        stdout, stderr, code = cli_runner(["config", "set", "test.key", "value"])
        assert "Set test.key = value" in stdout
        assert code == 0

        # Verify it was written
        prefs_file = temp_config_dir / "preferences.yml"
        prefs = yaml.safe_load(prefs_file.read_text())
        assert prefs["test"]["key"] == "value"

    def test_set_boolean_value(self, cli_runner, temp_config_dir):
        """Test setting a boolean value."""
        stdout, stderr, code = cli_runner(["config", "set", "test.enabled", "true"])
        assert code == 0

        prefs_file = temp_config_dir / "preferences.yml"
        prefs = yaml.safe_load(prefs_file.read_text())
        assert prefs["test"]["enabled"] is True

    def test_set_numeric_value(self, cli_runner, temp_config_dir):
        """Test setting a numeric value."""
        stdout, stderr, code = cli_runner(["config", "set", "test.count", "42"])
        assert code == 0

        prefs_file = temp_config_dir / "preferences.yml"
        prefs = yaml.safe_load(prefs_file.read_text())
        assert prefs["test"]["count"] == 42


class TestConfigDelete:
    """Tests for 'agentic config delete' command."""

    def test_delete_existing_key(self, cli_runner, sample_prefs):
        """Test deleting an existing key."""
        stdout, stderr, code = cli_runner(["config", "delete", "test.nested.value"])
        assert "Deleted test.nested.value" in stdout
        assert code == 0

        # Verify it was deleted
        prefs = yaml.safe_load(sample_prefs.read_text())
        assert "value" not in prefs.get("test", {}).get("nested", {})

    def test_delete_missing_key(self, cli_runner, sample_prefs):
        """Test deleting a non-existent key."""
        stdout, stderr, code = cli_runner(["config", "delete", "nonexistent.key"])
        assert "Key not found" in stderr
        assert code == 1

    def test_delete_top_level_key(self, cli_runner, sample_prefs):
        """Test deleting a top-level key."""
        stdout, stderr, code = cli_runner(["config", "delete", "test"])
        assert "Deleted test" in stdout
        assert code == 0

        prefs = yaml.safe_load(sample_prefs.read_text())
        assert "test" not in prefs


class TestConfigList:
    """Tests for 'agentic config list' command."""

    def test_list_preferences(self, cli_runner, sample_prefs):
        """Test listing all preferences."""
        stdout, stderr, code = cli_runner(["config", "list"])
        assert "Preferences:" in stdout
        # Rich tree output shows "worktree" without colon
        assert "worktree" in stdout
        assert "default_base" in stdout
        assert "main" in stdout
        assert code == 0

    def test_list_no_preferences(self, cli_runner, temp_config_dir):
        """Test listing when no preferences exist."""
        stdout, stderr, code = cli_runner(["config", "list"])
        assert "No preferences found" in stdout
        assert code == 0
