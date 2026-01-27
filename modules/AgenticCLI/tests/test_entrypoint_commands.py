"""Tests for entrypoint CLI commands.

Unit tests for the entrypoint command module covering:
- _get_entrypoints_dirs() path resolution
- _find_entrypoint() name resolution (with/without underscore)
- _list_entrypoints() discovery
- cmd_list() text and JSON output
- cmd_show() content display
- cmd_execute() variable substitution
- Error handling for missing entrypoints
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture
def entrypoints_dir(tmp_path):
    """Create a temporary entrypoints directory with test files."""
    entrypoints = tmp_path / ".claude" / "entrypoints"
    entrypoints.mkdir(parents=True)
    return entrypoints


@pytest.fixture
def mock_entrypoints_dir(entrypoints_dir, monkeypatch):
    """Patch _get_entrypoints_dirs to use temp directory."""
    from agenticcli.commands import entrypoint

    monkeypatch.setattr(entrypoint, "_get_entrypoints_dirs", lambda: [entrypoints_dir])
    return entrypoints_dir


@pytest.fixture
def sample_yml_entrypoint(entrypoints_dir):
    """Create a sample YAML entrypoint file."""
    filepath = entrypoints_dir / "_test_build.yml"
    content = {
        "entrypoint": {
            "name": "_test_build",
            "goal": "Build test implementation",
            "description": "Test entrypoint for building features",
        },
        "steps": [
            "Step 1: Initialize",
            "Step 2: Execute",
        ],
    }
    with open(filepath, "w") as f:
        yaml.dump(content, f)
    return filepath


@pytest.fixture
def sample_md_entrypoint(entrypoints_dir):
    """Create a sample Markdown entrypoint file."""
    filepath = entrypoints_dir / "_test_explore.md"
    content = """# Exploration Entrypoint

This is a test markdown entrypoint for exploration tasks.

## Variables

- {{PROJECT_NAME}}: The project name
- {{TASK_ID}}: The task identifier

## Steps

1. Analyze the {{PROJECT_NAME}} structure
2. Execute task {{TASK_ID}}
3. Report findings at {{TIMESTAMP}}
"""
    filepath.write_text(content)
    return filepath


@pytest.fixture
def sample_entrypoint_with_vars(entrypoints_dir):
    """Create an entrypoint with variable placeholders."""
    filepath = entrypoints_dir / "_vars_test.yml"
    content = """entrypoint:
  name: "_vars_test"
  goal: "Test variable substitution for {{PROJECT}}"

context: |
  Working on {{PROJECT}} with task {{TASK_ID}}.
  Started at {{TIMESTAMP}}.

  Custom value: {{ CUSTOM_VAR }}
