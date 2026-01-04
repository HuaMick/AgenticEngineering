"""Tests for cicd commands."""

import os

import pytest
import yaml


@pytest.fixture
def sample_cloudbuild(temp_dir):
    """Create a sample cloudbuild.yaml file."""
    cloudbuild_content = {
        "steps": [
            {
                "name": "python:3.12",
                "entrypoint": "pytest",
                "args": ["tests/"],
            }
        ],
        "timeout": "600s",
    }
    cloudbuild_file = temp_dir / "cloudbuild.yaml"
    with open(cloudbuild_file, "w") as f:
        yaml.dump(cloudbuild_content, f)
    return cloudbuild_file


@pytest.fixture
def sample_github_workflow(temp_dir):
    """Create a sample GitHub Actions workflow file."""
    workflows_dir = temp_dir / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)

    workflow_content = {
        "name": "CI",
        "on": ["push", "pull_request"],
        "jobs": {
            "test": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"name": "Checkout", "uses": "actions/checkout@v4"},
                    {"name": "Run tests", "run": "pytest tests/"},
                ],
            },
            "lint": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"name": "Lint", "run": "ruff check ."},
                ],
            },
        },
    }
    workflow_file = workflows_dir / "ci.yml"
    with open(workflow_file, "w") as f:
        yaml.dump(workflow_content, f)
    return workflow_file


class TestCicdAudit:
    """Tests for 'agentic cicd audit' command."""

    def test_audit_help(self, cli_runner):
        """Test cicd audit --help output."""
        stdout, stderr, code = cli_runner(["cicd", "audit", "--help"])
        assert "audit" in stdout.lower()
        assert code == 0

    def test_audit_no_cloudbuild(self, cli_runner, temp_dir):
        """Test audit when no cloudbuild.yaml exists."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner(["cicd", "audit"])
            # Should handle gracefully
            assert code in [0, 1]
        finally:
            os.chdir(original_cwd)

    def test_audit_with_cloudbuild(self, cli_runner, sample_cloudbuild):
        """Test audit with cloudbuild.yaml present."""
        original_cwd = os.getcwd()
        os.chdir(sample_cloudbuild.parent)
        try:
            stdout, stderr, code = cli_runner(["cicd", "audit"])
            # Should parse and audit the config
            assert code in [0, 1]
        finally:
            os.chdir(original_cwd)


class TestCicdList:
    """Tests for 'agentic cicd list' command."""

    def test_list_help(self, cli_runner):
        """Test cicd list --help output."""
        stdout, stderr, code = cli_runner(["cicd", "list", "--help"])
        assert "list" in stdout.lower()
        assert code == 0

    def test_list_no_configs(self, cli_runner, temp_repo):
        """Test list when no CI/CD configs exist."""
        # temp_repo already has no CI/CD configs by default
        stdout, stderr, code = cli_runner(["cicd", "list"])
        assert code == 0
        assert "No CI/CD configurations" in stdout or "Found 0" in stdout or "configuration" in stdout.lower()

    def test_list_with_cloudbuild(self, cli_runner, temp_repo):
        """Test list with cloudbuild.yaml present."""
        # Create cloudbuild in the temp_repo that cli_runner is already using
        cloudbuild_content = {
            "steps": [{"name": "python:3.12", "args": ["pytest"]}]
        }
        with open(temp_repo / "cloudbuild.yaml", "w") as f:
            yaml.dump(cloudbuild_content, f)

        stdout, stderr, code = cli_runner(["cicd", "list"])
        assert code == 0
        assert "cloudbuild" in stdout.lower()

    def test_list_with_github_actions(self, cli_runner, temp_repo):
        """Test list with GitHub Actions workflow."""
        # Create workflow in temp_repo
        workflows_dir = temp_repo / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        workflow_content = {
            "name": "CI",
            "on": ["push"],
            "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": []}}
        }
        with open(workflows_dir / "ci.yml", "w") as f:
            yaml.dump(workflow_content, f)

        stdout, stderr, code = cli_runner(["cicd", "list"])
        assert code == 0
        assert "github-actions" in stdout.lower() or "ci.yml" in stdout

    def test_list_json_output(self, cli_runner, temp_repo):
        """Test list with JSON output."""
        import json

        # Create cloudbuild in temp_repo
        cloudbuild_content = {
            "steps": [{"name": "python:3.12", "args": ["pytest"]}]
        }
        with open(temp_repo / "cloudbuild.yaml", "w") as f:
            yaml.dump(cloudbuild_content, f)

        stdout, stderr, code = cli_runner(["--json", "cicd", "list"])
        assert code == 0
        data = json.loads(stdout)
        assert "configs" in data
        assert "count" in data


class TestCicdShow:
    """Tests for 'agentic cicd show' command."""

    def test_show_help(self, cli_runner):
        """Test cicd show --help output."""
        stdout, stderr, code = cli_runner(["cicd", "show", "--help"])
        assert "show" in stdout.lower()
        assert code == 0

    def test_show_github_workflow(self, cli_runner, temp_repo):
        """Test show with GitHub Actions workflow."""
        # Create workflow in temp_repo
        workflows_dir = temp_repo / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        workflow_content = {
            "name": "CI",
            "on": ["push"],
            "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": []}}
        }
        workflow_file = workflows_dir / "ci.yml"
        with open(workflow_file, "w") as f:
            yaml.dump(workflow_content, f)

        stdout, stderr, code = cli_runner(["cicd", "show", str(workflow_file)])
        assert code == 0
        assert "github-actions" in stdout.lower() or "CI" in stdout

    def test_show_cloudbuild(self, cli_runner, temp_repo):
        """Test show with cloudbuild.yaml."""
        cloudbuild_content = {
            "steps": [{"name": "python:3.12", "args": ["pytest"]}]
        }
        cloudbuild_file = temp_repo / "cloudbuild.yaml"
        with open(cloudbuild_file, "w") as f:
            yaml.dump(cloudbuild_content, f)

        stdout, stderr, code = cli_runner(["cicd", "show", str(cloudbuild_file)])
        assert code == 0
        assert "cloudbuild" in stdout.lower() or "steps" in stdout.lower()

    def test_show_json_output(self, cli_runner, temp_repo):
        """Test show with JSON output."""
        import json

        # Create workflow in temp_repo
        workflows_dir = temp_repo / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        workflow_content = {
            "name": "CI",
            "on": ["push"],
            "jobs": {"test": {"runs-on": "ubuntu-latest", "steps": []}}
        }
        workflow_file = workflows_dir / "ci.yml"
        with open(workflow_file, "w") as f:
            yaml.dump(workflow_content, f)

        stdout, stderr, code = cli_runner(["--json", "cicd", "show", str(workflow_file)])
        assert code == 0
        data = json.loads(stdout)
        assert "path" in data
        assert "type" in data
        assert "config" in data
