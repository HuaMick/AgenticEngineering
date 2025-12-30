"""Unit tests for HelpWorkflow.

Tests the help, version, and documentation display workflow functionality.
Following the Domain → Workflow → Entrypoint pattern.
"""

import pytest
from myagents.backend.services.agents.workflows.help_workflow import HelpWorkflow


@pytest.fixture
def workflow():
    """Create a HelpWorkflow instance for testing."""
    return HelpWorkflow()


@pytest.mark.workflow_help
class TestShowVersion:
    """Test show_version() method."""

    def test_show_version_format(self, workflow):
        """Test version string format."""
        result = workflow.show_version()

        assert isinstance(result, str)
        assert "myagents" in result.lower()

    def test_show_version_includes_number_or_development(self, workflow):
        """Test version includes version number or development marker."""
        result = workflow.show_version()

        # Should be either "myagents X.Y.Z" or "myagents (development version)"
        assert "myagents" in result and (
            "development" in result or any(char.isdigit() for char in result)
        )


@pytest.mark.workflow_help
class TestShowMainHelp:
    """Test show_main_help() method."""

    def test_show_main_help_returns_string(self, workflow):
        """Test main help returns string."""
        result = workflow.show_main_help()

        assert isinstance(result, str)
        assert len(result) > 0

    def test_show_main_help_includes_commands(self, workflow):
        """Test main help includes command list."""
        result = workflow.show_main_help()

        # Check for key commands
        assert "chat" in result.lower()
        assert "studio" in result.lower()
        assert "preferences" in result.lower()
        assert "update" in result.lower()
        assert "rebuild" in result.lower()

    def test_show_main_help_includes_usage(self, workflow):
        """Test main help includes usage section."""
        result = workflow.show_main_help()

        assert "usage:" in result.lower() or "myagents [command]" in result.lower()

    def test_show_main_help_includes_options(self, workflow):
        """Test main help includes options section."""
        result = workflow.show_main_help()

        assert "--help" in result or "-h" in result
        assert "--version" in result or "-v" in result

    def test_show_main_help_includes_examples(self, workflow):
        """Test main help includes examples section."""
        result = workflow.show_main_help()

        assert "example" in result.lower()


@pytest.mark.workflow_help
class TestShowCommandHelp:
    """Test show_command_help() method."""

    @pytest.mark.parametrize("command,expected_keywords", [
        ("chat", ["chat", "agent"]),
        ("studio", ["studio", "start", "stop", "status"]),
        ("preferences", ["preference", "get", "set", "list"]),
        ("config", ["config", "init"]),
        ("secrets", ["secret", "get"]),
        ("update", ["update"]),
        ("rebuild", ["rebuild", "build"]),
    ])
    def test_show_command_help(self, workflow, command, expected_keywords):
        """Test help for commands returns expected keywords."""
        result = workflow.show_command_help(command)

        assert isinstance(result, str)
        for keyword in expected_keywords:
            assert keyword in result.lower(), f"Expected '{keyword}' in help for {command}"

    def test_show_command_help_update_includes_install(self, workflow):
        """Test update command help includes install/reinstall."""
        result = workflow.show_command_help("update")
        assert "reinstall" in result.lower() or "install" in result.lower()

    def test_show_command_help_unknown(self, workflow):
        """Test help for unknown command."""
        result = workflow.show_command_help("unknown_command")

        assert isinstance(result, str)
        assert "no help available" in result.lower()


@pytest.mark.workflow_help
class TestShowWorkflowDocs:
    """Test show_workflow_docs() method."""

    def test_show_workflow_docs_health_check(self, workflow):
        """Test workflow documentation for health_check."""
        result = workflow.show_workflow_docs("health_check")

        assert isinstance(result, str)
        assert "health check" in result.lower()
        assert "workflow" in result.lower()

    def test_show_workflow_docs_studio(self, workflow):
        """Test workflow documentation for studio."""
        result = workflow.show_workflow_docs("studio")

        assert isinstance(result, str)
        assert "studio" in result.lower()
        assert "workflow" in result.lower()

    def test_show_workflow_docs_preferences(self, workflow):
        """Test workflow documentation for preferences."""
        result = workflow.show_workflow_docs("preferences")

        assert isinstance(result, str)
        assert "preference" in result.lower()
        assert "workflow" in result.lower()

    def test_show_workflow_docs_help(self, workflow):
        """Test workflow documentation for help."""
        result = workflow.show_workflow_docs("help")

        assert isinstance(result, str)
        assert "help" in result.lower()
        assert "workflow" in result.lower()

    def test_show_workflow_docs_unknown(self, workflow):
        """Test workflow documentation for unknown workflow."""
        result = workflow.show_workflow_docs("unknown_workflow")

        assert isinstance(result, str)
        assert "no documentation available" in result.lower()


