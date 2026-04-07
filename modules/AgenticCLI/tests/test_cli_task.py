"""Tests for ticket subcommand CLI functionality.

Unit tests for argument parsing of ticket prefill, list, status, and add commands.
"""

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.story("US-PLN-009")]


@pytest.mark.story("US-PLN-009")
class TestTaskListParser:
    """Tests for 'agentic epic ticket list' argument parsing."""

    def test_list_help_shows_options(self, cli_runner):
        """Test list --help shows all options."""
        stdout, stderr, code = cli_runner(["epic", "ticket", "list", "--help"])
        assert "--plan" in stdout
        assert "--status" in stdout
        assert "--verbose" in stdout
        assert code == 0

    def test_list_status_filter_choices(self, cli_runner):
        """Test --status accepts valid choices."""
        # Valid choices should be: all, pending, in_progress, completed
        valid_choices = ["all", "pending", "in_progress", "completed"]
        for choice in valid_choices:
            # Parse is valid even if runtime fails for other reasons
            result = cli_runner(["epic", "ticket", "list", "--status", choice])
            # Parser should not reject valid choices
            assert "invalid choice" not in result.stderr.lower()

    def test_list_status_rejects_invalid(self, cli_runner):
        """Test --status rejects invalid values."""
        stdout, stderr, code = cli_runner(
            ["epic", "ticket", "list", "--status", "invalid_status"]
        )
        assert code != 0
        assert "invalid" in stderr.lower()

    def test_list_accepts_verbose_flag(self, cli_runner):
        """Test --verbose flag is recognized."""
        result = cli_runner(["epic", "ticket", "list", "--verbose", "--help"])
        # Help should show the verbose option
        assert "--verbose" in result.stdout or "-v" in result.stdout


@pytest.mark.story("US-PLN-009")
class TestTaskAddParser:
    """Tests for 'agentic epic ticket add' argument parsing."""

    def test_add_help_shows_options(self, cli_runner):
        """Test add --help shows all options."""
        stdout, stderr, code = cli_runner(["epic", "ticket", "add", "--help"])
        assert "description" in stdout.lower()
        assert "--plan" in stdout
        assert "--phase" in stdout
        assert "--id" in stdout
        assert "--priority" in stdout
        assert code == 0

    def test_add_requires_description(self, cli_runner):
        """Test that description is required."""
        stdout, stderr, code = cli_runner(["epic", "ticket", "add"])
        assert code != 0
        assert "required" in stderr.lower() or "argument" in stderr.lower()

    def test_add_priority_choices(self, cli_runner):
        """Test --priority accepts valid choices."""
        valid_choices = ["low", "medium", "high"]
        for choice in valid_choices:
            result = cli_runner([
                "epic", "ticket", "add", "Test task",
                "--priority", choice
            ])
            # Parser should not reject valid choices
            assert "invalid choice" not in result.stderr.lower()

    def test_add_priority_rejects_invalid(self, cli_runner):
        """Test --priority rejects invalid values."""
        stdout, stderr, code = cli_runner([
            "epic", "ticket", "add", "Test task",
            "--priority", "critical"  # invalid
        ])
        assert code != 0
        assert "invalid" in stderr.lower()

    def test_add_accepts_phase_option(self, cli_runner):
        """Test --phase option is recognized."""
        result = cli_runner([
            "epic", "ticket", "add", "Test task",
            "--phase", "build_01"
        ])
        # Parser should accept --phase
        assert "unrecognized" not in result.stderr.lower()

    def test_add_accepts_custom_id(self, cli_runner):
        """Test --id option for custom task ID."""
        result = cli_runner([
            "epic", "ticket", "add", "Test task",
            "--id", "custom_001"
        ])
        # Parser should accept --id
        assert "unrecognized" not in result.stderr.lower()
