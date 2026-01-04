"""Tests for config commands."""

import yaml


class TestConfigShow:
    """Tests for 'agentic config show' command."""

    def test_show_no_config(self, cli_runner, temp_config_dir):
        """Test show displays defaults when no config file exists."""
        stdout, stderr, code = cli_runner(["config", "show"])
        # Now shows merged config with defaults
        assert "Configuration (merged)" in stdout
        assert "default" in stdout  # Source attribution
        assert code == 0

    def test_show_with_config(self, cli_runner, temp_config_dir):
        """Test show displays config with source attribution."""
        config = {"version": 1, "defaults": {"base_branch": "main"}}
        config_file = temp_config_dir / "config.yml"
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        stdout, stderr, code = cli_runner(["config", "show"])
        assert "Configuration (merged)" in stdout
        assert "version" in stdout
        assert "global" in stdout  # Source attribution for global config
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


class TestConfigShowPath:
    """Tests for 'agentic config show-path' command."""

    def test_show_path_displays_paths(self, cli_runner, temp_config_dir):
        """Test show-path lists config file paths."""
        stdout, stderr, code = cli_runner(["config", "show-path"])
        assert "Config file paths" in stdout
        assert "global" in stdout
        assert code == 0

    def test_show_path_shows_existence_status(self, cli_runner, temp_config_dir):
        """Test show-path shows whether files exist."""
        # Create config file
        config_file = temp_config_dir / "config.yml"
        config_file.write_text("version: 1\n")

        stdout, stderr, code = cli_runner(["config", "show-path"])
        assert "exists" in stdout
        assert code == 0

    def test_show_path_json(self, cli_runner, temp_config_dir):
        """Test show-path JSON output."""
        result = cli_runner("--json", "config", "show-path")
        assert result.returncode == 0

        import json

        data = json.loads(result.stdout)
        assert "paths" in data
        assert len(data["paths"]) >= 1


class TestConfigClear:
    """Tests for 'agentic config clear' command."""

    def test_clear_requires_force(self, cli_runner, temp_config_dir):
        """Test clear fails without --force."""
        result = cli_runner("config", "clear")
        assert result.returncode == 1
        assert "force" in result.stderr.lower()

    def test_clear_with_force(self, cli_runner, temp_config_dir):
        """Test clear with --force removes config."""
        # Create config file
        config_file = temp_config_dir / "config.yml"
        config_file.write_text("version: 1\n")
        assert config_file.exists()

        result = cli_runner("config", "clear", "--force")
        assert result.returncode == 0
        assert not config_file.exists()

    def test_clear_no_files(self, cli_runner, temp_config_dir):
        """Test clear when no config files exist."""
        result = cli_runner("config", "clear", "--force")
        assert result.returncode == 0
        assert "No configuration files" in result.stdout


class TestConfigSetPath:
    """Tests for 'agentic config set-path' command."""

    def test_set_path_valid_file(self, cli_runner, temp_config_dir, temp_repo):
        """Test set-path with valid YAML file."""
        # Create a valid config file
        custom_config = temp_repo / "custom-config.yml"
        custom_config.write_text("version: 1\ndefaults:\n  base_branch: custom\n")

        result = cli_runner("config", "set-path", str(custom_config))
        assert result.returncode == 0
        assert "Custom config path set" in result.stdout

    def test_set_path_nonexistent_file(self, cli_runner, temp_config_dir):
        """Test set-path with non-existent file."""
        result = cli_runner("config", "set-path", "/nonexistent/path.yml")
        assert result.returncode == 1
        assert "does not exist" in result.stderr

    def test_set_path_invalid_yaml(self, cli_runner, temp_config_dir, temp_repo):
        """Test set-path with invalid YAML file."""
        # Create an invalid YAML file
        invalid_file = temp_repo / "invalid.yml"
        invalid_file.write_text("invalid: [unclosed bracket")

        result = cli_runner("config", "set-path", str(invalid_file))
        assert result.returncode == 1
        assert "Invalid YAML" in result.stderr


