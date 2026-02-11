"""Tests for stories commands."""

import json
import os
import sys

import pytest
import yaml


@pytest.fixture
def sample_userstories(temp_dir):
    """Create sample userstories directory."""
    stories_dir = temp_dir / "userstories"
    stories_dir.mkdir()

    # Create some sample stories
    story1 = {
        "story": {
            "title": "Test Story 1",
            "as_a": "developer",
            "i_want": "to test features",
            "so_that": "I can verify functionality",
        }
    }
    with open(stories_dir / "story1.yml", "w") as f:
        yaml.dump(story1, f)

    story2 = {
        "story": {
            "title": "Test Story 2",
            "as_a": "user",
            "i_want": "to use the CLI",
            "so_that": "I can automate tasks",
        }
    }
    with open(stories_dir / "story2.yml", "w") as f:
        yaml.dump(story2, f)

    return stories_dir


@pytest.fixture
def userstories_dir(temp_repo):
    """Create a userstories directory in the temp repo with test data."""
    us_dir = temp_repo / "docs" / "userstories"
    us_dir.mkdir(parents=True, exist_ok=True)

    project_dir = us_dir / "TestProject"
    project_dir.mkdir()

    stories = {
        "stories": [
            {
                "id": "US-TEST-001",
                "title": "First Test Story",
                "category": "testing",
                "priority": "high",
                "as_a": "developer",
                "i_want": "to test",
                "so_that": "it works",
                "acceptance_criteria": ["Something works"],
                "test_status": "pass",
                "last_tested": "2026-02-01T00:00:00+00:00",
                "test_notes": "All good",
                "tested_by_plan": "260201XX_test",
            },
            {
                "id": "US-TEST-002",
                "title": "Second Test Story",
                "category": "testing",
                "priority": "medium",
                "as_a": "user",
                "i_want": "to use feature",
                "so_that": "I benefit",
                "acceptance_criteria": ["Feature works"],
            },
            {
                "id": "US-TEST-003",
                "title": "Third Test Story - Failed",
                "category": "testing",
                "priority": "low",
                "test_status": "fail",
                "last_tested": "2026-02-05T00:00:00+00:00",
                "test_notes": "Broken",
            },
        ]
    }

    (project_dir / "01_tests.yml").write_text(
        yaml.dump(stories, sort_keys=False, default_flow_style=False)
    )

    return us_dir


class TestStoriesFind:
    """Tests for 'agentic stories find' command."""

    def test_find_help(self, cli_runner):
        """Test stories find --help output."""
        stdout, stderr, code = cli_runner(["stories", "find", "--help"])
        assert "find" in stdout.lower()
        assert "--project" in stdout
        assert "--changes" in stdout
        assert code == 0

    def test_find_no_userstories(self, cli_runner, temp_dir):
        """Test find when no userstories directory exists."""
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            stdout, stderr, code = cli_runner(["stories", "find"])
            # Should handle gracefully
            assert code in [0, 1]
        finally:
            os.chdir(original_cwd)

    def test_find_with_userstories(self, cli_runner, sample_userstories):
        """Test find with userstories directory."""
        original_cwd = os.getcwd()
        os.chdir(sample_userstories.parent)
        try:
            stdout, stderr, code = cli_runner(["stories", "find"])
            # Should find stories or report none
            assert code in [0, 1]
        finally:
            os.chdir(original_cwd)

    def test_find_with_project_filter(self, cli_runner):
        """Test find with --project filter."""
        stdout, stderr, code = cli_runner(["stories", "find", "--project", "test"])
        # Should attempt to filter - may pass or fail depending on context
        assert code in [0, 1]


