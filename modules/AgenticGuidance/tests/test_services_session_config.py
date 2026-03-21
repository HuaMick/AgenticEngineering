"""Tests for session configuration and naming conventions."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.story("US-SES-001")

from agenticguidance.services.session_config import (
    SessionConfig,
    SessionConfigLoader,
    SessionNamingConvention,
    SessionNamingResult,
)


class TestSessionConfig:
    """Tests for SessionConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SessionConfig()

        assert config.default_shell == "/bin/bash"
        assert config.auto_attach is False
        assert config.max_sessions == 0
        assert config.auto_cleanup is True
        assert config.persist_registry is True
        assert config.worktree_auto_link is True
        assert config.plan_auto_link is True

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = SessionConfig(max_sessions=5, auto_attach=True)

        result = config.to_dict()

        assert result["max_sessions"] == 5
        assert result["auto_attach"] is True
        assert "default_shell" in result

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "default_shell": "/bin/zsh",
            "max_sessions": 10,
            "auto_cleanup": False,
        }

        config = SessionConfig.from_dict(data)

        assert config.default_shell == "/bin/zsh"
        assert config.max_sessions == 10
        assert config.auto_cleanup is False
        # Defaults for missing keys
        assert config.auto_attach is False

    def test_from_dict_missing_keys(self):
        """Test from_dict handles missing keys with defaults."""
        data = {}

        config = SessionConfig.from_dict(data)

        assert config.default_shell == "/bin/bash"
        assert config.max_sessions == 0


class TestSessionNamingConvention:
    """Tests for SessionNamingConvention class."""

    def test_validate_valid_name(self):
        """Test validation of valid session names."""
        naming = SessionNamingConvention()

        result = naming.validate("my-session")

        assert result.valid is True
        assert result.name == "my-session"

    def test_validate_empty_name(self):
        """Test validation rejects empty names."""
        naming = SessionNamingConvention()

        result = naming.validate("")

        assert result.valid is False
        assert "empty" in result.message.lower()

    def test_validate_too_long(self):
        """Test validation rejects names over 50 chars."""
        naming = SessionNamingConvention()
        long_name = "a" * 51

        result = naming.validate(long_name)

        assert result.valid is False
        assert "too long" in result.message.lower()
        assert result.suggested is not None
        assert len(result.suggested) <= 50

    def test_validate_reserved_names(self):
        """Test validation rejects reserved names."""
        naming = SessionNamingConvention()

        for reserved in ["main", "master", "default", "all"]:
            result = naming.validate(reserved)
            assert result.valid is False
            assert "reserved" in result.message.lower()

    def test_validate_invalid_start(self):
        """Test validation rejects names starting with non-letter."""
        naming = SessionNamingConvention()

        result = naming.validate("123-session")

        assert result.valid is False
        assert result.suggested is not None
        assert result.suggested[0].isalpha()

    def test_validate_invalid_chars(self):
        """Test validation rejects names with spaces."""
        naming = SessionNamingConvention()

        result = naming.validate("my session")

        assert result.valid is False
        assert result.suggested is not None

    def test_sanitize_name_spaces(self):
        """Test sanitize replaces spaces with hyphens."""
        naming = SessionNamingConvention()

        result = naming._sanitize_name("my session name")

        assert " " not in result
        assert "-" in result

    def test_sanitize_name_special_chars(self):
        """Test sanitize removes special characters."""
        naming = SessionNamingConvention()

        result = naming._sanitize_name("session@#$%test")

        assert "@" not in result
        assert "#" not in result

    def test_sanitize_name_leading_number(self):
        """Test sanitize handles leading numbers."""
        naming = SessionNamingConvention()

        result = naming._sanitize_name("123session")

        assert result[0].isalpha()

    def test_generate_from_worktree(self):
        """Test session name generation from worktree path."""
        naming = SessionNamingConvention()

        result = naming.generate_from_worktree("/home/user/AgenticEngineering-feature-auth")

        assert "feature" in result or "auth" in result
        assert naming.validate(result).valid

    def test_generate_from_plan(self):
        """Test session name generation from plan folder."""
        naming = SessionNamingConvention()

        result = naming.generate_from_plan("260126AT_agentictmux")

        # Should extract plan ID
        assert "260126AT" in result or naming.validate(result).valid


class TestSessionConfigLoader:
    """Tests for SessionConfigLoader class."""

    def test_load_default_when_no_file(self, tmp_path):
        """Test returns default config when file doesn't exist."""
        loader = SessionConfigLoader(tmp_path / "nonexistent.yml")

        config = loader.load()

        assert config.default_shell == "/bin/bash"
        assert config.max_sessions == 0

    def test_load_from_file(self, tmp_path):
        """Test loading config from file."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
session:
  max_sessions: 10
  auto_attach: true
  default_shell: /bin/zsh
""")

        loader = SessionConfigLoader(config_file)
        config = loader.load()

        assert config.max_sessions == 10
        assert config.auto_attach is True
        assert config.default_shell == "/bin/zsh"

    def test_load_handles_invalid_yaml(self, tmp_path):
        """Test load handles invalid YAML gracefully."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("invalid: yaml: content:")

        loader = SessionConfigLoader(config_file)
        config = loader.load()

        # Should return defaults
        assert config.default_shell == "/bin/bash"

    def test_save_creates_file(self, tmp_path):
        """Test save creates config file."""
        config_file = tmp_path / "subdir" / "config.yml"
        loader = SessionConfigLoader(config_file)

        config = SessionConfig(max_sessions=5)
        result = loader.save(config)

        assert result is True
        assert config_file.exists()

    def test_save_and_load_roundtrip(self, tmp_path):
        """Test config survives save/load cycle."""
        config_file = tmp_path / "config.yml"
        loader = SessionConfigLoader(config_file)

        original = SessionConfig(
            max_sessions=15,
            auto_attach=True,
            default_shell="/bin/fish",
        )

        loader.save(original)
        loaded = loader.load()

        assert loaded.max_sessions == original.max_sessions
        assert loaded.auto_attach == original.auto_attach
        assert loaded.default_shell == original.default_shell


class TestNamingResultDataclass:
    """Tests for SessionNamingResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = SessionNamingResult(
            valid=True,
            name="test-session",
            message="Valid",
        )

        assert result.valid is True
        assert result.suggested is None

    def test_invalid_result_with_suggestion(self):
        """Test creating invalid result with suggestion."""
        result = SessionNamingResult(
            valid=False,
            name="123invalid",
            message="Must start with letter",
            suggested="s-123invalid",
        )

        assert result.valid is False
        assert result.suggested is not None
