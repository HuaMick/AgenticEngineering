"""Tests for stories report --coverage flag and Fence 4 marker validation (P4-T3).

Validates the --coverage flag on `agentic stories report` and the Fence 4
post-execution story marker validation in _check_fences.
"""

import re
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tests for _scan_pytest_story_markers
# ---------------------------------------------------------------------------

class TestScanPytestStoryMarkers:
    """Test the marker scanner used by --coverage flag."""

    def test_scan_returns_set(self):
        """Verify _scan_pytest_story_markers returns a set."""
        from agenticcli.commands.stories import _scan_pytest_story_markers

        result = _scan_pytest_story_markers()
        assert isinstance(result, set)

    def test_scan_finds_markers_in_real_tests(self):
        """Verify scanner finds markers in actual test files (if any exist)."""
        from agenticcli.commands.stories import _scan_pytest_story_markers

        result = _scan_pytest_story_markers()
        # Our test_story_marker_conftest.py uses @pytest.mark.story("US-FAKE-999")
        # If that file exists in the test tree, it should be found
        # This is a structural test — we don't require specific IDs
        assert isinstance(result, set)
        for sid in result:
            assert isinstance(sid, str)
            # All IDs should match US-XXX-NNN pattern
            assert re.match(r'^[A-Z]{2}-[A-Z]+-\d+$', sid), f"Invalid story ID format: {sid}"

    def test_scan_handles_missing_test_dirs(self, tmp_path):
        """Verify scanner handles missing test directories gracefully."""
        from agenticcli.commands.stories import _scan_pytest_story_markers

        # Patch Path.cwd to point to a temp dir with no test dirs
        with patch("agenticcli.commands.stories.Path") as mock_path:
            mock_path.cwd.return_value = tmp_path
            # Create a fake .git so repo root is found
            (tmp_path / ".git").mkdir()
            result = _scan_pytest_story_markers()
            # Should return empty set, not crash
            assert isinstance(result, set)


# ---------------------------------------------------------------------------
# Tests for cmd_report with --coverage
# ---------------------------------------------------------------------------

