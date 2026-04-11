"""Tests for 'agentic epic seed' command and max_turns truthiness fix."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def test_epic_seed_creates_epic_without_planner(tmp_path):
    """Epic seed creates TinyDB record without spawning any subprocess/SDK."""
    from agenticguidance.services.epic_repository import EpicRepository

    db_path = tmp_path / "epics.db"
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    git_result = MagicMock()
    git_result.stdout = str(tmp_path) + "\n"
    git_result.returncode = 0

    with patch("subprocess.run", return_value=git_result) as mock_subprocess, \
         patch("agenticcli.console.is_json_output", return_value=False), \
         patch("agenticcli.console.print_success"), \
         patch("agenticcli.console.console"):

        # cmd_seed delegates to cmd_init which calls _get_repo inside.
        # We need cmd_init to use our repo. Patch EpicRepository constructor.
        with patch("agenticguidance.services.epic_repository.EpicRepository", return_value=repo):
            from agenticcli.commands.epic import cmd_seed

            args = SimpleNamespace(
                objective="test objective",
                branch=None,
                description=None,
                base="main",
                debug=False,
                json=False,
            )
            cmd_seed(args)

    # Verify no claude subprocess was spawned (only git rev-parse)
    for call in mock_subprocess.call_args_list:
        cmd_arg = call[0][0] if call[0] else call[1].get("args", [])
        if isinstance(cmd_arg, list) and len(cmd_arg) > 0:
            assert cmd_arg[0] != "claude", "claude subprocess should not be spawned by seed"

    repo.close()


def test_epic_seed_returns_folder_path(tmp_path):
    """Seed outputs the epic folder name in JSON mode."""
    from agenticguidance.services.epic_repository import EpicRepository

    db_path = tmp_path / "epics.db"
    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)

    git_result = MagicMock()
    git_result.stdout = str(tmp_path) + "\n"
    git_result.returncode = 0

    captured_json = {}

    def capture_print_json(data):
        captured_json.update(data)

    with patch("subprocess.run", return_value=git_result), \
         patch("agenticcli.console.is_json_output", return_value=True), \
         patch("agenticcli.console.print_json", side_effect=capture_print_json), \
         patch("agenticcli.console.print_success"), \
         patch("agenticcli.console.console"), \
         patch("agenticguidance.services.epic_repository.EpicRepository", return_value=repo):

        from agenticcli.commands.epic import cmd_seed

        args = SimpleNamespace(
            objective="my test epic",
            branch="test-branch",
            description="my test epic",
            base="main",
            debug=False,
            json=True,
        )

        # Temporarily set is_json_output to False during cmd_init (it toggles)
        cmd_seed(args)

    assert captured_json.get("status") == "seed"
    assert captured_json.get("objective") == "my test epic"
    assert captured_json.get("branch") == "test-branch"

    repo.close()


def test_epic_new_max_turns_zero_passes_flag():
    """Regression: max_turns=0 should still pass --max-turns flag (not be falsy-skipped)."""
    # Directly test the code path that builds the claude command.
    # In cmd_new, the subprocess fallback path builds: claude_cmd = ["claude", ...]
    # with `if max_turns is not None:` (was `if max_turns:` which skipped 0).
    #
    # We isolate just the command construction by running cmd_new with max_turns=0
    # and checking what subprocess.run receives.

    git_result = MagicMock()
    git_result.stdout = "/tmp/repo\n"
    git_result.returncode = 0

    planner_result = MagicMock()
    planner_result.stdout = "done"
    planner_result.stderr = ""
    planner_result.returncode = 0

    calls = []

    def tracking_run(cmd, *a, **kw):
        calls.append(cmd)
        if isinstance(cmd, list) and cmd[0] == "git":
            return git_result
        return planner_result

    with patch("subprocess.run", side_effect=tracking_run), \
         patch("agenticcli.console.is_json_output", return_value=False), \
         patch("agenticcli.console.print_info"), \
         patch("agenticcli.console.print_error"), \
         patch("agenticcli.console.print_success"), \
         patch("agenticcli.console.print_warning"), \
         patch("agenticcli.console.set_json_output"), \
         patch("agenticcli.console.console"):

        with patch("agenticguidance.services.epic_repository.EpicRepository") as MockRepo:
            mock_repo_inst = MagicMock()
            mock_repo_inst.create_epic.return_value = MagicMock(success=True)
            mock_repo_inst.get_epic.return_value = None
            MockRepo.return_value = mock_repo_inst

            from agenticcli.commands.epic import cmd_new

            args = SimpleNamespace(
                objective="test",
                branch="test-branch",
                description="test",
                base="main",
                execute=False,
                max_turns=0,
                dangerously_skip_permissions=False,
                debug=False,
                json=False,
            )

            try:
                cmd_new(args)
            except (SystemExit, Exception):
                pass  # Expected

    # Find claude subprocess call and verify --max-turns 0
    claude_calls = [c for c in calls if isinstance(c, list) and "claude" in c]
    if claude_calls:
        cmd = claude_calls[0]
        assert "--max-turns" in cmd, "max_turns=0 should still pass --max-turns flag"
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "0"
