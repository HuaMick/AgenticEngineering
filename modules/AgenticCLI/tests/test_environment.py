"""Tests for environment management workflow and commands."""

import json

import yaml


class TestEnvironmentProvider:
    """Tests for EnvironmentProvider class."""

    def test_get_all_empty(self, temp_config_dir):
        """Test get_all with no configured variables."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider

        provider = EnvironmentProvider(config_dir=temp_config_dir)
        env_vars = provider.get_all()

        # Should only have AGENTIC_* from current env if any
        for name in env_vars:
            assert name.startswith("AGENTIC_")

    def test_load_from_config(self, temp_config_dir):
        """Test loading variables from config file."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider, SecretSource

        # Create config with environment section
        config_file = temp_config_dir / "config.yml"
        config = {
            "version": 1,
            "environment": {
                "MY_VAR": "value1",
                "AGENTIC_TEST": "value2",
            },
        }
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        provider = EnvironmentProvider(config_dir=temp_config_dir)
        env_vars = provider.get_all()

        assert "MY_VAR" in env_vars
        assert env_vars["MY_VAR"].value == "value1"
        assert env_vars["MY_VAR"].source == SecretSource.CONFIG

    def test_load_from_prefs(self, temp_config_dir):
        """Test loading variables from preferences file."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider, SecretSource

        # Create prefs with environment section
        prefs_file = temp_config_dir / "preferences.yml"
        prefs = {
            "environment": {
                "PREF_VAR": "pref_value",
            },
        }
        with open(prefs_file, "w") as f:
            yaml.dump(prefs, f)

        provider = EnvironmentProvider(config_dir=temp_config_dir)
        env_vars = provider.get_all()

        assert "PREF_VAR" in env_vars
        assert env_vars["PREF_VAR"].value == "pref_value"
        assert env_vars["PREF_VAR"].source == SecretSource.PREFS

    def test_runtime_overrides(self, temp_config_dir):
        """Test runtime overrides take precedence."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider, SecretSource

        # Create config with variable
        config_file = temp_config_dir / "config.yml"
        config = {"environment": {"MY_VAR": "from_config"}}
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        provider = EnvironmentProvider(
            config_dir=temp_config_dir,
            runtime_overrides={"MY_VAR": "from_runtime"},
        )
        env_vars = provider.get_all()

        assert env_vars["MY_VAR"].value == "from_runtime"
        assert env_vars["MY_VAR"].source == SecretSource.RUNTIME

    def test_set_runtime(self, temp_config_dir):
        """Test setting runtime variables."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider

        provider = EnvironmentProvider(config_dir=temp_config_dir)
        provider.set_runtime("NEW_VAR", "new_value")

        env_vars = provider.get_all()
        assert "NEW_VAR" in env_vars
        assert env_vars["NEW_VAR"].value == "new_value"

    def test_clear_runtime(self, temp_config_dir):
        """Test clearing runtime variables."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider

        provider = EnvironmentProvider(
            config_dir=temp_config_dir,
            runtime_overrides={"VAR1": "value1", "VAR2": "value2"},
        )

        # Clear specific
        provider.clear_runtime("VAR1")
        assert "VAR1" not in provider.runtime_overrides
        assert "VAR2" in provider.runtime_overrides

        # Clear all
        provider.clear_runtime()
        assert len(provider.runtime_overrides) == 0


