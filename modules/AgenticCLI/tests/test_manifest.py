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


@pytest.fixture
def modules_with_manifests(temp_dir):
    """Create a modules directory with multiple manifests."""
    modules_dir = temp_dir / "modules"
    modules_dir.mkdir()

    # Agent 1
    agent1_dir = modules_dir / "agent-one"
    agent1_dir.mkdir()
    with open(agent1_dir / "manifest.yml", "w") as f:
        yaml.dump({
            "name": "agent-one",
            "version": "1.0.0",
            "type": "builder",
            "description": "First test agent",
        }, f)

    # Agent 2
    agent2_dir = modules_dir / "agent-two"
    agent2_dir.mkdir()
    with open(agent2_dir / "manifest.yml", "w") as f:
        yaml.dump({
            "name": "agent-two",
            "version": "2.0.0",
            "type": "tester",
            "description": "Second test agent",
        }, f)

    return temp_dir


class TestManifestShow:
    """Tests for 'agentic manifest show' command."""

    def test_show_help(self, cli_runner):
        """Test manifest show --help output."""
        stdout, stderr, code = cli_runner(["agent", "manifest", "show", "--help"])
        assert "show" in stdout.lower()
        assert "path" in stdout
        assert code == 0

    def test_show_manifest_file(self, cli_runner, sample_manifest):
        """Test showing a manifest file."""
        stdout, stderr, code = cli_runner(["agent", "manifest", "show", str(sample_manifest)])
        assert "test-agent" in stdout
        assert code == 0

    def test_show_agent_directory(self, cli_runner, agent_directory):
        """Test showing manifest from agent directory."""
        stdout, stderr, code = cli_runner(["agent", "manifest", "show", str(agent_directory)])
        assert "test-agent" in stdout
        assert code == 0

    def test_show_missing_path(self, cli_runner, temp_dir):
        """Test show with non-existent path."""
        stdout, stderr, code = cli_runner(["agent", "manifest", "show", str(temp_dir / "nonexistent")])
        assert code == 1

    def test_show_no_manifest(self, cli_runner, temp_dir):
        """Test show with directory that has no manifest."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        stdout, stderr, code = cli_runner(["agent", "manifest", "show", str(empty_dir)])
        assert code == 1


class TestManifestList:
    """Tests for 'agentic manifest list' command."""

    def test_list_help(self, cli_runner):
        """Test manifest list --help output."""
        stdout, stderr, code = cli_runner(["agent", "manifest", "list", "--help"])
        assert "list" in stdout.lower()
        assert code == 0

    def test_list_no_manifests(self, cli_runner, temp_repo):
        """Test list when no manifests exist."""
        # temp_repo already has no manifests by default
        stdout, stderr, code = cli_runner(["agent", "manifest", "list"])
        assert code == 0
        assert "No manifests found" in stdout or "Found 0" in stdout or "manifest" in stdout.lower()

    def test_list_with_manifests(self, cli_runner, temp_repo):
        """Test list with manifests present."""
        # Create modules with manifests in temp_repo
        modules_dir = temp_repo / "modules"
        modules_dir.mkdir()

        agent1_dir = modules_dir / "agent-one"
        agent1_dir.mkdir()
        with open(agent1_dir / "manifest.yml", "w") as f:
            yaml.dump({
                "name": "agent-one",
                "version": "1.0.0",
                "type": "builder",
            }, f)

        stdout, stderr, code = cli_runner(["agent", "manifest", "list"])
        assert code == 0
        assert "agent-one" in stdout

    def test_list_json_output(self, cli_runner, temp_repo):
        """Test list with JSON output."""
        import json

        # Create modules with manifests in temp_repo
        modules_dir = temp_repo / "modules"
        modules_dir.mkdir()

        agent1_dir = modules_dir / "agent-one"
        agent1_dir.mkdir()
        with open(agent1_dir / "manifest.yml", "w") as f:
            yaml.dump({
                "name": "agent-one",
                "version": "1.0.0",
            }, f)

        stdout, stderr, code = cli_runner(["--json", "agent", "manifest", "list"])
        assert code == 0
        data = json.loads(stdout)
        assert "manifests" in data
        assert "count" in data


class TestManifestValidate:
    """Tests for 'agentic manifest validate' command."""

    def test_validate_help(self, cli_runner):
        """Test manifest validate --help output."""
        stdout, stderr, code = cli_runner(["agent", "manifest", "validate", "--help"])
        assert "validate" in stdout.lower()
        assert code == 0

    def test_validate_valid_manifest(self, cli_runner, sample_manifest):
        """Test validating a valid manifest."""
        stdout, stderr, code = cli_runner(["agent", "manifest", "validate", str(sample_manifest)])
        assert code == 0
        assert "valid" in stdout.lower()

    def test_validate_invalid_manifest(self, cli_runner, temp_dir):
        """Test validating an invalid manifest (missing name)."""
        invalid_manifest = temp_dir / "invalid.yml"
        with open(invalid_manifest, "w") as f:
            yaml.dump({"version": "1.0.0"}, f)

        stdout, stderr, code = cli_runner(["agent", "manifest", "validate", str(invalid_manifest)])
        assert code == 1
        assert "Missing required field" in stdout or "issue" in stdout.lower()

    def test_validate_json_output(self, cli_runner, sample_manifest):
        """Test validate with JSON output."""
        import json

        stdout, stderr, code = cli_runner(["--json", "agent", "manifest", "validate", str(sample_manifest)])
        assert code == 0
        data = json.loads(stdout)
        assert "valid" in data
        assert data["valid"] is True

    def test_validate_with_warnings(self, cli_runner, temp_dir):
        """Test validating a manifest with warnings (missing recommended fields)."""
        minimal_manifest = temp_dir / "minimal.yml"
        with open(minimal_manifest, "w") as f:
            yaml.dump({"name": "minimal-agent"}, f)

        stdout, stderr, code = cli_runner(["agent", "manifest", "validate", str(minimal_manifest)])
        assert code == 0  # Valid but with warnings
        assert "warning" in stdout.lower() or "Missing recommended" in stdout

    def test_validate_missing_file(self, cli_runner, temp_dir):
        """Test validating a non-existent file."""
        stdout, stderr, code = cli_runner(["agent", "manifest", "validate", str(temp_dir / "nonexistent.yml")])
        assert code == 1
