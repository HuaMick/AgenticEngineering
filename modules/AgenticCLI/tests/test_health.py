"""Tests for health command."""

import json

import pytest

pytestmark = pytest.mark.story("US-SET-004", "US-GDN-062", "US-GDN-090", "US-GDN-101", "US-GDN-091")


@pytest.mark.story("US-SET-004")
class TestHealthCommand:
    """Tests for agentic health command."""

    def test_health_command(self, cli_runner):
        """Test health command runs."""
        result = cli_runner("setup", "health")
        assert result.returncode == 0
        assert "Health Check" in result.stdout or "cli_version" in result.stdout

    def test_health_json_output(self, cli_runner):
        """Test health command JSON output."""
        result = cli_runner("--json", "setup", "health")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "status" in data
        assert "checks" in data
        assert any(c["name"] == "cli_version" for c in data["checks"])

    def test_health_help(self, cli_runner):
        """Test health --help."""
        result = cli_runner("setup", "health", "--help")
        assert result.returncode == 0
        assert "health" in result.stdout.lower()

    def test_health_checks_config_dir(self, cli_runner):
        """Test health checks config directory."""
        result = cli_runner("--json", "setup", "health")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        config_check = next((c for c in data["checks"] if c["name"] == "config_dir"), None)
        assert config_check is not None
        assert config_check["status"] in ("pass", "warn")

    def test_health_checks_git(self, cli_runner):
        """Test health checks git availability."""
        result = cli_runner("--json", "setup", "health")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        git_check = next((c for c in data["checks"] if c["name"] == "git"), None)
        assert git_check is not None
        # Git should be available in test environment
        assert git_check["status"] == "pass"

    def test_health_checks_uv(self, cli_runner):
        """Test health checks uv availability."""
        result = cli_runner("--json", "setup", "health")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        uv_check = next((c for c in data["checks"] if c["name"] == "uv"), None)
        assert uv_check is not None
        # UV should be available in test environment
        assert uv_check["status"] in ("pass", "warn")
