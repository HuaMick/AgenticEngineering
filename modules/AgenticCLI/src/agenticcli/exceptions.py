"""Custom exceptions for AgenticCLI.

This module provides a unified exception hierarchy for the CLI,
enabling consistent error handling with recovery suggestions.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ErrorContext:
    """Context information for errors."""

    file_path: Optional[str] = None
    line_number: Optional[int] = None
    command: Optional[str] = None
    operation: Optional[str] = None
    details: dict = field(default_factory=dict)


class AgenticError(Exception):
    """Base exception for all AgenticCLI errors.

    Attributes:
        message: Human-readable error message
        recovery_hint: Suggested action to resolve the error
        context: Additional context about the error
        exit_code: Suggested exit code for CLI
    """

    default_exit_code: int = 1

    def __init__(
        self,
        message: str,
        recovery_hint: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        exit_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.message = message
        self.recovery_hint = recovery_hint
        self.context = context or ErrorContext()
        self.exit_code = exit_code or self.default_exit_code

    def to_dict(self) -> dict:
        """Convert exception to dictionary for JSON output."""
        result = {
            "error": self.__class__.__name__,
            "message": self.message,
            "exit_code": self.exit_code,
        }
        if self.recovery_hint:
            result["recovery_hint"] = self.recovery_hint
        if self.context.file_path:
            result["file_path"] = self.context.file_path
        if self.context.line_number:
            result["line_number"] = self.context.line_number
        if self.context.command:
            result["command"] = self.context.command
        if self.context.operation:
            result["operation"] = self.context.operation
        if self.context.details:
            result["details"] = self.context.details
        return result

    def __str__(self) -> str:
        parts = [self.message]
        if self.recovery_hint:
            parts.append(f"\nHint: {self.recovery_hint}")
        return "".join(parts)


class PlanError(AgenticError):
    """Errors related to plan file operations."""

    default_exit_code: int = 20

    @classmethod
    def not_found(cls, path: str) -> "PlanError":
        """Create error for missing plan file."""
        return cls(
            message=f"Plan file not found: {path}",
            recovery_hint="Create a plan with 'agentic plan scaffold' or check the file path",
            context=ErrorContext(file_path=path, operation="plan_read"),
        )

    @classmethod
    def invalid_yaml(cls, path: str, error: str, line: Optional[int] = None) -> "PlanError":
        """Create error for invalid YAML in plan file."""
        return cls(
            message=f"Invalid YAML in plan file: {error}",
            recovery_hint="Check the YAML syntax at the indicated location",
            context=ErrorContext(
                file_path=path,
                line_number=line,
                operation="plan_parse",
                details={"parse_error": error},
            ),
        )

    @classmethod
    def invalid_structure(cls, path: str, missing_field: str) -> "PlanError":
        """Create error for invalid plan structure."""
        return cls(
            message=f"Invalid plan structure: missing required field '{missing_field}'",
            recovery_hint=f"Add the '{missing_field}' field to your plan file",
            context=ErrorContext(
                file_path=path,
                operation="plan_validate",
                details={"missing_field": missing_field},
            ),
        )

    @classmethod
    def task_not_found(cls, task_id: str, plan_path: str) -> "PlanError":
        """Create error for missing task in plan."""
        return cls(
            message=f"Task '{task_id}' not found in plan",
            recovery_hint="Check the task ID or list tasks with 'agentic plan status'",
            context=ErrorContext(
                file_path=plan_path,
                operation="plan_task",
                details={"task_id": task_id},
            ),
        )


class EpicFileError(AgenticError):
    """Errors related to epic file operations."""

    default_exit_code: int = 20

    @classmethod
    def not_found(cls, path: str) -> "EpicFileError":
        """Create error for missing epic file."""
        return cls(
            message=f"Epic file not found: {path}",
            recovery_hint="Create an epic with 'agentic epic scaffold' or check the file path",
            context=ErrorContext(file_path=path, operation="epic_read"),
        )

    @classmethod
    def invalid_yaml(cls, path: str, error: str, line: Optional[int] = None) -> "EpicFileError":
        """Create error for invalid YAML in epic file."""
        return cls(
            message=f"Invalid YAML in epic file: {error}",
            recovery_hint="Check the YAML syntax at the indicated location",
            context=ErrorContext(
                file_path=path,
                line_number=line,
                operation="epic_parse",
                details={"parse_error": error},
            ),
        )

    @classmethod
    def invalid_structure(cls, path: str, missing_field: str) -> "EpicFileError":
        """Create error for invalid epic structure."""
        return cls(
            message=f"Invalid epic structure: missing required field '{missing_field}'",
            recovery_hint=f"Add the '{missing_field}' field to your epic file",
            context=ErrorContext(
                file_path=path,
                operation="epic_validate",
                details={"missing_field": missing_field},
            ),
        )

    @classmethod
    def ticket_not_found(cls, ticket_id: str, epic_path: str) -> "EpicFileError":
        """Create error for missing ticket in epic."""
        return cls(
            message=f"Ticket '{ticket_id}' not found in epic",
            recovery_hint="Check the ticket ID or list tickets with 'agentic epic status'",
            context=ErrorContext(
                file_path=epic_path,
                operation="epic_ticket",
                details={"ticket_id": ticket_id},
            ),
        )


# Backward compatibility alias
PlanFileError = EpicFileError


class EpicFolderError(AgenticError):
    """Errors related to epic folder operations."""

    default_exit_code: int = 20

    @classmethod
    def not_found(cls, path: str) -> "EpicFolderError":
        """Create error for missing epic folder."""
        return cls(
            message=f"Epic folder not found: {path}",
            recovery_hint="Create an epic folder with 'agentic epic scaffold' or check the path",
            context=ErrorContext(file_path=path, operation="epic_folder_read"),
        )

    @classmethod
    def invalid_structure(cls, path: str, reason: str) -> "EpicFolderError":
        """Create error for invalid epic folder structure."""
        return cls(
            message=f"Invalid epic folder structure: {reason}",
            recovery_hint="Use 'agentic epic scaffold' to create a valid epic folder structure",
            context=ErrorContext(
                file_path=path,
                operation="epic_folder_validate",
                details={"reason": reason},
            ),
        )


# Backward compatibility alias
PlanFolderError = EpicFolderError


class ConfigError(AgenticError):
    """Errors related to configuration operations."""

    default_exit_code: int = 30

    @classmethod
    def key_not_found(cls, key: str) -> "ConfigError":
        """Create error for missing config key."""
        return cls(
            message=f"Configuration key not found: {key}",
            recovery_hint=f"Set the key with 'agentic config set {key} <value>' or list available keys",
            context=ErrorContext(operation="config_get", details={"key": key}),
        )

    @classmethod
    def invalid_value(cls, key: str, value: str, expected: str) -> "ConfigError":
        """Create error for invalid config value."""
        return cls(
            message=f"Invalid value for '{key}': {value}",
            recovery_hint=f"Expected {expected}",
            context=ErrorContext(
                operation="config_set",
                details={"key": key, "value": value, "expected": expected},
            ),
        )

    @classmethod
    def file_not_found(cls, path: str) -> "ConfigError":
        """Create error for missing config file."""
        return cls(
            message=f"Configuration file not found: {path}",
            recovery_hint="Initialize configuration with 'agentic config init'",
            context=ErrorContext(file_path=path, operation="config_load"),
        )


class ValidationError(AgenticError):
    """Errors related to input validation."""

    default_exit_code: int = 40

    @classmethod
    def invalid_branch_name(cls, name: str, reason: str) -> "ValidationError":
        """Create error for invalid branch name."""
        return cls(
            message=f"Invalid branch name '{name}': {reason}",
            recovery_hint="Use alphanumeric characters, hyphens, underscores, and slashes only",
            context=ErrorContext(operation="validate_branch", details={"branch": name, "reason": reason}),
        )

    @classmethod
    def invalid_epic_folder(cls, path: str, reason: str) -> "ValidationError":
        """Create error for invalid epic folder structure."""
        return cls(
            message=f"Invalid epic folder structure: {reason}",
            recovery_hint="Use 'agentic epic scaffold' to create a valid epic folder structure",
            context=ErrorContext(file_path=path, operation="validate_epic_folder", details={"reason": reason}),
        )

    @classmethod
    def invalid_plan_folder(cls, path: str, reason: str) -> "ValidationError":
        """Create error for invalid plan folder structure.

        Deprecated: use invalid_epic_folder instead.
        """
        return cls.invalid_epic_folder(path, reason)

    @classmethod
    def schema_violation(cls, path: str, violations: list) -> "ValidationError":
        """Create error for YAML schema violations."""
        violations_str = "; ".join(violations[:3])
        if len(violations) > 3:
            violations_str += f" (and {len(violations) - 3} more)"
        return cls(
            message=f"Schema validation failed: {violations_str}",
            recovery_hint="Check the epic file format against the schema requirements",
            context=ErrorContext(
                file_path=path,
                operation="validate_schema",
                details={"violations": violations},
            ),
        )


class EnvironmentError(AgenticError):
    """Errors related to environment variable operations."""

    default_exit_code: int = 50

    @classmethod
    def missing_required(cls, var_name: str) -> "EnvironmentError":
        """Create error for missing required environment variable."""
        return cls(
            message=f"Required environment variable not set: {var_name}",
            recovery_hint=f"Set the variable with 'export {var_name}=<value>' or configure in preferences",
            context=ErrorContext(operation="env_get", details={"variable": var_name}),
        )

    @classmethod
    def subprocess_failed(cls, command: str, exit_code: int, stderr: str) -> "EnvironmentError":
        """Create error for failed subprocess execution."""
        return cls(
            message=f"Command failed with exit code {exit_code}",
            recovery_hint="Check the command output for details",
            context=ErrorContext(
                operation="env_run",
                details={"command": command, "exit_code": exit_code, "stderr": stderr[:500]},
            ),
            exit_code=exit_code,
        )


class TemplateError(AgenticError):
    """Errors related to template operations."""

    default_exit_code: int = 60

    @classmethod
    def not_found(cls, template_name: str) -> "TemplateError":
        """Create error for missing template."""
        return cls(
            message=f"Template not found: {template_name}",
            recovery_hint="List available templates with 'agentic template list'",
            context=ErrorContext(operation="template_render", details={"template": template_name}),
        )

    @classmethod
    def render_failed(cls, template_name: str, error: str) -> "TemplateError":
        """Create error for template rendering failure."""
        return cls(
            message=f"Failed to render template '{template_name}': {error}",
            recovery_hint="Check the template syntax and context variables",
            context=ErrorContext(
                operation="template_render",
                details={"template": template_name, "error": error},
            ),
        )


# Mapping of exception types to their exit codes for reference
EXIT_CODES = {
    "AgenticError": 1,
    "EpicFileError": 20,
    "EpicFolderError": 20,
    "PlanFileError": 20,
    "PlanFolderError": 20,
    "PlanError": 20,
    "ConfigError": 30,
    "ValidationError": 40,
    "EnvironmentError": 50,
    "TemplateError": 60,
}