class TestCmdReportCoverage:
    """Test the cmd_report function with coverage flag."""

    def test_report_without_coverage_flag(self):
        """Verify report works without --coverage flag (backward compat)."""
        from unittest.mock import MagicMock

        from agenticcli.commands.stories import cmd_report

        args = MagicMock()
        args.project = None
        args.coverage = False

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=[]):
            with patch("agenticcli.console.is_json_output", return_value=True):
                with patch("agenticcli.console.print_json") as mock_json:
                    cmd_report(args)
                    mock_json.assert_called_once()
                    result = mock_json.call_args[0][0]
                    assert "marker_coverage" not in result

    def test_report_with_coverage_flag_json(self):
        """Verify --coverage adds marker_coverage to JSON output."""
        from agenticcli.commands.stories import cmd_report

        args = MagicMock()
        args.project = None
        args.coverage = True

        fake_stories = [
            {"id": "US-CLI-110", "test_status": "pass"},
            {"id": "US-CLI-111", "test_status": "untested"},
        ]

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=fake_stories):
            with patch("agenticcli.commands.stories._scan_pytest_story_markers", return_value={"US-CLI-110"}):
                with patch("agenticcli.console.is_json_output", return_value=True):
                    with patch("agenticcli.console.print_json") as mock_json:
                        cmd_report(args)
                        result = mock_json.call_args[0][0]
                        assert "marker_coverage" in result
                        mc = result["marker_coverage"]
                        assert mc["total_stories"] == 2
                        assert mc["covered_by_markers"] == 1
                        assert mc["coverage_pct"] == 50.0
                        assert "US-CLI-111" in mc["uncovered"]
                        assert mc["orphan_markers"] == []

    def test_report_coverage_100_percent(self):
        """Verify 100% coverage when all stories have markers."""
        from agenticcli.commands.stories import cmd_report

        args = MagicMock()
        args.project = None
        args.coverage = True

        fake_stories = [
            {"id": "US-CLI-110", "test_status": "pass"},
            {"id": "US-CLI-111", "test_status": "pass"},
        ]

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=fake_stories):
            with patch("agenticcli.commands.stories._scan_pytest_story_markers",
                       return_value={"US-CLI-110", "US-CLI-111"}):
                with patch("agenticcli.console.is_json_output", return_value=True):
                    with patch("agenticcli.console.print_json") as mock_json:
                        cmd_report(args)
                        result = mock_json.call_args[0][0]
                        mc = result["marker_coverage"]
                        assert mc["coverage_pct"] == 100.0
                        assert mc["uncovered"] == []
                        assert mc["covered_by_markers"] == 2

    def test_report_coverage_detects_orphan_markers(self):
        """Verify orphan_markers contains IDs referencing non-existent stories."""
        from agenticcli.commands.stories import cmd_report

        args = MagicMock()
        args.project = None
        args.coverage = True

        fake_stories = [
            {"id": "US-CLI-110", "test_status": "pass"},
        ]

        # Scanner finds markers for US-CLI-110 (valid) AND US-ORPHAN-001 (not a story)
        with patch("agenticcli.commands.stories._collect_all_stories", return_value=fake_stories):
            with patch("agenticcli.commands.stories._scan_pytest_story_markers",
                       return_value={"US-CLI-110", "US-ORPHAN-001"}):
                with patch("agenticcli.console.is_json_output", return_value=True):
                    with patch("agenticcli.console.print_json") as mock_json:
                        cmd_report(args)
                        result = mock_json.call_args[0][0]
                        mc = result["marker_coverage"]
                        assert "US-ORPHAN-001" in mc["orphan_markers"]
                        assert mc["covered_by_markers"] == 1

    def test_report_coverage_empty_stories_no_division_error(self):
        """Verify coverage calculation handles zero stories without ZeroDivisionError."""
        from agenticcli.commands.stories import cmd_report

        args = MagicMock()
        args.project = None
        args.coverage = True

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=[]):
            with patch("agenticcli.commands.stories._scan_pytest_story_markers", return_value=set()):
                with patch("agenticcli.console.is_json_output", return_value=True):
                    with patch("agenticcli.console.print_json") as mock_json:
                        cmd_report(args)
                        result = mock_json.call_args[0][0]
                        mc = result["marker_coverage"]
                        assert mc["total_stories"] == 0
                        assert mc["coverage_pct"] == 0
                        assert mc["uncovered"] == []

    def test_report_coverage_no_markers_all_uncovered(self):
        """Verify all stories uncovered when no markers exist."""
        from agenticcli.commands.stories import cmd_report

        args = MagicMock()
        args.project = None
        args.coverage = True

        fake_stories = [
            {"id": "US-CLI-110", "test_status": "untested"},
            {"id": "US-CLI-111", "test_status": "untested"},
        ]

        with patch("agenticcli.commands.stories._collect_all_stories", return_value=fake_stories):
            with patch("agenticcli.commands.stories._scan_pytest_story_markers", return_value=set()):
                with patch("agenticcli.console.is_json_output", return_value=True):
                    with patch("agenticcli.console.print_json") as mock_json:
                        cmd_report(args)
                        mc = mock_json.call_args[0][0]["marker_coverage"]
                        assert mc["coverage_pct"] == 0
                        assert mc["covered_by_markers"] == 0
                        assert len(mc["uncovered"]) == 2


# ---------------------------------------------------------------------------
# Tests for Fence 4 (Marker Coverage)
# ---------------------------------------------------------------------------