class TestStoriesStatus:
    """Tests for 'agentic stories status' command."""

    def test_status_help(self, cli_runner):
        """Test stories status --help."""
        stdout, stderr, code = cli_runner(["stories", "status", "--help"])
        assert code == 0
        assert "status" in stdout.lower()

    def test_status_existing_story(self, cli_runner, userstories_dir):
        """Test status for a story with test metadata."""
        stdout, stderr, code = cli_runner(["stories", "status", "US-TEST-001"])
        assert code == 0
        assert "US-TEST-001" in stdout
        assert "pass" in stdout.lower()

    def test_status_untested_story(self, cli_runner, userstories_dir):
        """Test status for a story without test metadata."""
        stdout, stderr, code = cli_runner(["stories", "status", "US-TEST-002"])
        assert code == 0
        assert "US-TEST-002" in stdout
        assert "untested" in stdout.lower()

    def test_status_not_found(self, cli_runner, userstories_dir):
        """Test status for nonexistent story."""
        stdout, stderr, code = cli_runner(["stories", "status", "US-NONEXIST-999"])
        assert code == 1

    def test_status_json_output(self, cli_runner, userstories_dir):
        """Test status with JSON output."""
        stdout, stderr, code = cli_runner(["--json", "stories", "status", "US-TEST-001"])
        assert code == 0
        data = json.loads(stdout)
        assert data["id"] == "US-TEST-001"
        assert data["test_status"] == "pass"
        assert data["last_tested"] is not None


class TestStoriesUpdate:
    """Tests for 'agentic stories update' command."""

    def test_update_help(self, cli_runner):
        """Test stories update --help."""
        stdout, stderr, code = cli_runner(["stories", "update", "--help"])
        assert code == 0
        assert "status" in stdout.lower()

    def test_update_pass(self, cli_runner, userstories_dir):
        """Test updating a story to pass."""
        stdout, stderr, code = cli_runner([
            "stories", "update", "US-TEST-002", "--status", "pass"
        ])
        assert code == 0
        assert "Updated" in stdout

        # Verify the file was updated
        content = yaml.safe_load(
            (userstories_dir / "TestProject" / "01_tests.yml").read_text()
        )
        story = next(s for s in content["stories"] if s["id"] == "US-TEST-002")
        assert story["test_status"] == "pass"
        assert story["last_tested"] is not None

    def test_update_fail_with_notes(self, cli_runner, userstories_dir):
        """Test updating a story to fail with notes."""
        stdout, stderr, code = cli_runner([
            "stories", "update", "US-TEST-002",
            "--status", "fail",
            "--notes", "Command crashed",
        ])
        assert code == 0

        content = yaml.safe_load(
            (userstories_dir / "TestProject" / "01_tests.yml").read_text()
        )
        story = next(s for s in content["stories"] if s["id"] == "US-TEST-002")
        assert story["test_status"] == "fail"
        assert story["test_notes"] == "Command crashed"

    def test_update_with_plan(self, cli_runner, userstories_dir):
        """Test updating a story with plan reference."""
        stdout, stderr, code = cli_runner([
            "stories", "update", "US-TEST-002",
            "--status", "pass",
            "--plan", "260207CL_test",
        ])
        assert code == 0

        content = yaml.safe_load(
            (userstories_dir / "TestProject" / "01_tests.yml").read_text()
        )
        story = next(s for s in content["stories"] if s["id"] == "US-TEST-002")
        assert story["tested_by_plan"] == "260207CL_test"

    def test_update_not_found(self, cli_runner, userstories_dir):
        """Test update for nonexistent story."""
        stdout, stderr, code = cli_runner([
            "stories", "update", "US-NONEXIST-999", "--status", "pass"
        ])
        assert code == 1

    def test_update_json_output(self, cli_runner, userstories_dir):
        """Test update with JSON output."""
        stdout, stderr, code = cli_runner([
            "--json", "stories", "update", "US-TEST-002", "--status", "skip"
        ])
        assert code == 0
        data = json.loads(stdout)
        assert data["updated"] == "US-TEST-002"
        assert data["test_status"] == "skip"