class TestTieredConfigLoader:
    """Tests for TieredConfigLoader class."""

    def test_load_defaults_only(self):
        """Test loading with no config files returns defaults."""
        from agenticcli.workflows.config_workflow import DEFAULT_CONFIG, TieredConfigLoader

        loader = TieredConfigLoader()
        config = loader.load()
        assert config["defaults"]["base_branch"] == DEFAULT_CONFIG["defaults"]["base_branch"]
        assert config["version"] == 1

    def test_load_global_overrides_defaults(self, temp_config_dir):
        """Test global config overrides defaults."""
        from agenticcli.workflows.config_workflow import TieredConfigLoader

        config_file = temp_config_dir / "config.yml"
        config_file.write_text("defaults:\n  base_branch: develop\n")

        loader = TieredConfigLoader(global_config_path=config_file)
        config = loader.load()
        assert config["defaults"]["base_branch"] == "develop"

    def test_load_project_overrides_global(self, temp_config_dir, temp_repo):
        """Test project config overrides global."""
        from agenticcli.workflows.config_workflow import TieredConfigLoader

        global_config = temp_config_dir / "config.yml"
        global_config.write_text("defaults:\n  base_branch: global-value\n")

        project_config = temp_repo / ".agenticcli.yml"
        project_config.write_text("defaults:\n  base_branch: project-value\n")

        loader = TieredConfigLoader(
            global_config_path=global_config,
            project_config_path=project_config,
        )
        config = loader.load()
        assert config["defaults"]["base_branch"] == "project-value"

    def test_get_with_source_attribution(self, temp_config_dir):
        """Test get() returns source attribution."""
        from agenticcli.workflows.config_workflow import ConfigSource, TieredConfigLoader

        config_file = temp_config_dir / "config.yml"
        config_file.write_text("defaults:\n  base_branch: custom\n")

        loader = TieredConfigLoader(global_config_path=config_file)
        result = loader.get("defaults.base_branch")

        assert result.value == "custom"
        assert result.source == ConfigSource.GLOBAL
        assert str(config_file) in result.path

    def test_get_default_source(self):
        """Test get() returns default source for unset values."""
        from agenticcli.workflows.config_workflow import ConfigSource, TieredConfigLoader

        loader = TieredConfigLoader()
        result = loader.get("defaults.base_branch")

        assert result.source == ConfigSource.DEFAULT

    def test_env_var_overrides_file(self, temp_config_dir, monkeypatch):
        """Test environment variables override file config."""
        from agenticcli.workflows.config_workflow import TieredConfigLoader

        config_file = temp_config_dir / "config.yml"
        config_file.write_text("defaults:\n  base_branch: from-file\n")

        monkeypatch.setenv("AGENTIC_BASE_BRANCH", "from-env")

        loader = TieredConfigLoader(global_config_path=config_file)
        config = loader.load()
        assert config["defaults"]["base_branch"] == "from-env"

    def test_env_var_source_attribution(self, monkeypatch):
        """Test env var source attribution."""
        from agenticcli.workflows.config_workflow import ConfigSource, TieredConfigLoader

        monkeypatch.setenv("AGENTIC_BASE_BRANCH", "env-value")

        loader = TieredConfigLoader()
        result = loader.get("defaults.base_branch")

        assert result.value == "env-value"
        assert result.source == ConfigSource.ENV

    def test_cli_overrides_env(self, monkeypatch):
        """Test CLI overrides override environment."""
        from agenticcli.workflows.config_workflow import TieredConfigLoader

        monkeypatch.setenv("AGENTIC_BASE_BRANCH", "from-env")

        loader = TieredConfigLoader(
            cli_overrides={"defaults": {"base_branch": "from-cli"}}
        )
        config = loader.load()
        assert config["defaults"]["base_branch"] == "from-cli"

    def test_merged_with_sources(self):
        """Test get_merged_with_sources returns source info."""
        from agenticcli.workflows.config_workflow import TieredConfigLoader

        loader = TieredConfigLoader()
        merged = loader.get_merged_with_sources()

        assert "defaults" in merged
        assert "base_branch" in merged["defaults"]
        assert merged["defaults"]["base_branch"]["source"] == "default"


class TestConfigShowMerged:
    """Tests for merged config display."""

    def test_show_merged_json(self, cli_runner, temp_config_dir):
        """Test config show in JSON mode shows merged and sources."""
        import json

        result = cli_runner("--json", "config", "show")
        assert result.returncode == 0

        data = json.loads(result.stdout)
        assert "merged" in data
        assert "sources" in data

    def test_show_merged_with_project_config(self, cli_runner, temp_repo):
        """Test config show includes project config when present."""
        # Create project config
        project_config = temp_repo / ".agenticcli.yml"
        project_config.write_text("defaults:\n  repo_abbreviation: PROJ\n")

        result = cli_runner("config", "show")
        assert result.returncode == 0
        assert "project" in result.stdout
        assert "PROJ" in result.stdout
