"""Tests for ntfy configuration schema, env var mapping, and validation."""

import os
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.story("US-SET-005")

from agenticguidance.services.config import (
    DEFAULT_CONFIG,
    ENV_VAR_MAPPING,
    ConfigWorkflow,
    TieredConfigLoader,
)


class TestNtfyConfigDefaults:
    """Verify ntfy keys exist in DEFAULT_CONFIG with correct defaults."""

    def test_default_topic_empty(self):
        assert DEFAULT_CONFIG["ntfy"]["topic"] == ""

    def test_default_server(self):
        assert DEFAULT_CONFIG["ntfy"]["server"] == "https://ntfy.sh"

    def test_default_enabled(self):
        assert DEFAULT_CONFIG["ntfy"]["enabled"] is True

    def test_defaults_loaded_by_tiered_loader(self):
        """TieredConfigLoader.load() includes ntfy defaults."""
        loader = TieredConfigLoader()
        config = loader.load()
        assert config["ntfy"]["topic"] == ""
        assert config["ntfy"]["server"] == "https://ntfy.sh"
        assert config["ntfy"]["enabled"] is True

    def test_get_ntfy_topic_returns_default(self):
        loader = TieredConfigLoader()
        result = loader.get("ntfy.topic")
        assert result.value == ""
        assert result.source.value == "default"

    def test_get_ntfy_server_returns_default(self):
        loader = TieredConfigLoader()
        result = loader.get("ntfy.server")
        assert result.value == "https://ntfy.sh"

    def test_get_ntfy_enabled_returns_default(self):
        loader = TieredConfigLoader()
        result = loader.get("ntfy.enabled")
        assert result.value is True


class TestNtfyConfigEnvVars:
    """Verify environment variable mapping for ntfy keys."""

    def test_env_var_topic_mapped(self):
        assert "AGENTIC_NTFY_TOPIC" in ENV_VAR_MAPPING
        assert ENV_VAR_MAPPING["AGENTIC_NTFY_TOPIC"] == "ntfy.topic"

    def test_env_var_server_mapped(self):
        assert "AGENTIC_NTFY_SERVER" in ENV_VAR_MAPPING
        assert ENV_VAR_MAPPING["AGENTIC_NTFY_SERVER"] == "ntfy.server"

    @patch.dict(os.environ, {"AGENTIC_NTFY_TOPIC": "my-phone"})
    def test_env_var_topic_overrides_default(self):
        loader = TieredConfigLoader()
        config = loader.load()
        assert config["ntfy"]["topic"] == "my-phone"

    @patch.dict(os.environ, {"AGENTIC_NTFY_TOPIC": "my-phone"})
    def test_env_var_topic_source_attribution(self):
        loader = TieredConfigLoader()
        result = loader.get("ntfy.topic")
        assert result.value == "my-phone"
        assert result.source.value == "environment"

    @patch.dict(os.environ, {"AGENTIC_NTFY_SERVER": "https://ntfy.example.com"})
    def test_env_var_server_overrides_default(self):
        loader = TieredConfigLoader()
        config = loader.load()
        assert config["ntfy"]["server"] == "https://ntfy.example.com"

    @patch.dict(os.environ, {"AGENTIC_NTFY_SERVER": "https://ntfy.example.com"})
    def test_env_var_server_source_attribution(self):
        loader = TieredConfigLoader()
        result = loader.get("ntfy.server")
        assert result.value == "https://ntfy.example.com"
        assert result.source.value == "environment"


class TestNtfyConfigValidation:
    """Verify validation logic for ntfy config keys in ConfigWorkflow.set_pref()."""

    def test_valid_server_https(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.server", "https://ntfy.example.com")
        assert result.success is True
        assert result.data["value"] == "https://ntfy.example.com"

    def test_valid_server_http(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.server", "http://localhost:8080")
        assert result.success is True

    def test_invalid_server_url_no_scheme(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        with pytest.raises(ValueError, match="must be a URL"):
            wf.set_pref("ntfy.server", "not-a-url")

    def test_invalid_server_url_ftp(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        with pytest.raises(ValueError, match="must be a URL"):
            wf.set_pref("ntfy.server", "ftp://files.example.com")

    def test_empty_topic_accepted(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.topic", "")
        assert result.success is True
        assert result.data["value"] == ""

    def test_nonempty_topic_accepted(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.topic", "my-phone-topic")
        assert result.success is True
        assert result.data["value"] == "my-phone-topic"

    def test_enabled_true_string(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.enabled", "true")
        assert result.success is True

    def test_enabled_false_string(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.enabled", "false")
        assert result.success is True

    def test_enabled_yes_string(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.enabled", "yes")
        assert result.success is True

    def test_enabled_no_string(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.enabled", "no")
        assert result.success is True

    def test_enabled_1_string(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.enabled", "1")
        assert result.success is True

    def test_enabled_0_string(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.enabled", "0")
        assert result.success is True

    def test_enabled_bool_true(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.enabled", True)
        assert result.success is True

    def test_enabled_bool_false(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("ntfy.enabled", False)
        assert result.success is True

    def test_enabled_invalid_value(self, tmp_path):
        wf = ConfigWorkflow(config_dir=tmp_path)
        with pytest.raises(ValueError, match="must be a boolean"):
            wf.set_pref("ntfy.enabled", "maybe")

    def test_unrelated_keys_unaffected(self, tmp_path):
        """Setting non-ntfy keys should not trigger ntfy validation."""
        wf = ConfigWorkflow(config_dir=tmp_path)
        result = wf.set_pref("worktree.default_base", "develop")
        assert result.success is True
        assert result.data["value"] == "develop"


class TestExistingConfigKeysUnchanged:
    """Verify existing config keys are untouched by ntfy additions."""

    def test_version_unchanged(self):
        assert DEFAULT_CONFIG["version"] == 1

    def test_defaults_unchanged(self):
        assert DEFAULT_CONFIG["defaults"]["repo_abbreviation"] == "AE"
        assert DEFAULT_CONFIG["defaults"]["base_branch"] == "main"

    def test_worktree_unchanged(self):
        assert DEFAULT_CONFIG["worktree"]["default_base"] == "main"

    def test_plan_unchanged(self):
        assert DEFAULT_CONFIG["plan"]["auto_scaffold"] is True

    def test_existing_env_vars_unchanged(self):
        assert ENV_VAR_MAPPING["AGENTIC_BASE_BRANCH"] == "defaults.base_branch"
        assert ENV_VAR_MAPPING["AGENTIC_REPO_ABBREVIATION"] == "defaults.repo_abbreviation"
        assert ENV_VAR_MAPPING["AGENTIC_WORKTREE_BASE"] == "worktree.default_base"
        assert ENV_VAR_MAPPING["AGENTIC_PLAN_AUTO_SCAFFOLD"] == "plan.auto_scaffold"
