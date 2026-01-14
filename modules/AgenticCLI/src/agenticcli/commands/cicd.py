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
    elif args.cicd_command == "list":
        cmd_list(args)
    elif args.cicd_command == "show":
        cmd_show(args)
    else:
        print("Usage: agentic cicd <audit|list|show>", file=sys.stderr)
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


def _find_all_cicd_configs() -> list[dict]:
    """Find all CI/CD configuration files in the project."""
    configs = []
    cwd = Path.cwd()

    # Cloud Build
    for name in ["cloudbuild.yaml", "cloudbuild.yml"]:
        path = cwd / name
        if path.exists():
            configs.append({"type": "cloudbuild", "path": path, "name": name})

    # GitHub Actions
    gh_workflows = cwd / ".github" / "workflows"
    if gh_workflows.exists():
        for workflow in gh_workflows.glob("*.yml"):
            configs.append({"type": "github-actions", "path": workflow, "name": workflow.name})
        for workflow in gh_workflows.glob("*.yaml"):
            configs.append({"type": "github-actions", "path": workflow, "name": workflow.name})

    # CircleCI
    circleci = cwd / ".circleci" / "config.yml"
    if circleci.exists():
        configs.append({"type": "circleci", "path": circleci, "name": "config.yml"})

    # GitLab CI
    gitlab = cwd / ".gitlab-ci.yml"
    if gitlab.exists():
        configs.append({"type": "gitlab-ci", "path": gitlab, "name": ".gitlab-ci.yml"})

    # Azure Pipelines
    azure = cwd / "azure-pipelines.yml"
    if azure.exists():
        configs.append({"type": "azure-pipelines", "path": azure, "name": "azure-pipelines.yml"})

    return configs


def _parse_github_actions(config_path: Path) -> dict:
    """Parse GitHub Actions workflow configuration."""
    try:
        content = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError as e:
        return {"error": f"YAML error: {e}"}

    if not content:
        return {}

    result = {
        "name": content.get("name", config_path.stem),
        "triggers": [],
        "jobs": [],
    }

    # Extract triggers
    if "on" in content:
        triggers = content["on"]
        if isinstance(triggers, str):
            result["triggers"] = [triggers]
        elif isinstance(triggers, list):
            result["triggers"] = triggers
        elif isinstance(triggers, dict):
            result["triggers"] = list(triggers.keys())

    # Extract jobs
    if "jobs" in content:
        for job_id, job_config in content["jobs"].items():
            job_info = {
                "id": job_id,
                "name": job_config.get("name", job_id),
                "runs_on": job_config.get("runs-on", "unknown"),
                "steps": len(job_config.get("steps", [])),
            }

            # Check for test steps
            for step in job_config.get("steps", []):
                step_run = step.get("run", "")
                if "pytest" in step_run or "test" in step.get("name", "").lower():
                    job_info["has_tests"] = True
                    break

            result["jobs"].append(job_info)

    return result


def cmd_list(args):
    """List all CI/CD configurations found in the project."""
    from agenticcli.console import console, is_json_output, print_header, print_json

    configs = _find_all_cicd_configs()

    if is_json_output():
        print_json({
            "configs": [
                {"type": c["type"], "path": str(c["path"]), "name": c["name"]}
                for c in configs
            ],
            "count": len(configs),
        })
        return

    print_header("CI/CD Configurations")

    if not configs:
        console.print("\n[dim]No CI/CD configurations found.[/dim]")
        console.print("\n[dim]Searched for:[/dim]")
        console.print("  [dim]- cloudbuild.yaml / cloudbuild.yml[/dim]")
        console.print("  [dim]- .github/workflows/*.yml[/dim]")
        console.print("  [dim]- .circleci/config.yml[/dim]")
        console.print("  [dim]- .gitlab-ci.yml[/dim]")
        console.print("  [dim]- azure-pipelines.yml[/dim]")
        return

    from rich.table import Table

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", style="cyan")
    table.add_column("File", style="green")
    table.add_column("Path")

    for config in configs:
        table.add_row(
            config["type"],
            config["name"],
            str(config["path"].relative_to(Path.cwd())),
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(configs)} configuration(s)[/dim]")


def cmd_show(args):
    """Show details of a specific CI/CD configuration."""
    from agenticcli.console import (
        console,
        is_json_output,
        print_error,
        print_header,
        print_json,
    )

    config_path = Path(args.path) if hasattr(args, "path") and args.path else None

    if not config_path:
        # Auto-detect first config
        configs = _find_all_cicd_configs()
        if not configs:
            print_error("No CI/CD configuration found. Specify a path.")
            sys.exit(1)
        config_path = configs[0]["path"]

    if not config_path.exists():
        print_error(f"Configuration not found: {config_path}")
        sys.exit(1)

    # Determine type and parse
    if "workflows" in str(config_path):
        config_type = "github-actions"
        parsed = _parse_github_actions(config_path)
    elif config_path.name.startswith("cloudbuild"):
        config_type = "cloudbuild"
        steps = _parse_cloudbuild(config_path)
        parsed = {"steps": steps, "step_count": len(steps)}
    else:
        config_type = "unknown"
        try:
            parsed = yaml.safe_load(config_path.read_text())
        except yaml.YAMLError as e:
            parsed = {"error": str(e)}

    if is_json_output():
        print_json({
            "path": str(config_path),
            "type": config_type,
            "config": parsed,
        })
        return

    print_header(f"CI/CD Configuration: {config_path.name}")
    console.print(f"\n[bold]Type:[/bold] [cyan]{config_type}[/cyan]")
    console.print(f"[bold]Path:[/bold] {config_path}")

    if config_type == "github-actions":
        if "name" in parsed:
            console.print(f"[bold]Workflow:[/bold] [green]{parsed['name']}[/green]")

        if "triggers" in parsed and parsed["triggers"]:
            console.print("\n[bold magenta]Triggers:[/bold magenta]")
            for trigger in parsed["triggers"]:
                console.print(f"  [dim]-[/dim] [cyan]{trigger}[/cyan]")

        if "jobs" in parsed and parsed["jobs"]:
            console.print("\n[bold magenta]Jobs:[/bold magenta]")
            for job in parsed["jobs"]:
                has_tests = "[green]✓ tests[/green]" if job.get("has_tests") else ""
                console.print(
                    f"  [dim]-[/dim] [cyan]{job['id']}[/cyan] "
                    f"({job['steps']} steps, {job['runs_on']}) {has_tests}"
                )

    elif config_type == "cloudbuild":
        console.print(f"\n[bold]Steps:[/bold] {parsed.get('step_count', 0)}")
        if "steps" in parsed:
            console.print("\n[bold magenta]Build Steps:[/bold magenta]")
            for step in parsed["steps"][:10]:
                step_id = step.get("id") or step.get("name", "")[:30]
                is_test = "[green]✓ test[/green]" if step.get("is_test") else ""
                console.print(f"  [dim]-[/dim] [cyan]{step_id}[/cyan] {is_test}")
            if len(parsed["steps"]) > 10:
                console.print(f"  [dim]... and {len(parsed['steps']) - 10} more[/dim]")

    console.print()
