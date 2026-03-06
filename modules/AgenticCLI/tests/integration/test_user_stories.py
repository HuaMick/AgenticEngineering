"""Integration test for user stories workflow.

End-to-end test that validates the complete user stories workflow:
1. Create plan with user_stories in YAML
2. agentic plan stories list
3. agentic plan stories test
4. Verify generated test structure

This test ensures the stories commands work together to list and generate
test cases from user stories defined in plan files.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.integration


class TestUserStoriesWorkflow:
    """Integration test for the complete user stories workflow."""

    @pytest.fixture
    def stories_repo(self):
        """Create a full integration test repo with git for user stories testing.

        Sets up:
        - Git repository with initial commit
        - docs/epics/live directory structure
        - User configuration for git
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "StoriesProject"
            repo_path.mkdir()

            # Initialize git
            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@stories.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Stories Test User"],
                cwd=repo_path,
                capture_output=True,
            )

            # Create initial structure
            (repo_path / "docs" / "epics" / "live").mkdir(parents=True)
            (repo_path / "README.md").write_text("# Stories Test Project\n")

            # Initial commit
            subprocess.run(
                ["git", "add", "."],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def cli_in_repo(self, stories_repo):
        """Run CLI commands in the stories repo.

        Provides a function that executes CLI commands and returns:
        - stdout: Standard output
        - stderr: Standard error
        - exit_code: Exit code from the command
        """
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(stories_repo)

        def run_cli(*args, expect_exit=None):
            from agenticcli.cli import run_cli as _run_cli
            from agenticcli.console import set_json_output

            set_json_output(False)

            if len(args) == 1 and isinstance(args[0], list):
                cmd_args = args[0]
            else:
                cmd_args = list(args)

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            exit_code = 0

            with patch.object(sys, "argv", ["agentic"] + cmd_args):
                with redirect_stdout(stdout_capture):
                    with redirect_stderr(stderr_capture):
                        try:
                            _run_cli()
                        except SystemExit as e:
                            exit_code = e.code if e.code is not None else 0

            stdout = stdout_capture.getvalue()
            stderr = stderr_capture.getvalue()

            if expect_exit is not None:
                assert exit_code == expect_exit, (
                    f"Expected exit {expect_exit}, got {exit_code}. "
                    f"stdout: {stdout}, stderr: {stderr}"
                )

            return stdout, stderr, exit_code

        yield run_cli

        os.chdir(original_cwd)

    def _create_plan_with_stories(self, plan_path: Path) -> dict:
        """Create a plan file with user stories for testing.

        Args:
            plan_path: Path to the plan folder.

        Returns:
            The plan content dictionary.
        """
        plan_content = {
            "plan": {
                "name": "User Stories Test Plan",
                "status": "in_progress",
                "objective": "Test user story workflow",
                "phases": [
                    {
                        "id": "P1",
                        "name": "Implementation",
                        "status": "pending",
                        "tickets": [
                            {
                                "id": "T1",
                                "description": "Implement feature",
                                "status": "pending",
                            }
                        ],
                    }
                ],
            },
            "user_stories": [
                {
                    "id": "US-TEST-001",
                    "as": "developer",
                    "i_want": "list all user stories in the plan",
                    "so_that": "I can see what features need to be implemented",
                    "command": "agentic plan stories list",
                    "acceptance": [
                        "Shows story ID",
                        "Shows persona (as)",
                        "Shows action (i_want)",
                    ],
                },
                {
                    "id": "US-TEST-002",
                    "as": "tester",
                    "i_want": "generate test cases from user stories",
                    "so_that": "I can validate that features meet acceptance criteria",
                    "command": "agentic plan stories test",
                    "acceptance": [
                        "Generates test_id for each story",
                        "Includes expected_outcome",
                        "Includes validation_type",
                    ],
                },
                {
                    "id": "US-TEST-003",
                    "as": "automation engineer",
                    "i_want": "export test cases to a file",
                    "so_that": "I can integrate them into CI/CD pipelines",
                    "command": "agentic plan stories test --output tests.yml",
                    "acceptance": [
                        "Creates YAML file with test cases",
                        "File is valid YAML",
                    ],
                },
            ],
        }

        # Write the plan file
        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f, default_flow_style=False, sort_keys=False)

        return plan_content

    def test_full_user_stories_workflow(self, cli_in_repo, stories_repo):
        """Test complete user stories workflow from creation to test generation.

        This test exercises the full user stories flow:
        1. Scaffold a plan folder
        2. Create plan file with user_stories
        3. Run stories list to view stories
        4. Run stories test to generate test YAML
        5. Verify generated test structure
        """
        # Step 1: Scaffold a plan folder
        stdout, stderr, code = cli_in_repo("agent", "epic", "scaffold", "stories-test")
        assert code == 0, f"Plan scaffold failed: {stderr}"
        assert "Created planning folder" in stdout

        # Verify plan folder was created
        plan_path = stories_repo / "docs" / "epics" / "live" / "stories-test"
        assert plan_path.exists(), "Plan folder was not created"

        # Step 2: Create plan file with user_stories
        plan_content = self._create_plan_with_stories(plan_path)

        # Verify file was created
        plan_file = plan_path / "plan_build.yml"
        assert plan_file.exists(), "plan_build.yml was not created"

        # Step 3: Run stories list
        stdout, stderr, code = cli_in_repo(
            "agent", "epic", "stories", "list",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Stories list failed: {stderr}"

        # Verify stories are listed
        assert "US-TEST-001" in stdout, "Story US-TEST-001 not found in output"
        assert "US-TEST-002" in stdout, "Story US-TEST-002 not found in output"
        assert "US-TEST-003" in stdout, "Story US-TEST-003 not found in output"
        assert "developer" in stdout or "tester" in stdout, "Personas not shown"

        # Step 4: Run stories test to generate test YAML (to stdout)
        stdout, stderr, code = cli_in_repo(
            "agent", "epic", "stories", "test",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Stories test failed: {stderr}"

        # Verify test output structure
        assert "test_suite" in stdout or "test_cases" in stdout, (
            "Test output missing expected structure"
        )
        assert "test_US-TEST-001" in stdout, "Test case for US-TEST-001 not generated"
        assert "test_US-TEST-002" in stdout, "Test case for US-TEST-002 not generated"
        assert "test_US-TEST-003" in stdout, "Test case for US-TEST-003 not generated"

        # Parse the YAML output
        test_output = yaml.safe_load(stdout)
        assert test_output is not None, "Could not parse test output as YAML"
        assert "test_cases" in test_output, "test_cases key missing from output"
        assert len(test_output["test_cases"]) == 3, (
            f"Expected 3 test cases, got {len(test_output['test_cases'])}"
        )

        # Verify test case structure
        for test_case in test_output["test_cases"]:
            assert "test_id" in test_case, "test_id missing from test case"
            assert "story_id" in test_case, "story_id missing from test case"
            assert "expected_outcome" in test_case, "expected_outcome missing"
            assert "validation_type" in test_case, "validation_type missing"

    def test_stories_list_json_output(self, cli_in_repo, stories_repo):
        """Test stories list command with JSON output mode.

        Verifies that JSON output mode works for stories list
        and produces machine-readable output.
        """
        # Setup plan with stories
        plan_path = stories_repo / "docs" / "epics" / "live" / "json-stories"
        plan_path.mkdir(parents=True)
        self._create_plan_with_stories(plan_path)

        # Run stories list with JSON output
        stdout, stderr, code = cli_in_repo(
            "--json", "agent", "epic", "stories", "list",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Stories list JSON failed: {stderr}"

        # Parse JSON output
        data = json.loads(stdout)
        assert "user_stories" in data, "user_stories key missing from JSON"
        assert "count" in data, "count key missing from JSON"
        assert data["count"] == 3, f"Expected 3 stories, got {data['count']}"

        # Verify story structure in JSON
        for story in data["user_stories"]:
            assert "id" in story, "Story missing id field"
            assert "as" in story, "Story missing as field"
            assert "i_want" in story, "Story missing i_want field"

    def test_stories_test_to_file(self, cli_in_repo, stories_repo):
        """Test stories test command with file output.

        Verifies that test cases can be written to a file
        in YAML or JSON format.
        """
        # Setup plan with stories
        plan_path = stories_repo / "docs" / "epics" / "live" / "file-output"
        plan_path.mkdir(parents=True)
        self._create_plan_with_stories(plan_path)

        # Test YAML file output
        yaml_output = plan_path / "generated_tests.yml"
        stdout, stderr, code = cli_in_repo(
            "agent", "epic", "stories", "test",
            "--plan", str(plan_path),
            "--output", str(yaml_output)
        )
        assert code == 0, f"Stories test YAML output failed: {stderr}"
        assert yaml_output.exists(), "YAML output file was not created"
        assert "Generated" in stdout, "Success message not shown"

        # Verify YAML file content
        yaml_content = yaml.safe_load(yaml_output.read_text())
        assert yaml_content is not None, "Could not parse YAML output file"
        assert "test_suite" in yaml_content, "test_suite missing from YAML file"
        assert "test_cases" in yaml_content, "test_cases missing from YAML file"
        assert len(yaml_content["test_cases"]) == 3, "Expected 3 test cases in file"

        # Test JSON file output
        json_output = plan_path / "generated_tests.json"
        stdout, stderr, code = cli_in_repo(
            "agent", "epic", "stories", "test",
            "--plan", str(plan_path),
            "--output", str(json_output),
            "--format", "json"
        )
        assert code == 0, f"Stories test JSON output failed: {stderr}"
        assert json_output.exists(), "JSON output file was not created"

        # Verify JSON file content
        with open(json_output) as f:
            json_content = json.load(f)
        assert "test_suite" in json_content, "test_suite missing from JSON file"
        assert "test_cases" in json_content, "test_cases missing from JSON file"

    def test_stories_test_validation_types(self, cli_in_repo, stories_repo):
        """Test that stories test generates correct validation types.

        Verifies that the validation_type is correctly determined
        based on the command type.
        """
        # Create plan with different command types
        plan_path = stories_repo / "docs" / "epics" / "live" / "validation-types"
        plan_path.mkdir(parents=True)

        plan_content = {
            "plan": {
                "name": "Validation Types Test",
                "status": "pending",
            },
            "user_stories": [
                {
                    "id": "US-VAL-001",
                    "as": "user",
                    "i_want": "create a new plan",
                    "so_that": "I have a workspace",
                    "command": "agentic plan scaffold my-plan",
                },
                {
                    "id": "US-VAL-002",
                    "as": "user",
                    "i_want": "list all plans",
                    "so_that": "I can see available plans",
                    "command": "agentic plan list",
                },
                {
                    "id": "US-VAL-003",
                    "as": "user",
                    "i_want": "get plan status in JSON",
                    "so_that": "I can parse it programmatically",
                    "command": "agentic --json plan status",
                },
                {
                    "id": "US-VAL-004",
                    "as": "user",
                    "i_want": "perform a manual action",
                    "so_that": "I can complete the workflow",
                    # No command - should be manual validation
                },
            ],
        }

        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Generate test cases
        stdout, stderr, code = cli_in_repo(
            "agent", "epic", "stories", "test",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Stories test failed: {stderr}"

        # Parse output and verify validation types
        test_output = yaml.safe_load(stdout)
        test_cases = {tc["story_id"]: tc for tc in test_output["test_cases"]}

        # scaffold command -> file_exists validation
        assert test_cases["US-VAL-001"]["validation_type"] == "file_exists", (
            "scaffold command should have file_exists validation"
        )

        # list command -> output_contains validation
        assert test_cases["US-VAL-002"]["validation_type"] == "output_contains", (
            "list command should have output_contains validation"
        )

        # --json command -> json_schema validation
        assert test_cases["US-VAL-003"]["validation_type"] == "json_schema", (
            "--json command should have json_schema validation"
        )

        # No command -> manual validation
        assert test_cases["US-VAL-004"]["validation_type"] == "manual", (
            "No command should have manual validation"
        )

    def test_stories_list_no_stories(self, cli_in_repo, stories_repo):
        """Test stories list when plan has no user stories.

        Verifies graceful handling when no stories are found.
        """
        # Create plan without user_stories
        plan_path = stories_repo / "docs" / "epics" / "live" / "no-stories"
        plan_path.mkdir(parents=True)

        plan_content = {
            "plan": {
                "name": "No Stories Plan",
                "status": "pending",
                "phases": [{"id": "P1", "name": "Phase 1"}],
            }
        }

        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Run stories list
        stdout, stderr, code = cli_in_repo(
            "agent", "epic", "stories", "list",
            "--plan", str(plan_path)
        )
        # Should succeed but show no stories
        assert code == 0, f"Stories list failed: {stderr}"
        # Output should indicate no stories found
        combined = stdout + stderr
        assert "0" in combined or "No user stories" in combined or "Total: 0" in combined

    def test_stories_test_no_stories(self, cli_in_repo, stories_repo):
        """Test stories test when plan has no user stories.

        Verifies error handling when trying to generate tests
        from a plan with no stories.
        """
        # Create plan without user_stories
        plan_path = stories_repo / "docs" / "epics" / "live" / "no-stories-test"
        plan_path.mkdir(parents=True)

        plan_content = {
            "plan": {
                "name": "No Stories Plan",
                "status": "pending",
            }
        }

        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Run stories test - should fail with no stories
        stdout, stderr, code = cli_in_repo(
            "agent", "epic", "stories", "test",
            "--plan", str(plan_path)
        )
        assert code != 0, "Expected failure when no stories to generate tests from"
        combined = stdout + stderr
        assert "No user stories" in combined or "not found" in combined.lower()


class TestUserStoriesEdgeCases:
    """Edge case tests for user stories workflow."""

    @pytest.fixture
    def edge_repo(self):
        """Create a repo for edge case testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "EdgeStoriesProject"
            repo_path.mkdir()

            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@edge.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Edge Test User"],
                cwd=repo_path,
                capture_output=True,
            )

            (repo_path / "docs" / "epics" / "live").mkdir(parents=True)
            (repo_path / "README.md").write_text("# Edge Case Stories\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def edge_cli(self, edge_repo):
        """Run CLI commands in edge case repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(edge_repo)

        def run_cli(*args):
            from agenticcli.cli import run_cli as _run_cli
            from agenticcli.console import set_json_output

            set_json_output(False)

            if len(args) == 1 and isinstance(args[0], list):
                cmd_args = args[0]
            else:
                cmd_args = list(args)

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            exit_code = 0

            with patch.object(sys, "argv", ["agentic"] + cmd_args):
                with redirect_stdout(stdout_capture):
                    with redirect_stderr(stderr_capture):
                        try:
                            _run_cli()
                        except SystemExit as e:
                            exit_code = e.code if e.code is not None else 0

            return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

        yield run_cli

        os.chdir(original_cwd)

    def test_stories_with_special_characters(self, edge_cli, edge_repo):
        """Test handling of special characters in user story content.

        Verifies that special characters in story descriptions
        are properly handled during list and test generation.
        """
        plan_path = edge_repo / "docs" / "epics" / "live" / "special-chars"
        plan_path.mkdir(parents=True)

        plan_content = {
            "plan": {"name": "Special Chars Plan"},
            "user_stories": [
                {
                    "id": "US-SPECIAL-001",
                    "as": "developer",
                    "i_want": "handle 'quotes' and \"double quotes\"",
                    "so_that": "I can use any text (including parentheses)",
                    "command": "agentic plan status --filter='active'",
                },
                {
                    "id": "US-SPECIAL-002",
                    "as": "user",
                    "i_want": "search for files with regex: *.yml",
                    "so_that": "I can find YAML files",
                    "command": "agentic stories find --pattern='*.yml'",
                },
            ],
        }

        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Stories list should handle special characters
        stdout, stderr, code = edge_cli(
            "agent", "epic", "stories", "list",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Stories list failed: {stderr}"
        assert "US-SPECIAL-001" in stdout
        assert "US-SPECIAL-002" in stdout

        # Stories test should handle special characters
        stdout, stderr, code = edge_cli(
            "agent", "epic", "stories", "test",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Stories test failed: {stderr}"

        test_output = yaml.safe_load(stdout)
        assert len(test_output["test_cases"]) == 2

    def test_stories_from_multiple_plan_files(self, edge_cli, edge_repo):
        """Test aggregation of stories from multiple plan_*.yml files.

        Verifies that stories are collected from all plan files
        in the plan folder.
        """
        plan_path = edge_repo / "docs" / "epics" / "live" / "multi-file"
        plan_path.mkdir(parents=True)

        # Create first plan file with stories
        plan1 = {
            "plan": {"name": "Build Plan"},
            "user_stories": [
                {
                    "id": "US-BUILD-001",
                    "as": "builder",
                    "i_want": "build the feature",
                    "so_that": "it works",
                },
            ],
        }
        with open(plan_path / "plan_build.yml", "w") as f:
            yaml.dump(plan1, f)

        # Create second plan file with stories
        plan2 = {
            "plan": {"name": "Test Plan"},
            "user_stories": [
                {
                    "id": "US-TEST-001",
                    "as": "tester",
                    "i_want": "test the feature",
                    "so_that": "it is validated",
                },
                {
                    "id": "US-TEST-002",
                    "as": "qa",
                    "i_want": "verify quality",
                    "so_that": "it meets standards",
                },
            ],
        }
        with open(plan_path / "plan_test.yml", "w") as f:
            yaml.dump(plan2, f)

        # Stories list should aggregate from both files
        stdout, stderr, code = edge_cli(
            "agent", "epic", "stories", "list",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Stories list failed: {stderr}"
        assert "US-BUILD-001" in stdout, "Story from plan_build.yml not found"
        assert "US-TEST-001" in stdout, "Story from plan_test.yml not found"
        assert "US-TEST-002" in stdout, "Second story from plan_test.yml not found"

        # Stories test should generate tests for all stories
        stdout, stderr, code = edge_cli(
            "agent", "epic", "stories", "test",
            "--plan", str(plan_path)
        )
        assert code == 0

        test_output = yaml.safe_load(stdout)
        assert len(test_output["test_cases"]) == 3, (
            f"Expected 3 test cases from multiple files, got {len(test_output['test_cases'])}"
        )

    def test_stories_nested_in_plan_key(self, edge_cli, edge_repo):
        """Test stories nested under plan or feature key.

        Verifies that stories can be found when nested under
        different parent keys in the YAML structure.
        """
        plan_path = edge_repo / "docs" / "epics" / "live" / "nested-stories"
        plan_path.mkdir(parents=True)

        # Stories nested under 'plan' key
        plan_content = {
            "plan": {
                "name": "Nested Plan",
                "status": "pending",
                "user_stories": [
                    {
                        "id": "US-NESTED-001",
                        "as": "user",
                        "i_want": "use nested stories",
                        "so_that": "they are found",
                    },
                ],
            },
        }

        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Stories should be found when nested
        stdout, stderr, code = edge_cli(
            "agent", "epic", "stories", "list",
            "--plan", str(plan_path)
        )
        assert code == 0, f"Stories list failed: {stderr}"
        assert "US-NESTED-001" in stdout, "Nested story not found"

    def test_stories_with_acceptance_list(self, edge_cli, edge_repo):
        """Test stories with acceptance criteria as list.

        Verifies that acceptance criteria lists are properly
        included in generated test cases.
        """
        plan_path = edge_repo / "docs" / "epics" / "live" / "acceptance-list"
        plan_path.mkdir(parents=True)

        plan_content = {
            "plan": {"name": "Acceptance Test"},
            "user_stories": [
                {
                    "id": "US-ACC-001",
                    "as": "tester",
                    "i_want": "have clear acceptance criteria",
                    "so_that": "I know when the feature is complete",
                    "command": "agentic plan validate",
                    "acceptance": [
                        "Criteria 1: Feature loads within 2 seconds",
                        "Criteria 2: No errors in console",
                        "Criteria 3: All tests pass",
                    ],
                },
            ],
        }

        plan_file = plan_path / "plan_build.yml"
        with open(plan_file, "w") as f:
            yaml.dump(plan_content, f)

        # Generate test cases
        stdout, stderr, code = edge_cli(
            "agent", "epic", "stories", "test",
            "--plan", str(plan_path)
        )
        assert code == 0

        test_output = yaml.safe_load(stdout)
        test_case = test_output["test_cases"][0]

        # Verify acceptance criteria is included
        assert "acceptance_criteria" in test_case, "acceptance_criteria missing"
        assert len(test_case["acceptance_criteria"]) == 3, (
            "Expected 3 acceptance criteria"
        )


class TestUserStoriesIntegrationWithOtherCommands:
    """Test user stories integration with other plan commands."""

    @pytest.fixture
    def integration_repo(self):
        """Create a repo for integration testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "IntegrationStoriesProject"
            repo_path.mkdir()

            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@integration.com"],
                cwd=repo_path,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Integration Test User"],
                cwd=repo_path,
                capture_output=True,
            )

            (repo_path / "docs" / "epics" / "live").mkdir(parents=True)
            (repo_path / "README.md").write_text("# Integration Stories\n")
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def integration_cli(self, integration_repo):
        """Run CLI commands in integration repo."""
        import io
        import sys
        from contextlib import redirect_stderr, redirect_stdout

        original_cwd = os.getcwd()
        os.chdir(integration_repo)

        def run_cli(*args):
            from agenticcli.cli import run_cli as _run_cli
            from agenticcli.console import set_json_output

            set_json_output(False)

            if len(args) == 1 and isinstance(args[0], list):
                cmd_args = args[0]
            else:
                cmd_args = list(args)

            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            exit_code = 0

            with patch.object(sys, "argv", ["agentic"] + cmd_args):
                with redirect_stdout(stdout_capture):
                    with redirect_stderr(stderr_capture):
                        try:
                            _run_cli()
                        except SystemExit as e:
                            exit_code = e.code if e.code is not None else 0

            return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

        yield run_cli

        os.chdir(original_cwd)



    def test_complete_plan_workflow_with_stories(
        self, integration_cli, integration_repo
    ):
        """Test complete workflow: scaffold -> template -> stories -> orchestration.

        Verifies that user stories integrate into the full plan workflow.
        """
        # Step 1: Scaffold
        stdout, stderr, code = integration_cli("agent", "epic", "scaffold", "full-workflow")
        assert code == 0

        plan_path = integration_repo / "docs" / "epics" / "live" / "full-workflow"

        # Step 2: Generate template with stories
        output_file = plan_path / "plan_build.yml"
        content = {
            "plan": {
                "name": "Full Workflow Plan",
                "status": "pending",
                "objective": "Test complete workflow",
                "phases": [
                    {
                        "id": "P1",
                        "name": "Build",
                        "status": "pending",
                        "tickets": [{"id": "T1", "description": "Build task"}],
                    }
                ],
            },
            "user_stories": [
                {
                    "id": "US-FLOW-001",
                    "as": "user",
                    "i_want": "complete the workflow",
                    "so_that": "the feature is delivered",
                    "command": "agentic plan status",
                },
            ],
        }
        with open(output_file, "w") as f:
            yaml.dump(content, f)

        # Step 3: Verify stories list works
        stdout, stderr, code = integration_cli(
            "agent", "epic", "stories", "list",
            "--plan", str(plan_path)
        )
        assert code == 0
        assert "US-FLOW-001" in stdout

        # Step 4: Generate tests
        stdout, stderr, code = integration_cli(
            "agent", "epic", "stories", "test",
            "--plan", str(plan_path)
        )
        assert code == 0
        assert "test_US-FLOW-001" in stdout

        # Step 5: Generate orchestration
        stdout, stderr, code = integration_cli(
            "agent", "epic", "orchestration", "generate",
            "--plan", str(plan_path)
        )
        assert code == 0

        # Step 6: Validate plan (should pass with orchestration)
        stdout, stderr, code = integration_cli(
            "agent", "epic", "orchestration", "validate",
            "--plan", str(plan_path)
        )
        assert code == 0
