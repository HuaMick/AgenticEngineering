"""Tests for template commands."""


class TestTemplateGenerate:
    """Tests for 'agentic template generate' command."""

    def test_generate_build_template(self, cli_runner):
        """Test generating a build template."""
        # cli_runner already runs in a git repo (temp_repo)
        stdout, stderr, code = cli_runner(["template", "generate", "build"])
        # Works with both Jinja2 ("# Build Plan") and simple ("# Implementation Plan") templates
        assert "Plan" in stdout
        assert "status: pending" in stdout
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
        assert "status: pending" in content
        assert code == 0


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
