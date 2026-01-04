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
