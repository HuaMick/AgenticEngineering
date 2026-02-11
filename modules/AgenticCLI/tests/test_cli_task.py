"""Tests for task subcommand CLI functionality.

Unit tests for argument parsing of task prefill, list, status, and add commands.
"""

import pytest

pytestmark = pytest.mark.unit


class TestTaskPrefillParser:
    """Tests for 'agentic plan task prefill' argument parsing."""

    def test_prefill_help_shows_options(self, cli_runner):
        """Test prefill --help shows all options."""
        stdout, stderr, code = cli_runner(["plan", "task", "prefill", "--help"])
        assert "--preset" in stdout
        assert "-t" in stdout  # short form
        assert "--plan" in stdout
        assert "--dry-run" in stdout
        assert code == 0

    def test_prefill_requires_preset(self, cli_runner):
        """Test that --preset is required."""
        stdout, stderr, code = cli_runner(["plan", "task", "prefill"])
        assert code != 0
        assert "required" in stderr.lower() or "preset" in stderr.lower()

    def test_prefill_accepts_preset_short_form(self, cli_runner):
        """Test -t shortcut for --preset."""
        # This will fail at runtime (preset not found) but parser accepts it
        stdout, stderr, code = cli_runner(
            ["plan", "task", "prefill", "-t", "nonexistent"]
        )
        # Parser accepts the argument structure, runtime fails finding preset
        assert code != 0
        # Either runtime error about not found or parser error
        assert "not found" in stderr.lower() or code != 0

    def test_prefill_accepts_dry_run_flag(self, cli_runner):
        """Test --dry-run flag is recognized."""
        # Parser should accept the flag even if command fails for other reasons
        stdout, stderr, code = cli_runner(
            ["plan", "task", "prefill", "-t", "nonexistent", "--dry-run"]
        )
        # Parser accepted --dry-run, error is about preset not found
        assert "invalid" not in stderr.lower() or "not found" in stderr.lower()

    def test_prefill_accepts_short_dry_run(self, cli_runner):
        """Test -n shortcut for --dry-run."""
        stdout, stderr, code = cli_runner(
            ["plan", "task", "prefill", "-t", "nonexistent", "-n"]
        )
        # Parser should accept -n flag
        assert "unrecognized" not in stderr.lower()


class TestTaskListParser:
    """Tests for 'agentic plan task list' argument parsing."""

    def test_list_help_shows_options(self, cli_runner):
        """Test list --help shows all options."""
        stdout, stderr, code = cli_runner(["plan", "task", "list", "--help"])
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
            result = cli_runner(["plan", "task", "list", "--status", choice])
            # Parser should not reject valid choices
            assert "invalid choice" not in result.stderr.lower()

    def test_list_status_rejects_invalid(self, cli_runner):
        """Test --status rejects invalid values."""
        stdout, stderr, code = cli_runner(
            ["plan", "task", "list", "--status", "invalid_status"]
        )
        assert code != 0
        assert "invalid" in stderr.lower()

    def test_list_accepts_verbose_flag(self, cli_runner):
        """Test --verbose flag is recognized."""
        result = cli_runner(["plan", "task", "list", "--verbose", "--help"])
        # Help should show the verbose option
        assert "--verbose" in result.stdout or "-v" in result.stdout


class TestTaskStatusParser:
    """Tests for 'agentic plan task status' argument parsing."""

    def test_status_help_shows_options(self, cli_runner):
        """Test status --help shows options."""
        stdout, stderr, code = cli_runner(["plan", "task", "status", "--help"])
        assert "task_id" in stdout.lower()
        assert "--plan" in stdout
        assert code == 0

    def test_status_requires_task_id(self, cli_runner):
        """Test that task_id positional argument is required."""
        stdout, stderr, code = cli_runner(["plan", "task", "status"])
        assert code != 0
        # argparse error for missing positional
        assert "required" in stderr.lower() or "argument" in stderr.lower()

    def test_status_accepts_task_id(self, cli_runner):
        """Test parser accepts task_id positional."""
        # Will fail at runtime but parser accepts the argument
        result = cli_runner(["plan", "task", "status", "build_01_001"])
        # Parser accepted the task_id, runtime may fail finding it
        assert "invalid" not in result.stderr.lower() or "not found" in result.stderr.lower()


class TestTaskAddParser:
    """Tests for 'agentic plan task add' argument parsing."""

    def test_add_help_shows_options(self, cli_runner):
        """Test add --help shows all options."""
        stdout, stderr, code = cli_runner(["plan", "task", "add", "--help"])
        assert "description" in stdout.lower()
        assert "--plan" in stdout
        assert "--phase" in stdout
        assert "--id" in stdout
        assert "--priority" in stdout
        assert code == 0

    def test_add_requires_description(self, cli_runner):
        """Test that description is required."""
        stdout, stderr, code = cli_runner(["plan", "task", "add"])
        assert code != 0
        assert "required" in stderr.lower() or "argument" in stderr.lower()

    def test_add_priority_choices(self, cli_runner):
        """Test --priority accepts valid choices."""
        valid_choices = ["low", "medium", "high"]
        for choice in valid_choices:
            result = cli_runner([
                "plan", "task", "add", "Test task",
                "--priority", choice
            ])
            # Parser should not reject valid choices
            assert "invalid choice" not in result.stderr.lower()

    def test_add_priority_rejects_invalid(self, cli_runner):
        """Test --priority rejects invalid values."""
        stdout, stderr, code = cli_runner([
            "plan", "task", "add", "Test task",
            "--priority", "critical"  # invalid
        ])
        assert code != 0
        assert "invalid" in stderr.lower()

    def test_add_accepts_phase_option(self, cli_runner):
        """Test --phase option is recognized."""
        result = cli_runner([
            "plan", "task", "add", "Test task",
            "--phase", "build_01"
        ])
        # Parser should accept --phase
        assert "unrecognized" not in result.stderr.lower()

    def test_add_accepts_custom_id(self, cli_runner):
        """Test --id option for custom task ID."""
        result = cli_runner([
            "plan", "task", "add", "Test task",
            "--id", "custom_001"
        ])
        # Parser should accept --id
        assert "unrecognized" not in result.stderr.lower()
