"""Tests for custom exceptions."""


from agenticcli.exceptions import (
    AgenticError,
    ConfigError,
    EnvironmentError,
    ErrorContext,
    PlanError,
    TemplateError,
    ValidationError,
    WorktreeError,
)


class TestErrorContext:
    """Tests for ErrorContext dataclass."""

    def test_default_context(self):
        """Test default context has None values."""
        ctx = ErrorContext()
        assert ctx.file_path is None
        assert ctx.line_number is None
        assert ctx.command is None
        assert ctx.operation is None
        assert ctx.details == {}

    def test_context_with_values(self):
        """Test context with provided values."""
        ctx = ErrorContext(
            file_path="/path/to/file",
            line_number=42,
            command="worktree create",
            operation="git_branch",
            details={"branch": "feature-x"},
        )
        assert ctx.file_path == "/path/to/file"
        assert ctx.line_number == 42
        assert ctx.command == "worktree create"
        assert ctx.operation == "git_branch"
        assert ctx.details == {"branch": "feature-x"}


class TestAgenticError:
    """Tests for base AgenticError class."""

    def test_basic_error(self):
        """Test basic error creation."""
        err = AgenticError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"
        assert err.recovery_hint is None
        assert err.exit_code == 1

    def test_error_with_hint(self):
        """Test error with recovery hint."""
        err = AgenticError("Failed", recovery_hint="Try again")
        assert "Try again" in str(err)
        assert err.recovery_hint == "Try again"

    def test_error_with_context(self):
        """Test error with context."""
        ctx = ErrorContext(file_path="/test", operation="test_op")
        err = AgenticError("Error", context=ctx)
        assert err.context.file_path == "/test"
        assert err.context.operation == "test_op"

    def test_error_to_dict(self):
        """Test error to dictionary conversion."""
        ctx = ErrorContext(
            file_path="/path/file.yml",
            line_number=10,
            command="test",
            operation="parse",
            details={"key": "value"},
        )
        err = AgenticError(
            "Parse failed",
            recovery_hint="Check syntax",
            context=ctx,
            exit_code=5,
        )
        data = err.to_dict()

        assert data["error"] == "AgenticError"
        assert data["message"] == "Parse failed"
        assert data["recovery_hint"] == "Check syntax"
        assert data["exit_code"] == 5
        assert data["file_path"] == "/path/file.yml"
        assert data["line_number"] == 10
        assert data["command"] == "test"
        assert data["operation"] == "parse"
        assert data["details"] == {"key": "value"}

    def test_error_to_dict_minimal(self):
        """Test minimal error to dictionary."""
        err = AgenticError("Simple error")
        data = err.to_dict()

        assert data["error"] == "AgenticError"
        assert data["message"] == "Simple error"
        assert "recovery_hint" not in data
        assert "file_path" not in data


class TestWorktreeError:
    """Tests for WorktreeError class."""

    def test_default_exit_code(self):
        """Test default exit code is 10."""
        err = WorktreeError("Worktree error")
        assert err.exit_code == 10

    def test_branch_exists(self):
        """Test branch_exists factory method."""
        err = WorktreeError.branch_exists("feature-x")
        assert "feature-x" in err.message
        assert "already exists" in err.message
        assert "git branch -d" in err.recovery_hint
        assert err.context.operation == "worktree_create"
        assert err.context.details["branch"] == "feature-x"

    def test_worktree_exists(self):
        """Test worktree_exists factory method."""
        err = WorktreeError.worktree_exists("/path/to/worktree")
        assert "/path/to/worktree" in err.message
        assert "Remove" in err.recovery_hint

    def test_not_in_repo(self):
        """Test not_in_repo factory method."""
        err = WorktreeError.not_in_repo()
        assert "Not in a git repository" in err.message
        assert "git init" in err.recovery_hint

    def test_invalid_base_branch(self):
        """Test invalid_base_branch factory method."""
        err = WorktreeError.invalid_base_branch("nonexistent")
        assert "nonexistent" in err.message
        assert "--base" in err.recovery_hint


