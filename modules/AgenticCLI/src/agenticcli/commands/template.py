"""Template generation commands.

Generate plan files from templates.
"""

import sys
from datetime import datetime
from pathlib import Path


def handle(args, ctx=None):
    """Route template subcommands."""
    if args.template_command == "generate":
        cmd_generate(args)
    elif args.template_command == "list":
        cmd_list(args)
    else:
        print("Usage: agentic template <generate|list>", file=sys.stderr)
        sys.exit(1)


TEMPLATE_DESCRIPTIONS = {
    "build": "Implementation plan for building new features with phased tasks",
    "test": "Test plan with unit, integration, and e2e test phases",
    "cleanup": "Audit and cleanup plan for code review and documentation",
    "guidance": "Guidance improvement plan for agent friction analysis",
}

TEMPLATES = {
    "build": """# Implementation Plan
# Generated: {date}

plan:
  name: "Build Phase Implementation"
  worktree: "{worktree}"
  branch: "{branch}"
  status: planning
  created: "{date}"

  objective: |
    TODO: Describe the build objective

  scope:
    includes: []
    excludes: []

  phases:
    - id: "01"
      name: "Phase 1"
      status: pending
      tasks: []
""",
    "test": """# Test Plan
# Generated: {date}

plan:
  name: "Test Phases"
  worktree: "{worktree}"
  branch: "{branch}"
  status: pending
  created: "{date}"

  phases:
    - id: "test-01"
      name: "Unit Tests"
      status: pending
      scope: "Individual components"

    - id: "test-02"
      name: "Integration Tests"
      status: pending
      scope: "Component interactions"

  test_strategy:
    - type: "unit"
      scope: "Individual functions"
      location: "tests/unit/"

    - type: "integration"
      scope: "Command execution"
      location: "tests/integration/"

    - type: "e2e"
      scope: "Full CLI invocation"
      location: "tests/e2e/"

  user_stories: []
""",
    "cleanup": """# Audit and Cleanup Plan
# Generated: {date}

plan:
  name: "Audit and Cleanup"
  worktree: "{worktree}"
  branch: "{branch}"
  status: pending
  created: "{date}"

  phases:
    - id: "audit-01"
      name: "Code Audit"
      status: pending
      tasks:
        - "Review for unused imports"
        - "Check for dead code"
        - "Validate test coverage"

    - id: "cleanup-01"
      name: "Cleanup"
      status: pending
      tasks:
        - "Remove development artifacts"
        - "Clean build directories"
        - "Update documentation"

  cleanup_targets:
    - "Remove development artifacts"
    - "Clean unused imports"
    - "Validate test coverage"
    - "Update documentation"

  documentation:
    - "README.md with usage examples"
    - "Command help text"
    - "Integration guide"
""",
    "guidance": """# Guidance Plan
# Generated: {date}

plan:
  name: "Guidance Improvement"
  worktree: "{worktree}"
  branch: "{branch}"
  status: pending
  created: "{date}"

  objective: |
    Improve agent guidance based on observed friction points

  phases:
    - id: "analyze"
      name: "Analyze Agent Logs"
      status: pending
      tasks:
        - "Review agent execution logs"
        - "Identify friction points"
        - "Document improvement opportunities"

    - id: "update"
      name: "Update Guidance"
      status: pending
      tasks:
        - "Update process.yml files"
        - "Update inputs.yml references"
        - "Add missing signposts"

  friction_points: []
  improvements: []
""",
}


def _get_context() -> dict:
    """Get context for template substitution."""
    import subprocess

    worktree = str(Path.cwd())
    branch = ""

    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
    except subprocess.CalledProcessError:
        branch = "unknown"

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "worktree": worktree,
        "branch": branch,
    }


def _try_jinja2_render(template_type: str, context: dict) -> str | None:
    """Try to render using Jinja2 templates if available.

    Returns None if Jinja2 template not found.
    """
    try:
        from agenticguidance.services import TemplateContext, TemplateWorkflow

        workflow = TemplateWorkflow()
        jinja_template = f"{template_type}_plan.yml.j2"

        # Check if template exists
        templates = workflow.list_templates()
        if any(t["name"] == f"{template_type}_plan" for t in templates):
            # Create context
            tpl_context = TemplateContext(
                plan_name=context.get("plan_name", template_type.title()),
                worktree=context.get("worktree", ""),
                branch=context.get("branch", ""),
            )
            workflow.context = tpl_context
            return workflow.render(jinja_template)
    except Exception:
        pass
    return None


def cmd_generate(args):
    """Generate a plan file from template."""
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success

    template_type = args.type
    output_path = Path(args.output) if args.output else None

    if template_type not in TEMPLATES:
        print_error(f"Unknown template type: {template_type}")
        if not is_json_output():
            console.print(f"[dim]Available types: {', '.join(TEMPLATES.keys())}[/dim]")
        sys.exit(1)

    context = _get_context()

    # Try Jinja2 first, fall back to simple templates
    content = _try_jinja2_render(template_type, context)
    if content is None:
        # Fall back to simple string formatting
        template = TEMPLATES[template_type]
        content = template.format(**context)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        if is_json_output():
            print_json({"generated": str(output_path), "type": template_type})
        else:
            print_success(f"Generated: {output_path}")
    else:
        # Print to stdout (even in JSON mode, content is YAML)
        console.print(content)


def cmd_list(args):
    """List available template types."""
    from agenticcli.console import console, is_json_output, print_header, print_json, print_table

    if is_json_output():
        templates = [{"type": t, "description": d} for t, d in TEMPLATE_DESCRIPTIONS.items()]
        print_json({"templates": templates})
        return

    print_header("Available Template Types")

    rows = []
    for template_type, description in TEMPLATE_DESCRIPTIONS.items():
        rows.append([f"[cyan]{template_type}[/cyan]", description])

    print_table("", ["Type", "Description"], rows)

    console.print()
    console.print("[dim]Usage: agentic template generate <type> [--output FILE][/dim]")