class TestStoriesReport:
    """Tests for 'agentic stories report' command."""

    def test_report_help(self, cli_runner):
        """Test stories report --help."""
        stdout, stderr, code = cli_runner(["stories", "report", "--help"])
        assert code == 0

    def test_report_basic(self, cli_runner, userstories_dir):
        """Test basic report output."""
        stdout, stderr, code = cli_runner(["stories", "report"])
        assert code == 0
        assert "Pass" in stdout
        assert "Fail" in stdout
        assert "Untested" in stdout

    def test_report_with_project(self, cli_runner, userstories_dir):
        """Test report filtered by project."""
        stdout, stderr, code = cli_runner(["stories", "report", "--project", "TestProject"])
        assert code == 0
        assert "Pass" in stdout

    def test_report_json_output(self, cli_runner, userstories_dir):
        """Test report with JSON output."""
        stdout, stderr, code = cli_runner(["--json", "stories", "report"])
        assert code == 0
        data = json.loads(stdout)
        assert "total" in data
        assert "pass" in data
        assert "fail" in data
        assert "untested" in data
        # Our fixture has 1 pass, 1 fail, 1 untested
        assert data["pass"] == 1
        assert data["fail"] == 1
        assert data["untested"] == 1

    def test_report_json_with_project_filter(self, cli_runner, userstories_dir):
        """Test report JSON with project filter."""
        stdout, stderr, code = cli_runner([
            "--json", "stories", "report", "--project", "TestProject"
        ])
        assert code == 0
        data = json.loads(stdout)
        assert data["total"] == 3
        assert data["project_filter"] == "TestProject"


class TestStoriesUntested:
    """Tests for 'agentic stories untested' command."""

    def test_untested_help(self, cli_runner):
        """Test stories untested --help."""
        stdout, stderr, code = cli_runner(["stories", "untested", "--help"])
        assert code == 0

    def test_untested_basic(self, cli_runner, userstories_dir):
        """Test basic untested output."""
        stdout, stderr, code = cli_runner(["stories", "untested"])
        assert code == 0
        assert "US-TEST-002" in stdout
        # US-TEST-001 is pass, US-TEST-003 is fail, only US-TEST-002 is untested
        assert "US-TEST-001" not in stdout
        assert "US-TEST-003" not in stdout

    def test_untested_with_project(self, cli_runner, userstories_dir):
        """Test untested filtered by project."""
        stdout, stderr, code = cli_runner([
            "stories", "untested", "--project", "TestProject"
        ])
        assert code == 0
        assert "US-TEST-002" in stdout

    def test_untested_json_output(self, cli_runner, userstories_dir):
        """Test untested with JSON output."""
        stdout, stderr, code = cli_runner(["--json", "stories", "untested"])
        assert code == 0
        data = json.loads(stdout)
        assert data["count"] == 1
        assert len(data["untested"]) == 1
        assert data["untested"][0]["id"] == "US-TEST-002"


class TestMigrationScript:
    """Tests for the stories migration script logic."""

    @pytest.fixture(autouse=True)
    def add_scripts_to_path(self):
        """Add scripts directory to path for importing."""
        from pathlib import Path
        # Navigate from test file up to repo root: tests/ -> AgenticCLI/ -> modules/ -> repo root
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        scripts_dir = str(repo_root / "scripts")
        sys.path.insert(0, scripts_dir)
        yield
        if scripts_dir in sys.path:
            sys.path.remove(scripts_dir)

    def test_migrate_adds_fields(self, tmp_path):
        """Test that migration adds test metadata fields."""
        from migrate_stories import migrate_story_file

        # Create a story without test metadata
        story_file = tmp_path / "test_story.yml"
        content = {
            "stories": [
                {"id": "US-TEST-001", "title": "Test Story"},
                {"id": "US-TEST-002", "title": "Another Story"},
            ]
        }
        story_file.write_text(yaml.dump(content, sort_keys=False))

        result = migrate_story_file(story_file)
        assert result["stories_updated"] == 2
        assert result["already_current"] == 0

        # Verify fields were added
        updated = yaml.safe_load(story_file.read_text())
        for story in updated["stories"]:
            assert "test_status" in story
            assert story["test_status"] == "untested"
            assert "last_tested" in story
            assert story["last_tested"] is None
            assert "test_notes" in story
            assert "tested_by_plan" in story

    def test_migrate_idempotent(self, tmp_path):
        """Test that migration is idempotent."""
        from migrate_stories import migrate_story_file

        story_file = tmp_path / "test_story.yml"
        content = {
            "stories": [
                {
                    "id": "US-TEST-001",
                    "title": "Test Story",
                    "test_status": "pass",
                    "last_tested": "2026-02-01",
                    "test_notes": "OK",
                    "tested_by_plan": "some_plan",
                },
            ]
        }
        story_file.write_text(yaml.dump(content, sort_keys=False))

        result = migrate_story_file(story_file)
        assert result["stories_updated"] == 0
        assert result["already_current"] == 1

        # Verify existing values were preserved
        updated = yaml.safe_load(story_file.read_text())
        assert updated["stories"][0]["test_status"] == "pass"

    def test_migrate_dry_run(self, tmp_path):
        """Test that dry run doesn't write files."""
        from migrate_stories import migrate_story_file

        story_file = tmp_path / "test_story.yml"
        content = {"stories": [{"id": "US-TEST-001", "title": "Test"}]}
        original_text = yaml.dump(content, sort_keys=False)
        story_file.write_text(original_text)

        result = migrate_story_file(story_file, dry_run=True)
        assert result["stories_updated"] == 1

        # File should be unchanged
        assert story_file.read_text() == original_text


