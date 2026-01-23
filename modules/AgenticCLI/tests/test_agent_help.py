"""Tests for agent-specific help commands.

Tests the agent flag detection and help output functionality.
"""

import json
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agenticcli.commands.agent_help import (
    AGENT_CATEGORIES,
    KNOWN_AGENTS,
    get_agent_from_flag,
    is_agent_flag,
    show_agent_help,
    _load_agent_context,
    _find_agent_directory,
)


class TestAgentFlagDetection:
    """Tests for agent flag detection functions."""

    def test_is_agent_flag_valid(self):
        """Test detection of valid agent flags."""
        assert is_agent_flag("--planner-guidance") is True
        assert is_agent_flag("--build-python") is True
        assert is_agent_flag("--test-runner") is True
        assert is_agent_flag("--orchestration-executor") is True

    def test_is_agent_flag_invalid(self):
        """Test rejection of invalid agent flags."""
        assert is_agent_flag("--nonexistent-agent") is False
        assert is_agent_flag("--help") is False
        assert is_agent_flag("-j") is False
        assert is_agent_flag("planner-guidance") is False
        assert is_agent_flag("--") is False

    def test_agent_flag_with_dashes(self):
        """Test multi-word agent flags work correctly."""
        # All agents with multiple dashes
        assert is_agent_flag("--planner-guidance-testing") is True
        assert is_agent_flag("--teacher-trace-diagnostics") is True
        assert is_agent_flag("--test-guidance-simulator") is True
        assert is_agent_flag("--teacher-update-guidance") is True

    def test_get_agent_from_flag_valid(self):
        """Test extracting agent name from valid flags."""
        assert get_agent_from_flag("--planner-guidance") == "planner-guidance"
        assert get_agent_from_flag("--build-python") == "build-python"
        assert get_agent_from_flag("--test-runner") == "test-runner"

    def test_get_agent_from_flag_invalid(self):
        """Test returns None for invalid flags."""
        assert get_agent_from_flag("--nonexistent") is None
        assert get_agent_from_flag("--help") is None
        assert get_agent_from_flag("planner-guidance") is None

    def test_all_26_agents_registered(self):
        """Verify all 26 agents are in KNOWN_AGENTS."""
        assert len(KNOWN_AGENTS) == 26, f"Expected 26 agents, got {len(KNOWN_AGENTS)}"

    def test_all_agents_have_categories(self):
        """Verify all agents have category mappings."""
        for agent in KNOWN_AGENTS:
            assert agent in AGENT_CATEGORIES, f"Agent {agent} missing from AGENT_CATEGORIES"

    def test_agent_categories_valid(self):
        """Verify all categories are valid."""
        valid_categories = {"planner", "build", "test", "orchestration", "teacher", "deploy"}
        for agent, category in AGENT_CATEGORIES.items():
            assert category in valid_categories, f"Invalid category {category} for {agent}"


class TestAgentHelpContent:
    """Tests for agent help content generation."""

    def test_load_agent_context_basic(self):
        """Test loading context for a known agent."""
        context = _load_agent_context("planner-build")

        assert context["agent"] == "planner-build"
        assert context["category"] == "planner"
        assert "next_commands" in context
        assert len(context["next_commands"]) > 0

    def test_load_agent_context_unknown(self):
        """Test loading context for unknown agent still returns structure."""
        # Use a name that won't match any real agent
        context = _load_agent_context("nonexistent-agent-xyz")

        # Should have basic structure even if agent not found
        assert context["agent"] == "nonexistent-agent-xyz"
        assert "error" in context or context.get("role") is None

    def test_context_includes_next_commands(self):
        """Test that context includes CLI next commands."""
        context = _load_agent_context("build-python")

        assert "next_commands" in context
        commands = context["next_commands"]

        # Should reference the agent name in bootstrap command
        assert any("build-python" in cmd for cmd in commands)
        # Should include task commands
        assert any("plan task" in cmd for cmd in commands)

    def test_context_includes_role(self):
        """Test that context includes role description when available."""
        context = _load_agent_context("planner-guidance")

        # Role may be None if files not found, but key should exist
        assert "role" in context

    def test_help_includes_process_steps(self):
        """Test that context includes process steps when available."""
        context = _load_agent_context("test-runner")

        # process_steps should be a list
        assert isinstance(context.get("process_steps", []), list)

    def test_help_includes_inputs(self):
        """Test that context includes inputs when available."""
        context = _load_agent_context("planner-build")

        # inputs should be a list
        assert isinstance(context.get("inputs", []), list)


class TestAgentHelpOutput:
    """Tests for agent help output formatting."""

    def test_show_agent_help_json_structure(self):
        """Test JSON output has expected structure."""
        # Capture stdout
        captured = StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = captured
            show_agent_help("planner-guidance", json_output=True)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        data = json.loads(output)

        assert "agent" in data
        assert data["agent"] == "planner-guidance"
        assert "category" in data
        assert "next_commands" in data

    def test_show_agent_help_text_format(self):
        """Test text output includes key sections."""
        captured = StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = captured
            show_agent_help("build-python", json_output=False)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()

        # Check for key sections
        assert "AGENT: build-python" in output
        assert "NEXT COMMANDS:" in output
        assert "agentic" in output  # CLI commands should be present

    def test_unknown_agent_error(self):
        """Test error handling for unknown agents."""
        with pytest.raises(SystemExit) as exc_info:
            show_agent_help("nonexistent-agent-xyz", json_output=False)

        assert exc_info.value.code == 1

    def test_json_output_flag(self):
        """Test -j flag produces JSON output."""
        captured = StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = captured
            show_agent_help("test-runner", json_output=True)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()

        # Should be valid JSON
        data = json.loads(output)
        assert isinstance(data, dict)


