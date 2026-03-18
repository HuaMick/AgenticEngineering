"""Tests for story-test hard link infrastructure.

Tests the AST-based marker scanner, sync/coverage/run CLI commands,
and conftest strict mode.
"""

import ast
import json
import os
import subprocess
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# AST Scanner Tests
# ---------------------------------------------------------------------------

class TestExtractStoryIdsFromDecorators:
    """Test _extract_story_ids_from_decorators() helper."""

    def _parse_func(self, source: str):
        """Parse a function definition and return the AST node."""
        tree = ast.parse(textwrap.dedent(source))
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                return node
        raise ValueError("No function/class found in source")

    def test_single_marker(self):
        from agenticcli.commands.stories import _extract_story_ids_from_decorators
        node = self._parse_func('''
            @pytest.mark.story("US-CLI-110")
            def test_foo():
                pass
        ''')
        assert _extract_story_ids_from_decorators(node) == {"US-CLI-110"}

    def test_multiple_ids_in_one_marker(self):
        from agenticcli.commands.stories import _extract_story_ids_from_decorators
        node = self._parse_func('''
            @pytest.mark.story("US-CLI-110", "US-CLI-111")
            def test_foo():
                pass
        ''')
        assert _extract_story_ids_from_decorators(node) == {"US-CLI-110", "US-CLI-111"}

    def test_no_markers(self):
        from agenticcli.commands.stories import _extract_story_ids_from_decorators
        node = self._parse_func('''
            def test_foo():
                pass
        ''')
        assert _extract_story_ids_from_decorators(node) == set()

    def test_other_markers_ignored(self):
        from agenticcli.commands.stories import _extract_story_ids_from_decorators
        node = self._parse_func('''
            @pytest.mark.slow
            @pytest.mark.parametrize("x", [1, 2])
            def test_foo():
                pass
        ''')
        assert _extract_story_ids_from_decorators(node) == set()

    def test_mixed_markers(self):
        from agenticcli.commands.stories import _extract_story_ids_from_decorators
        node = self._parse_func('''
            @pytest.mark.slow
            @pytest.mark.story("US-CLI-110")
            def test_foo():
                pass
        ''')
        assert _extract_story_ids_from_decorators(node) == {"US-CLI-110"}


