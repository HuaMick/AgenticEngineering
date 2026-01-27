"""Entrypoint commands for discovering and executing workflow entrypoints.

Provides CLI commands to list, show, and execute entrypoint files that define
workflow starting points for orchestration and planning.

Commands:
    list: List all available entrypoints
    show: Display contents of an entrypoint file
    execute: Execute an entrypoint with variable substitution
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml


def handle(args, ctx=None):
    """Route entrypoint subcommands.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    if args.entrypoint_command == "list":
        cmd_list(args, ctx)
    elif args.entrypoint_command == "show":
        cmd_show(args, ctx)
    elif args.entrypoint_command == "execute":
        cmd_execute(args, ctx)
    else:
        print(
            "Usage: agentic entrypoint <list|show|execute> ...",
            file=sys.stderr,
        )
        sys.exit(1)


def _get_entrypoints_dirs() -> list[Path]:
    """Get list of directories to search for entrypoint files.

    Returns:
        List of Path objects for entrypoint directories, in priority order:
        1. Current working directory: .claude/entrypoints/
        2. Project root: modules/AgenticGuidance/entrypoints/
    """
    dirs = []

    # 1. Current working directory: .claude/entrypoints/
    cwd_entrypoints = Path.cwd() / ".claude" / "entrypoints"
    if cwd_entrypoints.exists() and cwd_entrypoints.is_dir():
        dirs.append(cwd_entrypoints)

    # 2. Project root: modules/AgenticGuidance/entrypoints/
    # Try to find the project root by looking for AgenticGuidance module
    # Start from cwd and walk up to find the project root
    current = Path.cwd()
    while current != current.parent:
        guidance_entrypoints = current / "modules" / "AgenticGuidance" / "entrypoints"
        if guidance_entrypoints.exists() and guidance_entrypoints.is_dir():
            dirs.append(guidance_entrypoints)
            break
        current = current.parent

    return dirs


def _normalize_entrypoint_name(name: str) -> str:
    """Normalize entrypoint name by removing leading underscore if present.

    Args:
        name: Entrypoint name (e.g., "_plan_build" or "plan_build")

    Returns:
        Normalized name without leading underscore.
    """
    return name.lstrip("_")


def _get_entrypoint_name_from_file(filepath: Path) -> str:
    """Extract entrypoint name from filename.

    Args:
        filepath: Path to entrypoint file.

    Returns:
        Entrypoint name without underscore prefix or extension.
    """
    # Files named _<name>.yml or _<name>.md
    stem = filepath.stem  # e.g., "_plan_build"
    return stem.lstrip("_")  # e.g., "plan_build"


def _find_entrypoint(name: str) -> Optional[Path]:
    """Resolve entrypoint name to file path.

    Args:
        name: Entrypoint name (with or without underscore prefix).

    Returns:
        Path to the entrypoint file, or None if not found.
    """
    normalized = _normalize_entrypoint_name(name)
    dirs = _get_entrypoints_dirs()

    for dir_path in dirs:
        # Try .yml first, then .md
        for ext in [".yml", ".yaml", ".md"]:
            filepath = dir_path / f"_{normalized}{ext}"
            if filepath.exists():
                return filepath

    return None


def _get_repo_root() -> Optional[Path]:
    """Find the repository root by walking up from cwd.

    Looks for .git directory or modules/ directory as indicators.

    Returns:
        Path to repository root, or None if not found.
    """
    current = Path.cwd()
    while current != current.parent:
        if (current / ".git").exists() or (current / "modules").exists():
            return current
        current = current.parent
    return None


def _find_inputs_yml(entrypoint_data: dict, repo_root: Path) -> Optional[Path]:
    """Find inputs.yml relative to the orchestration path in entrypoint.

    Algorithm:
    1. Parse entrypoint YAML to get orchestration: field
    2. Extract agent path from orchestration
    3. Replace process.mmd with inputs.yml
    4. Return absolute path to inputs.yml

    Args:
        entrypoint_data: Parsed entrypoint YAML data.
        repo_root: Repository root path for resolving relative paths.

    Returns:
        Path to inputs.yml, or None if not found.
    """
    # Get orchestration field from entrypoint
    entrypoint = entrypoint_data.get("entrypoint", {})
    orchestration_path = entrypoint.get("orchestration")

    if not orchestration_path:
        return None

    # orchestration_path is like:
    # "modules/AgenticGuidance/agents/orchestration/orchestration-planning/process.mmd"
    # Replace the filename with inputs.yml
    orchestration_dir = Path(orchestration_path).parent
    inputs_path = repo_root / orchestration_dir / "inputs.yml"

    if inputs_path.exists():
        return inputs_path

    return None


