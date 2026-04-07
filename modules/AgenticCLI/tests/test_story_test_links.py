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

pytestmark = [pytest.mark.story("US-STR-001")]


# ---------------------------------------------------------------------------
# AST Scanner Tests
# ---------------------------------------------------------------------------

@pytest.mark.story("US-STR-001")
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
            @pytest.mark.story("US-STR-001")
            def test_foo():
                pass
        ''')
        assert _extract_story_ids_from_decorators(node) == {"US-STR-001"}

    def test_multiple_ids_in_one_marker(self):
        from agenticcli.commands.stories import _extract_story_ids_from_decorators
        node = self._parse_func('''
            @pytest.mark.story("US-STR-001", "US-STR-002")
            def test_foo():
                pass
        ''')
        assert _extract_story_ids_from_decorators(node) == {"US-STR-001", "US-STR-002"}

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
            @pytest.mark.story("US-STR-001")
            def test_foo():
                pass
        ''')
        assert _extract_story_ids_from_decorators(node) == {"US-STR-001"}


@pytest.mark.story("US-STR-001")
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

            @pytest.mark.story("US-STR-001")
            def test_one():
                pass

            @pytest.mark.story("US-STR-001", "US-STR-002")
            def test_two():
                pass

            def test_no_marker():
                pass
        '''))

        with patch("os.getcwd", return_value=str(tmp_path)):
            # Need to patch Path.cwd too
            with patch.object(Path, "cwd", return_value=tmp_path):
                mappings = _scan_pytest_story_markers_detailed()

        assert "US-STR-001" in mappings
        assert len(mappings["US-STR-001"]) == 2
        assert "US-STR-002" in mappings
        assert len(mappings["US-STR-002"]) == 1

    def test_handles_class_markers(self, tmp_path):
        from agenticcli.commands.stories import _scan_pytest_story_markers_detailed

        (tmp_path / ".git").mkdir()
        test_dir = tmp_path / "modules" / "AgenticCLI" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_class.py").write_text(textwrap.dedent('''
            import pytest

            @pytest.mark.story("US-STR-003")
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

        assert "US-STR-003" in mappings
        # Only test_ methods, not helper
        assert len(mappings["US-STR-003"]) == 2

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

@pytest.mark.story("US-STR-001")
class TestCmdSync:
    """Test cmd_sync command."""

    def test_sync_populates_tinydb(self, tmp_path):
        from agenticcli.commands.stories import cmd_sync

        db_path = tmp_path / ".agentic" / "epics.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        mock_mappings = {
            "US-STR-001": ["tests/test_a.py::test_1"],
            "US-STR-002": ["tests/test_b.py::test_2"],
        }

        with patch("agenticcli.commands.stories._scan_pytest_story_markers_detailed", return_value=mock_mappings), \
             patch("agenticcli.commands.stories._collect_all_stories", return_value=[
                 {"id": "US-STR-001"}, {"id": "US-STR-002"}, {"id": "US-STR-003"}
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


@pytest.mark.story("US-STR-001")
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
        repo.sync_story_tests({"US-STR-001": ["tests/test_a.py::test_1"]})
        repo.close()

        (tmp_path / ".git").mkdir()

        with patch("agenticcli.commands.stories._get_repo_db_path", return_value=db_path), \
             patch.object(Path, "cwd", return_value=tmp_path), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            with pytest.raises(SystemExit) as exc_info:
                cmd_run(SimpleNamespace(story_id="US-STR-001", module=None, testmon=False))
            assert exc_info.value.code == 0

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "tests/test_a.py::test_1" in cmd
        assert "-v" in cmd