class TestPlanError:
    """Tests for PlanError class."""

    def test_default_exit_code(self):
        """Test default exit code is 20."""
        err = PlanError("Plan error")
        assert err.exit_code == 20

    def test_not_found(self):
        """Test not_found factory method."""
        err = PlanError.not_found("/path/plan.yml")
        assert "/path/plan.yml" in err.message
        assert "plan scaffold" in err.recovery_hint
        assert err.context.file_path == "/path/plan.yml"

    def test_invalid_yaml(self):
        """Test invalid_yaml factory method."""
        err = PlanError.invalid_yaml("/plan.yml", "unexpected key", line=15)
        assert "Invalid YAML" in err.message
        assert err.context.line_number == 15
        assert err.context.details["parse_error"] == "unexpected key"

    def test_invalid_structure(self):
        """Test invalid_structure factory method."""
        err = PlanError.invalid_structure("/plan.yml", "phases")
        assert "phases" in err.message
        assert "phases" in err.recovery_hint

    def test_task_not_found(self):
        """Test task_not_found factory method."""
        err = PlanError.task_not_found("task-01", "/plan.yml")
        assert "task-01" in err.message
        assert "plan status" in err.recovery_hint


class TestConfigError:
    """Tests for ConfigError class."""

    def test_default_exit_code(self):
        """Test default exit code is 30."""
        err = ConfigError("Config error")
        assert err.exit_code == 30

    def test_key_not_found(self):
        """Test key_not_found factory method."""
        err = ConfigError.key_not_found("my.setting")
        assert "my.setting" in err.message
        assert "config set my.setting" in err.recovery_hint

    def test_invalid_value(self):
        """Test invalid_value factory method."""
        err = ConfigError.invalid_value("count", "abc", "integer")
        assert "abc" in err.message
        assert "integer" in err.recovery_hint

    def test_file_not_found(self):
        """Test file_not_found factory method."""
        err = ConfigError.file_not_found("/config.yml")
        assert "/config.yml" in err.message
        assert "config init" in err.recovery_hint


class TestValidationError:
    """Tests for ValidationError class."""

    def test_default_exit_code(self):
        """Test default exit code is 40."""
        err = ValidationError("Validation error")
        assert err.exit_code == 40

    def test_invalid_branch_name(self):
        """Test invalid_branch_name factory method."""
        err = ValidationError.invalid_branch_name("bad..name", "consecutive dots")
        assert "bad..name" in err.message
        assert "consecutive dots" in err.message
        assert "alphanumeric" in err.recovery_hint

    def test_invalid_plan_folder(self):
        """Test invalid_plan_folder factory method."""
        err = ValidationError.invalid_plan_folder("/plans/bad", "missing live directory")
        assert "missing live directory" in err.message
        assert "plan scaffold" in err.recovery_hint

    def test_schema_violation(self):
        """Test schema_violation factory method."""
        violations = ["missing 'name'", "invalid 'status'", "extra field 'foo'", "another"]
        err = ValidationError.schema_violation("/plan.yml", violations)
        assert "missing 'name'" in err.message
        assert "and 1 more" in err.message
        assert err.context.details["violations"] == violations


class TestEnvironmentError:
    """Tests for EnvironmentError class."""

    def test_default_exit_code(self):
        """Test default exit code is 50."""
        err = EnvironmentError("Env error")
        assert err.exit_code == 50

    def test_missing_required(self):
        """Test missing_required factory method."""
        err = EnvironmentError.missing_required("API_KEY")
        assert "API_KEY" in err.message
        assert "export API_KEY" in err.recovery_hint

    def test_subprocess_failed(self):
        """Test subprocess_failed factory method."""
        err = EnvironmentError.subprocess_failed("npm test", 1, "Error output")
        assert "exit code 1" in err.message
        assert err.exit_code == 1
        assert err.context.details["stderr"] == "Error output"


class TestTemplateError:
    """Tests for TemplateError class."""

    def test_default_exit_code(self):
        """Test default exit code is 60."""
        err = TemplateError("Template error")
        assert err.exit_code == 60

    def test_not_found(self):
        """Test not_found factory method."""
        err = TemplateError.not_found("custom_plan")
        assert "custom_plan" in err.message
        assert "template list" in err.recovery_hint

    def test_render_failed(self):
        """Test render_failed factory method."""
        err = TemplateError.render_failed("build.j2", "undefined variable 'name'")
        assert "build.j2" in err.message
        assert "undefined variable" in err.message