def _parse_location_references(data: dict | list, collected: list = None) -> list[dict]:
    """Extract all location: fields from YAML data recursively.

    Searches all YAML nodes for keys named "location" and collects
    file path values along with optional descriptions.

    Args:
        data: Parsed YAML data (dict or list).
        collected: Internal list for collecting results.

    Returns:
        List of dicts with 'path' and optional 'description' keys.
    """
    if collected is None:
        collected = []

    if isinstance(data, dict):
        # Check if this dict has a 'location' key
        if "location" in data:
            location = data["location"]
            if isinstance(location, str):
                collected.append({
                    "path": location,
                    "description": data.get("description", ""),
                })
        # Recurse into all values
        for value in data.values():
            _parse_location_references(value, collected)

    elif isinstance(data, list):
        for item in data:
            _parse_location_references(item, collected)

    return collected


def _compile_context(
    filepath: Path,
    entrypoint_content: str,
    variables: dict,
) -> dict:
    """Compile complete context bundle by resolving all references.

    Algorithm:
    1. Read and parse entrypoint YAML
    2. Extract orchestration: field if present
    3. Find and read orchestration file (process.mmd)
    4. Find and read inputs.yml
    5. Parse inputs.yml for location: references
    6. Read all referenced files
    7. Build output dictionary with sections

    Args:
        filepath: Path to the entrypoint file.
        entrypoint_content: Already processed entrypoint content with variables applied.
        variables: Variable substitution dict (for potential future use).

    Returns:
        Dict with structure:
        {
            "entrypoint": {"path": str, "content": str},
            "orchestration": {"path": str, "content": str} | None,
            "inputs": {"path": str, "content": str} | None,
            "references": [{"path": str, "content": str, "description": str}, ...]
        }
    """
    result = {
        "entrypoint": {
            "path": str(filepath),
            "content": entrypoint_content,
        },
        "orchestration": None,
        "inputs": None,
        "references": [],
    }

    repo_root = _get_repo_root()
    if not repo_root:
        return result

    # Parse the original entrypoint file (without variable substitution)
    # to get the orchestration path
    try:
        original_content = filepath.read_text()
        entrypoint_data = yaml.safe_load(original_content)
        if not isinstance(entrypoint_data, dict):
            return result
    except Exception:
        return result

    # Get orchestration file
    entrypoint_section = entrypoint_data.get("entrypoint", {})
    orchestration_path = entrypoint_section.get("orchestration")

    if orchestration_path:
        full_orchestration_path = repo_root / orchestration_path
        if full_orchestration_path.exists():
            try:
                result["orchestration"] = {
                    "path": orchestration_path,
                    "content": full_orchestration_path.read_text(),
                }
            except Exception:
                result["orchestration"] = {
                    "path": orchestration_path,
                    "content": None,
                    "error": "Failed to read file",
                }
        else:
            result["orchestration"] = {
                "path": orchestration_path,
                "content": None,
                "error": "File not found",
            }

    # Find and read inputs.yml
    inputs_path = _find_inputs_yml(entrypoint_data, repo_root)
    if inputs_path:
        try:
            inputs_content = inputs_path.read_text()
            # Store relative path from repo root
            relative_inputs_path = inputs_path.relative_to(repo_root)
            result["inputs"] = {
                "path": str(relative_inputs_path),
                "content": inputs_content,
            }

            # Parse location references from inputs.yml
            try:
                inputs_data = yaml.safe_load(inputs_content)
                if isinstance(inputs_data, dict):
                    location_refs = _parse_location_references(inputs_data)

                    # Read each referenced file
                    for ref in location_refs:
                        ref_path = ref["path"]
                        full_ref_path = repo_root / ref_path

                        if full_ref_path.exists():
                            try:
                                result["references"].append({
                                    "path": ref_path,
                                    "content": full_ref_path.read_text(),
                                    "description": ref.get("description", ""),
                                })
                            except Exception:
                                result["references"].append({
                                    "path": ref_path,
                                    "content": None,
                                    "error": "Failed to read file",
                                    "description": ref.get("description", ""),
                                })
                        else:
                            result["references"].append({
                                "path": ref_path,
                                "content": None,
                                "error": "File not found",
                                "description": ref.get("description", ""),
                            })
            except Exception:
                pass  # Gracefully handle YAML parse errors

        except Exception:
            relative_inputs_path = inputs_path.relative_to(repo_root)
            result["inputs"] = {
                "path": str(relative_inputs_path),
                "content": None,
                "error": "Failed to read file",
            }

    return result


