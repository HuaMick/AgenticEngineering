#!/usr/bin/env python3
"""AgenticCLI main command structure.

Uses Typer for command parsing with native shell completion.
Command handlers use the existing handle(args, ctx) bridge pattern.
"""

import sys
from types import SimpleNamespace
from typing import List, Optional

import typer
from typing_extensions import Annotated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ns(**kwargs) -> SimpleNamespace:
    """Create a SimpleNamespace that mimics an argparse Namespace.

    All handle(args, ctx) functions read attributes from args.  We build
    a SimpleNamespace with the same attribute names argparse would set.
    """
    return SimpleNamespace(**kwargs)


def _get_ctx(json_output: bool = False, debug: bool = False):
    """Build a CLIContext, configure JSON mode & logging."""
    if json_output:
        from agenticcli.console import set_json_output
        set_json_output(True)

    from agenticcli.context import CLIContext
    ctx = CLIContext.discover(json_output=json_output)

    from agenticcli.logging import setup_logging
    setup_logging(
        log_dir=ctx.logs_dir,
        level="DEBUG" if debug else None,
        debug_to_console=debug,
    )
    return ctx


def _require_project(ctx, command: str):
    """Check project requirement for project-scoped commands."""
    ctx.require_project(command)


def _stability_banner(command: str):
    """Display stability banner for non-stable commands."""
    from agenticcli.console import print_stability_banner
    print_stability_banner(command)


# ---------------------------------------------------------------------------
# App definition
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="agentic",
    help="AgenticCLI - Command-line interface for AgenticEngineering",
    add_completion=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)

# We store global flags in a module-level dict so sub-Typer callbacks can read them.
_global = {"json": False, "debug": False}


def _version_callback(value: bool):
    if value:
        from agenticcli import __version__
        print(f"agentic {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option(
        "--version", callback=_version_callback, is_eager=True,
        help="Show version information")] = False,
    json_output: Annotated[bool, typer.Option(
        "--json", "-j", help="Output in JSON format")] = False,
    debug: Annotated[bool, typer.Option(
        "--debug", "-d", help="Enable debug logging")] = False,
):
    """AgenticCLI - Command-line interface for AgenticEngineering."""
    _global["json"] = json_output
    _global["debug"] = debug
    # If no subcommand given, show help and exit cleanly
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit(0)


# ===========================================================================
# SIMPLE COMMANDS (no subcommands)
# ===========================================================================

@app.command()
def setup(
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing configuration")] = False,
):
    """Interactive setup wizard for initial configuration."""
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("setup")
    from agenticcli.commands import setup as _mod
    _mod.handle(_ns(command="setup", json=_global["json"], debug=_global["debug"], force=force), ctx=cli_ctx)


@app.command()
def health():
    """Check CLI health, dependencies, and configuration status."""
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("health")
    from agenticcli.commands import health as _mod
    _mod.handle(_ns(command="health", json=_global["json"], debug=_global["debug"]), ctx=cli_ctx)


@app.command()
def update():
    """Reinstall AgenticCLI from source using uv sync."""
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("update")
    from agenticcli.commands import package
    package.handle_update(_ns(command="update", json=_global["json"], debug=_global["debug"]), ctx=cli_ctx)


@app.command()
def rebuild():
    """Full rebuild: clean artifacts, rebuild package, reinstall."""
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("rebuild")
    from agenticcli.commands import package
    package.handle_rebuild(_ns(command="rebuild", json=_global["json"], debug=_global["debug"]), ctx=cli_ctx)


# ===========================================================================
# PREFERENCES (aliases: prefs, pref)
# ===========================================================================

preferences_app = typer.Typer(help="Manage user preferences", no_args_is_help=True)
app.add_typer(preferences_app, name="preferences")
app.add_typer(preferences_app, name="prefs", hidden=True)
app.add_typer(preferences_app, name="pref", hidden=True)


def _prefs_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("preferences")
    from agenticcli.commands import preferences
    preferences.handle(args, ctx=cli_ctx)


@preferences_app.command("get")
def prefs_get(key: str = typer.Argument(..., help="Preference key")):
    """Get a preference value."""
    _prefs_handle(_ns(command="preferences", prefs_command="get", json=_global["json"], debug=_global["debug"], key=key))


@preferences_app.command("set")
def prefs_set(
    key: str = typer.Argument(..., help="Preference key"),
    value: str = typer.Argument(..., help="Preference value"),
):
    """Set a preference value."""
    _prefs_handle(_ns(command="preferences", prefs_command="set", json=_global["json"], debug=_global["debug"], key=key, value=value))


@preferences_app.command("list")
def prefs_list():
    """List all preferences."""
    _prefs_handle(_ns(command="preferences", prefs_command="list", json=_global["json"], debug=_global["debug"]))


@preferences_app.command("delete")
def prefs_delete(key: str = typer.Argument(..., help="Preference key to delete")):
    """Delete a preference."""
    _prefs_handle(_ns(command="preferences", prefs_command="delete", json=_global["json"], debug=_global["debug"], key=key))


@preferences_app.command("clear")
def prefs_clear(
    force: Annotated[bool, typer.Option("--force", "-f", help="Clear without confirmation")] = False,
):
    """Clear all preferences."""
    _prefs_handle(_ns(command="preferences", prefs_command="clear", json=_global["json"], debug=_global["debug"], force=force))


# ===========================================================================
# CONFIG (alias: cfg)
# ===========================================================================

config_app = typer.Typer(help="Configuration management", no_args_is_help=True)
app.add_typer(config_app, name="config")
app.add_typer(config_app, name="cfg", hidden=True)


def _config_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("config")
    from agenticcli.commands import config
    config.handle(args, ctx=cli_ctx)


@config_app.command("show")
def config_show():
    """Display current configuration."""
    _config_handle(_ns(command="config", config_command="show", json=_global["json"], debug=_global["debug"]))


@config_app.command("init")
def config_init():
    """Initialize configuration."""
    _config_handle(_ns(command="config", config_command="init", json=_global["json"], debug=_global["debug"]))


