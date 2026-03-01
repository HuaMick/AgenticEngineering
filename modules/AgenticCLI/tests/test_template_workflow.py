"""Tests for Jinja2 template workflow."""



class TestTemplateContext:
    """Tests for TemplateContext dataclass."""

    def test_default_context(self):
        """Test default context has expected fields."""
        from agenticcli.workflows.template_workflow import TemplateContext

        ctx = TemplateContext()

        assert ctx.date is not None
        assert ctx.timestamp is not None
        assert ctx.year is not None
        assert ctx.iteration == 1

    def test_to_dict(self):
        """Test context to dictionary conversion."""
        from agenticcli.workflows.template_workflow import TemplateContext

        ctx = TemplateContext(
            project_name="TestProject",
            plan_name="test-plan",
            iteration=5,
        )

        data = ctx.to_dict()
        assert data["project_name"] == "TestProject"
        assert data["plan_name"] == "test-plan"
        assert data["iteration"] == 5

    def test_extra_vars(self):
        """Test extra variables are included."""
        from agenticcli.workflows.template_workflow import TemplateContext

        ctx = TemplateContext(extra={"custom_var": "custom_value"})
        data = ctx.to_dict()

        assert "custom_var" in data
        assert data["custom_var"] == "custom_value"


class TestTemplateWorkflow:
    """Tests for TemplateWorkflow class."""

    def test_list_templates(self):
        """Test listing available templates."""
        from agenticcli.workflows.template_workflow import TemplateWorkflow

        workflow = TemplateWorkflow()
        templates = workflow.list_templates()

        # Should find our Jinja2 templates
        names = [t["name"] for t in templates]
        assert "build_plan" in names
        assert "test_plan" in names

    def test_render_string(self):
        """Test rendering a template string."""
        from agenticcli.workflows.template_workflow import TemplateContext, TemplateWorkflow

        workflow = TemplateWorkflow(context=TemplateContext(plan_name="MyPlan"))
        result = workflow.render_string("Name: {{ plan_name }}")

        assert result == "Name: MyPlan"

    def test_render_with_context_override(self):
        """Test rendering with context override."""
        from agenticcli.workflows.template_workflow import TemplateContext, TemplateWorkflow

        workflow = TemplateWorkflow(context=TemplateContext(plan_name="Default"))
        result = workflow.render_string(
            "Name: {{ plan_name }}",
            context={"plan_name": "Override"},
        )

        assert result == "Name: Override"

    def test_render_build_template(self):
        """Test rendering the build_plan template."""
        from agenticcli.workflows.template_workflow import TemplateContext, TemplateWorkflow
        from pathlib import Path

        workflow = TemplateWorkflow(
            context=TemplateContext(
                plan_name="FeatureX",
                branch="feature-x",
                project_root=Path("/path/to/project"),
            )
        )
        result = workflow.render("build_plan.yml.j2")

        assert "FeatureX" in result
        assert "feature-x" in result
        assert "status: pending" in result

    def test_render_to_file(self, temp_dir):
        """Test rendering template to file."""
        from agenticcli.workflows.template_workflow import TemplateContext, TemplateWorkflow

        workflow = TemplateWorkflow(
            context=TemplateContext(plan_name="TestPlan")
        )

        output_path = temp_dir / "output.yml"
        workflow.render_to_file("build_plan.yml.j2", output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "TestPlan" in content


class TestTemplateFilters:
    """Tests for custom Jinja2 filters."""

    def test_snake_case_filter(self):
        """Test snake_case filter."""
        from agenticcli.workflows.template_workflow import TemplateWorkflow

        workflow = TemplateWorkflow()
        result = workflow.render_string("{{ 'HelloWorld' | snake_case }}")
        assert result == "hello_world"

    def test_camel_case_filter(self):
        """Test camel_case filter."""
        from agenticcli.workflows.template_workflow import TemplateWorkflow

        workflow = TemplateWorkflow()
        result = workflow.render_string("{{ 'hello_world' | camel_case }}")
        assert result == "HelloWorld"

    def test_kebab_case_filter(self):
        """Test kebab_case filter."""
        from agenticcli.workflows.template_workflow import TemplateWorkflow

        workflow = TemplateWorkflow()
        result = workflow.render_string("{{ 'HelloWorld' | kebab_case }}")
        assert result == "hello-world"

    def test_title_case_filter(self):
        """Test title_case filter."""
        from agenticcli.workflows.template_workflow import TemplateWorkflow

        workflow = TemplateWorkflow()
        result = workflow.render_string("{{ 'hello-world' | title_case }}")
        assert result == "Hello World"

    def test_yaml_list_filter(self):
        """Test yaml_list filter."""
        from agenticcli.workflows.template_workflow import TemplateWorkflow

        workflow = TemplateWorkflow()
        result = workflow.render_string(
            "{{ items | yaml_list }}",
            context={"items": ["a", "b", "c"]},
        )
        assert "- a" in result
        assert "- b" in result
        assert "- c" in result


class TestCreateContextFromCLI:
    """Tests for creating context from CLIContext."""

    def test_create_from_cli_context(self, cli_runner, temp_repo):
        """Test creating template context from CLI context."""
        from agenticcli.context import CLIContext
        from agenticcli.workflows.template_workflow import create_template_context_from_cli

        # cli_runner already sets up the git repo and changes to it
        ctx = CLIContext.discover()
        tpl_ctx = create_template_context_from_cli(ctx)

        # Project root should be discovered
        assert tpl_ctx.project_root is not None
        assert tpl_ctx.project_name != ""

    def test_create_from_none(self):
        """Test creating context with None CLI context."""
        from agenticcli.workflows.template_workflow import create_template_context_from_cli

        tpl_ctx = create_template_context_from_cli(None)

        # Should still have defaults
        assert tpl_ctx.date is not None
        assert tpl_ctx.iteration == 1