def _format_compiled_output(compiled: dict) -> str:
    """Format compiled context for text output with section headers.

    Args:
        compiled: Compiled context dict from _compile_context.

    Returns:
        Formatted text output with section delimiters.
    """
    sections = []

    # Entrypoint section
    entrypoint = compiled["entrypoint"]
    entrypoint_name = Path(entrypoint["path"]).stem
    sections.append(f"# === ENTRYPOINT: {entrypoint_name} ===")
    sections.append(entrypoint["content"])

    # Orchestration section
    if compiled["orchestration"]:
        orch = compiled["orchestration"]
        orch_name = Path(orch["path"]).name
        if orch.get("content"):
            sections.append(f"\n# === ORCHESTRATION: {orch_name} ===")
            sections.append(orch["content"])
        elif orch.get("error"):
            sections.append(f"\n# === MISSING: {orch['path']} ({orch['error']}) ===")

    # Inputs section
    if compiled["inputs"]:
        inputs = compiled["inputs"]
        inputs_name = Path(inputs["path"]).name
        if inputs.get("content"):
            sections.append(f"\n# === INPUTS: {inputs_name} ===")
            sections.append(inputs["content"])
        elif inputs.get("error"):
            sections.append(f"\n# === MISSING: {inputs['path']} ({inputs['error']}) ===")

    # Referenced files
    for ref in compiled["references"]:
        ref_name = Path(ref["path"]).name
        if ref.get("content"):
            sections.append(f"\n# === REFERENCED: {ref_name} ===")
            sections.append(ref["content"])
        elif ref.get("error"):
            sections.append(f"\n# === MISSING: {ref['path']} ({ref['error']}) ===")

    return "\n".join(sections)


def _extract_description(filepath: Path) -> str:
    """Extract description from entrypoint file.

    For YAML files: Extract from entrypoint.goal or entrypoint.description
    For Markdown files: Extract first comment line or heading

    Args:
        filepath: Path to entrypoint file.

    Returns:
        Description string, or empty string if not found.
    """
    try:
        content = filepath.read_text()

        if filepath.suffix in (".yml", ".yaml"):
            data = yaml.safe_load(content)
            if data and isinstance(data, dict):
                entrypoint = data.get("entrypoint", {})
                # Prefer goal, fallback to description
                return entrypoint.get("goal", entrypoint.get("description", ""))

        elif filepath.suffix == ".md":
            # Try to get first heading or first non-empty line
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("#"):
                    # Remove markdown heading markers
                    return line.lstrip("#").strip()
                elif line and not line.startswith("<!--"):
                    return line[:100]  # Truncate long lines

    except Exception:
        pass

    return ""


def _list_entrypoints() -> list[dict]:
    """List all available entrypoints.

    Returns:
        List of dicts with entrypoint info:
        - name: Entrypoint name (without underscore)
        - path: Full path to file
        - type: File extension (yml, yaml, md)
        - description: Extracted description
    """
    entrypoints = []
    seen_names = set()  # Track seen names to avoid duplicates

    dirs = _get_entrypoints_dirs()

    for dir_path in dirs:
        for filepath in sorted(dir_path.iterdir()):
            if not filepath.is_file():
                continue

            # Check for entrypoint naming convention: _<name>.<ext>
            if not filepath.name.startswith("_"):
                continue

            if filepath.suffix not in (".yml", ".yaml", ".md"):
                continue

            name = _get_entrypoint_name_from_file(filepath)

            # Skip duplicates (first found wins)
            if name in seen_names:
                continue
            seen_names.add(name)

            entrypoints.append({
                "name": f"_{name}",  # Include underscore in display name
                "path": str(filepath),
                "type": filepath.suffix.lstrip("."),
                "description": _extract_description(filepath),
            })

    return entrypoints