class TestScanPytestStoryMarkersDetailed:
    """Test _scan_pytest_story_markers_detailed() full scanner."""

    def test_scans_test_files(self, tmp_path):
        from agenticcli.commands.stories import _scan_pytest_story_markers_detailed

        # Create a mock repo structure
        (tmp_path / ".git").mkdir()
        test_dir = tmp_path / "modules" / "AgenticCLI" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_example.py").write_text(textwrap.dedent('''
            import pytest

            @pytest.mark.story("US-CLI-110")
            def test_one():
                pass

            @pytest.mark.story("US-CLI-110", "US-CLI-111")
            def test_two():
                pass

            def test_no_marker():
                pass
        '''))

        with patch("os.getcwd", return_value=str(tmp_path)):
            # Need to patch Path.cwd too
            with patch.object(Path, "cwd", return_value=tmp_path):
                mappings = _scan_pytest_story_markers_detailed()

        assert "US-CLI-110" in mappings
        assert len(mappings["US-CLI-110"]) == 2
        assert "US-CLI-111" in mappings
        assert len(mappings["US-CLI-111"]) == 1

    def test_handles_class_markers(self, tmp_path):
        from agenticcli.commands.stories import _scan_pytest_story_markers_detailed

        (tmp_path / ".git").mkdir()
        test_dir = tmp_path / "modules" / "AgenticCLI" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_class.py").write_text(textwrap.dedent('''
            import pytest

            @pytest.mark.story("US-CLI-200")
            class TestMyFeature:
                def test_method_a(self):
                    pass

                def test_method_b(self):
                    pass

                def helper_not_a_test(self):
                    pass
        '''))

        with patch.object(Path, "cwd", return_value=tmp_path):
            mappings = _scan_pytest_story_markers_detailed()

        assert "US-CLI-200" in mappings
        # Only test_ methods, not helper
        assert len(mappings["US-CLI-200"]) == 2

    def test_empty_test_dir(self, tmp_path):
        from agenticcli.commands.stories import _scan_pytest_story_markers_detailed

        (tmp_path / ".git").mkdir()
        # No test dirs exist

        with patch.object(Path, "cwd", return_value=tmp_path):
            mappings = _scan_pytest_story_markers_detailed()

        assert mappings == {}


# ---------------------------------------------------------------------------
# CLI Command Tests (cmd_sync, cmd_coverage, cmd_run)
# ---------------------------------------------------------------------------

class TestCmdSync:
    """Test cmd_sync command."""

    def test_sync_populates_tinydb(self, tmp_path):
        from agenticcli.commands.stories import cmd_sync

        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        mock_mappings = {
            "US-CLI-110": ["tests/test_a.py::test_1"],
            "US-CLI-111": ["tests/test_b.py::test_2"],
        }

        with patch("agenticcli.commands.stories._scan_pytest_story_markers_detailed", return_value=mock_mappings), \
             patch("agenticcli.commands.stories._collect_all_stories", return_value=[
                 {"id": "US-CLI-110"}, {"id": "US-CLI-111"}, {"id": "US-CLI-112"}
             ]), \
             patch("agenticcli.commands.stories._get_repo_db_path", return_value=db_path), \
             patch("agenticcli.console.is_json_output", return_value=True), \
             patch("agenticcli.console.print_json") as mock_print:
            cmd_sync(SimpleNamespace())

        assert mock_print.called
        result = mock_print.call_args[0][0]
        assert result["stories_synced"] == 2
        assert result["test_functions"] == 2
        assert result["orphan_markers"] == []


class TestCmdCoverage:
    """Test cmd_coverage command."""

    def test_coverage_reports_stats(self, tmp_path):
        from agenticcli.commands.stories import cmd_coverage

        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Populate TinyDB
        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.sync_story_tests({"US-CLI-110": ["tests/test_a.py::test_1"]})
        repo.close()

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=[
                 {"id": "US-CLI-110"}, {"id": "US-CLI-111"}
             ]), \
             patch("agenticcli.commands.stories._get_repo_db_path", return_value=db_path), \
             patch("agenticcli.console.is_json_output", return_value=True), \
             patch("agenticcli.console.print_json") as mock_print:
            cmd_coverage(SimpleNamespace(project=None, min_pct=None, exit_code=False))

        result = mock_print.call_args[0][0]
        assert result["total_stories"] == 2
        assert result["covered"] == 1
        assert result["uncovered_count"] == 1
        assert "US-CLI-111" in result["uncovered"]
        assert result["coverage_pct"] == 50.0

    def test_coverage_exit_code_on_low_coverage(self, tmp_path):
        from agenticcli.commands.stories import cmd_coverage

        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=[
                 {"id": "US-CLI-110"}, {"id": "US-CLI-111"}
             ]), \
             patch("agenticcli.commands.stories._get_repo_db_path", return_value=db_path), \
             patch("agenticcli.console.is_json_output", return_value=True), \
             patch("agenticcli.console.print_json"):
            with pytest.raises(SystemExit) as exc_info:
                cmd_coverage(SimpleNamespace(project=None, min_pct=80.0, exit_code=True))
            assert exc_info.value.code == 1


class TestCmdRun:
    """Test cmd_run command."""

    def test_run_no_tests_found(self, tmp_path):
        from agenticcli.commands.stories import cmd_run

        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        with patch("agenticcli.commands.stories._get_repo_db_path", return_value=db_path), \
             patch("agenticcli.console.is_json_output", return_value=False), \
             patch("agenticcli.console.print_error"):
            with pytest.raises(SystemExit) as exc_info:
                cmd_run(SimpleNamespace(story_id="US-NOPE-999", module=None, testmon=False))
            assert exc_info.value.code == 1

    def test_run_invokes_pytest(self, tmp_path):
        from agenticcli.commands.stories import cmd_run

        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        from agenticguidance.services.epic_repository import EpicRepository
        repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
        repo.sync_story_tests({"US-CLI-110": ["tests/test_a.py::test_1"]})
        repo.close()

        (tmp_path / ".git").mkdir()

        with patch("agenticcli.commands.stories._get_repo_db_path", return_value=db_path), \
             patch.object(Path, "cwd", return_value=tmp_path), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            with pytest.raises(SystemExit) as exc_info:
                cmd_run(SimpleNamespace(story_id="US-CLI-110", module=None, testmon=False))
            assert exc_info.value.code == 0

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "tests/test_a.py::test_1" in cmd
        assert "-v" in cmd
