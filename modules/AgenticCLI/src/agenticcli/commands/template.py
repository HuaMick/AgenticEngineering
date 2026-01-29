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


def _parse_phases(phases_str: str) -> list[dict]:
    """Parse phases string into list of phase dictionaries.

    Args:
        phases_str: Comma-separated list of ID:Name pairs
                   Example: "P1:Build,P2:Test,P3:Deploy"

    Returns:
        List of phase dictionaries with id, name, status, and tasks fields.

    Raises:
        ValueError: If phases_str is malformed.
    """
    phases = []
    for pair in phases_str.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            raise ValueError(
                f"Invalid phase format '{pair}'. Expected 'ID:Name' (e.g., 'P1:Build')"
            )
        parts = pair.split(":", 1)
        phase_id = parts[0].strip()
        phase_name = parts[1].strip()
        if not phase_id or not phase_name:
            raise ValueError(
                f"Invalid phase format '{pair}'. Both ID and Name are required."
            )
        phases.append({
            "id": phase_id,
            "name": phase_name,
            "status": "pending",
            "tasks": [],
        })
    return phases


def _inject_phases(content: str, phases: list[dict]) -> str:
    """Inject custom phases into generated template content.

    Replaces the default phases section with user-provided phases.

    Args:
        content: The template YAML content.
        phases: List of phase dictionaries from _parse_phases().

    Returns:
        Modified content with custom phases.
    """
    import re

    # Build YAML representation of phases
    phases_yaml_lines = []
    for phase in phases:
        phases_yaml_lines.append(f'    - id: "{phase["id"]}"')
        phases_yaml_lines.append(f'      name: "{phase["name"]}"')
        phases_yaml_lines.append(f'      status: {phase["status"]}')
        phases_yaml_lines.append("      tasks: []")
    phases_yaml = "\n".join(phases_yaml_lines)

    # Pattern to match the phases section in YAML
    # Matches from "phases:" to the next top-level key or end of plan section
    # This handles multi-line phases blocks
    pattern = r"(  phases:\n)((?:    - [^\n]*\n(?:      [^\n]*\n)*)+)"

    def replace_phases(match):
        return f"  phases:\n{phases_yaml}\n"

    new_content = re.sub(pattern, replace_phases, content)

    return new_content


def _parse_success_criteria(criteria_str: str) -> list[str]:
    """Parse success criteria string into list of criteria.

    Args:
        criteria_str: Comma-separated or newline-separated list of criteria.
                     Example: "Tests pass,Coverage > 80%,No lint errors"
                     Or multiline:
                     "Tests pass
                     Coverage > 80%
                     No lint errors"

    Returns:
        List of success criteria strings, stripped of whitespace.
    """
    criteria = []
    # Split by newlines first, then by commas if no newlines
    if "\n" in criteria_str:
        items = criteria_str.split("\n")
    else:
        items = criteria_str.split(",")

    for item in items:
        item = item.strip()
        if item:
            criteria.append(item)

    return criteria


def _inject_success_criteria(content: str, criteria: list[str]) -> str:
    """Inject success_criteria into generated template content.

    Adds a success_criteria field to the plan section in the YAML content.

    Args:
        content: The template YAML content.
        criteria: List of success criteria strings.

    Returns:
        Modified content with success_criteria field added.
    """
    import re

    # Build YAML representation of success criteria
    criteria_yaml_lines = ["  success_criteria:"]
    for criterion in criteria:
        # Escape quotes in criteria text
        escaped = criterion.replace('"', '\\"')
        criteria_yaml_lines.append(f'    - "{escaped}"')
    criteria_yaml = "\n".join(criteria_yaml_lines)

    # Find where to insert - after status: line in plan section
    # Look for pattern like "  status: planning" or "  status: pending"
    pattern = r"(  status:\s*\w+\n)(  created:)"

    def insert_criteria(match):
        return f"{match.group(1)}\n{criteria_yaml}\n\n{match.group(2)}"

    new_content = re.sub(pattern, insert_criteria, content, count=1)

    # If pattern not found, try inserting after created: line instead
    if new_content == content:
        pattern = r"(  created:\s*\"[^\"]+\"\n)"

        def insert_after_created(match):
            return f"{match.group(1)}\n{criteria_yaml}\n"

        new_content = re.sub(pattern, insert_after_created, content, count=1)

    return new_content


def _inject_objective(content: str, objective: str) -> str:
    """Inject objective into generated template content.

    Replaces placeholder objective text with the provided objective.
    Handles multi-line objectives by indenting continuation lines.
    """
    import re

    # Format objective with proper YAML indentation for multi-line
    lines = objective.strip().split("\n")
    if len(lines) == 1:
        formatted_objective = lines[0]
    else:
        # Multi-line: use YAML block scalar with proper indentation
        formatted_objective = "\n    ".join(lines)

    # Pattern to match objective placeholder in YAML
    # Matches: objective: |
    #            TODO: Describe the build objective
    # or: objective: |
    #       Improve agent guidance based on observed friction points
    pattern = r"(objective:\s*\|)\n(\s+)(TODO: Describe[^\n]*|[^\n]+)"

    def replace_objective(match):
        prefix = match.group(1)  # "objective: |"
        indent = match.group(2)  # whitespace indentation
        return f"{prefix}\n{indent}{formatted_objective}"

    new_content = re.sub(pattern, replace_objective, content, count=1)

    # If no match found (template doesn't have objective field), add it after plan name
    if new_content == content and "objective:" not in content:
        # Find where to insert - after plan: name: line
        pattern = r"(plan:\s*\n\s+name:\s*[^\n]+)"
        replacement = r"\1\n\n  objective: |\n    " + formatted_objective
        new_content = re.sub(pattern, replacement, content, count=1)

    return new_content


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
    objective = getattr(args, "objective", None)
    phases_str = getattr(args, "phases", None)
    success_criteria_str = getattr(args, "success_criteria", None)

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

    # Inject objective if provided
    if objective:
        content = _inject_objective(content, objective)

    # Inject custom phases if provided
    if phases_str:
        try:
            phases = _parse_phases(phases_str)
            if phases:
                content = _inject_phases(content, phases)
        except ValueError as e:
            print_error(str(e))
            sys.exit(1)

    # Inject success criteria if provided
    if success_criteria_str:
        criteria = _parse_success_criteria(success_criteria_str)
        if criteria:
            content = _inject_success_criteria(content, criteria)

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
    console.print("[dim]Usage: agentic template generate <type> [--output FILE] [--objective TEXT] [--phases 'P1:Build,P2:Test'] [--success-criteria 'Criteria1,Criteria2'][/dim]")