@pytest.mark.workflow_help
class TestGenerateUsageExamples:
    """Test generate_usage_examples() method."""

    def test_generate_usage_examples_all(self, workflow):
        """Test generating all usage examples."""
        result = workflow.generate_usage_examples()

        assert isinstance(result, list)
        assert len(result) > 0
        # Check that examples exist for various commands
        examples_text = " ".join(result)
        assert "chat" in examples_text.lower()
        assert "studio" in examples_text.lower()
        assert "preferences" in examples_text.lower()

    @pytest.mark.parametrize("command,expected_keywords", [
        ("chat", ["chat"]),
        ("studio", ["studio", "start", "stop"]),
        ("preferences", ["preferences", "set", "get"]),
        ("config", ["config"]),
        ("secrets", ["secrets"]),
        ("update", ["update"]),
        ("rebuild", ["rebuild"]),
    ])
    def test_generate_usage_examples_for_command(self, workflow, command, expected_keywords):
        """Test generating examples for specific commands."""
        result = workflow.generate_usage_examples(command=command)

        assert isinstance(result, list)
        assert len(result) > 0
        for keyword in expected_keywords:
            has_kw = any(keyword in example.lower() for example in result)
            assert has_kw, f"Expected '{keyword}' in examples for {command}"

    def test_generate_usage_examples_unknown_command(self, workflow):
        """Test generating examples for unknown command."""
        result = workflow.generate_usage_examples(command="unknown_command")

        assert isinstance(result, list)
        assert len(result) > 0
        # Should return a message about no examples available or fallback examples
        result_text = " ".join(result).lower()
        assert any(phrase in result_text for phrase in [
            "no example", "not available", "unknown", "no specific",
            "general", "myagents"  # fallback to general examples
        ]), f"Expected fallback message or general examples for unknown command but got: {result}"


@pytest.mark.workflow_help
class TestHelpWorkflowIntegration:
    """Test HelpWorkflow integration scenarios."""

    def test_all_commands_have_help(self, workflow):
        """Test that all commands have help text."""
        commands = ["chat", "studio", "preferences", "config", "secrets", "update", "rebuild"]

        for command in commands:
            help_text = workflow.show_command_help(command)
            assert len(help_text) > 0
            assert command in help_text.lower()

    def test_all_commands_have_examples(self, workflow):
        """Test that all commands have usage examples."""
        commands = ["chat", "studio", "preferences", "config", "secrets", "update", "rebuild"]

        for command in commands:
            examples = workflow.generate_usage_examples(command=command)
            assert len(examples) > 0

    def test_workflow_docs_for_all_workflows(self, workflow):
        """Test that all workflows have documentation."""
        workflows = ["health_check", "studio", "preferences", "help"]

        for wf in workflows:
            docs = workflow.show_workflow_docs(wf)
            assert len(docs) > 0
            assert "workflow" in docs.lower()


@pytest.mark.workflow_help
class TestHelpWorkflowInitialization:
    """Test HelpWorkflow initialization."""

    def test_workflow_init(self):
        """Test workflow initialization."""
        workflow = HelpWorkflow()

        assert workflow is not None
        assert isinstance(workflow, HelpWorkflow)

    def test_workflow_methods_callable(self, workflow):
        """Test that all workflow methods are callable."""
        assert callable(workflow.show_version)
        assert callable(workflow.show_main_help)
        assert callable(workflow.show_command_help)
        assert callable(workflow.show_workflow_docs)
        assert callable(workflow.generate_usage_examples)
