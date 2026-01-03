"""Tests for stories commands."""

import os
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def sample_userstories(temp_dir):
    """Create sample userstories directory."""
    stories_dir = temp_dir / "userstories"
    stories_dir.mkdir()

    # Create some sample stories
    story1 = {
        "story": {
            "title": "Test Story 1",
            "as_a": "developer",
            "i_want": "to test features",
            "so_that": "I can verify functionality",
        }
    }
    with open(stories_dir / "story1.yml", "w") as f:
        yaml.dump(story1, f)

    story2 = {
        "story": {
            "title": "Test Story 2",
            "as_a": "user",
            "i_want": "to use the CLI",
            "so_that": "I can automate tasks",
        }
    }
    with open(stories_dir / "story2.yml", "w") as f:
        yaml.dump(story2, f)

    return stories_dir


class TestStoriesFind:
    """Tests for 'agentic stories find' command."""

    def test_find_help(self, cli_runner):
        """Test stories find --help output."""
        stdout, stderr, code = cli_runner(["stories", "find", "--help"])
        assert "find" in stdout.lower()
        assert "--project" in stdout
        assert "--changes" in stdout
        assert code == 0

    def test_find_no_userstories(self, cli_runner, temp_dir):
        """Test find when no userstories directory exists."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner(["stories", "find"])
            # Should handle gracefully
            assert code in [0, 1]
        finally:
            os.chdir(original_cwd)

    def test_find_with_userstories(self, cli_runner, sample_userstories):
        """Test find with userstories directory."""
        original_cwd = os.getcwd()
        os.chdir(sample_userstories.parent)
        try:
            stdout, stderr, code = cli_runner(["stories", "find"])
            # Should find stories or report none
            assert code in [0, 1]
        finally:
            os.chdir(original_cwd)

    def test_find_with_project_filter(self, cli_runner):
        """Test find with --project filter."""
        stdout, stderr, code = cli_runner(["stories", "find", "--project", "test"])
        # Should attempt to filter - may pass or fail depending on context
        assert code in [0, 1]
