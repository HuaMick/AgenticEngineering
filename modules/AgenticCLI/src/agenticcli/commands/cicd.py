"""CI/CD audit commands.

Audit CI/CD configuration against codebase.
"""

import sys
from pathlib import Path

import yaml


def handle(args, ctx=None):
    """Route cicd subcommands."""
    if args.cicd_command == "audit":
        cmd_audit(args)
    else:
        print("Usage: agentic cicd audit", file=sys.stderr)
        sys.exit(1)


def _find_cicd_config() -> Path | None:
    """Find CI/CD configuration file."""
    search_paths = [
        Path.cwd() / "cloudbuild.yaml",
        Path.cwd() / "cloudbuild.yml",
        Path.cwd() / ".github" / "workflows",
        Path.cwd() / ".circleci" / "config.yml",
    ]

    for path in search_paths:
        if path.exists():
            return path

    return None


def _parse_cloudbuild(config_path: Path) -> list[dict]:
    """Parse Google Cloud Build configuration."""
    try:
        content = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError as e:
        return [{"error": f"YAML error: {e}"}]

    if not content:
        return []

    steps = []
    for step in content.get("steps", []):
        step_info = {
            "name": step.get("name", ""),
            "id": step.get("id", ""),
            "args": step.get("args", []),
        }

        # Check if this is a test step
        args_str = " ".join(str(a) for a in step.get("args", []))
        if "pytest" in args_str or "test" in step.get("id", "").lower():
            step_info["is_test"] = True
            # Extract test paths
            for arg in step.get("args", []):
                if "tests/" in str(arg):
                    step_info["test_path"] = str(arg)

        steps.append(step_info)

    return steps


def _find_test_directories() -> list[str]:
    """Find actual test directories in the codebase."""
    test_dirs = []

    tests_root = Path.cwd() / "tests"
    if tests_root.exists():
        for item in tests_root.iterdir():
            if item.is_dir() and not item.name.startswith("__"):
                test_dirs.append(f"tests/{item.name}")

    # Also check for tests in modules
    modules_dir = Path.cwd() / "modules"
    if modules_dir.exists():
        for module in modules_dir.iterdir():
            module_tests = module / "tests"
            if module_tests.exists():
                test_dirs.append(str(module_tests.relative_to(Path.cwd())))

    return sorted(test_dirs)


def cmd_audit(args):
    """Audit CI/CD configuration against codebase."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
        print_success,
        print_warning,
    )

    config_path = _find_cicd_config()

    if not config_path:
        if is_json_output():
            print_json({"error": "No CI/CD configuration found"})
        else:
            print_error("No CI/CD configuration found")
            console.print("[dim]Searched for:[/dim]")
            console.print("  [dim]- cloudbuild.yaml[/dim]")
            console.print("  [dim]- .github/workflows/[/dim]")
            console.print("  [dim]- .circleci/config.yml[/dim]")
        sys.exit(1)

    # Parse configuration
    if config_path.name.startswith("cloudbuild"):
        steps = _parse_cloudbuild(config_path)
    else:
        if not is_json_output():
            print_warning(f"Unsupported config type: {config_path}")
        steps = []

    # Find test steps
    test_steps = [s for s in steps if s.get("is_test")]
    configured_tests = set()
    for step in test_steps:
        if "test_path" in step:
            configured_tests.add(step["test_path"])

    # Find actual test directories
    actual_tests = set(_find_test_directories())

    # Check for discrepancies
    missing_in_ci = actual_tests - configured_tests
    missing_in_code = configured_tests - actual_tests

    discrepancies = []
    for path in sorted(missing_in_ci):
        discrepancies.append({"type": "not_in_ci", "path": path})
    for path in sorted(missing_in_code):
        discrepancies.append({"type": "no_tests", "path": path})

    if is_json_output():
        print_json(
            {
                "config": str(config_path),
                "test_steps": test_steps,
                "configured_tests": list(configured_tests),
                "actual_tests": list(actual_tests),
                "discrepancies": discrepancies,
                "valid": len(discrepancies) == 0,
            }
        )
    else:
        print_header(f"CI/CD Audit: {config_path}")

        console.print("\n[bold magenta]CI/CD Test Steps:[/bold magenta]")
        console.print("[dim]" + "-" * 40 + "[/dim]")
        if test_steps:
            for step in test_steps:
                console.print(f"  [dim]-[/dim] [cyan]{step.get('id', step.get('name', ''))}[/cyan]")
                if "test_path" in step:
                    console.print(f"    [dim]Path:[/dim] {step['test_path']}")
        else:
            console.print("  [dim](none found)[/dim]")

        console.print("\n[bold magenta]Actual Test Directories:[/bold magenta]")
        console.print("[dim]" + "-" * 40 + "[/dim]")
        if actual_tests:
            for test_dir in sorted(actual_tests):
                console.print(f"  [dim]-[/dim] [green]{test_dir}[/green]")
        else:
            console.print("  [dim](none found)[/dim]")

        if missing_in_ci:
            console.print(
                "\n[yellow]Missing from CI/CD[/yellow] (tests exist but not in pipeline):"
            )
            for path in sorted(missing_in_ci):
                console.print(f"  [yellow]-[/yellow] {path}")

        if missing_in_code:
            console.print("\n[red]Missing from Codebase[/red] (in pipeline but no tests found):")
            for path in sorted(missing_in_code):
                console.print(f"  [red]-[/red] {path}")

        console.print("\n" + "[dim]" + "-" * 60 + "[/dim]")
        if discrepancies:
            console.print(f"[red]Found {len(discrepancies)} discrepancies[/red]")
        else:
            print_success("No discrepancies found")

    if discrepancies:
        sys.exit(1)