"""
    filepath.write_text(content)
    return filepath


class TestGetEntrypointsDirs:
    """Tests for _get_entrypoints_dirs function."""

    def test_returns_list(self, tmp_path, monkeypatch):
        """Test that _get_entrypoints_dirs returns a list."""
        from agenticcli.commands import entrypoint

        monkeypatch.chdir(tmp_path)
        result = entrypoint._get_entrypoints_dirs()

        assert isinstance(result, list)

    def test_includes_cwd_entrypoints(self, tmp_path, monkeypatch):
        """Test that CWD .claude/entrypoints is included if it exists."""
        from agenticcli.commands import entrypoint

        # Create .claude/entrypoints in tmp_path
        entrypoints_dir = tmp_path / ".claude" / "entrypoints"
        entrypoints_dir.mkdir(parents=True)

        monkeypatch.chdir(tmp_path)
        result = entrypoint._get_entrypoints_dirs()

        assert entrypoints_dir in result

    def test_excludes_nonexistent_cwd_entrypoints(self, tmp_path, monkeypatch):
        """Test that nonexistent CWD .claude/entrypoints is not included."""
        from agenticcli.commands import entrypoint

        monkeypatch.chdir(tmp_path)
        # No .claude/entrypoints created
        result = entrypoint._get_entrypoints_dirs()

        expected_path = tmp_path / ".claude" / "entrypoints"
        assert expected_path not in result

    def test_searches_for_project_entrypoints(self, tmp_path, monkeypatch):
        """Test that project modules/AgenticGuidance/entrypoints is searched."""
        from agenticcli.commands import entrypoint

        # Create project structure with AgenticGuidance entrypoints
        project_entrypoints = tmp_path / "modules" / "AgenticGuidance" / "entrypoints"
        project_entrypoints.mkdir(parents=True)

        monkeypatch.chdir(tmp_path)
        result = entrypoint._get_entrypoints_dirs()

        assert project_entrypoints in result


class TestNormalizeEntrypointName:
    """Tests for _normalize_entrypoint_name function."""

    def test_strips_leading_underscore(self):
        """Test that leading underscore is stripped."""
        from agenticcli.commands import entrypoint

        assert entrypoint._normalize_entrypoint_name("_plan_build") == "plan_build"

    def test_preserves_name_without_underscore(self):
        """Test that name without underscore is preserved."""
        from agenticcli.commands import entrypoint

        assert entrypoint._normalize_entrypoint_name("plan_build") == "plan_build"

    def test_strips_multiple_leading_underscores(self):
        """Test that multiple leading underscores are stripped."""
        from agenticcli.commands import entrypoint

        assert entrypoint._normalize_entrypoint_name("__test") == "test"


class TestGetEntrypointNameFromFile:
    """Tests for _get_entrypoint_name_from_file function."""

    def test_extracts_name_from_yml_file(self, tmp_path):
        """Test extracting name from .yml file."""
        from agenticcli.commands import entrypoint

        filepath = tmp_path / "_plan_build.yml"
        filepath.touch()

        assert entrypoint._get_entrypoint_name_from_file(filepath) == "plan_build"

    def test_extracts_name_from_md_file(self, tmp_path):
        """Test extracting name from .md file."""
        from agenticcli.commands import entrypoint

        filepath = tmp_path / "_explore.md"
        filepath.touch()

        assert entrypoint._get_entrypoint_name_from_file(filepath) == "explore"


class TestFindEntrypoint:
    """Tests for _find_entrypoint function."""

    def test_finds_yml_entrypoint(self, mock_entrypoints_dir, sample_yml_entrypoint):
        """Test finding a YAML entrypoint file."""
        from agenticcli.commands import entrypoint

        result = entrypoint._find_entrypoint("test_build")

        assert result == sample_yml_entrypoint

    def test_finds_entrypoint_with_underscore_prefix(
        self, mock_entrypoints_dir, sample_yml_entrypoint
    ):
        """Test finding entrypoint when name includes underscore prefix."""
        from agenticcli.commands import entrypoint

        result = entrypoint._find_entrypoint("_test_build")

        assert result == sample_yml_entrypoint

    def test_finds_md_entrypoint(self, mock_entrypoints_dir, sample_md_entrypoint):
        """Test finding a Markdown entrypoint file."""
        from agenticcli.commands import entrypoint

        result = entrypoint._find_entrypoint("test_explore")

        assert result == sample_md_entrypoint

    def test_returns_none_for_missing_entrypoint(self, mock_entrypoints_dir):
        """Test that None is returned for nonexistent entrypoint."""
        from agenticcli.commands import entrypoint

        result = entrypoint._find_entrypoint("nonexistent")

        assert result is None

    def test_prefers_yml_over_md(self, mock_entrypoints_dir):
        """Test that .yml is preferred over .md when both exist."""
        from agenticcli.commands import entrypoint

        # Create both .yml and .md with same name
        yml_file = mock_entrypoints_dir / "_dual.yml"
        md_file = mock_entrypoints_dir / "_dual.md"
        yml_file.write_text("entrypoint:\n  name: dual\n")
        md_file.write_text("# Dual entrypoint")

        result = entrypoint._find_entrypoint("dual")

        assert result == yml_file


class TestExtractDescription:
    """Tests for _extract_description function."""

    def test_extracts_goal_from_yml(self, sample_yml_entrypoint):
        """Test extracting goal from YAML entrypoint."""
        from agenticcli.commands import entrypoint

        result = entrypoint._extract_description(sample_yml_entrypoint)

        assert result == "Build test implementation"

    def test_extracts_heading_from_md(self, sample_md_entrypoint):
        """Test extracting heading from Markdown entrypoint."""
        from agenticcli.commands import entrypoint

        result = entrypoint._extract_description(sample_md_entrypoint)

        assert result == "Exploration Entrypoint"

    def test_returns_empty_for_invalid_file(self, tmp_path):
        """Test that empty string is returned for invalid file."""
        from agenticcli.commands import entrypoint

        invalid_file = tmp_path / "_invalid.yml"
        invalid_file.write_text("not: valid: yaml: {{")

        result = entrypoint._extract_description(invalid_file)

        assert result == ""


class TestListEntrypoints:
    """Tests for _list_entrypoints function."""

    def test_returns_list_of_dicts(self, mock_entrypoints_dir, sample_yml_entrypoint):
        """Test that _list_entrypoints returns list of dicts."""
        from agenticcli.commands import entrypoint

        result = entrypoint._list_entrypoints()

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(ep, dict) for ep in result)

    def test_includes_required_fields(self, mock_entrypoints_dir, sample_yml_entrypoint):
        """Test that entrypoint dicts include required fields."""
        from agenticcli.commands import entrypoint

        result = entrypoint._list_entrypoints()
        ep = result[0]

        assert "name" in ep
        assert "path" in ep
        assert "type" in ep
        assert "description" in ep

    def test_includes_underscore_in_name(
        self, mock_entrypoints_dir, sample_yml_entrypoint
    ):
        """Test that entrypoint name includes underscore prefix."""
        from agenticcli.commands import entrypoint

        result = entrypoint._list_entrypoints()
        ep = result[0]

        assert ep["name"].startswith("_")

    def test_skips_non_underscore_files(self, mock_entrypoints_dir):
        """Test that files not starting with underscore are skipped."""
        from agenticcli.commands import entrypoint

        # Create file without underscore prefix
        regular_file = mock_entrypoints_dir / "regular.yml"
        regular_file.write_text("name: regular")

        result = entrypoint._list_entrypoints()

        names = [ep["name"] for ep in result]
        assert "_regular" not in names
        assert "regular" not in names

    def test_skips_non_entrypoint_extensions(self, mock_entrypoints_dir):
        """Test that non-yml/md files are skipped."""
        from agenticcli.commands import entrypoint

        # Create file with invalid extension
        txt_file = mock_entrypoints_dir / "_test.txt"
        txt_file.write_text("test content")

        result = entrypoint._list_entrypoints()

        names = [ep["name"] for ep in result]
        assert "_test" not in names

    def test_returns_empty_for_no_entrypoints(self, mock_entrypoints_dir):
        """Test that empty list is returned when no entrypoints exist."""
        from agenticcli.commands import entrypoint

        result = entrypoint._list_entrypoints()

        assert result == []

    def test_deduplicates_by_name(self, mock_entrypoints_dir):
        """Test that duplicate names from different dirs are deduplicated."""
        from agenticcli.commands import entrypoint

        # Create same-named entrypoint
        yml_file = mock_entrypoints_dir / "_dupe.yml"
        yml_file.write_text("entrypoint:\n  name: dupe\n")

        # Mock two directories returning same name
        second_dir = mock_entrypoints_dir.parent / "second_entrypoints"
        second_dir.mkdir(parents=True)
        second_file = second_dir / "_dupe.yml"
        second_file.write_text("entrypoint:\n  name: dupe2\n")

        with patch.object(
            entrypoint, "_get_entrypoints_dirs", return_value=[mock_entrypoints_dir, second_dir]
        ):
            result = entrypoint._list_entrypoints()

        dupe_entries = [ep for ep in result if ep["name"] == "_dupe"]
        assert len(dupe_entries) == 1  # First one wins


class TestCmdList:
    """Tests for cmd_list command."""

    def test_list_text_output(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test cmd_list with text output."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace()

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_list(args)

        captured = capsys.readouterr()
        assert "Available Entrypoints" in captured.out
        assert "_test_build" in captured.out

    def test_list_json_output(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test cmd_list with JSON output."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace()

        with patch("agenticcli.console.is_json_output", return_value=True):
            entrypoint.cmd_list(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert "entrypoints" in output
        assert "count" in output
        assert output["count"] == 1
        assert output["entrypoints"][0]["name"] == "_test_build"

    def test_list_empty_text_output(self, mock_entrypoints_dir, capsys):
        """Test cmd_list text output when no entrypoints exist."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace()

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_list(args)

        captured = capsys.readouterr()
        assert "No entrypoints found" in captured.out

    def test_list_empty_json_output(self, mock_entrypoints_dir, capsys):
        """Test cmd_list JSON output when no entrypoints exist."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace()

        with patch("agenticcli.console.is_json_output", return_value=True):
            entrypoint.cmd_list(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["count"] == 0
        assert output["entrypoints"] == []


class TestCmdShow:
    """Tests for cmd_show command."""

    def test_show_displays_content(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test cmd_show displays entrypoint content."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(name="test_build")

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_show(args)

        captured = capsys.readouterr()
        assert "entrypoint:" in captured.out
        assert "goal: Build test implementation" in captured.out

    def test_show_json_output(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test cmd_show with JSON output."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(name="test_build")

        with patch("agenticcli.console.is_json_output", return_value=True):
            entrypoint.cmd_show(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["name"] == "_test_build"
        assert output["type"] == "yml"
        assert "content" in output
        assert "entrypoint:" in output["content"]

    def test_show_accepts_underscore_prefix(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test cmd_show accepts name with underscore prefix."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(name="_test_build")

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_show(args)

        captured = capsys.readouterr()
        assert "entrypoint:" in captured.out

    def test_show_missing_entrypoint_error(self, mock_entrypoints_dir, capsys):
        """Test cmd_show exits with error for missing entrypoint."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(name="nonexistent")

        with pytest.raises(SystemExit) as exc_info:
            with patch("agenticcli.console.is_json_output", return_value=False):
                entrypoint.cmd_show(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Entrypoint not found" in captured.err
        assert "nonexistent" in captured.err

    def test_show_provides_hint(self, mock_entrypoints_dir, capsys):
        """Test cmd_show provides hint when entrypoint not found."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(name="missing")

        with pytest.raises(SystemExit):
            with patch("agenticcli.console.is_json_output", return_value=False):
                entrypoint.cmd_show(args)

        captured = capsys.readouterr()
        assert "agentic entrypoint list" in captured.err


class TestCmdExecute:
    """Tests for cmd_execute command."""

    def test_execute_outputs_content(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test cmd_execute outputs entrypoint content."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(name="test_build", vars=[], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert "entrypoint:" in captured.out

    def test_execute_substitutes_variables(
        self, mock_entrypoints_dir, sample_entrypoint_with_vars, capsys
    ):
        """Test cmd_execute performs variable substitution."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(
            name="vars_test",
            vars=["PROJECT=MyProject", "TASK_ID=TASK-123", "CUSTOM_VAR=custom_value"],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert "MyProject" in captured.out
        assert "TASK-123" in captured.out
        assert "custom_value" in captured.out
        # Original placeholders should be replaced
        assert "{{PROJECT}}" not in captured.out
        assert "{{TASK_ID}}" not in captured.out

    def test_execute_adds_timestamp(
        self, mock_entrypoints_dir, sample_entrypoint_with_vars, capsys
    ):
        """Test cmd_execute adds TIMESTAMP variable."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(name="vars_test", vars=[], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        # TIMESTAMP should be replaced with ISO format date
        assert "{{TIMESTAMP}}" not in captured.out

    def test_execute_preserves_unknown_variables(
        self, mock_entrypoints_dir, sample_entrypoint_with_vars, capsys
    ):
        """Test cmd_execute preserves unknown variable placeholders."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(name="vars_test", vars=[], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        # Unknown variables should remain as-is
        assert "{{PROJECT}}" in captured.out
        assert "{{TASK_ID}}" in captured.out

    def test_execute_handles_whitespace_in_placeholders(
        self, mock_entrypoints_dir, sample_entrypoint_with_vars, capsys
    ):
        """Test cmd_execute handles {{ VAR }} with whitespace."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(
            name="vars_test",
            vars=["CUSTOM_VAR=whitespace_test"],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert "whitespace_test" in captured.out
        assert "{{ CUSTOM_VAR }}" not in captured.out

    def test_execute_prepends_context(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test cmd_execute prepends context when provided."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(
            name="test_build",
            vars=[],
            context="This is additional context for the agent.",
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        # Context should be prepended with header
        assert "# Context" in captured.out
        assert "This is additional context" in captured.out
        # Original content should still be present
        assert "entrypoint:" in captured.out

    def test_execute_json_output(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test cmd_execute with JSON output."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(
            name="test_build",
            vars=["VAR1=value1"],
            context="Test context",
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["name"] == "_test_build"
        assert "content" in output
        assert "VAR1" in output["variables_applied"]
        assert "TIMESTAMP" in output["variables_applied"]
        assert output["context_prepended"] is True

    def test_execute_missing_entrypoint_error(self, mock_entrypoints_dir, capsys):
        """Test cmd_execute exits with error for missing entrypoint."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(name="nonexistent", vars=[], context=None)

        with pytest.raises(SystemExit) as exc_info:
            with patch("agenticcli.console.is_json_output", return_value=False):
                entrypoint.cmd_execute(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Entrypoint not found" in captured.err

    def test_execute_invalid_var_format_error(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test cmd_execute exits with error for invalid var format."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(
            name="test_build",
            vars=["INVALID_VAR_NO_EQUALS"],
            context=None,
        )

        with pytest.raises(SystemExit) as exc_info:
            with patch("agenticcli.console.is_json_output", return_value=False):
                entrypoint.cmd_execute(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Invalid variable format" in captured.err


class TestHandleRouting:
    """Tests for the handle function command routing."""

    def test_handle_routes_to_list(self, mock_entrypoints_dir, capsys):
        """Test handle routes 'list' command correctly."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(entrypoint_command="list")

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.handle(args)

        captured = capsys.readouterr()
        assert "Available Entrypoints" in captured.out or "No entrypoints found" in captured.out

    def test_handle_routes_to_show(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test handle routes 'show' command correctly."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(entrypoint_command="show", name="test_build")

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.handle(args)

        captured = capsys.readouterr()
        assert "entrypoint:" in captured.out

    def test_handle_routes_to_execute(
        self, mock_entrypoints_dir, sample_yml_entrypoint, capsys
    ):
        """Test handle routes 'execute' command correctly."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(
            entrypoint_command="execute",
            name="test_build",
            vars=[],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.handle(args)

        captured = capsys.readouterr()
        assert "entrypoint:" in captured.out

    def test_handle_invalid_command_error(self, mock_entrypoints_dir, capsys):
        """Test handle exits with error for invalid command."""
        from agenticcli.commands import entrypoint

        args = SimpleNamespace(entrypoint_command="invalid")

        with pytest.raises(SystemExit) as exc_info:
            entrypoint.handle(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Usage:" in captured.err
