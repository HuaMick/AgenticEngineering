"""Health check command for diagnostics and CI/CD."""

import shutil
import sys
from typing import Any


def handle(args, ctx=None):
    """Run health checks and report status.

    Args:
        args: Parsed command arguments.
        ctx: Optional CLIContext for dependency injection.
    """
    from agenticcli import __version__
    from agenticcli.console import is_json_output, print_json

    checks = []
    all_passed = True

    # Check 1: CLI Version
    checks.append(
        {
            "name": "cli_version",
            "status": "pass",
            "message": f"AgenticCLI v{__version__}",
            "value": __version__,
        }
    )

    # Check 2: Config Directory
    config_dir = ctx.config_dir if ctx else None
    if config_dir and config_dir.exists():
        checks.append(
            {
                "name": "config_dir",
                "status": "pass",
                "message": f"Config directory exists: {config_dir}",
                "value": str(config_dir),
            }
        )
    else:
        checks.append(
            {
                "name": "config_dir",
                "status": "warn",
                "message": "Config directory not found. Run 'agentic setup'",
                "value": str(config_dir) if config_dir else None,
            }
        )

    # Check 3: Config File
    config_file = ctx.config_file if ctx else None
    if config_file and config_file.exists():
        checks.append(
            {
                "name": "config_file",
                "status": "pass",
                "message": f"Config file exists: {config_file}",
                "value": str(config_file),
            }
        )
    else:
        checks.append(
            {
                "name": "config_file",
                "status": "warn",
                "message": "Config file not found. Run 'agentic setup'",
                "value": None,
            }
        )

    # Check 4: Project Root (if in project)
    if ctx and ctx.is_in_project:
        checks.append(
            {
                "name": "project_root",
                "status": "pass",
                "message": f"Project detected: {ctx.project_root}",
                "value": str(ctx.project_root),
            }
        )
    else:
        checks.append(
            {
                "name": "project_root",
                "status": "info",
                "message": "Not in a project directory",
                "value": None,
            }
        )

    # Check 5: Git
    git_path = shutil.which("git")
    if git_path:
        checks.append(
            {
                "name": "git",
                "status": "pass",
                "message": f"Git found: {git_path}",
                "value": git_path,
            }
        )
    else:
        checks.append(
            {
                "name": "git",
                "status": "fail",
                "message": "Git not found in PATH",
                "value": None,
            }
        )
        all_passed = False

    # Check 6: UV
    uv_path = shutil.which("uv")
    if uv_path:
        checks.append(
            {
                "name": "uv",
                "status": "pass",
                "message": f"UV found: {uv_path}",
                "value": uv_path,
            }
        )
    else:
        checks.append(
            {
                "name": "uv",
                "status": "warn",
                "message": "UV not found (optional but recommended)",
                "value": None,
            }
        )

    # Check 7: Logs Directory
    logs_dir = ctx.logs_dir if ctx else None
    if logs_dir and logs_dir.exists():
        log_file = logs_dir / "agenticcli.log"
        log_exists = log_file.exists()
        checks.append(
            {
                "name": "logs_dir",
                "status": "pass",
                "message": f"Logs directory exists: {logs_dir}",
                "value": str(logs_dir),
                "log_file_exists": log_exists,
            }
        )
    else:
        checks.append(
            {
                "name": "logs_dir",
                "status": "info",
                "message": f"Logs directory will be created: {logs_dir}",
                "value": str(logs_dir) if logs_dir else None,
            }
        )

    # Check 8: Story Test Coverage
    try:
        from pathlib import Path
        from agenticcli.commands.stories import _collect_all_stories
        from agenticguidance.services.epic_repository import EpicRepository

        stories = _collect_all_stories()
        all_story_ids = {s["id"] for s in stories}
        total = len(all_story_ids)

        if total == 0:
            checks.append({
                "name": "story_coverage",
                "status": "info",
                "message": "No stories found",
                "value": {"total": 0, "covered": 0, "uncovered_count": 0, "uncovered": [], "coverage_pct": 0},
            })
        else:
            db_path = Path.home() / ".agentic" / "epics.db"
            repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
            uncovered = repo.get_uncovered_stories(all_story_ids)
            repo.close()

            covered_count = total - len(uncovered)
            pct = round(covered_count / total * 100, 1)

            if uncovered:
                msg = f"Story coverage: {covered_count}/{total} ({pct}%) — {len(uncovered)} uncovered"
                status = "fail"
                all_passed = False
            else:
                msg = f"All {total} stories covered"
                status = "pass"

            checks.append({
                "name": "story_coverage",
                "status": status,
                "message": msg,
                "value": {
                    "total": total,
                    "covered": covered_count,
                    "uncovered_count": len(uncovered),
                    "uncovered": uncovered,
                    "coverage_pct": pct,
                },
            })
    except Exception:
        checks.append({
            "name": "story_coverage",
            "status": "info",
            "message": "Story coverage check unavailable",
            "value": None,
        })

    # Output
    if is_json_output():
        print_json(
            {
                "status": "healthy" if all_passed else "unhealthy",
                "checks": checks,
            }
        )
    else:
        _print_human_readable(checks, all_passed)

    if not all_passed:
        sys.exit(1)


def _print_human_readable(checks: list[dict[str, Any]], all_passed: bool):
    """Print health check results in human-readable format."""
    from agenticcli.console import console

    console.print("\n[bold]AgenticCLI Health Check[/bold]\n")

    status_icons = {
        "pass": "[green]OK[/green]",
        "fail": "[red]FAIL[/red]",
        "warn": "[yellow]WARN[/yellow]",
        "info": "[blue]INFO[/blue]",
    }

    for check in checks:
        icon = status_icons.get(check["status"], "[dim]?[/dim]")
        console.print(f"  {icon}  {check['name']}: {check['message']}")

    console.print("")
    if all_passed:
        console.print("[green]All health checks passed.[/green]\n")
    else:
        console.print("[red]Some health checks failed.[/red]\n")
