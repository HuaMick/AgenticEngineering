"""Tests for manifest commands."""

import pytest
import yaml


@pytest.fixture
def sample_manifest(temp_dir):
    """Create a sample manifest.yml file."""
    manifest_content = {
        "name": "test-agent",
        "version": "1.0.0",
        "description": "A test agent for testing",
        "triggers": ["on_commit", "on_pr"],
        "patterns": ["*.py", "*.yml"],
        "capabilities": ["read", "write", "execute"],
    }
    manifest_file = temp_dir / "manifest.yml"
    with open(manifest_file, "w") as f:
        yaml.dump(manifest_content, f)
    return manifest_file


@pytest.fixture
def agent_directory(temp_dir):
    """Create a sample agent directory with manifest."""
    agent_dir = temp_dir / "test-agent"
    agent_dir.mkdir()

    manifest_content = {
        "name": "test-agent",
        "version": "1.0.0",
        "description": "A test agent",
    }
    with open(agent_dir / "manifest.yml", "w") as f:
        yaml.dump(manifest_content, f)

    return agent_dir


class TestManifestShow:
    """Tests for 'agentic manifest show' command."""

    def test_show_help(self, cli_runner):
        """Test manifest show --help output."""
        stdout, stderr, code = cli_runner(["manifest", "show", "--help"])
        assert "show" in stdout.lower()
        assert "path" in stdout
        assert code == 0

    def test_show_manifest_file(self, cli_runner, sample_manifest):
        """Test showing a manifest file."""
        stdout, stderr, code = cli_runner(["manifest", "show", str(sample_manifest)])
        assert "test-agent" in stdout
        assert code == 0

    def test_show_agent_directory(self, cli_runner, agent_directory):
        """Test showing manifest from agent directory."""
        stdout, stderr, code = cli_runner(["manifest", "show", str(agent_directory)])
        assert "test-agent" in stdout
        assert code == 0

    def test_show_missing_path(self, cli_runner, temp_dir):
        """Test show with non-existent path."""
        stdout, stderr, code = cli_runner(["manifest", "show", str(temp_dir / "nonexistent")])
        assert code == 1

    def test_show_no_manifest(self, cli_runner, temp_dir):
        """Test show with directory that has no manifest."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        stdout, stderr, code = cli_runner(["manifest", "show", str(empty_dir)])
        assert code == 1
