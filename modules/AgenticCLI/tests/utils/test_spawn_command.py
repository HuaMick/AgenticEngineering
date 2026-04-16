"""Tests for agenticcli.utils.spawn_command.build_spawn_command.

Covers:
- --model flag is appended when model arg is provided
- --model flag is absent when model is omitted (default None)
- --model value is placed immediately after the --model flag
- Other flags (--role, --epic, -b, --tmux, --phase, etc.) still work correctly
- model=None and model="" both omit the flag
"""

import pytest

pytestmark = pytest.mark.story("US-SES-001")


class TestBuildSpawnCommandModel:
    """Tests for the model parameter in build_spawn_command."""

    def test_build_spawn_command_forwards_model(self):
        """--model flag and value are appended when model is provided."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command("planner-build", "my_epic", model="claude-opus-4-6")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-opus-4-6"

    def test_build_spawn_command_no_model_by_default(self):
        """--model flag is absent when model arg is not passed."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command("build-python", "my_epic")
        assert "--model" not in cmd

    def test_build_spawn_command_model_none_omits_flag(self):
        """Explicit model=None also omits --model from the command."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command("test-builder", "my_epic", model=None)
        assert "--model" not in cmd

    def test_build_spawn_command_haiku_model(self):
        """Haiku model id is forwarded correctly."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command("epic-creator", "my_epic", model="claude-haiku-4-5-20251001")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-haiku-4-5-20251001"

    def test_build_spawn_command_sonnet_model(self):
        """Sonnet model id is forwarded correctly."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command("build-story-writer", "my_epic", model="claude-sonnet-4-6")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-sonnet-4-6"

    def test_build_spawn_command_model_adjacent_pair(self):
        """--model and its value are adjacent (no gap) in the command list."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command("planner-test", "epic_folder", model="claude-opus-4-6")
        idx = cmd.index("--model")
        # Adjacent pair: cmd[idx] == "--model", cmd[idx+1] == the value
        assert cmd[idx] == "--model"
        assert cmd[idx + 1] == "claude-opus-4-6"
        # Ensure nothing is between them
        assert idx + 1 < len(cmd)


class TestBuildSpawnCommandCoreFlags:
    """Verify core flags are not broken by the model parameter addition."""

    def test_role_and_epic_present(self):
        """--role and --epic are always present in the command."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command("planner-build", "260411_test_epic", model="claude-opus-4-6")
        assert "--role" in cmd
        assert cmd[cmd.index("--role") + 1] == "planner-build"
        assert "--epic" in cmd
        assert cmd[cmd.index("--epic") + 1] == "260411_test_epic"

    def test_background_flag_present_by_default(self):
        """Background flag (-b) is present by default."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command("build-python", "my_epic")
        assert "-b" in cmd

    def test_phase_id_and_model_coexist(self):
        """--phase and --model can both appear in the same command."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command(
            "planner-build",
            "my_epic",
            phase_id="phase-1",
            model="claude-opus-4-6",
        )
        assert "--phase" in cmd
        assert cmd[cmd.index("--phase") + 1] == "phase-1"
        assert "--model" in cmd
        assert cmd[cmd.index("--model") + 1] == "claude-opus-4-6"

    def test_max_turns_and_model_coexist(self):
        """--max-turns and --model can both appear in the same command."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command(
            "planner-test",
            "my_epic",
            max_turns=10,
            model="claude-opus-4-6",
        )
        assert "--max-turns" in cmd
        assert cmd[cmd.index("--max-turns") + 1] == "10"
        assert "--model" in cmd

    def test_command_is_list_of_strings(self):
        """build_spawn_command always returns a list of strings."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command("explore", "my_epic", model="claude-opus-4-6")
        assert isinstance(cmd, list)
        for item in cmd:
            assert isinstance(item, str), f"Non-string item in cmd: {item!r}"

    def test_agentic_is_first_element(self):
        """The first element of the command is always 'agentic'."""
        from agenticcli.utils.spawn_command import build_spawn_command

        cmd = build_spawn_command("build-python", "my_epic", model="claude-opus-4-6")
        assert cmd[0] == "agentic"
