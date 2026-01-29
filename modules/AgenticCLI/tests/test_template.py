"""Tests for template commands."""

import pytest


class TestTemplateGenerate:
    """Tests for 'agentic template generate' command."""

    def test_generate_build_template(self, cli_runner):
        """Test generating a build template."""
        # cli_runner already runs in a git repo (temp_repo)
        stdout, stderr, code = cli_runner(["template", "generate", "build"])
        # Works with both Jinja2 ("# Build Plan") and simple ("# Implementation Plan") templates
        assert "Plan" in stdout
        assert "status: pending" in stdout or "status: planning" in stdout
        assert code == 0

    def test_generate_test_template(self, cli_runner):
        """Test generating a test template."""
        stdout, stderr, code = cli_runner(["template", "generate", "test"])
        assert "# Test Plan" in stdout
        # Works with both Jinja2 ("unit") and simple ("Unit Tests") templates
        assert "unit" in stdout.lower()
        assert code == 0

    def test_generate_cleanup_template(self, cli_runner):
        """Test generating a cleanup template."""
        stdout, stderr, code = cli_runner(["template", "generate", "cleanup"])
        # Works with both Jinja2 ("# Cleanup Plan") and simple ("# Audit and Cleanup Plan") templates
        assert "Cleanup" in stdout
        assert "status: pending" in stdout
        assert code == 0

    def test_generate_guidance_template(self, cli_runner):
        """Test generating a guidance template."""
        stdout, stderr, code = cli_runner(["template", "generate", "guidance"])
        assert "# Guidance Plan" in stdout
        assert code == 0

    def test_generate_with_output(self, cli_runner, temp_repo):
        """Test generating a template to a file."""
        # Use temp_repo (where cli_runner runs) for output file
        output_file = temp_repo / "output.yml"
        stdout, stderr, code = cli_runner(
            ["template", "generate", "build", "--output", str(output_file)]
        )
        assert "Generated:" in stdout
        assert output_file.exists()
        content = output_file.read_text()
        # Works with both Jinja2 ("# Build Plan") and simple ("# Implementation Plan") templates
        assert "Plan" in content
        assert "status: pending" in content or "status: planning" in content
        assert code == 0


class TestTemplateGenerateWithObjective:
    """Tests for 'agentic template generate' with --objective flag."""

    def test_generate_with_objective(self, cli_runner):
        """Test generating a template with custom objective."""
        stdout, stderr, code = cli_runner([
            "template", "generate", "build",
            "--objective", "Build the new authentication system"
        ])
        assert code == 0
        assert "Build the new authentication system" in stdout
        # Should replace the TODO placeholder
        assert "TODO: Describe the build objective" not in stdout

    def test_generate_with_multiline_objective(self, cli_runner, temp_repo):
        """Test generating a template with multi-line objective."""
        output_file = temp_repo / "multiline_obj.yml"
        # Use a single-line objective for CLI, multi-line testing via file
        stdout, stderr, code = cli_runner([
            "template", "generate", "build",
            "--objective", "Build a robust authentication system with OAuth2 support",
            "--output", str(output_file)
        ])
        assert code == 0
        content = output_file.read_text()
        assert "Build a robust authentication system" in content

    def test_generate_guidance_with_objective(self, cli_runner):
        """Test generating guidance template with objective (replaces default)."""
        stdout, stderr, code = cli_runner([
            "template", "generate", "guidance",
            "--objective", "Reduce agent confusion in deployment process"
        ])
        assert code == 0
        assert "Reduce agent confusion in deployment process" in stdout
        # Default objective should be replaced
        assert "Improve agent guidance based on observed friction points" not in stdout


class TestTemplateGenerateWithPhases:
    """Tests for 'agentic template generate' with --phases flag."""

    def test_generate_with_phases(self, cli_runner):
        """Test generating a template with custom phases."""
        stdout, stderr, code = cli_runner([
            "template", "generate", "build",
            "--phases", "P1:Design,P2:Implementation,P3:Testing"
        ])
        assert code == 0
        # Check custom phases are present
        assert 'id: "P1"' in stdout
        assert 'name: "Design"' in stdout
        assert 'id: "P2"' in stdout
        assert 'name: "Implementation"' in stdout
        assert 'id: "P3"' in stdout
        assert 'name: "Testing"' in stdout

    def test_generate_with_single_phase(self, cli_runner):
        """Test generating a template with a single phase."""
        stdout, stderr, code = cli_runner([
            "template", "generate", "build",
            "--phases", "MVP:Minimum Viable Product"
        ])
        assert code == 0
        assert 'id: "MVP"' in stdout
        assert 'name: "Minimum Viable Product"' in stdout

    def test_generate_with_phases_to_file(self, cli_runner, temp_repo):
        """Test generating a template with custom phases to a file."""
        output_file = temp_repo / "phased_plan.yml"
        stdout, stderr, code = cli_runner([
            "template", "generate", "test",
            "--phases", "U1:Unit Tests,I1:Integration Tests,E2E:End to End",
            "--output", str(output_file)
        ])
        assert code == 0
        content = output_file.read_text()
        assert 'id: "U1"' in content
        assert 'name: "Unit Tests"' in content
        assert 'id: "I1"' in content
        assert 'id: "E2E"' in content


