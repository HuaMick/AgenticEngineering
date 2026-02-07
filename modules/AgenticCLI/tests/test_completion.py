"""Tests for shell completion (now native Typer)."""

from typer.testing import CliRunner

from agenticcli.cli import app


runner = CliRunner()


class TestNativeCompletion:
    """Tests that Typer's native completion flags are available."""

    def test_install_completion_flag_exists(self):
        """Test --install-completion is available."""
        result = runner.invoke(app, ["--help"])
        assert "--install-completion" in result.output

    def test_show_completion_flag_exists(self):
        """Test --show-completion is available."""
        result = runner.invoke(app, ["--help"])
        assert "--show-completion" in result.output


class TestTyperAppBasics:
    """Tests for Typer app configuration."""

    def test_app_has_correct_name(self):
        """Test the Typer app is named 'agentic'."""
        assert app.info.name == "agentic"

    def test_app_has_help(self):
        """Test the Typer app has help text."""
        assert app.info.help is not None

    def test_help_displays_commands(self):
        """Test --help lists main commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "plan" in result.output
        assert "health" in result.output
        assert "session" in result.output

    def test_version_flag(self):
        """Test --version returns version string."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "agentic" in result.output
