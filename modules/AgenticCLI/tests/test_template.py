"""Tests for template commands."""

import os
from pathlib import Path

import pytest


class TestTemplateGenerate:
    """Tests for 'agentic template generate' command."""

    def test_generate_build_template(self, cli_runner, temp_dir):
        """Test generating a build template."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner(["template", "generate", "build"])
            assert "# Implementation Plan" in stdout
            assert "Build Phase Implementation" in stdout
            assert code == 0
        finally:
            os.chdir(original_cwd)

    def test_generate_test_template(self, cli_runner, temp_dir):
        """Test generating a test template."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner(["template", "generate", "test"])
            assert "# Test Plan" in stdout
            assert "Unit Tests" in stdout
            assert code == 0
        finally:
            os.chdir(original_cwd)

    def test_generate_cleanup_template(self, cli_runner, temp_dir):
        """Test generating a cleanup template."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner(["template", "generate", "cleanup"])
            assert "# Audit and Cleanup Plan" in stdout
            assert code == 0
        finally:
            os.chdir(original_cwd)

    def test_generate_guidance_template(self, cli_runner, temp_dir):
        """Test generating a guidance template."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner(["template", "generate", "guidance"])
            assert "# Guidance Plan" in stdout
            assert code == 0
        finally:
            os.chdir(original_cwd)

    def test_generate_with_output(self, cli_runner, temp_dir):
        """Test generating a template to a file."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        output_file = temp_dir / "output.yml"
        try:
            stdout, stderr, code = cli_runner(["template", "generate", "build", "--output", str(output_file)])
            assert "Generated:" in stdout
            assert output_file.exists()
            content = output_file.read_text()
            assert "# Implementation Plan" in content
            assert code == 0
        finally:
            os.chdir(original_cwd)


class TestTemplateList:
    """Tests for 'agentic template list' command."""

    def test_list_templates(self, cli_runner):
        """Test listing all available templates."""
        stdout, stderr, code = cli_runner(["template", "list"])
        assert "Available Template Types" in stdout
        assert "build" in stdout
        assert "test" in stdout
        assert "cleanup" in stdout
        assert "guidance" in stdout
        assert code == 0

    def test_list_shows_descriptions(self, cli_runner):
        """Test that list shows template descriptions."""
        stdout, stderr, code = cli_runner(["template", "list"])
        assert "Implementation plan" in stdout
        assert "Test plan" in stdout
        assert code == 0