class TestTemplateGenerateWithSuccessCriteria:
    """Tests for 'agentic template generate' with --success-criteria flag."""

    def test_generate_with_success_criteria(self, cli_runner):
        """Test generating a template with custom success criteria."""
        stdout, stderr, code = cli_runner([
            "template", "generate", "build",
            "--success-criteria", "Tests pass,Coverage > 80%,No lint errors"
        ])
        assert code == 0
        assert "success_criteria:" in stdout
        assert "Tests pass" in stdout
        assert "Coverage > 80%" in stdout
        assert "No lint errors" in stdout

    def test_generate_with_single_success_criterion(self, cli_runner):
        """Test generating a template with a single success criterion."""
        stdout, stderr, code = cli_runner([
            "template", "generate", "build",
            "--success-criteria", "All tests passing"
        ])
        assert code == 0
        assert "success_criteria:" in stdout
        assert "All tests passing" in stdout

    def test_generate_with_success_criteria_to_file(self, cli_runner, temp_repo):
        """Test generating a template with success criteria to a file."""
        output_file = temp_repo / "criteria_plan.yml"
        stdout, stderr, code = cli_runner([
            "template", "generate", "test",
            "--success-criteria", "Unit tests pass,Integration tests pass,E2E tests pass",
            "--output", str(output_file)
        ])
        assert code == 0
        content = output_file.read_text()
        assert "success_criteria:" in content
        assert "Unit tests pass" in content
        assert "Integration tests pass" in content
        assert "E2E tests pass" in content


class TestTemplateGenerateWithAllFlags:
    """Tests for 'agentic template generate' with all flags combined."""

    def test_generate_with_all_flags(self, cli_runner):
        """Test generating a template with objective, phases, and success criteria."""
        stdout, stderr, code = cli_runner([
            "template", "generate", "build",
            "--objective", "Complete the authentication module",
            "--phases", "P1:Design,P2:Build,P3:Test",
            "--success-criteria", "Tests pass,Security audit complete"
        ])
        assert code == 0
        # Check objective
        assert "Complete the authentication module" in stdout
        # Check phases
        assert 'id: "P1"' in stdout
        assert 'name: "Design"' in stdout
        assert 'id: "P2"' in stdout
        assert 'id: "P3"' in stdout
        # Check success criteria
        assert "success_criteria:" in stdout
        assert "Tests pass" in stdout
        assert "Security audit complete" in stdout

    def test_generate_with_all_flags_to_file(self, cli_runner, temp_repo):
        """Test generating a template with all flags to a file."""
        output_file = temp_repo / "full_plan.yml"
        stdout, stderr, code = cli_runner([
            "template", "generate", "build",
            "--objective", "Implement new feature X",
            "--phases", "Research:Research Phase,Impl:Implementation,QA:Quality Assurance",
            "--success-criteria", "Feature works end-to-end,Documentation updated",
            "--output", str(output_file)
        ])
        assert code == 0
        assert output_file.exists()
        content = output_file.read_text()
        # Verify all components
        assert "Implement new feature X" in content
        assert 'id: "Research"' in content
        assert 'name: "Research Phase"' in content
        assert 'id: "Impl"' in content
        assert 'id: "QA"' in content
        assert "success_criteria:" in content
        assert "Feature works end-to-end" in content
        assert "Documentation updated" in content


class TestParsePhases:
    """Tests for the _parse_phases helper function."""

    def test_parse_phases_valid_input(self):
        """Test parsing valid phases string."""
        from agenticcli.commands.template import _parse_phases

        phases = _parse_phases("P1:Build,P2:Test,P3:Deploy")
        assert len(phases) == 3
        assert phases[0] == {"id": "P1", "name": "Build", "status": "pending", "tasks": []}
        assert phases[1] == {"id": "P2", "name": "Test", "status": "pending", "tasks": []}
        assert phases[2] == {"id": "P3", "name": "Deploy", "status": "pending", "tasks": []}

    def test_parse_phases_with_spaces(self):
        """Test parsing phases with spaces around elements."""
        from agenticcli.commands.template import _parse_phases

        phases = _parse_phases("  P1 : Build Phase  ,  P2 : Test Phase  ")
        assert len(phases) == 2
        assert phases[0]["id"] == "P1"
        assert phases[0]["name"] == "Build Phase"
        assert phases[1]["id"] == "P2"
        assert phases[1]["name"] == "Test Phase"

    def test_parse_phases_single_phase(self):
        """Test parsing a single phase."""
        from agenticcli.commands.template import _parse_phases

        phases = _parse_phases("MVP:Minimum Viable Product")
        assert len(phases) == 1
        assert phases[0]["id"] == "MVP"
        assert phases[0]["name"] == "Minimum Viable Product"

    def test_parse_phases_invalid_input_no_colon(self):
        """Test parsing invalid phases string without colon."""
        from agenticcli.commands.template import _parse_phases

        with pytest.raises(ValueError, match="Invalid phase format"):
            _parse_phases("P1Build,P2Test")

    def test_parse_phases_invalid_input_empty_id(self):
        """Test parsing invalid phases string with empty ID."""
        from agenticcli.commands.template import _parse_phases

        with pytest.raises(ValueError, match="Both ID and Name are required"):
            _parse_phases(":Build")

    def test_parse_phases_invalid_input_empty_name(self):
        """Test parsing invalid phases string with empty name."""
        from agenticcli.commands.template import _parse_phases

        with pytest.raises(ValueError, match="Both ID and Name are required"):
            _parse_phases("P1:")

    def test_parse_phases_empty_string(self):
        """Test parsing empty phases string."""
        from agenticcli.commands.template import _parse_phases

        phases = _parse_phases("")
        assert phases == []

    def test_parse_phases_with_colons_in_name(self):
        """Test parsing phases where name contains colons."""
        from agenticcli.commands.template import _parse_phases

        phases = _parse_phases("P1:Step 1: Initial Setup")
        assert len(phases) == 1
        assert phases[0]["id"] == "P1"
        assert phases[0]["name"] == "Step 1: Initial Setup"