def cmd_list(args, ctx=None):
    """List all available entrypoints.

    Args:
        args: Parsed arguments.
        ctx: CLI context.
    """
    from agenticcli.console import console, is_json_output, print_json

    entrypoints = _list_entrypoints()
    json_output = is_json_output()

    if json_output:
        print_json({
            "entrypoints": entrypoints,
            "count": len(entrypoints),
        })
    else:
        console.print("\n[bold]Available Entrypoints[/bold]")
        console.print("=" * 21)

        if not entrypoints:
            console.print("  [dim]No entrypoints found.[/dim]")
        else:
            # Calculate column widths
            max_name_len = max(len(ep["name"]) for ep in entrypoints)
            name_width = max(max_name_len, 16)

            for ep in entrypoints:
                name = ep["name"]
                desc = ep["description"][:60] + "..." if len(ep["description"]) > 60 else ep["description"]
                console.print(f"  {name:<{name_width}}  {desc}")

        console.print()


def cmd_show(args, ctx=None):
    """Display full contents of an entrypoint file.

    Args:
        args: Parsed arguments with required name.
        ctx: CLI context.
    """
    from agenticcli.console import is_json_output, print_error, print_json

    name = args.name
    json_output = is_json_output()

    filepath = _find_entrypoint(name)

    if not filepath:
        print_error(f"Entrypoint not found: {name}")
        print(
            "Hint: Use 'agentic entrypoint list' to see available entrypoints.",
            file=sys.stderr,
        )
        sys.exit(1)

    content = filepath.read_text()

    if json_output:
        print_json({
            "name": f"_{_normalize_entrypoint_name(name)}",
            "path": str(filepath),
            "type": filepath.suffix.lstrip("."),
            "content": content,
        })
    else:
        print(content)


def cmd_execute(args, ctx=None):
    """Execute an entrypoint with variable substitution.

    Reads the entrypoint file, applies variable substitution, and outputs
    the processed content to stdout.

    Args:
        args: Parsed arguments with:
            - name: Entrypoint name (required)
            - vars: List of KEY=VALUE pairs (optional)
            - context: Additional context text to prepend (optional)
            - compile: Compile complete context bundle (optional)
        ctx: CLI context.
    """
    from agenticcli.console import is_json_output, print_error, print_json

    name = args.name
    var_pairs = getattr(args, "vars", None) or []
    context_text = getattr(args, "context", None)
    compile_mode = getattr(args, "compile", False)
    json_output = is_json_output()

    filepath = _find_entrypoint(name)

    if not filepath:
        print_error(f"Entrypoint not found: {name}")
        print(
            "Hint: Use 'agentic entrypoint list' to see available entrypoints.",
            file=sys.stderr,
        )
        sys.exit(1)

    content = filepath.read_text()

    # Parse --vars KEY=VALUE pairs into dict
    variables = {}
    for pair in var_pairs:
        if "=" in pair:
            key, value = pair.split("=", 1)
            variables[key.strip()] = value.strip()
        else:
            print_error(f"Invalid variable format: {pair} (expected KEY=VALUE)")
            sys.exit(1)

    # Add built-in variables
    variables["TIMESTAMP"] = datetime.now().isoformat()

    # Apply variable substitution
    # Support both {{VAR}} and {{ VAR }} with optional whitespace
    def replace_var(match):
        var_name = match.group(1).strip()
        return variables.get(var_name, match.group(0))  # Keep original if not found

    content = re.sub(r"\{\{\s*(\w+)\s*\}\}", replace_var, content)

    # Prepend context if provided
    if context_text:
        content = f"# Context\n{context_text}\n\n---\n\n{content}"

    # Handle --compile flag: compile complete context bundle
    if compile_mode:
        compiled = _compile_context(filepath, content, variables)

        if json_output:
            print_json({
                "name": f"_{_normalize_entrypoint_name(name)}",
                "compiled": True,
                "entrypoint": compiled["entrypoint"],
                "orchestration": compiled["orchestration"],
                "inputs": compiled["inputs"],
                "references": compiled["references"],
                "reference_count": len(compiled["references"]),
            })
        else:
            print(_format_compiled_output(compiled))
        return

    # Standard output (no compile)
    if json_output:
        print_json({
            "name": f"_{_normalize_entrypoint_name(name)}",
            "path": str(filepath),
            "variables_applied": list(variables.keys()),
            "context_prepended": context_text is not None,
            "content": content,
        })
    else:
        print(content)