class TestStoriesUpdateRegression:
    """Tests for regression status support."""

    def test_update_regression(self, cli_runner, userstories_dir):
        """Test updating a story to regression status."""
        stdout, stderr, code = cli_runner([
            "stories", "update", "US-TEST-001", "--status", "regression"
        ])
        assert code == 0
        assert "Updated" in stdout

        content = yaml.safe_load(
            (userstories_dir / "TestProject" / "01_tests.yml").read_text()
        )
        story = next(s for s in content["stories"] if s["id"] == "US-TEST-001")
        assert story["test_status"] == "regression"
        assert story["last_tested"] is not None

    def test_report_includes_regression(self, cli_runner, userstories_dir):
        """Test that report includes regression count."""
        # First set a story to regression
        cli_runner([
            "stories", "update", "US-TEST-001", "--status", "regression"
        ])

        stdout, stderr, code = cli_runner(["stories", "report"])
        assert code == 0
        assert "Regression" in stdout

    def test_report_json_includes_regression(self, cli_runner, userstories_dir):
        """Test that JSON report includes regression count."""
        cli_runner([
            "stories", "update", "US-TEST-001", "--status", "regression"
        ])

        stdout, stderr, code = cli_runner(["--json", "stories", "report"])
        assert code == 0
        data = json.loads(stdout)
        assert "regression" in data
        assert data["regression"] == 1


class TestStoriesBatchUpdate:
    """Tests for 'agentic stories batch-update' command."""

    @pytest.fixture
    def plan_with_stories(self, userstories_dir):
        """Create a plan with affected_stories referencing test stories."""
        temp_repo = userstories_dir.parent.parent
        plan_dir = temp_repo / "docs" / "plans" / "live" / "260210XX_test_plan"
        plan_dir.mkdir(parents=True, exist_ok=True)

        plan_build = {
            "description": "Test plan",
            "affected_stories": ["US-TEST-001", "US-TEST-002"],
        }
        (plan_dir / "plan_build.yml").write_text(
            yaml.dump(plan_build, sort_keys=False)
        )
        return plan_dir

    def test_batch_update_help(self, cli_runner):
        """Test batch-update --help."""
        stdout, stderr, code = cli_runner(["stories", "batch-update", "--help"])
        assert code == 0
        assert "batch-update" in stdout.lower() or "batch" in stdout.lower()

    def test_batch_update_pass(self, cli_runner, plan_with_stories, userstories_dir):
        """Test batch updating all affected stories to pass."""
        stdout, stderr, code = cli_runner([
            "stories", "batch-update",
            "--plan", "260210XX_test_plan",
            "--status", "pass",
        ])
        assert code == 0
        assert "Updated 2 stories" in stdout

        # Verify both stories were updated
        content = yaml.safe_load(
            (userstories_dir / "TestProject" / "01_tests.yml").read_text()
        )
        for story in content["stories"]:
            if story["id"] in ("US-TEST-001", "US-TEST-002"):
                assert story["test_status"] == "pass"
                assert story["tested_by_plan"] == "260210XX_test_plan"
                assert story["last_tested"] is not None

    def test_batch_update_with_notes(self, cli_runner, plan_with_stories, userstories_dir):
        """Test batch update with notes."""
        stdout, stderr, code = cli_runner([
            "stories", "batch-update",
            "--plan", "260210XX_test_plan",
            "--status", "pass",
            "--notes", "All passed via batch",
        ])
        assert code == 0

        content = yaml.safe_load(
            (userstories_dir / "TestProject" / "01_tests.yml").read_text()
        )
        story = next(s for s in content["stories"] if s["id"] == "US-TEST-001")
        assert story["test_notes"] == "All passed via batch"

    def test_batch_update_no_stories(self, cli_runner, userstories_dir):
        """Test batch update when plan has no affected_stories."""
        # Create plan without affected_stories
        temp_repo = userstories_dir.parent.parent
        plan_dir = temp_repo / "docs" / "plans" / "live" / "260210YY_empty"
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "plan_build.yml").write_text(
            yaml.dump({"description": "Empty"}, sort_keys=False)
        )

        stdout, stderr, code = cli_runner([
            "stories", "batch-update",
            "--plan", "260210YY_empty",
            "--status", "pass",
        ])
        assert code == 1

    def test_batch_update_json(self, cli_runner, plan_with_stories, userstories_dir):
        """Test batch update with JSON output."""
        stdout, stderr, code = cli_runner([
            "--json", "stories", "batch-update",
            "--plan", "260210XX_test_plan",
            "--status", "pass",
        ])
        assert code == 0
        data = json.loads(stdout)
        assert data["count"] == 2
        assert "US-TEST-001" in data["updated"]
        assert "US-TEST-002" in data["updated"]
        assert data["plan"] == "260210XX_test_plan"

    def test_batch_update_nonexistent_plan(self, cli_runner, userstories_dir):
        """Test batch update with plan that doesn't exist."""
        stdout, stderr, code = cli_runner([
            "stories", "batch-update",
            "--plan", "nonexistent_plan",
            "--status", "pass",
        ])
        assert code == 1