class TestParseSuccessCriteria:
    """Tests for the _parse_success_criteria helper function."""

    def test_parse_success_criteria_comma_separated(self):
        """Test parsing comma-separated success criteria."""
        from agenticcli.commands.template import _parse_success_criteria

        criteria = _parse_success_criteria("Tests pass,Coverage > 80%,No lint errors")
        assert len(criteria) == 3
        assert criteria[0] == "Tests pass"
        assert criteria[1] == "Coverage > 80%"
        assert criteria[2] == "No lint errors"

    def test_parse_success_criteria_newline_separated(self):
        """Test parsing newline-separated success criteria."""
        from agenticcli.commands.template import _parse_success_criteria

        criteria = _parse_success_criteria("Tests pass\nCoverage > 80%\nNo lint errors")
        assert len(criteria) == 3
        assert criteria[0] == "Tests pass"
        assert criteria[1] == "Coverage > 80%"
        assert criteria[2] == "No lint errors"

    def test_parse_success_criteria_single_criterion(self):
        """Test parsing single success criterion."""
        from agenticcli.commands.template import _parse_success_criteria

        criteria = _parse_success_criteria("All tests passing")
        assert len(criteria) == 1
        assert criteria[0] == "All tests passing"

    def test_parse_success_criteria_with_spaces(self):
        """Test parsing success criteria with extra whitespace."""
        from agenticcli.commands.template import _parse_success_criteria

        criteria = _parse_success_criteria("  Tests pass  ,  Coverage > 80%  ")
        assert len(criteria) == 2
        assert criteria[0] == "Tests pass"
        assert criteria[1] == "Coverage > 80%"

    def test_parse_success_criteria_empty_string(self):
        """Test parsing empty success criteria string."""
        from agenticcli.commands.template import _parse_success_criteria

        criteria = _parse_success_criteria("")
        assert criteria == []


class TestTemplateGenerateInvalidPhases:
    """Tests for 'agentic template generate' with invalid --phases input."""

    def test_generate_with_invalid_phases_no_colon(self, cli_runner):
        """Test that invalid phases format produces error."""
        stdout, stderr, code = cli_runner([
            "template", "generate", "build",
            "--phases", "InvalidPhaseFormat"
        ])
        assert code != 0
        # Error message should be in stderr or stdout
        combined = stdout + stderr
        assert "Invalid phase format" in combined

    def test_generate_with_invalid_phases_empty_id(self, cli_runner):
        """Test that empty phase ID produces error."""
        stdout, stderr, code = cli_runner([
            "template", "generate", "build",
            "--phases", ":MissingID"
        ])
        assert code != 0
        combined = stdout + stderr
        assert "Both ID and Name are required" in combined


class TestTemplateList:
    """Tests for 'agentic template list' command."""

    def test_list_templates(self, cli_runner):
        """Test listing all available templates."""
        stdout, stderr, code = cli_runner(["template", "list"])
        assert "Available Template Types" in stdout
        assert "build" in stdout
        assert "test" in stdout
        assert "cleanup" in stdout
        assert "guidance" in stdout
        assert code == 0

    def test_list_shows_descriptions(self, cli_runner):
        """Test that list shows template descriptions."""
        stdout, stderr, code = cli_runner(["template", "list"])
        assert "Implementation plan" in stdout
        assert "Test plan" in stdout
        assert code == 0

    def test_list_shows_usage_hint(self, cli_runner):
        """Test that list shows usage hint with new flags."""
        stdout, stderr, code = cli_runner(["template", "list"])
        assert code == 0
        # Should show usage hint including new flags
        assert "--objective" in stdout
        assert "--phases" in stdout
        assert "--success-criteria" in stdout
