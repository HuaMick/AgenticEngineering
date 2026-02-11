"""Template workflow - re-exports from AgenticGuidance with CLI adapter."""

from pathlib import Path
from typing import Optional

from agenticguidance.services.template import TemplateContext
from agenticguidance.services.template import TemplateWorkflow as _BaseTemplateWorkflow
from agenticguidance.services.template import create_template_context_from_project

# CLI templates directory
_CLI_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class TemplateWorkflow(_BaseTemplateWorkflow):
    """CLI-adapted TemplateWorkflow that includes CLI templates directory."""

    def __init__(self, templates_dirs=None, context=None):
        if templates_dirs is None:
            templates_dirs = []
        if _CLI_TEMPLATES_DIR.exists() and _CLI_TEMPLATES_DIR not in templates_dirs:
            templates_dirs = [_CLI_TEMPLATES_DIR] + list(templates_dirs)
        super().__init__(templates_dirs=templates_dirs, context=context)


def create_template_context_from_cli(cli_context) -> TemplateContext:
    """Create TemplateContext from a CLIContext.

    Args:
        cli_context: A CLIContext instance (or None).

    Returns:
        TemplateContext with project info filled in from CLI context.
    """
    if cli_context is None:
        return TemplateContext()

    if cli_context.project_root:
        return create_template_context_from_project(cli_context.project_root)

    return TemplateContext()


__all__ = [
    "TemplateContext",
    "TemplateWorkflow",
    "create_template_context_from_cli",
    "create_template_context_from_project",
]