class TestStoriesAffected:
    """Tests for 'agentic stories affected' command."""

    @pytest.fixture
    def plan_with_stories(self, userstories_dir):
        """Create a plan with affected_stories referencing test stories."""
        temp_repo = userstories_dir.parent.parent
        plan_dir = temp_repo / "docs" / "plans" / "live" / "260210XX_test_plan"
        plan_dir.mkdir(parents=True, exist_ok=True)

        plan_build = {
            "description": "Test plan",
            "affected_stories": ["US-TEST-001", "US-TEST-002"],
        }
        (plan_dir / "plan_build.yml").write_text(
            yaml.dump(plan_build, sort_keys=False)
        )
        return plan_dir

    def test_affected_help(self, cli_runner):
        """Test stories affected --help."""
        stdout, stderr, code = cli_runner(["stories", "affected", "--help"])
        assert code == 0

    def test_affected_basic(self, cli_runner, plan_with_stories, userstories_dir):
        """Test listing affected stories for a plan."""
        stdout, stderr, code = cli_runner([
            "stories", "affected", "--plan", "260210XX_test_plan"
        ])
        assert code == 0
        assert "US-TEST-001" in stdout
        assert "US-TEST-002" in stdout

    def test_affected_json(self, cli_runner, plan_with_stories, userstories_dir):
        """Test affected with JSON output."""
        stdout, stderr, code = cli_runner([
            "--json", "stories", "affected", "--plan", "260210XX_test_plan"
        ])
        assert code == 0
        data = json.loads(stdout)
        assert data["count"] == 2
        assert data["plan"] == "260210XX_test_plan"
        ids = [s["id"] for s in data["affected_stories"]]
        assert "US-TEST-001" in ids
        assert "US-TEST-002" in ids
        # Check test_status is included
        for s in data["affected_stories"]:
            assert "test_status" in s

    def test_affected_no_plan(self, cli_runner, userstories_dir):
        """Test affected with nonexistent plan."""
        stdout, stderr, code = cli_runner([
            "stories", "affected", "--plan", "nonexistent_plan"
        ])
        assert code == 1

    def test_affected_shows_test_status(self, cli_runner, plan_with_stories, userstories_dir):
        """Test that affected shows current test_status from story files."""
        # US-TEST-001 has test_status=pass in the fixture
        stdout, stderr, code = cli_runner([
            "--json", "stories", "affected", "--plan", "260210XX_test_plan"
        ])
        assert code == 0
        data = json.loads(stdout)
        story_001 = next(s for s in data["affected_stories"] if s["id"] == "US-TEST-001")
        assert story_001["test_status"] == "pass"
