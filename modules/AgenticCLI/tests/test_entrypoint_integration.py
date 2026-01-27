"""Integration tests for entrypoint execute command.

Tests real entrypoint file execution, variable substitution patterns,
and output format suitable for agent consumption.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml


@pytest.fixture
def project_with_entrypoints(tmp_path):
    """Create a project structure with entrypoints directory."""
    # Create project structure
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create .claude/entrypoints directory
    entrypoints_dir = project_dir / ".claude" / "entrypoints"
    entrypoints_dir.mkdir(parents=True)

    # Create modules/AgenticGuidance/entrypoints as fallback location
    guidance_entrypoints = project_dir / "modules" / "AgenticGuidance" / "entrypoints"
    guidance_entrypoints.mkdir(parents=True)

    return project_dir


@pytest.fixture
def entrypoints_dir(project_with_entrypoints):
    """Return the .claude/entrypoints directory."""
    return project_with_entrypoints / ".claude" / "entrypoints"


@pytest.fixture
def guidance_entrypoints_dir(project_with_entrypoints):
    """Return the modules/AgenticGuidance/entrypoints directory."""
    return project_with_entrypoints / "modules" / "AgenticGuidance" / "entrypoints"


@pytest.fixture
def build_entrypoint(entrypoints_dir):
    """Create a realistic build entrypoint file."""
    filepath = entrypoints_dir / "_build.yml"
    content = """entrypoint:
  name: "_build"
  goal: "Execute build workflow for {{PROJECT_NAME}}"
  description: "Build entrypoint for constructing features"

context:
  project: "{{PROJECT_NAME}}"
  task: "{{TASK_ID}}"
  timestamp: "{{TIMESTAMP}}"

phases:
  - name: "Setup"
    description: "Initialize build environment for {{PROJECT_NAME}}"
    steps:
      - "Load project configuration"
      - "Validate dependencies"

  - name: "Build"
    description: "Execute build steps"
    steps:
      - "Compile sources"
      - "Run tests"

  - name: "Deploy"
    description: "Deploy {{PROJECT_NAME}} artifacts"
    steps:
      - "Package artifacts"
      - "Push to registry"

output:
  format: "yaml"
  includes:
    - "Build logs"
    - "Test results"
    - "Deployment status"
"""
    filepath.write_text(content)
    return filepath


@pytest.fixture
def explore_entrypoint(entrypoints_dir):
    """Create a markdown exploration entrypoint."""
    filepath = entrypoints_dir / "_explore.md"
    content = """# Exploration Workflow

Exploring project: {{PROJECT_NAME}}
Task identifier: {{TASK_ID}}
Started at: {{TIMESTAMP}}

## Objectives

1. Analyze the {{PROJECT_NAME}} codebase structure
2. Identify key components and dependencies
3. Document findings for task {{TASK_ID}}

## Custom Configuration

Configuration value: {{CONFIG_VALUE}}

## Output Requirements

- Provide structured analysis in markdown format
- Include file paths and line references
- Summarize key findings at the end
"""
    filepath.write_text(content)
    return filepath


@pytest.fixture
def orchestration_entrypoint(guidance_entrypoints_dir):
    """Create an entrypoint in the guidance module location."""
    filepath = guidance_entrypoints_dir / "_orchestrate.yml"
    content = """entrypoint:
  name: "_orchestrate"
  goal: "Orchestrate execution of plan {{PLAN_ID}}"

orchestration:
  plan: "{{PLAN_ID}}"
  phase: "{{PHASE}}"
  mode: "{{MODE}}"

steps:
  - "Load plan {{PLAN_ID}}"
  - "Execute phase {{PHASE}}"
  - "Report status"