@config_app.command("get")
def config_get(key: str = typer.Argument(..., help="Preference key")):
    """Get a preference value."""
    _config_handle(_ns(command="config", config_command="get", json=_global["json"], debug=_global["debug"], key=key))


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Preference key"),
    value: str = typer.Argument(..., help="Value to set"),
):
    """Set a preference value."""
    _config_handle(_ns(command="config", config_command="set", json=_global["json"], debug=_global["debug"], key=key, value=value))


@config_app.command("list")
def config_list():
    """List all preferences."""
    _config_handle(_ns(command="config", config_command="list", json=_global["json"], debug=_global["debug"]))


@config_app.command("delete")
def config_delete(key: str = typer.Argument(..., help="Preference key to delete")):
    """Delete a preference value."""
    _config_handle(_ns(command="config", config_command="delete", json=_global["json"], debug=_global["debug"], key=key))


@config_app.command("show-path")
def config_show_path():
    """Show all config file paths."""
    _config_handle(_ns(command="config", config_command="show-path", json=_global["json"], debug=_global["debug"]))


@config_app.command("set-path")
def config_set_path(path: str = typer.Argument(..., help="Path to custom config file")):
    """Set custom config file path."""
    _config_handle(_ns(command="config", config_command="set-path", json=_global["json"], debug=_global["debug"], path=path))


@config_app.command("clear")
def config_clear(
    force: Annotated[bool, typer.Option("--force", "-f", help="Confirm clearing")] = False,
):
    """Clear configuration."""
    _config_handle(_ns(command="config", config_command="clear", json=_global["json"], debug=_global["debug"], force=force))


# ===========================================================================
# STATE
# ===========================================================================

state_app = typer.Typer(help="Manage process state registry", no_args_is_help=True)
app.add_typer(state_app, name="state")


def _state_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("state")
    from agenticcli.commands import state
    state.handle(args, ctx=cli_ctx)


@state_app.command("list")
def state_list(
    active: Annotated[bool, typer.Option("--active", "-a", help="Show only active processes")] = False,
):
    """List registered processes."""
    _state_handle(_ns(command="state", state_command="list", json=_global["json"], debug=_global["debug"], active=active))


@state_app.command("show")
def state_show(pid: int = typer.Argument(..., help="Process ID to show")):
    """Show details of a specific process."""
    _state_handle(_ns(command="state", state_command="show", json=_global["json"], debug=_global["debug"], pid=pid))