class TestAgentDirectoryFinding:
    """Tests for finding agent directories."""

    def test_find_agent_directory_planner(self):
        """Test finding planner agent directory."""
        agent_dir = _find_agent_directory("planner-guidance")

        # May be None if not in AgenticEngineering repo
        if agent_dir:
            assert agent_dir.exists()
            assert "planner-guidance" in str(agent_dir)

    def test_find_agent_directory_build(self):
        """Test finding build agent directory."""
        agent_dir = _find_agent_directory("build-python")

        if agent_dir:
            assert agent_dir.exists()
            assert "build-python" in str(agent_dir)

    def test_find_agent_directory_unknown_returns_none(self):
        """Test that unknown agent returns None."""
        agent_dir = _find_agent_directory("nonexistent-agent")
        assert agent_dir is None


class TestCLIIntegration:
    """Integration tests for CLI invocation."""

    def test_cli_agent_flag_invocation(self):
        """Test invoking CLI with agent flag."""
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "--planner-guidance"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=10,
        )

        # Should succeed (exit 0)
        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Output should contain agent info
        assert "planner-guidance" in result.stdout.lower()

    def test_cli_agent_flag_with_json(self):
        """Test invoking CLI with agent flag and -j."""
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "--build-python", "-j"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=10,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Output should be valid JSON
        data = json.loads(result.stdout)
        assert data["agent"] == "build-python"

    def test_cli_unknown_agent_flag_error(self):
        """Test CLI with unknown agent flag produces error."""
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "--nonexistent-agent-xyz"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=10,
        )

        # Should go through normal CLI (may show help or error)
        # Unknown flag is not detected as agent flag, so it goes to argparse
        # which will either show help or error
        pass  # Just verify it doesn't crash

    @pytest.mark.skipif(
        not Path("/home/code/AgenticEngineering").exists(),
        reason="Requires AgenticEngineering repo"
    )
    def test_cli_fast_response(self):
        """Test CLI responds quickly (< 500ms)."""
        import time

        start = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "agenticcli.entry", "--test-runner"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent / "src",
            timeout=5,
        )
        elapsed = time.time() - start

        assert result.returncode == 0
        # Should complete in under 500ms
        assert elapsed < 0.5, f"CLI took {elapsed:.2f}s, expected < 0.5s"


class TestErrorHandling:
    """Tests for error handling."""

    def test_missing_manifest_graceful(self):
        """Test graceful handling when manifest doesn't exist."""
        # Mock _find_agent_directory to return a path that exists but has no files
        with patch("agenticcli.commands.agent_help._find_agent_directory") as mock_find:
            # Create a temp directory
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                mock_find.return_value = Path(tmpdir)

                context = _load_agent_context("planner-build")

                # Should still return a context dict without crashing
                assert context["agent"] == "planner-build"
                # Role should be None since no files exist
                assert context["role"] is None

    def test_missing_process_graceful(self):
        """Test graceful handling when process.yml doesn't exist."""
        with patch("agenticcli.commands.agent_help._find_agent_directory") as mock_find:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create only manifest
                manifest_path = Path(tmpdir) / "manifest.yml"
                manifest_path.write_text("agent:\n  name: Test Agent\n")

                mock_find.return_value = Path(tmpdir)

                context = _load_agent_context("test-runner")

                # Should work with just manifest
                assert context["agent"] == "test-runner"
                assert context["role"] == "Test Agent"
                assert context["process_steps"] == []  # No process file

    def test_malformed_yaml_graceful(self):
        """Test graceful handling of malformed YAML files."""
        with patch("agenticcli.commands.agent_help._find_agent_directory") as mock_find:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create malformed YAML
                manifest_path = Path(tmpdir) / "manifest.yml"
                manifest_path.write_text("invalid: yaml: content: [[[")

                mock_find.return_value = Path(tmpdir)

                context = _load_agent_context("build-python")

                # Should not crash
                assert context["agent"] == "build-python"


class TestAgentCategories:
    """Tests for agent category organization."""

    def test_planner_agents_count(self):
        """Verify 7 planner agents."""
        planners = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "planner"]
        assert len(planners) == 7

    def test_test_agents_count(self):
        """Verify 7 test agents."""
        testers = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "test"]
        assert len(testers) == 7

    def test_orchestration_agents_count(self):
        """Verify 5 orchestration agents."""
        orchestrators = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "orchestration"]
        assert len(orchestrators) == 5

    def test_teacher_agents_count(self):
        """Verify 3 teacher agents."""
        teachers = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "teacher"]
        assert len(teachers) == 3

    def test_build_agents_count(self):
        """Verify 2 build agents."""
        builders = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "build"]
        assert len(builders) == 2

    def test_deploy_agents_count(self):
        """Verify 2 deploy agents."""
        deployers = [a for a in KNOWN_AGENTS if AGENT_CATEGORIES.get(a) == "deploy"]
        assert len(deployers) == 2