class TestSecretMasking:
    """Tests for secret detection and masking."""

    def test_secret_name_detection(self):
        """Test detection of secret-like variable names."""
        from agenticcli.workflows.environment_workflow import is_secret_name

        assert is_secret_name("API_KEY") is True
        assert is_secret_name("DATABASE_PASSWORD") is True
        assert is_secret_name("AWS_SECRET_ACCESS_KEY") is True
        assert is_secret_name("AUTH_TOKEN") is True
        assert is_secret_name("PRIVATE_KEY") is True

        assert is_secret_name("NORMAL_VAR") is False
        assert is_secret_name("DEBUG") is False
        assert is_secret_name("LOG_LEVEL") is False

    def test_secret_masking(self, temp_config_dir):
        """Test that secrets are masked in display."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider

        config_file = temp_config_dir / "config.yml"
        config = {
            "environment": {
                "API_KEY": "super_secret_key_12345",
                "NORMAL_VAR": "visible_value",
            },
        }
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        provider = EnvironmentProvider(config_dir=temp_config_dir)
        env_vars = provider.get_all()

        # Secret should be masked
        assert env_vars["API_KEY"].is_secret is True
        assert "super_secret" not in env_vars["API_KEY"].display_value()
        assert "*" in env_vars["API_KEY"].display_value()

        # Normal should not be masked
        assert env_vars["NORMAL_VAR"].is_secret is False
        assert env_vars["NORMAL_VAR"].display_value() == "visible_value"


class TestEnvironmentExport:
    """Tests for environment export functionality."""

    def test_export_shell(self, temp_config_dir):
        """Test shell format export."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider

        config_file = temp_config_dir / "config.yml"
        config = {"environment": {"MY_VAR": "my_value"}}
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        provider = EnvironmentProvider(config_dir=temp_config_dir)
        shell_export = provider.export_shell()

        assert "export MY_VAR='my_value'" in shell_export

    def test_export_shell_escapes_quotes(self, temp_config_dir):
        """Test that single quotes are escaped in shell export."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider

        provider = EnvironmentProvider(
            config_dir=temp_config_dir,
            runtime_overrides={"QUOTED": "it's a test"},
        )
        shell_export = provider.export_shell()

        # Should escape single quotes
        assert "it's a test" not in shell_export or "\"'\"" in shell_export

    def test_export_json(self, temp_config_dir):
        """Test JSON format export."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider

        config_file = temp_config_dir / "config.yml"
        config = {"environment": {"MY_VAR": "my_value", "API_KEY": "secret"}}
        with open(config_file, "w") as f:
            yaml.dump(config, f)

        provider = EnvironmentProvider(config_dir=temp_config_dir)
        json_export = provider.export_json()

        assert "MY_VAR" in json_export
        assert json_export["MY_VAR"]["value"] == "my_value"
        assert json_export["MY_VAR"]["is_secret"] is False

        # Secrets should be masked in JSON export
        assert "API_KEY" in json_export
        assert json_export["API_KEY"]["is_secret"] is True
        assert "secret" not in json_export["API_KEY"]["value"]


class TestSubprocessEnvironment:
    """Tests for subprocess environment injection."""

    def test_get_subprocess_env(self, temp_config_dir):
        """Test getting environment for subprocess."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider

        provider = EnvironmentProvider(
            config_dir=temp_config_dir,
            runtime_overrides={"TEST_VAR": "test_value"},
        )
        env = provider.get_subprocess_env()

        # Should include current env plus configured
        assert "PATH" in env  # From current env
        assert "TEST_VAR" in env
        assert env["TEST_VAR"] == "test_value"

    def test_run_with_env(self, temp_config_dir):
        """Test running command with injected environment."""
        from agenticcli.workflows.environment_workflow import EnvironmentProvider

        provider = EnvironmentProvider(
            config_dir=temp_config_dir,
            runtime_overrides={"MY_TEST_VAR": "hello_world"},
        )

        # Run a simple command that echoes an env var
        result = provider.run_with_env(
            ["sh", "-c", "echo $MY_TEST_VAR"],
            capture_output=True,
        )

        assert result.returncode == 0
        assert "hello_world" in result.stdout


class TestEnvCommands:
    """Tests for env CLI commands."""

    def test_env_show_empty(self, cli_runner, temp_config_dir):
        """Test env show with no configured variables."""
        stdout, stderr, code = cli_runner(["configure", "env", "show"])
        assert code == 0
        assert "Environment Configuration" in stdout

    def test_env_show_json(self, cli_runner, temp_config_dir):
        """Test env show with JSON output."""
        result = cli_runner("--json", "configure", "env", "show")
        assert result.returncode == 0

        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_env_export_shell(self, cli_runner, temp_config_dir):
        """Test env export in shell format."""
        stdout, stderr, code = cli_runner(["configure", "env", "export"])
        assert code == 0
        # May be empty or have AGENTIC_* vars

    def test_env_export_json(self, cli_runner, temp_config_dir):
        """Test env export in JSON format."""
        result = cli_runner("configure", "env", "export", "--format", "json")
        assert result.returncode == 0

        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_env_run_success(self, cli_runner, temp_config_dir):
        """Test env run with successful command."""
        result = cli_runner("configure", "env", "run", "echo", "hello")
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_env_run_failure(self, cli_runner, temp_config_dir):
        """Test env run with failing command."""
        # Use a command that doesn't need dash arguments
        result = cli_runner("configure", "env", "run", "false")
        assert result.returncode != 0

    def test_env_run_json(self, cli_runner, temp_config_dir):
        """Test env run with JSON output."""
        result = cli_runner("--json", "configure", "env", "run", "echo", "test")
        assert result.returncode == 0

        data = json.loads(result.stdout)
        assert "command" in data
        assert data["returncode"] == 0
        assert "test" in data["stdout"]