@state_app.command("clear")
def state_clear(
    all: Annotated[bool, typer.Option("--all", "-a", help="Clear all entries")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Force clear")] = False,
):
    """Clear entries from the registry."""
    _state_handle(_ns(command="state", state_command="clear", json=_global["json"], debug=_global["debug"], **{"all": all}, force=force))


@state_app.command("cleanup")
def state_cleanup():
    """Clean up stale processes."""
    _state_handle(_ns(command="state", state_command="cleanup", json=_global["json"], debug=_global["debug"]))


# ===========================================================================
# ENV
# ===========================================================================

env_app = typer.Typer(help="Manage environment variable injection", no_args_is_help=True)
app.add_typer(env_app, name="env")


def _env_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("env")
    from agenticcli.commands import env
    env.handle(args, ctx=cli_ctx)


@env_app.command("show")
def env_show():
    """Show environment configuration."""
    _env_handle(_ns(command="env", env_command="show", json=_global["json"], debug=_global["debug"]))


@env_app.command("export")
def env_export(
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "shell",
):
    """Export environment variables."""
    _env_handle(_ns(command="env", env_command="export", json=_global["json"], debug=_global["debug"], format=format))


@env_app.command("run")
def env_run(
    cmd_args: List[str] = typer.Argument(..., help="Command and arguments to run"),
):
    """Run command with injected environment."""
    _env_handle(_ns(command="env", env_command="run", json=_global["json"], debug=_global["debug"], cmd_args=cmd_args))


# ===========================================================================
# INPUTS
# ===========================================================================

inputs_app = typer.Typer(help="Validate and resolve inputs.yml references", no_args_is_help=True)
app.add_typer(inputs_app, name="inputs")


def _inputs_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _require_project(cli_ctx, "inputs")
    _stability_banner("inputs")
    from agenticcli.commands import inputs
    inputs.handle(args, ctx=cli_ctx)


@inputs_app.command("validate")
def inputs_validate(file: str = typer.Argument(..., help="Path to inputs.yml file")):
    """Validate all input references."""
    _inputs_handle(_ns(command="inputs", inputs_command="validate", json=_global["json"], debug=_global["debug"], file=file))


@inputs_app.command("resolve")
def inputs_resolve(file: str = typer.Argument(..., help="Path to inputs.yml file")):
    """Show resolved paths for all inputs."""
    _inputs_handle(_ns(command="inputs", inputs_command="resolve", json=_global["json"], debug=_global["debug"], file=file))


# ===========================================================================
# TEMPLATE (alias: tpl)
# ===========================================================================

template_app = typer.Typer(help="Generate plan files from templates", no_args_is_help=True)
app.add_typer(template_app, name="template")
app.add_typer(template_app, name="tpl", hidden=True)


def _template_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _require_project(cli_ctx, "template")
    _stability_banner("template")
    from agenticcli.commands import template
    template.handle(args, ctx=cli_ctx)


@template_app.command("generate")
def template_generate(
    type: str = typer.Argument(..., help="Template type: build, test, cleanup, guidance"),
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path")] = None,
    objective: Annotated[Optional[str], typer.Option("--objective", help="Main objective")] = None,
    phases: Annotated[Optional[str], typer.Option("--phases", help="Comma-separated ID:Name pairs")] = None,
    success_criteria: Annotated[Optional[str], typer.Option("--success-criteria", help="Comma-separated criteria")] = None,
):
    """Generate a plan file from template."""
    _template_handle(_ns(
        command="template", template_command="generate",
        json=_global["json"], debug=_global["debug"],
        type=type, output=output, objective=objective,
        phases=phases, success_criteria=success_criteria,
    ))


@template_app.command("list")
def template_list():
    """List available template types."""
    _template_handle(_ns(command="template", template_command="list", json=_global["json"], debug=_global["debug"]))


# ===========================================================================
# STORIES (alias: st)
# ===========================================================================

stories_app = typer.Typer(help="Find and manage user stories", no_args_is_help=True)
app.add_typer(stories_app, name="stories")
app.add_typer(stories_app, name="st", hidden=True)


def _stories_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _require_project(cli_ctx, "stories")
    _stability_banner("stories")
    from agenticcli.commands import stories
    stories.handle(args, ctx=cli_ctx)


@stories_app.command("find")
def stories_find(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
    changes: Annotated[Optional[List[str]], typer.Option("--changes", "-c", help="Filter by changed files")] = None,
):
    """Find user stories matching project or changed files."""
    _stories_handle(_ns(
        command="stories", stories_command="find",
        json=_global["json"], debug=_global["debug"],
        project=project, changes=changes,
    ))


@stories_app.command("init")
def stories_init(
    id: str = typer.Argument(..., help="Story ID"),
    title: Annotated[Optional[str], typer.Option("--title", "-t", help="Story title")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder name")] = None,
):
    """Initialize a new user story template."""
    _stories_handle(_ns(
        command="stories", stories_command="init",
        json=_global["json"], debug=_global["debug"],
        id=id, title=title, plan=plan,
    ))


@stories_app.command("cat")
def stories_cat(id: str = typer.Argument(..., help="Story ID or filename")):
    """Display a user story's content."""
    _stories_handle(_ns(command="stories", stories_command="cat", json=_global["json"], debug=_global["debug"], id=id))


@stories_app.command("status")
def stories_status(id: str = typer.Argument(..., help="Story ID")):
    """View test status for a story."""
    _stories_handle(_ns(command="stories", stories_command="status", json=_global["json"], debug=_global["debug"], id=id))


@stories_app.command("update")
def stories_update(
    id: str = typer.Argument(..., help="Story ID"),
    status: Annotated[str, typer.Option("--status", "-s", help="Test result: pass, fail, skip")] = ...,
    notes: Annotated[Optional[str], typer.Option("--notes", "-n", help="Test notes")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder")] = None,
):
    """Update test status for a story."""
    _stories_handle(_ns(
        command="stories", stories_command="update",
        json=_global["json"], debug=_global["debug"],
        id=id, status=status, notes=notes, plan=plan,
    ))


@stories_app.command("report")
def stories_report(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
):
    """Show pass/fail/untested summary."""
    _stories_handle(_ns(command="stories", stories_command="report", json=_global["json"], debug=_global["debug"], project=project))


@stories_app.command("untested")
def stories_untested(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
):
    """List stories needing validation."""
    _stories_handle(_ns(command="stories", stories_command="untested", json=_global["json"], debug=_global["debug"], project=project))


# ===========================================================================
# MANIFEST (alias: mf)
# ===========================================================================

manifest_app = typer.Typer(help="Manage agent manifests", no_args_is_help=True)
app.add_typer(manifest_app, name="manifest")
app.add_typer(manifest_app, name="mf", hidden=True)


def _manifest_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _require_project(cli_ctx, "manifest")
    _stability_banner("manifest")
    from agenticcli.commands import manifest
    manifest.handle(args, ctx=cli_ctx)


@manifest_app.command("show")
def manifest_show(path: str = typer.Argument(..., help="Path to agent directory or manifest file")):
    """Display formatted agent manifest."""
    _manifest_handle(_ns(command="manifest", manifest_command="show", json=_global["json"], debug=_global["debug"], path=path))


@manifest_app.command("list")
def manifest_list(path: Optional[str] = typer.Argument(None, help="Base path to search")):
    """List all manifests in the project."""
    _manifest_handle(_ns(command="manifest", manifest_command="list", json=_global["json"], debug=_global["debug"], path=path))


@manifest_app.command("validate")
def manifest_validate(path: str = typer.Argument(..., help="Path to manifest file")):
    """Validate a manifest file."""
    _manifest_handle(_ns(command="manifest", manifest_command="validate", json=_global["json"], debug=_global["debug"], path=path))


# ===========================================================================
# CICD
# ===========================================================================

cicd_app = typer.Typer(help="CI/CD configuration management", no_args_is_help=True)
app.add_typer(cicd_app, name="cicd")


def _cicd_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _require_project(cli_ctx, "cicd")
    _stability_banner("cicd")
    from agenticcli.commands import cicd
    cicd.handle(args, ctx=cli_ctx)


@cicd_app.command("audit")
def cicd_audit():
    """Audit CI/CD configuration."""
    _cicd_handle(_ns(command="cicd", cicd_command="audit", json=_global["json"], debug=_global["debug"]))


@cicd_app.command("list")
def cicd_list():
    """List all CI/CD configurations."""
    _cicd_handle(_ns(command="cicd", cicd_command="list", json=_global["json"], debug=_global["debug"]))


@cicd_app.command("show")
def cicd_show(path: Optional[str] = typer.Argument(None, help="Path to CI/CD config file")):
    """Show CI/CD configuration details."""
    _cicd_handle(_ns(command="cicd", cicd_command="show", json=_global["json"], debug=_global["debug"], path=path))


# ===========================================================================
# WORKTREE (alias: wt)
# ===========================================================================

worktree_app = typer.Typer(help="Manage git worktrees with planning folder integration", no_args_is_help=True)
app.add_typer(worktree_app, name="worktree")
app.add_typer(worktree_app, name="wt", hidden=True)


def _worktree_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _require_project(cli_ctx, "worktree")
    _stability_banner("worktree")
    from agenticcli.commands import worktree
    worktree.handle(args, ctx=cli_ctx)


@worktree_app.command("create")
def worktree_create(
    branch: str = typer.Argument(..., help="Branch name for the new worktree"),
    base: Annotated[str, typer.Option("--base", "-b", help="Base branch")] = "main",
    no_plan: Annotated[bool, typer.Option("--no-plan", help="Skip planning folder creation")] = False,
    abbreviation: Annotated[Optional[str], typer.Option("--abbreviation", "-a", help="2-letter abbreviation")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Human-readable description")] = None,
):
    """Create a new worktree with planning folder."""
    _worktree_handle(_ns(
        command="worktree", worktree_command="create",
        json=_global["json"], debug=_global["debug"],
        branch=branch, base=base, no_plan=no_plan,
        abbreviation=abbreviation, description=description,
    ))


@worktree_app.command("list")
def worktree_list():
    """List all worktrees with their planning folders."""
    _worktree_handle(_ns(command="worktree", worktree_command="list", json=_global["json"], debug=_global["debug"]))


@worktree_app.command("remove")
def worktree_remove(
    branch: str = typer.Argument(..., help="Branch name of the worktree to remove"),
    force: Annotated[bool, typer.Option("--force", "-f", help="Force removal")] = False,
):
    """Remove a worktree."""
    _worktree_handle(_ns(
        command="worktree", worktree_command="remove",
        json=_global["json"], debug=_global["debug"],
        branch=branch, force=force,
    ))


@worktree_app.command("status")
def worktree_status():
    """Show detailed status of current worktree."""
    _worktree_handle(_ns(command="worktree", worktree_command="status", json=_global["json"], debug=_global["debug"]))


@worktree_app.command("validate")
def worktree_validate():
    """Validate worktree-plan synchronization."""
    _worktree_handle(_ns(command="worktree", worktree_command="validate", json=_global["json"], debug=_global["debug"]))


@worktree_app.command("sync")
def worktree_sync():
    """Synchronize workspace file with actual worktrees."""
    _worktree_handle(_ns(
        command="worktree", worktree_command="sync",
        json=_global["json"], debug=_global["debug"],
    ))


# ===========================================================================
# SESSION
# ===========================================================================

session_app = typer.Typer(help="Manage Claude Code sessions", no_args_is_help=True)
app.add_typer(session_app, name="session")


def _session_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("session")
    from agenticcli.commands import session
    session.handle(args, ctx=cli_ctx)


@session_app.command("spawn")
def session_spawn(
    prompt: Annotated[Optional[str], typer.Option("--prompt", "-p", help="The prompt to send")] = None,
    role: Annotated[Optional[str], typer.Option("--role", help="Agent role to spawn")] = None,
    task: Annotated[Optional[str], typer.Option("--task", help="Task ID to spawn agent for")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder name")] = None,
    max_turns: Annotated[Optional[int], typer.Option("--max-turns", "-m", help="Maximum agentic turns")] = None,
    background: Annotated[bool, typer.Option("--background", "-b", help="Run in background")] = False,
    directory: Annotated[Optional[str], typer.Option("--directory", "-d", help="Working directory")] = None,
    dangerously_skip_permissions: Annotated[bool, typer.Option(
        "--dangerously-skip-permissions", help="Skip permission prompts")] = False,
):
    """Spawn a new Claude Code session with a prompt."""
    # Mutual exclusion check (--role and --task cannot both be set)
    if role and task:
        from agenticcli.console import print_error
        print_error("--role and --task are mutually exclusive.")
        raise typer.Exit(1)

    _session_handle(_ns(
        command="session", session_command="spawn",
        json=_global["json"], debug=_global["debug"],
        prompt=prompt, role=role, task=task, plan=plan,
        max_turns=max_turns, background=background,
        directory=directory,
        dangerously_skip_permissions=dangerously_skip_permissions,
    ))


@session_app.command("list")
def session_list(
    active: Annotated[bool, typer.Option("--active", "-a", help="Show only active sessions")] = False,
):
    """List all sessions."""
    _session_handle(_ns(command="session", session_command="list", json=_global["json"], debug=_global["debug"], active=active))


@session_app.command("stop")
def session_stop(
    session_id: str = typer.Argument(..., help="Session ID to stop"),
    force: Annotated[bool, typer.Option("--force", "-f", help="Force kill")] = False,
):
    """Stop a running session."""
    _session_handle(_ns(
        command="session", session_command="stop",
        json=_global["json"], debug=_global["debug"],
        session_id=session_id, force=force,
    ))


@session_app.command("status")
def session_status(
    session_id: str = typer.Argument(..., help="Session ID to check"),
    show_output: Annotated[bool, typer.Option("--show-output", "-o", help="Display captured output")] = False,
):
    """Get detailed status of a session."""
    _session_handle(_ns(
        command="session", session_command="status",
        json=_global["json"], debug=_global["debug"],
        session_id=session_id, show_output=show_output,
    ))


# ===========================================================================
# LOOP
# ===========================================================================

loop_app = typer.Typer(help="Manage Ralph Loops (iterative agent execution)", no_args_is_help=True)
app.add_typer(loop_app, name="loop")


def _loop_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("loop")
    from agenticcli.commands import loop
    loop.handle(args, ctx=cli_ctx)


@loop_app.command("start")
def loop_start(
    prompt: Annotated[Optional[str], typer.Option("--prompt", "-p", help="Direct prompt string")] = None,
    prompt_file: Annotated[Optional[str], typer.Option("--prompt-file", "-f", help="Read prompt from file")] = None,
    entrypoint: Annotated[Optional[str], typer.Option("--entrypoint", "-e", help="Entrypoint reference")] = None,
    max_iterations: Annotated[int, typer.Option("--max-iterations", "-m", help="Max iterations")] = 10,
    completion_promise: Annotated[Optional[str], typer.Option("--completion-promise", "-c", help="Completion text")] = None,
    background: Annotated[bool, typer.Option("--background", "-b", help="Run in background")] = False,
    directory: Annotated[Optional[str], typer.Option("--directory", "-d", help="Working directory")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path")] = None,
    dangerously_skip_permissions: Annotated[bool, typer.Option(
        "--dangerously-skip-permissions", help="Skip permission prompts")] = False,
):
    """Start a Ralph Loop with a prompt."""
    _loop_handle(_ns(
        command="loop", loop_command="start",
        json=_global["json"], debug=_global["debug"],
        prompt=prompt, prompt_file=prompt_file, entrypoint=entrypoint,
        max_iterations=max_iterations, completion_promise=completion_promise,
        background=background, directory=directory, output=output,
        dangerously_skip_permissions=dangerously_skip_permissions,
    ))


@loop_app.command("stop")
def loop_stop(
    loop_id: str = typer.Argument(..., help="Loop ID to stop"),
    force: Annotated[bool, typer.Option("--force", "-f", help="Force kill")] = False,
):
    """Stop a running loop."""
    _loop_handle(_ns(command="loop", loop_command="stop", json=_global["json"], debug=_global["debug"], loop_id=loop_id, force=force))


@loop_app.command("status")
def loop_status(loop_id: str = typer.Argument(..., help="Loop ID to check")):
    """Display detailed status of a loop."""
    _loop_handle(_ns(command="loop", loop_command="status", json=_global["json"], debug=_global["debug"], loop_id=loop_id))


@loop_app.command("history")
def loop_history(
    active: Annotated[bool, typer.Option("--active", "-a", help="Show only active loops")] = False,
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="Filter by status")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max loops to show")] = 20,
):
    """Show past loop executions."""
    _loop_handle(_ns(
        command="loop", loop_command="history",
        json=_global["json"], debug=_global["debug"],
        active=active, status=status, limit=limit,
    ))


# ===========================================================================
# LANGSMITH (alias: ls)
# ===========================================================================

langsmith_app = typer.Typer(help="Query LangSmith traces, runs, projects, and statistics", no_args_is_help=True)
app.add_typer(langsmith_app, name="langsmith")
app.add_typer(langsmith_app, name="ls", hidden=True)


def _langsmith_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("langsmith")
    from agenticcli.commands import langsmith
    langsmith.handle(args, ctx=cli_ctx)


@langsmith_app.command("runs")
def langsmith_runs(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max runs to return")] = 20,
    type: Annotated[Optional[str], typer.Option("--type", "-t", help="Filter by run type")] = None,
    error: Annotated[bool, typer.Option("--error", "-e", help="Show only error runs")] = False,
):
    """List recent runs with filtering."""
    _langsmith_handle(_ns(
        command="langsmith", langsmith_command="runs",
        json=_global["json"], debug=_global["debug"],
        project=project, limit=limit, type=type, error=error,
    ))


@langsmith_app.command("run")
def langsmith_run(
    run_id: str = typer.Argument(..., help="The run ID to fetch"),
    url: Annotated[bool, typer.Option("--url", "-u", help="Generate shareable URL")] = False,
):
    """Show detailed info for a single run."""
    _langsmith_handle(_ns(
        command="langsmith", langsmith_command="run",
        json=_global["json"], debug=_global["debug"],
        run_id=run_id, url=url,
    ))


@langsmith_app.command("projects")
def langsmith_projects(
    detail: Annotated[bool, typer.Option("--detail", "-d", help="Show additional details")] = False,
):
    """List all projects."""
    _langsmith_handle(_ns(
        command="langsmith", langsmith_command="projects",
        json=_global["json"], debug=_global["debug"],
        detail=detail,
    ))


@langsmith_app.command("stats")
def langsmith_stats(
    project: Annotated[str, typer.Option("--project", "-p", help="Project name")] = ...,
    since: Annotated[Optional[str], typer.Option("--since", help="Start date")] = None,
    until: Annotated[Optional[str], typer.Option("--until", help="End date")] = None,
):
    """Show usage statistics for a project."""
    _langsmith_handle(_ns(
        command="langsmith", langsmith_command="stats",
        json=_global["json"], debug=_global["debug"],
        project=project, since=since, until=until,
    ))


@langsmith_app.command("friction")
def langsmith_friction(
    project: Annotated[str, typer.Option("--project", "-p", help="Project name")] = ...,
    sessions: Annotated[Optional[int], typer.Option("--sessions", help="Number of sessions to analyze")] = None,
    since: Annotated[Optional[str], typer.Option("--since", help="Start date")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max runs to analyze")] = 100,
    lookback_days: Annotated[int, typer.Option("--lookback-days", help="Days to look back")] = 7,
    min_affected: Annotated[int, typer.Option("--min-affected", help="Min sessions affected")] = 2,
    recommend: Annotated[bool, typer.Option("--recommend", "-r", help="Include recommendations")] = False,
    validate: Annotated[bool, typer.Option("--validate/--no-validate", help="Validate against guidance")] = True,
    json_flag: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
):
    """Analyze traces for friction patterns."""
    _langsmith_handle(_ns(
        command="langsmith", langsmith_command="friction",
        debug=_global["debug"],
        project=project, sessions=sessions, since=since,
        limit=limit, lookback_days=lookback_days, min_affected=min_affected,
        recommend=recommend, validate=validate,
        json=json_flag or _global["json"],
    ))


@langsmith_app.command("sessions")
def langsmith_sessions(
    project: Annotated[str, typer.Option("--project", "-p", help="Project name")] = ...,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of sessions")] = 10,
    since: Annotated[Optional[str], typer.Option("--since", help="Start date")] = None,
    json_flag: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
):
    """List recent sessions with run counts."""
    _langsmith_handle(_ns(
        command="langsmith", langsmith_command="sessions",
        debug=_global["debug"],
        project=project, limit=limit, since=since,
        json=json_flag or _global["json"],
    ))


# ===========================================================================
# QUESTION
# ===========================================================================

question_app = typer.Typer(help="Manage question queue for agent workflows", no_args_is_help=True)
app.add_typer(question_app, name="question")


def _question_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("question")
    from agenticcli.commands import question
    question.handle(args, ctx=cli_ctx)


@question_app.command("list")
def question_list(
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
    status: Annotated[str, typer.Option("--status", help="Filter by status")] = "pending",
    tmux_refresh: Annotated[bool, typer.Option("--tmux-refresh", help="Refresh tmux pane")] = False,
):
    """List questions with optional status filter."""
    _question_handle(_ns(
        command="question", question_command="list",
        json=_global["json"], debug=_global["debug"],
        plan=plan, status=status, tmux_refresh=tmux_refresh,
    ))


@question_app.command("show")
def question_show(
    question_id: str = typer.Argument(..., help="Question ID"),
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Show detailed information for a question."""
    _question_handle(_ns(
        command="question", question_command="show",
        json=_global["json"], debug=_global["debug"],
        question_id=question_id, plan=plan,
    ))


@question_app.command("answer")
def question_answer(
    question_id: Annotated[Optional[str], typer.Argument(help="Question ID to answer")] = None,
    text: Annotated[Optional[str], typer.Option("--text", help="Answer text")] = None,
    confidence: Annotated[Optional[str], typer.Option("--confidence", help="Confidence level")] = None,
    interactive: Annotated[bool, typer.Option("--interactive", "-i", help="Use interactive wizard")] = False,
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Answer a pending question."""
    ns = _ns(
        command="question", question_command="answer",
        json=_global["json"], debug=_global["debug"],
        text=text, confidence=confidence, interactive=interactive, plan=plan,
    )
    # Only set question_id if provided
    if question_id is not None:
        ns.question_id = question_id
    _question_handle(ns)


@question_app.command("ask")
def question_ask(
    text: str = typer.Argument(..., help="Question text"),
    severity: Annotated[str, typer.Option("--severity", help="Severity level")] = "medium",
    context: Annotated[Optional[str], typer.Option("--context", help="Additional context")] = None,
    suggest: Annotated[Optional[List[str]], typer.Option("--suggest", help="Suggested answer (repeatable)")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Create a new question."""
    _question_handle(_ns(
        command="question", question_command="ask",
        json=_global["json"], debug=_global["debug"],
        text=text, severity=severity, context=context, suggest=suggest, plan=plan,
    ))


@question_app.command("defer")
def question_defer(
    question_id: str = typer.Argument(..., help="Question ID to defer"),
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Defer a pending question."""
    _question_handle(_ns(
        command="question", question_command="defer",
        json=_global["json"], debug=_global["debug"],
        question_id=question_id, plan=plan,
    ))


@question_app.command("watch")
def question_watch(
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Watch question folders and display updates."""
    _question_handle(_ns(
        command="question", question_command="watch",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


@question_app.command("watch-daemon")
def question_watch_daemon(
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Start question watcher in background as daemon."""
    _question_handle(_ns(
        command="question", question_command="watch-daemon",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


@question_app.command("watch-stop")
def question_watch_stop():
    """Stop running question watcher daemon."""
    _question_handle(_ns(
        command="question", question_command="watch-stop",
        json=_global["json"], debug=_global["debug"],
    ))


# ===========================================================================
# ENTRYPOINT (alias: ep)
# ===========================================================================

entrypoint_app = typer.Typer(help="Discover and execute workflow entrypoints", no_args_is_help=True)
app.add_typer(entrypoint_app, name="entrypoint")
app.add_typer(entrypoint_app, name="ep", hidden=True)


def _entrypoint_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _require_project(cli_ctx, "entrypoint")
    _stability_banner("entrypoint")
    from agenticcli.commands import entrypoint
    entrypoint.handle(args, ctx=cli_ctx)


@entrypoint_app.command("list")
def entrypoint_list():
    """List all available entrypoints."""
    _entrypoint_handle(_ns(command="entrypoint", entrypoint_command="list", json=_global["json"], debug=_global["debug"]))


@entrypoint_app.command("show")
def entrypoint_show(name: str = typer.Argument(..., help="Entrypoint name")):
    """Show contents of an entrypoint file."""
    _entrypoint_handle(_ns(
        command="entrypoint", entrypoint_command="show",
        json=_global["json"], debug=_global["debug"],
        name=name,
    ))


@entrypoint_app.command("execute")
def entrypoint_execute(
    name: str = typer.Argument(..., help="Entrypoint name"),
    vars: Annotated[Optional[List[str]], typer.Option("--vars", "-v", help="KEY=VALUE substitution")] = None,
    context: Annotated[Optional[str], typer.Option("--context", help="Additional context text")] = None,
    compile: Annotated[bool, typer.Option("--compile", "-c", help="Compile complete context")] = False,
):
    """Execute entrypoint with variable substitution."""
    _entrypoint_handle(_ns(
        command="entrypoint", entrypoint_command="execute",
        json=_global["json"], debug=_global["debug"],
        name=name, vars=vars, context=context, compile=compile,
    ))


# ===========================================================================
# CONTEXT (alias: ctx)
# ===========================================================================

context_app = typer.Typer(help="CCI context retrieval for agents", no_args_is_help=True)
app.add_typer(context_app, name="context")
app.add_typer(context_app, name="ctx", hidden=True)


def _context_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _require_project(cli_ctx, "context")
    _stability_banner("context")
    from agenticcli.commands import context
    context.handle(args, ctx=cli_ctx)


@context_app.command("bootstrap")
def context_bootstrap(
    role: Annotated[Optional[str], typer.Option("--role", "-r", help="Role ID")] = None,
):
    """Get Seed Context: Active Task + Role Guidance + Essential Inputs."""
    _context_handle(_ns(
        command="context", context_command="bootstrap",
        json=_global["json"], debug=_global["debug"],
        role=role,
    ))


@context_app.command("role")
def context_role(
    role_id: str = typer.Argument(..., help="Role ID"),
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "yaml",
):
    """Returns process.yml and manifest.yml content for a role."""
    _context_handle(_ns(
        command="context", context_command="role",
        json=_global["json"], debug=_global["debug"],
        role_id=role_id, format=format,
    ))


@context_app.command("task")
def context_task(
    all: Annotated[bool, typer.Option("--all", "-a", help="Show all tasks")] = False,
):
    """Get active task from Main-First plan."""
    _context_handle(_ns(
        command="context", context_command="task",
        json=_global["json"], debug=_global["debug"],
        **{"all": all},
    ))


@context_app.command("inputs")
def context_inputs(
    role: Annotated[str, typer.Option("--role", "-r", help="Role ID")] = ...,
    resolve: Annotated[bool, typer.Option("--resolve", help="Expand layer references")] = False,
):
    """Returns input files for a role with path resolution."""
    _context_handle(_ns(
        command="context", context_command="inputs",
        json=_global["json"], debug=_global["debug"],
        role=role, resolve=resolve,
    ))


@context_app.command("generate-agent")
def context_generate_agent(
    role_id: str = typer.Argument(..., help="Role ID"),
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path")] = None,
):
    """Generate thin-client agent file from bootstrap template."""
    _context_handle(_ns(
        command="context", context_command="generate-agent",
        json=_global["json"], debug=_global["debug"],
        role_id=role_id, output=output,
    ))


# ===========================================================================
# PLAN (deeply nested: plan task start, plan phase add, etc.)
# ===========================================================================

plan_app = typer.Typer(help="Manage planning folders and track task status", no_args_is_help=True)
app.add_typer(plan_app, name="plan")


def _plan_handle(args):
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _require_project(cli_ctx, "plan")
    _stability_banner("plan")
    from agenticcli.commands import plan
    plan.handle(args, ctx=cli_ctx)


# --- plan new ---
@plan_app.command("new")
def plan_new(
    objective: Annotated[Optional[str], typer.Argument(help="Planning objective description")] = None,
    branch: Annotated[Optional[str], typer.Option("--branch", "-b", help="Git branch name (auto-generated from objective if omitted)")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Plan folder description suffix")] = None,
    base: Annotated[str, typer.Option("--base", help="Base branch for worktree")] = "main",
    execute: Annotated[bool, typer.Option("--execute", "-x", help="Auto-execute after planning completes")] = False,
    max_turns: Annotated[int, typer.Option("--max-turns", help="Max turns for planner agent")] = 25,
    dangerously_skip_permissions: Annotated[bool, typer.Option(
        "--dangerously-skip-permissions", help="Skip permission prompts for spawned sessions")] = False,
):
    """Create plan and spawn planner agent."""
    if not objective:
        from agenticcli.console import print_error
        print_error("Objective is required. Usage: agentic plan new \"your objective\"")
        raise typer.Exit(1)
    _plan_handle(_ns(
        command="plan", plan_command="new",
        json=_global["json"], debug=_global["debug"],
        objective=objective, branch=branch, description=description,
        base=base, execute=execute, max_turns=max_turns,
        dangerously_skip_permissions=dangerously_skip_permissions,
    ))


# --- plan init ---
@plan_app.command("init")
def plan_init(
    branch: str = typer.Argument(..., help="Branch name for worktree"),
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Plan description")] = None,
    base: Annotated[str, typer.Option("--base", "-b", help="Base branch")] = "main",
    objective: Annotated[Optional[str], typer.Option("--objective", "-o", help="Plan objective")] = None,
):
    """Initialize worktree and plan folder with proper naming."""
    _plan_handle(_ns(
        command="plan", plan_command="init",
        json=_global["json"], debug=_global["debug"],
        branch=branch, description=description, base=base, objective=objective,
    ))


# --- plan bootstrap ---
@plan_app.command("bootstrap")
def plan_bootstrap(
    branch: str = typer.Argument(..., help="Branch name for the plan"),
    objective: Annotated[str, typer.Option("--objective", "-o", help="Plan objective")] = ...,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Plan description")] = None,
):
    """Bootstrap a new plan with an objective."""
    _plan_handle(_ns(
        command="plan", plan_command="bootstrap",
        json=_global["json"], debug=_global["debug"],
        branch=branch, objective=objective, description=description,
    ))


# --- plan scaffold ---
@plan_app.command("scaffold")
def plan_scaffold(
    name: str = typer.Argument(..., help="Folder name"),
    worktree: Annotated[Optional[str], typer.Option("--worktree", "-w", help="Worktree path")] = None,
):
    """Create planning folder structure."""
    _plan_handle(_ns(
        command="plan", plan_command="scaffold",
        json=_global["json"], debug=_global["debug"],
        name=name, worktree=worktree,
    ))


# --- plan status ---
@plan_app.command("status")
def plan_status(path: Optional[str] = typer.Argument(None, help="Path to plan folder")):
    """Show plan status and task summary."""
    _plan_handle(_ns(command="plan", plan_command="status", json=_global["json"], debug=_global["debug"], path=path))


# --- plan validate ---
@plan_app.command("validate")
def plan_validate(
    path: str = typer.Argument(..., help="Path to plan folder"),
    strict: Annotated[bool, typer.Option("--strict", help="Fail on stub templates")] = False,
    check_fences: Annotated[bool, typer.Option("--check-fences", help="Validate UAT fence compliance")] = False,
):
    """Validate plan folder structure and YAML."""
    _plan_handle(_ns(
        command="plan", plan_command="validate",
        json=_global["json"], debug=_global["debug"],
        path=path, strict=strict, check_fences=check_fences,
    ))


# --- plan list ---
@plan_app.command("list")
def plan_list():
    """List all plans in the repository."""
    _plan_handle(_ns(command="plan", plan_command="list", json=_global["json"], debug=_global["debug"]))


# --- plan archive ---
@plan_app.command("archive")
def plan_archive(path: str = typer.Argument(..., help="Path to plan folder to archive")):
    """Copy plan to completed folder."""
    _plan_handle(_ns(command="plan", plan_command="archive", json=_global["json"], debug=_global["debug"], path=path))


# --- plan unarchive ---
@plan_app.command("unarchive")
def plan_unarchive(
    plan: Annotated[str, typer.Option("--plan", "-p", help="Plan folder name")] = ...,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Move plan from completed back to live."""
    _plan_handle(_ns(
        command="plan", plan_command="unarchive",
        json=_global["json"], debug=_global["debug"],
        plan=plan, force=force,
    ))


# --- plan task (nested sub-app) ---
plan_task_app = typer.Typer(help="Manage tasks in plan files", no_args_is_help=True)
plan_app.add_typer(plan_task_app, name="task")


@plan_task_app.command("start")
def plan_task_start(
    task_id: str = typer.Argument(..., help="Task ID"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    no_archive: Annotated[bool, typer.Option("--no-archive", help="Suppress auto-archival")] = False,
):
    """Mark task as in_progress."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="start",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=plan, no_archive=no_archive,
    ))


@plan_task_app.command("complete")
def plan_task_complete(
    task_id: str = typer.Argument(..., help="Task ID"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    no_archive: Annotated[bool, typer.Option("--no-archive", help="Suppress auto-archival")] = False,
):
    """Mark task as completed."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="complete",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=plan, no_archive=no_archive,
    ))


@plan_task_app.command("prefill")
def plan_task_prefill(
    preset: Annotated[str, typer.Option("--preset", "-t", help="Preset name")] = ...,
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
):
    """Load preset task list from template."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="prefill",
        json=_global["json"], debug=_global["debug"],
        preset=preset, plan=plan, dry_run=dry_run,
    ))


@plan_task_app.command("list")
def plan_task_list(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    status: Annotated[str, typer.Option("--status", "-s", help="Filter by status")] = "all",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show full details")] = False,
):
    """Show all tasks in current plan folder."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=plan, status=status, verbose=verbose,
    ))


@plan_task_app.command("status")
def plan_task_status(
    task_id: str = typer.Argument(..., help="Task ID"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
):
    """Show detailed status for a specific task."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="status",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=plan,
    ))


@plan_task_app.command("add")
def plan_task_add(
    description: str = typer.Argument(..., help="Task description"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    phase: Annotated[Optional[str], typer.Option("--phase", "-ph", help="Phase ID")] = None,
    id: Annotated[Optional[str], typer.Option("--id", help="Custom task ID")] = None,
    priority: Annotated[str, typer.Option("--priority", help="Task priority")] = "medium",
):
    """Add new task to plan."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="add",
        json=_global["json"], debug=_global["debug"],
        description=description, plan=plan, phase=phase, id=id, priority=priority,
    ))


@plan_task_app.command("update")
def plan_task_update(
    task_id: str = typer.Argument(..., help="Task ID"),
    status: Annotated[str, typer.Option("--status", "-s", help="New status")] = ...,
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    note: Annotated[Optional[str], typer.Option("--note", "-n", help="Completion note")] = None,
    no_archive: Annotated[bool, typer.Option("--no-archive", help="Suppress auto-archival")] = False,
):
    """Update task status in plan file."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="update",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, status=status, plan=plan, note=note, no_archive=no_archive,
    ))


@plan_task_app.command("current")
def plan_task_current(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
):
    """Get the current task to work on."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="current",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


# --- plan move (nested sub-app) ---
plan_move_app = typer.Typer(help="Move completed tasks or archive folder", no_args_is_help=True)
plan_app.add_typer(plan_move_app, name="move")


@plan_move_app.command("task")
def plan_move_task(
    task_id: str = typer.Argument(..., help="Task ID to move"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Move even with uncommitted changes")] = False,
):
    """Move a single completed task."""
    _plan_handle(_ns(
        command="plan", plan_command="move", move_type="task",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=plan, dry_run=dry_run, force=force,
    ))


@plan_move_app.command("tasks")
def plan_move_tasks(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Move even with uncommitted changes")] = False,
):
    """Move all completed tasks."""
    _plan_handle(_ns(
        command="plan", plan_command="move", move_type="tasks",
        json=_global["json"], debug=_global["debug"],
        plan=plan, dry_run=dry_run, force=force,
    ))


@plan_move_app.command("folder")
def plan_move_folder(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Archive even with uncommitted changes")] = False,
):
    """Archive the plan folder."""
    _plan_handle(_ns(
        command="plan", plan_command="move", move_type="folder",
        json=_global["json"], debug=_global["debug"],
        plan=plan, dry_run=dry_run, force=force,
    ))


# --- plan orchestration (nested sub-app) ---
plan_orch_app = typer.Typer(help="Manage plan orchestration MMD files", no_args_is_help=True)
plan_app.add_typer(plan_orch_app, name="orchestration")


@plan_orch_app.command("generate")
def plan_orchestration_generate(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing")] = False,
):
    """Generate orchestration MMD from plan YAML."""
    _plan_handle(_ns(
        command="plan", plan_command="orchestration", orchestration_action="generate",
        json=_global["json"], debug=_global["debug"],
        plan=plan, output=output, force=force,
    ))


@plan_orch_app.command("validate")
def plan_orchestration_validate(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
):
    """Validate orchestration MMD against plan YAML."""
    _plan_handle(_ns(
        command="plan", plan_command="orchestration", orchestration_action="validate",
        json=_global["json"], debug=_global["debug"],
        plan=plan, strict=strict,
    ))


# --- plan phase (nested sub-app) ---
plan_phase_app = typer.Typer(help="Manage plan phases", no_args_is_help=True)
plan_app.add_typer(plan_phase_app, name="phase")


@plan_phase_app.command("add")
def plan_phase_add(
    id: Annotated[str, typer.Option("--id", help="Phase ID")] = ...,
    name: Annotated[str, typer.Option("--name", help="Phase name")] = ...,
    description: Annotated[Optional[str], typer.Option("--description", help="Phase description")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
):
    """Add a new phase to plan_build.yml."""
    _plan_handle(_ns(
        command="plan", plan_command="phase", phase_action="add",
        json=_global["json"], debug=_global["debug"],
        id=id, name=name, description=description, plan=plan,
    ))


@plan_phase_app.command("list")
def plan_phase_list(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
):
    """List all phases in the plan."""
    _plan_handle(_ns(
        command="plan", plan_command="phase", phase_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


@plan_phase_app.command("update")
def plan_phase_update(
    phase_id: str = typer.Argument(..., help="Phase ID to update"),
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="New status")] = None,
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New name")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
):
    """Update a phase in plan_build.yml."""
    _plan_handle(_ns(
        command="plan", plan_command="phase", phase_action="update",
        json=_global["json"], debug=_global["debug"],
        phase_id=phase_id, status=status, name=name, plan=plan,
    ))


# --- plan stories (nested sub-app) ---
plan_stories_app = typer.Typer(help="Manage user stories in plan files", no_args_is_help=True)
plan_app.add_typer(plan_stories_app, name="stories")


@plan_stories_app.command("list")
def plan_stories_list(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
):
    """List user stories from plan YAML."""
    _plan_handle(_ns(
        command="plan", plan_command="stories", stories_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


@plan_stories_app.command("test")
def plan_stories_test(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "yaml",
):
    """Generate blind test scenarios from user stories."""
    _plan_handle(_ns(
        command="plan", plan_command="stories", stories_action="test",
        json=_global["json"], debug=_global["debug"],
        plan=plan, output=output, format=format,
    ))


# ===========================================================================
# COMMAND CATEGORIES (used by context/require_project checks above)
# ===========================================================================

GLOBAL_COMMANDS = {
    "setup", "config", "cfg", "preferences", "prefs", "pref",
    "update", "rebuild", "health", "state", "session", "loop",
    "env", "langsmith", "ls", "completion", "question",
}

PROJECT_COMMANDS = {
    "worktree", "wt", "plan", "inputs", "template", "tpl",
    "stories", "st", "manifest", "mf", "cicd",
    "context", "ctx", "entrypoint", "ep",
}


# ===========================================================================
# run_cli() — the public entry point called from entry.py
# ===========================================================================

def run_cli():
    """Main CLI entry point. Invokes the Typer app."""
    app()