class TestFence4MarkerCoverage:
    """Test Fence 4 story marker validation in _check_fences."""

    def _make_plan_path(self, tmp_path):
        """Create a minimal plan folder structure."""
        plan_dir = tmp_path / "docs" / "epics" / "live" / "260308PD_test"
        plan_dir.mkdir(parents=True)
        # Create .git to mark repo root
        (tmp_path / ".git").mkdir(exist_ok=True)
        return plan_dir

    def test_fence4_warn_when_no_affected_stories(self, tmp_path):
        """Verify Fence 4 returns WARN when no affected stories."""
        from agenticcli.commands.epic import _check_fences

        plan_path = self._make_plan_path(tmp_path)

        with patch("agenticcli.commands.epic._get_repo") as mock_repo:
            mock_repo.return_value = MagicMock()
            mock_repo.return_value.get_epic.return_value = None

            results = _check_fences(plan_path, [], [])
            assert "Fence 4 (Marker Coverage)" in results
            assert results["Fence 4 (Marker Coverage)"]["status"] == "WARN"

    def test_fence4_pass_when_all_stories_have_markers(self, tmp_path):
        """Verify Fence 4 returns PASS when all stories have markers."""
        from agenticcli.commands.epic import _check_fences

        plan_path = self._make_plan_path(tmp_path)

        # Create mock epic data with affected_stories
        mock_epic = MagicMock()
        mock_epic.affected_stories = ["US-CLI-110"]
        mock_epic.no_stories_rationale = None

        # Create a fake test file with the marker
        test_dir = tmp_path / "modules" / "AgenticCLI" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_feature.py").write_text(
            '@pytest.mark.story("US-CLI-110")\ndef test_feature(): pass\n'
        )

        with patch("agenticcli.commands.epic._get_repo") as mock_repo:
            mock_repo.return_value = MagicMock()
            mock_repo.return_value.get_epic.return_value = mock_epic

            results = _check_fences(plan_path, [], [])
            assert "Fence 4 (Marker Coverage)" in results
            assert results["Fence 4 (Marker Coverage)"]["status"] == "PASS"

    def test_fence4_warn_when_stories_missing_markers(self, tmp_path):
        """Verify Fence 4 returns WARN when stories lack markers."""
        from agenticcli.commands.epic import _check_fences

        plan_path = self._make_plan_path(tmp_path)

        mock_epic = MagicMock()
        mock_epic.affected_stories = ["US-CLI-110", "US-CLI-111"]
        mock_epic.no_stories_rationale = None

        # Create test dir but only marker for one story
        test_dir = tmp_path / "modules" / "AgenticCLI" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_feature.py").write_text(
            '@pytest.mark.story("US-CLI-110")\ndef test_feature(): pass\n'
        )

        with patch("agenticcli.commands.epic._get_repo") as mock_repo:
            mock_repo.return_value = MagicMock()
            mock_repo.return_value.get_epic.return_value = mock_epic

            results = _check_fences(plan_path, [], [])
            assert "Fence 4 (Marker Coverage)" in results
            f4 = results["Fence 4 (Marker Coverage)"]
            assert f4["status"] == "WARN"
            assert "US-CLI-111" in f4["message"]

    def test_fence4_pass_message_includes_count(self, tmp_path):
        """Verify Fence 4 PASS message mentions the number of covered stories."""
        from agenticcli.commands.epic import _check_fences

        plan_path = self._make_plan_path(tmp_path)

        mock_epic = MagicMock()
        mock_epic.affected_stories = ["US-CLI-110", "US-CLI-111"]
        mock_epic.no_stories_rationale = None

        test_dir = tmp_path / "modules" / "AgenticCLI" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_feature.py").write_text(
            '@pytest.mark.story("US-CLI-110")\ndef test_a(): pass\n'
            '@pytest.mark.story("US-CLI-111")\ndef test_b(): pass\n'
        )

        with patch("agenticcli.commands.epic._get_repo") as mock_repo:
            mock_repo.return_value = MagicMock()
            mock_repo.return_value.get_epic.return_value = mock_epic

            results = _check_fences(plan_path, [], [])
            f4 = results["Fence 4 (Marker Coverage)"]
            assert f4["status"] == "PASS"
            assert "2" in f4["message"]  # "All 2 affected stories"

    def test_fence4_warn_includes_coverage_percentage(self, tmp_path):
        """Verify Fence 4 WARN message includes coverage percentage."""
        from agenticcli.commands.epic import _check_fences

        plan_path = self._make_plan_path(tmp_path)

        mock_epic = MagicMock()
        mock_epic.affected_stories = ["US-CLI-110", "US-CLI-111"]
        mock_epic.no_stories_rationale = None

        test_dir = tmp_path / "modules" / "AgenticCLI" / "tests"
        test_dir.mkdir(parents=True)
        (test_dir / "test_feature.py").write_text(
            '@pytest.mark.story("US-CLI-110")\ndef test_a(): pass\n'
        )

        with patch("agenticcli.commands.epic._get_repo") as mock_repo:
            mock_repo.return_value = MagicMock()
            mock_repo.return_value.get_epic.return_value = mock_epic

            results = _check_fences(plan_path, [], [])
            f4 = results["Fence 4 (Marker Coverage)"]
            assert f4["status"] == "WARN"
            # Should show "1/2 (50%)" in message
            assert "1/2" in f4["message"]
            assert "50" in f4["message"]
