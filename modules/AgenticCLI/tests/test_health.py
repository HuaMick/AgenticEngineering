"""Tests for health command."""

import json
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.story("US-SET-004", "US-GDN-062", "US-GDN-090", "US-GDN-101", "US-GDN-091")


@pytest.mark.story("US-SET-004")
class TestHealthCommand:
    """Tests for agentic health command."""

    def test_health_command(self, cli_runner):
        """Test health command runs."""
        result = cli_runner("setup", "health")
        assert result.returncode == 0
        assert "Health Check" in result.stdout or "cli_version" in result.stdout

    def test_health_json_output(self, cli_runner):
        """Test health command JSON output."""
        result = cli_runner("--json", "setup", "health")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "status" in data
        assert "checks" in data
        assert any(c["name"] == "cli_version" for c in data["checks"])

    def test_health_help(self, cli_runner):
        """Test health --help."""
        result = cli_runner("setup", "health", "--help")
        assert result.returncode == 0
        assert "health" in result.stdout.lower()

    def test_health_checks_config_dir(self, cli_runner):
        """Test health checks config directory."""
        result = cli_runner("--json", "setup", "health")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        config_check = next((c for c in data["checks"] if c["name"] == "config_dir"), None)
        assert config_check is not None
        assert config_check["status"] in ("pass", "warn")

    def test_health_checks_git(self, cli_runner):
        """Test health checks git availability."""
        result = cli_runner("--json", "setup", "health")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        git_check = next((c for c in data["checks"] if c["name"] == "git"), None)
        assert git_check is not None
        # Git should be available in test environment
        assert git_check["status"] == "pass"

    def test_health_checks_uv(self, cli_runner):
        """Test health checks uv availability."""
        result = cli_runner("--json", "setup", "health")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        uv_check = next((c for c in data["checks"] if c["name"] == "uv"), None)
        assert uv_check is not None
        # UV should be available in test environment
        assert uv_check["status"] in ("pass", "warn")


def _get_story_coverage_check(cli_runner):
    """Helper to run health JSON and extract the story_coverage check."""
    result = cli_runner("--json", "setup", "health")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    check = next((c for c in data["checks"] if c["name"] == "story_coverage"), None)
    assert check is not None
    return check, data


@pytest.mark.story("US-GDN-090", "US-GDN-091")
class TestStoryCoverageHealth:
    """Tests for story_coverage graduated severity thresholds."""

    def test_story_coverage_all_covered(self, cli_runner):
        """100% coverage -> status 'pass'."""
        mock_repo = MagicMock()
        mock_repo.get_uncovered_stories.return_value = []

        with patch(
            "agenticcli.commands.stories._collect_all_stories",
            return_value=[{"id": "US-001"}, {"id": "US-002"}, {"id": "US-003"}],
        ), patch(
            "agenticguidance.services.epic_repository.EpicRepository",
            return_value=mock_repo,
        ):
            check, data = _get_story_coverage_check(cli_runner)

        assert check["status"] == "pass"
        assert check["value"]["total"] == 3
        assert check["value"]["covered"] == 3
        assert check["value"]["coverage_pct"] == 100.0
        assert data["status"] == "healthy"

    def test_story_coverage_above_threshold(self, cli_runner):
        """80% coverage (4/5) -> status 'pass' (above threshold)."""
        mock_repo = MagicMock()
        mock_repo.get_uncovered_stories.return_value = ["US-005"]

        with patch(
            "agenticcli.commands.stories._collect_all_stories",
            return_value=[
                {"id": f"US-00{i}"} for i in range(1, 6)
            ],
        ), patch(
            "agenticguidance.services.epic_repository.EpicRepository",
            return_value=mock_repo,
        ):
            check, data = _get_story_coverage_check(cli_runner)

        assert check["status"] == "pass"
        assert check["value"]["total"] == 5
        assert check["value"]["covered"] == 4
        assert check["value"]["coverage_pct"] == 80.0
        assert "above 80% threshold" in check["message"]
        assert data["status"] == "healthy"

    def test_story_coverage_below_threshold(self, cli_runner):
        """25% coverage (1/4) -> status 'warn' (below threshold)."""
        mock_repo = MagicMock()
        mock_repo.get_uncovered_stories.return_value = ["US-002", "US-003", "US-004"]

        with patch(
            "agenticcli.commands.stories._collect_all_stories",
            return_value=[{"id": f"US-00{i}"} for i in range(1, 5)],
        ), patch(
            "agenticguidance.services.epic_repository.EpicRepository",
            return_value=mock_repo,
        ):
            check, data = _get_story_coverage_check(cli_runner)

        assert check["status"] == "warn"
        assert check["value"]["total"] == 4
        assert check["value"]["covered"] == 1
        assert check["value"]["coverage_pct"] == 25.0
        assert "below 80% threshold" in check["message"]
        # warn should NOT cause unhealthy status
        assert data["status"] == "healthy"

    def test_story_coverage_no_stories(self, cli_runner):
        """No stories found -> status 'info'."""
        with patch(
            "agenticcli.commands.stories._collect_all_stories",
            return_value=[],
        ):
            check, data = _get_story_coverage_check(cli_runner)

        assert check["status"] == "info"
        assert check["value"]["total"] == 0
        assert check["value"]["covered"] == 0
        assert check["value"]["coverage_pct"] == 0
        assert data["status"] == "healthy"


@pytest.mark.story("US-GDN-090", "US-GDN-091")
class TestStoryCoverageErrorHandling:
    """Tests for story_coverage error handling and JSON value structure."""

    def test_story_coverage_error_returns_warn(self, cli_runner):
        """When TinyDB/stories unavailable, status should be 'warn'."""
        with patch(
            "agenticcli.commands.stories._collect_all_stories",
            side_effect=RuntimeError("TinyDB unavailable"),
        ):
            check, data = _get_story_coverage_check(cli_runner)

        assert check["status"] == "warn"
        assert check["message"] == "Story coverage check unavailable"
        assert check["value"] is None
        # warn should NOT cause unhealthy status
        assert data["status"] == "healthy"

    def test_story_coverage_json_value_fields(self, cli_runner):
        """Verify JSON value structure has all required fields."""
        mock_repo = MagicMock()
        mock_repo.get_uncovered_stories.return_value = ["US-003"]

        with patch(
            "agenticcli.commands.stories._collect_all_stories",
            return_value=[{"id": "US-001"}, {"id": "US-002"}, {"id": "US-003"}],
        ), patch(
            "agenticguidance.services.epic_repository.EpicRepository",
            return_value=mock_repo,
        ):
            check, _ = _get_story_coverage_check(cli_runner)

        value = check["value"]
        assert "total" in value
        assert "covered" in value
        assert "uncovered_count" in value
        assert "uncovered" in value
        assert "coverage_pct" in value
        assert isinstance(value["total"], int)
        assert isinstance(value["covered"], int)
        assert isinstance(value["uncovered_count"], int)
        assert isinstance(value["uncovered"], list)
        assert isinstance(value["coverage_pct"], float)
        assert value["total"] == 3
        assert value["covered"] == 2
        assert value["uncovered_count"] == 1
        assert value["uncovered"] == ["US-003"]
        assert value["coverage_pct"] == 66.7
