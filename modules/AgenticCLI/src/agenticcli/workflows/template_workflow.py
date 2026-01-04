"""Template Workflow - Jinja2-based plan generation.

Provides flexible template rendering with custom filters and
context-aware variable injection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Default template directory
DEFAULT_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


@dataclass
class TemplateContext:
    """Context for template rendering."""

    # Basic info
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    year: str = field(default_factory=lambda: datetime.now().strftime("%Y"))

    # Project info
    project_name: str = ""
    project_root: Optional[Path] = None
    repo_abbreviation: str = "AE"
    branch: str = ""

    # Plan info
    plan_name: str = ""
    iteration: int = 1
    worktree: str = ""

    # Custom variables
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for template rendering."""
        result = {
            "date": self.date,
            "timestamp": self.timestamp,
            "year": self.year,
            "project_name": self.project_name,
            "project_root": str(self.project_root) if self.project_root else "",
            "repo_abbreviation": self.repo_abbreviation,
            "branch": self.branch,
            "plan_name": self.plan_name,
            "iteration": self.iteration,
            "worktree": self.worktree,
        }
        result.update(self.extra)
        return result


class TemplateWorkflow:
    """Workflow for rendering Jinja2 templates.

    Supports custom filters and template discovery from multiple directories.
    """

    def __init__(
        self,
        templates_dirs: Optional[list[Path]] = None,
        context: Optional[TemplateContext] = None,
    ):
        """Initialize template workflow.

        Args:
            templates_dirs: List of template directories (priority order).
            context: Default context for rendering.
        """
        self.templates_dirs = templates_dirs or [DEFAULT_TEMPLATES_DIR]
        self.context = context or TemplateContext()

        # Ensure directories exist
        self.templates_dirs = [d for d in self.templates_dirs if d.exists()]

        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader([str(d) for d in self.templates_dirs]),
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Register custom filters
        self._register_filters()

    def _register_filters(self) -> None:
        """Register custom Jinja2 filters."""
        self.env.filters["date_format"] = self._date_format
        self.env.filters["snake_case"] = self._snake_case
        self.env.filters["camel_case"] = self._camel_case
        self.env.filters["kebab_case"] = self._kebab_case
        self.env.filters["title_case"] = self._title_case
        self.env.filters["yaml_list"] = self._yaml_list
        self.env.filters["indent_yaml"] = self._indent_yaml

    @staticmethod
    def _date_format(value: str, format_str: str = "%Y-%m-%d") -> str:
        """Format a date string."""
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime(format_str)
        except (ValueError, TypeError):
            return value

    @staticmethod
    def _snake_case(value: str) -> str:
        """Convert to snake_case."""
        import re
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", value)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower().replace("-", "_")

    @staticmethod
    def _camel_case(value: str) -> str:
        """Convert to CamelCase."""
        words = value.replace("-", "_").split("_")
        return "".join(word.capitalize() for word in words)

    @staticmethod
    def _kebab_case(value: str) -> str:
        """Convert to kebab-case."""
        import re
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", value)
        return re.sub("([a-z0-9])([A-Z])", r"\1-\2", s1).lower().replace("_", "-")

    @staticmethod
    def _title_case(value: str) -> str:
        """Convert to Title Case."""
        return value.replace("-", " ").replace("_", " ").title()

    @staticmethod
    def _yaml_list(items: list, indent: int = 2) -> str:
        """Format a list as YAML."""
        prefix = " " * indent
        return "\n".join(f"{prefix}- {item}" for item in items)

    @staticmethod
    def _indent_yaml(value: str, spaces: int = 2) -> str:
        """Indent YAML content."""
        prefix = " " * spaces
        lines = value.split("\n")
        return "\n".join(prefix + line if line.strip() else line for line in lines)

    def list_templates(self) -> list[dict]:
        """List available templates.

        Returns:
            List of template info dicts with name, path, and description.
        """
        templates = []

        for templates_dir in self.templates_dirs:
            for template_path in templates_dir.glob("*.yml.j2"):
                name = template_path.stem.replace(".yml", "")
                templates.append({
                    "name": name,
                    "path": str(template_path),
                    "directory": str(templates_dir),
                })

            # Also check for .yaml.j2
            for template_path in templates_dir.glob("*.yaml.j2"):
                name = template_path.stem.replace(".yaml", "")
                templates.append({
                    "name": name,
                    "path": str(template_path),
                    "directory": str(templates_dir),
                })

        return templates

    def render(
        self,
        template_name: str,
        context: Optional[dict] = None,
    ) -> str:
        """Render a template with context.

        Args:
            template_name: Name of template file (e.g., "build_plan.yml.j2").
            context: Additional context to merge with defaults.

        Returns:
            Rendered template string.
        """
        # Merge contexts
        merged_context = self.context.to_dict()
        if context:
            merged_context.update(context)

        # Load and render template
        template = self.env.get_template(template_name)
        return template.render(**merged_context)

    def render_string(
        self,
        template_string: str,
        context: Optional[dict] = None,
    ) -> str:
        """Render a template string directly.

        Args:
            template_string: Jinja2 template as a string.
            context: Context for rendering.

        Returns:
            Rendered string.
        """
        merged_context = self.context.to_dict()
        if context:
            merged_context.update(context)

        template = self.env.from_string(template_string)
        return template.render(**merged_context)

    def render_to_file(
        self,
        template_name: str,
        output_path: Path,
        context: Optional[dict] = None,
    ) -> None:
        """Render a template and write to file.

        Args:
            template_name: Name of template file.
            output_path: Path to write output.
            context: Additional context.
        """
        content = self.render(template_name, context)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)


def create_template_context_from_cli(ctx) -> TemplateContext:
    """Create TemplateContext from CLIContext.

    Args:
        ctx: CLIContext instance.

    Returns:
        TemplateContext with project info filled in.
    """
    context = TemplateContext()

    if ctx and ctx.project_root:
        context.project_root = ctx.project_root
        context.project_name = ctx.project_root.name

        # Try to get branch name
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=ctx.project_root,
                capture_output=True,
                text=True,
                check=True,
            )
            context.branch = result.stdout.strip()
        except subprocess.CalledProcessError:
            pass

        # Try to get worktree path
        context.worktree = str(ctx.project_root)

    return context