"""
    filepath.write_text(content)
    return filepath


class TestExecuteWithRealEntrypoints:
    """Tests for executing real entrypoint files."""

    def test_execute_yml_entrypoint(self, project_with_entrypoints, build_entrypoint, capsys, monkeypatch):
        """Test executing a real YAML entrypoint file."""
        from agenticcli.commands import entrypoint

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(
            name="_build",
            vars=["PROJECT_NAME=TestProject", "TASK_ID=T-001"],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()

        # Verify substitutions occurred
        assert "TestProject" in captured.out
        assert "T-001" in captured.out
        assert "{{PROJECT_NAME}}" not in captured.out
        assert "{{TASK_ID}}" not in captured.out

        # Verify structure is preserved
        assert "entrypoint:" in captured.out
        assert "phases:" in captured.out

    def test_execute_md_entrypoint(self, project_with_entrypoints, explore_entrypoint, capsys, monkeypatch):
        """Test executing a real Markdown entrypoint file."""
        from agenticcli.commands import entrypoint

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(
            name="explore",
            vars=[
                "PROJECT_NAME=MyApp",
                "TASK_ID=EXPLORE-42",
                "CONFIG_VALUE=production",
            ],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()

        # Verify markdown structure preserved
        assert "# Exploration Workflow" in captured.out
        assert "## Objectives" in captured.out

        # Verify substitutions
        assert "MyApp" in captured.out
        assert "EXPLORE-42" in captured.out
        assert "production" in captured.out

    def test_execute_from_guidance_location(
        self, project_with_entrypoints, orchestration_entrypoint, capsys, monkeypatch
    ):
        """Test executing entrypoint from modules/AgenticGuidance/entrypoints."""
        from agenticcli.commands import entrypoint

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(
            name="orchestrate",
            vars=["PLAN_ID=260127EX", "PHASE=build", "MODE=incremental"],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()

        assert "260127EX" in captured.out
        assert "build" in captured.out
        assert "incremental" in captured.out


class TestVariableSubstitutionPatterns:
    """Tests for {{VAR}} variable substitution patterns."""

    def test_standard_placeholder_substitution(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test standard {{VAR}} placeholder substitution."""
        from agenticcli.commands import entrypoint

        # Create test entrypoint
        filepath = entrypoints_dir / "_vars.yml"
        filepath.write_text("value: {{MYVAR}}")

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(name="vars", vars=["MYVAR=substituted"], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert "value: substituted" in captured.out

    def test_whitespace_in_placeholder(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test {{ VAR }} with internal whitespace."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_spaces.yml"
        filepath.write_text("value: {{ SPACED_VAR }}")

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(
            name="spaces", vars=["SPACED_VAR=works_with_spaces"], context=None
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert "value: works_with_spaces" in captured.out

    def test_multiple_same_variable(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test multiple occurrences of same variable."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_multi.yml"
        content = """first: {{NAME}}
second: {{NAME}}
third: {{ NAME }}"""
        filepath.write_text(content)

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(name="multi", vars=["NAME=repeated"], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert captured.out.count("repeated") == 3
        assert "{{NAME}}" not in captured.out
        assert "{{ NAME }}" not in captured.out

    def test_builtin_timestamp_variable(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test that TIMESTAMP is automatically added."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_time.yml"
        filepath.write_text("started: {{TIMESTAMP}}")

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(name="time", vars=[], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        # Timestamp should be ISO format date
        assert "{{TIMESTAMP}}" not in captured.out
        # Should contain date-like pattern
        assert "started: 20" in captured.out  # Starts with year

    def test_undefined_variables_preserved(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test that undefined variables are preserved in output."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_undef.yml"
        filepath.write_text("value: {{UNDEFINED_VAR}}")

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(name="undef", vars=[], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        # Undefined variable should remain as placeholder
        assert "{{UNDEFINED_VAR}}" in captured.out

    def test_mixed_defined_undefined_variables(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test mix of defined and undefined variables."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_mixed.yml"
        content = """defined: {{DEFINED_VAR}}
undefined: {{UNDEFINED_VAR}}"""
        filepath.write_text(content)

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(
            name="mixed", vars=["DEFINED_VAR=this_is_defined"], context=None
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert "defined: this_is_defined" in captured.out
        assert "undefined: {{UNDEFINED_VAR}}" in captured.out

    def test_variable_with_special_characters(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test variable values with special characters."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_special.yml"
        filepath.write_text("path: {{FILE_PATH}}")

        monkeypatch.chdir(project_with_entrypoints)

        # Value with path separators and special chars
        args = SimpleNamespace(
            name="special", vars=["FILE_PATH=/path/to/file.txt"], context=None
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert "path: /path/to/file.txt" in captured.out

    def test_variable_in_complex_yaml_structure(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test variables in nested YAML structures."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_nested.yml"
        content = """config:
  project:
    name: "{{PROJECT}}"
    tasks:
      - id: "{{TASK_1}}"
        priority: high
      - id: "{{TASK_2}}"
        priority: low
  output:
    directory: "{{OUTPUT_DIR}}"
"""
        filepath.write_text(content)

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(
            name="nested",
            vars=[
                "PROJECT=NestedTest",
                "TASK_1=T1",
                "TASK_2=T2",
                "OUTPUT_DIR=/tmp/out",
            ],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert 'name: "NestedTest"' in captured.out
        assert 'id: "T1"' in captured.out
        assert 'id: "T2"' in captured.out
        assert 'directory: "/tmp/out"' in captured.out


class TestOutputFormatForAgents:
    """Tests for output format suitable for agent consumption."""

    def test_text_output_is_plain_content(
        self, project_with_entrypoints, build_entrypoint, capsys, monkeypatch
    ):
        """Test that text output is plain, suitable for agent parsing."""
        from agenticcli.commands import entrypoint

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(
            name="build",
            vars=["PROJECT_NAME=Test", "TASK_ID=T-1"],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()

        # Should be valid YAML
        parsed = yaml.safe_load(captured.out)
        assert parsed is not None
        assert "entrypoint" in parsed

    def test_json_output_structure(
        self, project_with_entrypoints, build_entrypoint, capsys, monkeypatch
    ):
        """Test JSON output has correct structure for agents."""
        from agenticcli.commands import entrypoint

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(
            name="build",
            vars=["PROJECT_NAME=JSONTest", "TASK_ID=JSON-1"],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # Verify required fields for agent consumption
        assert "name" in output
        assert "path" in output
        assert "content" in output
        assert "variables_applied" in output
        assert "context_prepended" in output

        # Verify content is accessible as string
        assert isinstance(output["content"], str)
        assert "JSONTest" in output["content"]

    def test_json_output_variables_list(
        self, project_with_entrypoints, build_entrypoint, capsys, monkeypatch
    ):
        """Test JSON output includes applied variables list."""
        from agenticcli.commands import entrypoint

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(
            name="build",
            vars=["PROJECT_NAME=VarTest", "TASK_ID=V-1", "EXTRA=extra"],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=True):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        variables = output["variables_applied"]
        assert "PROJECT_NAME" in variables
        assert "TASK_ID" in variables
        assert "EXTRA" in variables
        assert "TIMESTAMP" in variables  # Built-in always added

    def test_context_prepending_format(
        self, project_with_entrypoints, build_entrypoint, capsys, monkeypatch
    ):
        """Test context is prepended with proper formatting."""
        from agenticcli.commands import entrypoint

        monkeypatch.chdir(project_with_entrypoints)

        context_text = "This is the user-provided context.\nIt has multiple lines."

        args = SimpleNamespace(
            name="build",
            vars=["PROJECT_NAME=ContextTest", "TASK_ID=C-1"],
            context=context_text,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()

        # Context should appear at top with header
        lines = captured.out.split("\n")
        assert lines[0] == "# Context"
        assert "This is the user-provided context." in captured.out
        assert "---" in captured.out  # Separator between context and content

        # Original content should follow
        assert "entrypoint:" in captured.out

    def test_markdown_output_preserved(
        self, project_with_entrypoints, explore_entrypoint, capsys, monkeypatch
    ):
        """Test markdown formatting is preserved in output."""
        from agenticcli.commands import entrypoint

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(
            name="explore",
            vars=[
                "PROJECT_NAME=MDTest",
                "TASK_ID=MD-1",
                "CONFIG_VALUE=test_config",
            ],
            context=None,
        )

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()

        # Markdown elements should be preserved
        assert "# Exploration Workflow" in captured.out
        assert "## Objectives" in captured.out
        assert "1. Analyze" in captured.out
        assert "- Provide structured" in captured.out


class TestEntrypointPriorityResolution:
    """Tests for entrypoint priority when same name exists in multiple locations."""

    def test_cwd_entrypoint_takes_priority(
        self, project_with_entrypoints, entrypoints_dir, guidance_entrypoints_dir, capsys, monkeypatch
    ):
        """Test .claude/entrypoints takes priority over modules/AgenticGuidance/entrypoints."""
        from agenticcli.commands import entrypoint

        # Create same-named entrypoint in both locations
        cwd_file = entrypoints_dir / "_priority.yml"
        cwd_file.write_text("source: cwd_entrypoints")

        guidance_file = guidance_entrypoints_dir / "_priority.yml"
        guidance_file.write_text("source: guidance_entrypoints")

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(name="priority", vars=[], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        # CWD should take priority
        assert "source: cwd_entrypoints" in captured.out
        assert "source: guidance_entrypoints" not in captured.out


class TestEdgeCases:
    """Edge case tests for entrypoint execution."""

    def test_empty_entrypoint_file(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test executing an empty entrypoint file."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_empty.yml"
        filepath.write_text("")

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(name="empty", vars=[], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        # Should output empty content without error
        assert captured.out.strip() == "" or captured.out.strip() == "# Context"

    def test_entrypoint_with_only_comments(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test entrypoint with only YAML comments."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_comments.yml"
        filepath.write_text("# This is a comment\n# Another comment\n")

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(name="comments", vars=[], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert "# This is a comment" in captured.out

    def test_entrypoint_with_unicode(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test entrypoint with unicode characters."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_unicode.yml"
        filepath.write_text("message: Hello {{NAME}} - Bonjour, Hola, Guten Tag!")

        monkeypatch.chdir(project_with_entrypoints)

        args = SimpleNamespace(name="unicode", vars=["NAME=World"], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert "Hello World - Bonjour, Hola, Guten Tag!" in captured.out

    def test_large_variable_value(
        self, project_with_entrypoints, entrypoints_dir, capsys, monkeypatch
    ):
        """Test with large variable value."""
        from agenticcli.commands import entrypoint

        filepath = entrypoints_dir / "_large.yml"
        filepath.write_text("content: {{LARGE}}")

        monkeypatch.chdir(project_with_entrypoints)

        large_value = "x" * 10000  # 10KB value
        args = SimpleNamespace(name="large", vars=[f"LARGE={large_value}"], context=None)

        with patch("agenticcli.console.is_json_output", return_value=False):
            entrypoint.cmd_execute(args)

        captured = capsys.readouterr()
        assert large_value in captured.out
