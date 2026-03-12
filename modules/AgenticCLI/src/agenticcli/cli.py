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


def _stability_banner(command: str):
    """Display stability banner for non-stable commands."""
    from agenticcli.console import print_stability_banner
    print_stability_banner(command)


def _dispatch(module_name: str, args, *, require_project: bool = False, banner: str | None = None):
    """Unified dispatcher for command modules.

    Replaces the 19+ identical _*_handle() functions with a single helper.
    Each call: resolves CLI context, optionally checks project scope,
    shows stability banner, then delegates to module.handle(args, ctx).
    """
    import importlib
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    if require_project:
        cli_ctx.require_project(banner or module_name)
    _stability_banner(banner or module_name)
    mod = importlib.import_module(f"agenticcli.commands.{module_name}")
    mod.handle(args, ctx=cli_ctx)


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
# SETUP GROUP (setup init, setup health, setup update, setup rebuild)
# ===========================================================================

setup_group = typer.Typer(help="Setup, health checks, and package management", no_args_is_help=True)
app.add_typer(setup_group, name="setup")


@setup_group.command("init")
def setup_init(
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing configuration")] = False,
):
    """Interactive setup wizard for initial configuration."""
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("setup")
    from agenticcli.commands import setup as _mod
    _mod.handle(_ns(command="setup", json=_global["json"], debug=_global["debug"], force=force), ctx=cli_ctx)


@setup_group.command("health")
def setup_health():
    """Check CLI health, dependencies, and configuration status."""
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("health")
    from agenticcli.commands import health as _mod
    _mod.handle(_ns(command="health", json=_global["json"], debug=_global["debug"]), ctx=cli_ctx)


@setup_group.command("update")
def setup_update():
    """Reinstall AgenticCLI from source using uv sync."""
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("update")
    from agenticcli.commands import package
    package.handle_update(_ns(command="update", json=_global["json"], debug=_global["debug"]), ctx=cli_ctx)


@setup_group.command("rebuild")
def setup_rebuild():
    """Full rebuild: clean artifacts, rebuild package, reinstall."""
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("rebuild")
    from agenticcli.commands import package
    package.handle_rebuild(_ns(command="rebuild", json=_global["json"], debug=_global["debug"]), ctx=cli_ctx)


# ===========================================================================
# CONFIGURE GROUP (configure config, configure preferences, configure env, configure state)
# ===========================================================================

configure_group = typer.Typer(help="Configuration, preferences, environment, and state management", no_args_is_help=True)
app.add_typer(configure_group, name="configure")
app.add_typer(configure_group, name="cfg", hidden=True)

# ===========================================================================
# PREFERENCES (nested under configure)
# ===========================================================================

preferences_app = typer.Typer(help="Manage user preferences", no_args_is_help=True)
configure_group.add_typer(preferences_app, name="preferences")
configure_group.add_typer(preferences_app, name="prefs", hidden=True)
configure_group.add_typer(preferences_app, name="pref", hidden=True)



def _prefs_handle(args):
    _dispatch("preferences", args)


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
configure_group.add_typer(config_app, name="config")



def _config_handle(args):
    _dispatch("config", args)


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
configure_group.add_typer(state_app, name="state")



def _state_handle(args):
    _dispatch("state", args)


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
configure_group.add_typer(env_app, name="env")



def _env_handle(args):
    _dispatch("env", args)


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
# STORIES (alias: st)
# ===========================================================================

stories_app = typer.Typer(help="Find and manage user stories", no_args_is_help=True)


@app.command("stories", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_stories(ctx: typer.Context):
    """Deprecated: use 'agentic agent stories'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic stories' has moved. Use 'agentic agent stories' instead.")
    raise typer.Exit(1)


@app.command("st", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_st(ctx: typer.Context):
    """Deprecated: use 'agentic agent stories'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic st' has moved. Use 'agentic agent stories' instead.")
    raise typer.Exit(1)


def _stories_handle(args):
    _dispatch("stories", args, require_project=True)


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
    status: Annotated[str, typer.Option("--status", "-s", help="Test result: pass, fail, skip, regression")] = ...,
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
    coverage: Annotated[bool, typer.Option("--coverage", help="Cross-reference pytest @pytest.mark.story markers against story inventory")] = False,
):
    """Show pass/fail/untested summary."""
    _stories_handle(_ns(command="stories", stories_command="report", json=_global["json"], debug=_global["debug"], project=project, coverage=coverage))


@stories_app.command("untested")
def stories_untested(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
):
    """List stories needing validation."""
    _stories_handle(_ns(command="stories", stories_command="untested", json=_global["json"], debug=_global["debug"], project=project))


@stories_app.command("batch-update")
def stories_batch_update(
    plan: Annotated[str, typer.Option("--plan", help="Plan folder name")] = ...,
    status: Annotated[str, typer.Option("--status", "-s", help="Test result: pass, fail, skip, regression")] = ...,
    notes: Annotated[Optional[str], typer.Option("--notes", "-n", help="Test notes")] = None,
):
    """Update all affected stories in a plan at once."""
    _stories_handle(_ns(
        command="stories", stories_command="batch-update",
        json=_global["json"], debug=_global["debug"],
        plan=plan, status=status, notes=notes,
    ))


@stories_app.command("affected")
def stories_affected(
    plan: Annotated[str, typer.Option("--plan", help="Plan folder name")] = ...,
):
    """List affected stories for a plan with their test status."""
    _stories_handle(_ns(
        command="stories", stories_command="affected",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


# ===========================================================================
# MANIFEST (alias: mf)
# ===========================================================================

manifest_app = typer.Typer(help="Manage agent manifests", no_args_is_help=True)


@app.command("manifest", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_manifest(ctx: typer.Context):
    """Deprecated: use 'agentic agent manifest'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic manifest' has moved. Use 'agentic agent manifest' instead.")
    raise typer.Exit(1)


@app.command("mf", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_mf(ctx: typer.Context):
    """Deprecated: use 'agentic agent manifest'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic mf' has moved. Use 'agentic agent manifest' instead.")
    raise typer.Exit(1)


def _manifest_handle(args):
    _dispatch("manifest", args, require_project=True)


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
# DEVOPS GROUP
# ===========================================================================

devops_group = typer.Typer(help="DevOps tools", no_args_is_help=True)
app.add_typer(devops_group, name="devops")

@devops_group.command("worktree", context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def worktree_deprecated(ctx: typer.Context):
    """[DEPRECATED] The worktree system has been removed."""
    _dispatch("worktree", _ns(command="worktree", worktree_command="deprecated"), require_project=False)


@devops_group.command("wt", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def worktree_deprecated_alias(ctx: typer.Context):
    """[DEPRECATED] The worktree system has been removed."""
    _dispatch("worktree", _ns(command="worktree", worktree_command="deprecated"), require_project=False)


# ===========================================================================
# SESSION
# ===========================================================================

session_app = typer.Typer(help="Manage Claude Code sessions, orchestration, and agents", no_args_is_help=True)
app.add_typer(session_app, name="session")



def _session_handle(args):
    _dispatch("session", args)


@session_app.command("spawn")
def session_spawn(
    prompt: Annotated[Optional[str], typer.Option("--prompt", "-p", help="The prompt to send")] = None,
    role: Annotated[Optional[str], typer.Option("--role", help="Agent role to spawn")] = None,
    task: Annotated[Optional[str], typer.Option("--task", help="Task ID to spawn agent for")] = None,
    epic: Annotated[Optional[str], typer.Option("--epic", help="Epic folder name")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", help="[Deprecated: use --epic] Epic folder name")] = None,
    max_turns: Annotated[Optional[int], typer.Option("--max-turns", "-m", help="Maximum agentic turns")] = None,
    background: Annotated[bool, typer.Option("--background", "-b", help="Run in background")] = False,
    directory: Annotated[Optional[str], typer.Option("--directory", "-d", help="Working directory")] = None,
    dangerously_skip_permissions: Annotated[bool, typer.Option(
        "--dangerously-skip-permissions/--no-dangerously-skip-permissions", help="Skip permission prompts (default: enabled)")] = True,
    tmux: Annotated[bool, typer.Option(
        "--tmux", help="Spawn session in a tmux pane")] = False,
    dry_run: Annotated[bool, typer.Option(
        "--dry-run", help="Report spawn diagnostics without actually spawning")] = False,
):
    """Spawn a new Claude Code session with a prompt."""
    # Mutual exclusion check (--role and --task cannot both be set)
    if role and task:
        from agenticcli.console import print_error
        print_error("--role and --task are mutually exclusive.")
        raise typer.Exit(1)

    # --plan is a deprecated alias for --epic; --epic takes precedence
    resolved_epic = epic or plan

    _session_handle(_ns(
        command="session", session_command="spawn",
        json=_global["json"], debug=_global["debug"],
        prompt=prompt, role=role, task=task, plan=resolved_epic,
        max_turns=max_turns, background=background,
        directory=directory,
        dangerously_skip_permissions=dangerously_skip_permissions,
        tmux=tmux,
        dry_run=dry_run,
    ))


@session_app.command("list")
def session_list(
    all_sessions: Annotated[bool, typer.Option("--all", "-a", help="Show all sessions including completed")] = False,
    type_filter: Annotated[Optional[str], typer.Option("--type", "-t", help="Filter by type: session, loop, orchestration")] = None,
):
    """List sessions, loops, and orchestrations (active only by default, use --all for all)."""
    _session_handle(_ns(command="session", session_command="list", json=_global["json"], debug=_global["debug"], show_all=all_sessions, type=type_filter))


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


@session_app.command("healthcheck")
def session_healthcheck(
    session_id: Annotated[str, typer.Argument(help="Session ID (or prefix)")],
    json_output: Annotated[bool, typer.Option("-j", "--json", help="JSON output")] = False,
    diagnose: Annotated[bool, typer.Option("--diagnose", help="Auto-spawn diagnostic planner for unhealthy sessions")] = False,
):
    """Check health and vitality of a session."""
    _session_handle(_ns(
        command="session", session_command="healthcheck",
        json=_global["json"], debug=_global["debug"],
        session_id=session_id, json_output=json_output,
        diagnose=diagnose,
    ))


@session_app.command("logs")
def session_logs(
    session_id: Annotated[str, typer.Argument(help="Session ID (or prefix)")],
    stderr: Annotated[bool, typer.Option("--stderr", help="Show stderr instead of stdout")] = False,
    lines: Annotated[int, typer.Option("-n", "--lines", help="Number of lines to show")] = 50,
    follow: Annotated[bool, typer.Option("-f", "--follow", help="Follow log output (tail -f)")] = False,
):
    """View stdout/stderr logs for a session."""
    _session_handle(_ns(
        command="session", session_command="logs",
        json=_global["json"], debug=_global["debug"],
        session_id=session_id, stderr=stderr,
        lines=lines, follow=follow,
    ))


orchestrate_app = typer.Typer(help="Run automated orchestration commands", no_args_is_help=True)
session_app.add_typer(orchestrate_app, name="orchestrate")

# --- Ralph (nested under orchestrate) ---
from agenticcli.commands.ralph import app as ralph_app
orchestrate_app.add_typer(ralph_app, name="ralph")


@orchestrate_app.command("planning")
def session_orchestrate_planning(
    epic: Annotated[Optional[str], typer.Option("--epic", help="Epic folder name or short ID (e.g. '260305AG')")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", help="[Deprecated: use --epic] Epic folder name")] = None,
    prompt: Annotated[Optional[str], typer.Option("--prompt", help="Additional prompt/instructions appended to each spawned agent")] = None,
    background: Annotated[bool, typer.Option("--background", "-b", help="Run in background")] = False,
    max_iterations: Annotated[int, typer.Option("--max-iterations", "-n", help="Max iterations")] = 10,
    completion_promise: Annotated[Optional[str], typer.Option("--completion-promise", "-c", help="Completion text")] = None,
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Project filter")] = None,
    directory: Annotated[Optional[str], typer.Option("--directory", "-d", help="Working directory")] = None,
    dangerously_skip_permissions: Annotated[bool, typer.Option("--dangerously-skip-permissions/--no-dangerously-skip-permissions", help="Skip permission prompts (default: enabled)")] = True,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Create tmux layout, verify panes, print JSON, then exit")] = False,
    budget: Annotated[float, typer.Option("--budget", help="Max USD cost before halting")] = 50.0,
):
    """Run automated orchestration planning for all plans that need it."""
    resolved_epic = epic or plan
    from agenticcli.commands.orchestrate import cmd_orchestrate
    cmd_orchestrate(_ns(
        command="orchestrate",
        json=_global["json"], debug=_global["debug"],
        action="planning", plan=resolved_epic, prompt=prompt, background=background,
        max_iterations=max_iterations, completion_promise=completion_promise,
        project=project, directory=directory,
        dangerously_skip_permissions=dangerously_skip_permissions,
        dry_run=dry_run, budget_usd=budget,
    ))


@orchestrate_app.command("executing")
def session_orchestrate_executing(
    epic: Annotated[Optional[str], typer.Option("--epic", help="Epic folder name or short ID (e.g. '260305AG')")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", help="[Deprecated: use --epic] Epic folder name")] = None,
    background: Annotated[bool, typer.Option("--background", "-b", help="Run in background")] = False,
    max_iterations: Annotated[int, typer.Option("--max-iterations", "-n", help="Max phase executions")] = 10,
    completion_promise: Annotated[Optional[str], typer.Option("--completion-promise", "-c", help="Completion text")] = None,
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Project filter")] = None,
    directory: Annotated[Optional[str], typer.Option("--directory", "-d", help="Working directory")] = None,
    dangerously_skip_permissions: Annotated[bool, typer.Option("--dangerously-skip-permissions/--no-dangerously-skip-permissions", help="Skip permission prompts for spawned agents (default: enabled)")] = True,
    budget: Annotated[float, typer.Option("--budget", help="Max USD cost before halting")] = 50.0,
):
    """Run automated orchestration execution for plans with completed MMDs."""
    resolved_epic = epic or plan
    from agenticcli.commands.orchestrate import cmd_orchestrate
    cmd_orchestrate(_ns(
        command="orchestrate",
        json=_global["json"], debug=_global["debug"],
        action="executing", plan=resolved_epic, background=background,
        max_iterations=max_iterations, completion_promise=completion_promise,
        project=project, directory=directory,
        dangerously_skip_permissions=dangerously_skip_permissions,
        dry_run=False, budget_usd=budget,
    ))



# ===========================================================================
# LANGSMITH (alias: ls)
# ===========================================================================

langsmith_app = typer.Typer(help="Query LangSmith traces, runs, projects, and statistics", no_args_is_help=True)
app.add_typer(langsmith_app, name="langsmith")
app.add_typer(langsmith_app, name="ls", hidden=True)


def _langsmith_handle(args):
    _dispatch("langsmith", args)


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
    _dispatch("question", args)


@question_app.command("list", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def question_list(ctx: typer.Context):
    """Deprecated: use 'agentic plan question list'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic question list' has moved. Use 'agentic plan question list' instead.")
    raise typer.Exit(1)


@question_app.command("show", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def question_show(ctx: typer.Context):
    """Deprecated: use 'agentic plan question show'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic question show' has moved. Use 'agentic plan question show' instead.")
    raise typer.Exit(1)


@question_app.command("answer", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def question_answer(ctx: typer.Context):
    """Deprecated: use 'agentic plan question answer'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic question answer' has moved. Use 'agentic plan question answer' instead.")
    raise typer.Exit(1)


@question_app.command("ask", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def question_ask(ctx: typer.Context):
    """Deprecated: use 'agentic agent question ask'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic question ask' has moved. Use 'agentic agent question ask' instead.")
    raise typer.Exit(1)


@question_app.command("defer", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def question_defer(ctx: typer.Context):
    """Deprecated: use 'agentic agent question defer'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic question defer' has moved. Use 'agentic agent question defer' instead.")
    raise typer.Exit(1)


@question_app.command("watch", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def question_watch(ctx: typer.Context):
    """Deprecated: use 'agentic agent question watch'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic question watch' has moved. Use 'agentic agent question watch' instead.")
    raise typer.Exit(1)


@question_app.command("watch-daemon", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def question_watch_daemon(ctx: typer.Context):
    """Deprecated: use 'agentic agent question watch-daemon'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic question watch-daemon' has moved. Use 'agentic agent question watch-daemon' instead.")
    raise typer.Exit(1)


@question_app.command("watch-stop", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def question_watch_stop(ctx: typer.Context):
    """Deprecated: use 'agentic agent question watch-stop'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic question watch-stop' has moved. Use 'agentic agent question watch-stop' instead.")
    raise typer.Exit(1)


@question_app.command("dashboard", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def question_dashboard(ctx: typer.Context):
    """Deprecated: use 'agentic plan question dashboard'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic question dashboard' has moved. Use 'agentic plan question dashboard' instead.")
    raise typer.Exit(1)


# ===========================================================================
# ENTRYPOINT (alias: ep)
# ===========================================================================

entrypoint_app = typer.Typer(help="Discover and execute workflow entrypoints", no_args_is_help=True)


@app.command("entrypoint", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_entrypoint(ctx: typer.Context):
    """Deprecated: use 'agentic agent entrypoint'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic entrypoint' has moved. Use 'agentic agent entrypoint' instead.")
    raise typer.Exit(1)


@app.command("ep", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_ep(ctx: typer.Context):
    """Deprecated: use 'agentic agent entrypoint'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic ep' has moved. Use 'agentic agent entrypoint' instead.")
    raise typer.Exit(1)


def _entrypoint_handle(args):
    _dispatch("entrypoint", args, require_project=True)


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


@app.command("context", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_context(ctx: typer.Context):
    """Deprecated: use 'agentic agent context'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic context' has moved. Use 'agentic agent context' instead.")
    raise typer.Exit(1)


@app.command("ctx", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_ctx(ctx: typer.Context):
    """Deprecated: use 'agentic agent context'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic ctx' has moved. Use 'agentic agent context' instead.")
    raise typer.Exit(1)


def _context_handle(args):
    _dispatch("context", args, require_project=True)


@context_app.command("bootstrap")
def context_bootstrap(
    role: Annotated[Optional[str], typer.Option("--role", "-r", help="Role ID")] = None,
    epic: Annotated[Optional[str], typer.Option("--epic", "-e", help="Epic folder name (skip auto-resolution)")] = None,
):
    """Get Seed Context: Active Task + Role Guidance + Essential Inputs."""
    _context_handle(_ns(
        command="context", context_command="bootstrap",
        json=_global["json"], debug=_global["debug"],
        role=role, epic=epic,
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
    role: Annotated[Optional[str], typer.Option("--role", "-r", help="Role ID")] = None,
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
    """All plan commands are removed. Print error and exit."""
    import json as _json
    json_mode = getattr(args, 'json', False) or getattr(args, 'json_output', False)
    if json_mode:
        print(_json.dumps({"error": "Command removed. Use 'agentic epic ...' instead."}))
    else:
        import sys as _sys
        print("Command removed. Use 'agentic epic ...' instead.", file=_sys.stderr)
        print("See 'agentic epic --help' for available commands.", file=_sys.stderr)
    raise typer.Exit(1)


def _epic_handle(args):
    _dispatch("epic", args, require_project=True)


# --- plan new ---
@plan_app.command("new", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def plan_new(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan new'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan new' has moved. Use 'agentic agent plan new' instead.")
    raise typer.Exit(1)


# --- plan init ---
@plan_app.command("init", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def plan_init(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan init'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan init' has moved. Use 'agentic agent plan init' instead.")
    raise typer.Exit(1)


# --- plan bootstrap ---
@plan_app.command("bootstrap", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def plan_bootstrap(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan bootstrap'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan bootstrap' has moved. Use 'agentic agent plan bootstrap' instead.")
    raise typer.Exit(1)


# --- plan scaffold ---
@plan_app.command("scaffold", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def plan_scaffold(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan scaffold'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan scaffold' has moved. Use 'agentic agent plan scaffold' instead.")
    raise typer.Exit(1)


# --- plan status ---
@plan_app.command("status")
def plan_status(
    path: Optional[str] = typer.Argument(None, help="Path to plan folder"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Command removed. Use 'agentic epic status' instead."""
    _plan_handle(_ns(json=_global["json"]))


# --- plan validate ---
@plan_app.command("validate", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def plan_validate(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan validate'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan validate' has moved. Use 'agentic agent plan validate' instead.")
    raise typer.Exit(1)


# --- plan list ---
@plan_app.command("list")
def plan_list():
    """Command removed. Use 'agentic epic list' instead."""
    _plan_handle(_ns(json=_global["json"]))


# --- plan archive ---
@plan_app.command("archive", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def plan_archive(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan archive'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan archive' has moved. Use 'agentic agent plan archive' instead.")
    raise typer.Exit(1)


# --- plan unarchive ---
@plan_app.command("unarchive", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def plan_unarchive(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan unarchive'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan unarchive' has moved. Use 'agentic agent plan unarchive' instead.")
    raise typer.Exit(1)


# --- plan task (nested sub-app) ---
plan_task_app = typer.Typer(help="Manage tasks in plan files", no_args_is_help=True)
@plan_app.command("task", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_plan_task(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan task'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan task' has moved. Use 'agentic agent plan task' instead.")
    raise typer.Exit(1)


@plan_task_app.command("start")
def plan_task_start(
    task_id: str = typer.Argument(..., help="Task ID"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
):
    """Mark task as in_progress."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="start",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=plan,
    ))


@plan_task_app.command("complete")
def plan_task_complete(
    task_id: str = typer.Argument(..., help="Task ID"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
):
    """Mark task as completed."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="complete",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=plan,
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


def _validate_status(value: str) -> str:
    valid = ["all", "pending", "in_progress", "completed"]
    if value not in valid:
        raise typer.BadParameter(f"Invalid choice: '{value}'. Choose from: {', '.join(valid)}")
    return value


def _validate_priority(value: str) -> str:
    valid = ["low", "medium", "high"]
    if value not in valid:
        raise typer.BadParameter(f"Invalid choice: '{value}'. Choose from: {', '.join(valid)}")
    return value


@plan_task_app.command("list")
def plan_task_list(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    status: Annotated[str, typer.Option("--status", "-s", help="Filter by status", callback=_validate_status)] = "all",
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
    priority: Annotated[str, typer.Option("--priority", help="Task priority", callback=_validate_priority)] = "medium",
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
):
    """Update task status in plan file."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="update",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, status=status, plan=plan, note=note,
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
@plan_app.command("move", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_plan_move(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan move'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan move' has moved. Use 'agentic agent plan move' instead.")
    raise typer.Exit(1)


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
@plan_app.command("orchestration", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_plan_orchestration(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan orchestration'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan orchestration' has moved. Use 'agentic agent plan orchestration' instead.")
    raise typer.Exit(1)


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
@plan_app.command("phase", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_plan_phase(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan phase'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan phase' has moved. Use 'agentic agent plan phase' instead.")
    raise typer.Exit(1)


@plan_phase_app.command("add")
def plan_phase_add(
    id: Annotated[str, typer.Option("--id", help="Phase ID")] = ...,
    name: Annotated[str, typer.Option("--name", help="Phase name")] = ...,
    description: Annotated[Optional[str], typer.Option("--description", help="Phase description")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
):
    """Add a new phase to the epic in TinyDB."""
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
    """Update a phase in TinyDB."""
    _plan_handle(_ns(
        command="plan", plan_command="phase", phase_action="update",
        json=_global["json"], debug=_global["debug"],
        phase_id=phase_id, status=status, name=name, plan=plan,
    ))


# --- plan stories (nested sub-app) ---
plan_stories_app = typer.Typer(help="Manage user stories in plan files", no_args_is_help=True)
@plan_app.command("stories", hidden=True, context_settings={"allow_extra_args": True, "allow_interspersed_args": False})
def _deprecated_plan_stories(ctx: typer.Context):
    """Deprecated: use 'agentic agent plan stories'."""
    from agenticcli.console import print_error
    print_error("Command 'agentic plan stories' has moved. Use 'agentic agent plan stories' instead.")
    raise typer.Exit(1)


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


# --- plan db (nested sub-app) ---
plan_db_app = typer.Typer(help="Manage plan TinyDB database", no_args_is_help=True)
plan_app.add_typer(plan_db_app, name="db", hidden=True)


@plan_db_app.command("sync")
def plan_db_sync():
    """[DISABLED] db sync is no longer available. TinyDB is the sole data store."""
    _plan_handle(_ns(command="plan", plan_command="db", db_action="sync", json=_global["json"], debug=_global["debug"]))


@plan_db_app.command("status")
def plan_db_status():
    """Show TinyDB database statistics."""
    _plan_handle(_ns(command="plan", plan_command="db", db_action="status", json=_global["json"], debug=_global["debug"]))


# --- plan cancel (user-facing) ---
@plan_app.command("cancel")
def plan_cancel(
    path: Optional[str] = typer.Argument(None, help="Plan name or path"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Command removed. Use 'agentic epic cancel' instead."""
    _plan_handle(_ns(json=_global["json"]))


# --- plan question ---
plan_question_app = typer.Typer(help="Manage question queue for plan workflows", no_args_is_help=True)
plan_app.add_typer(plan_question_app, name="question")


@plan_question_app.command("list")
def plan_question_list(
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


@plan_question_app.command("show")
def plan_question_show(
    question_id: str = typer.Argument(..., help="Question ID"),
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Show detailed information for a question."""
    _question_handle(_ns(
        command="question", question_command="show",
        json=_global["json"], debug=_global["debug"],
        question_id=question_id, plan=plan,
    ))


@plan_question_app.command("answer")
def plan_question_answer(
    question_id: Annotated[Optional[str], typer.Argument(help="Question ID to answer")] = None,
    text: Annotated[Optional[str], typer.Option("--text", help="Answer text")] = None,
    confidence: Annotated[Optional[str], typer.Option("--confidence", help="Confidence level (high, medium, low)")] = None,
    interactive: Annotated[bool, typer.Option("--interactive", "-i", help="Use interactive wizard")] = False,
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Answer a pending question."""
    ns = _ns(
        command="question", question_command="answer",
        json=_global["json"], debug=_global["debug"],
        text=text, confidence=confidence, interactive=interactive, plan=plan,
    )
    if question_id is not None:
        ns.question_id = question_id
    _question_handle(ns)


@plan_question_app.command("dashboard")
def plan_question_dashboard(
    refresh: Annotated[int, typer.Option("--refresh", "-r", help="Refresh interval in seconds")] = 5,
    no_tmux_window: Annotated[bool, typer.Option("--no-tmux-window", help="Run TUI directly without creating tmux window", hidden=True)] = False,
):
    """Interactive dashboard for answering pending questions."""
    _question_handle(_ns(
        command="question", question_command="dashboard",
        json=_global["json"], debug=_global["debug"],
        refresh=refresh, no_tmux_window=no_tmux_window,
    ))


# ===========================================================================
# EPIC (new primary vocabulary: epic list, epic ticket start, etc.)
# ===========================================================================

epic_app = typer.Typer(
    help="Manage epic folders and track ticket status.\n\nStatuses: proposed (new/planned), in_progress (active work), completed (done).",
    no_args_is_help=True,
)
app.add_typer(epic_app, name="epic")


# --- epic list ---
@epic_app.command("list")
def epic_list(
    all_epics: Annotated[bool, typer.Option("--all", "-a", help="Include completed epics (hidden by default)")] = False,
):
    """List epics in the repository.

    Statuses: proposed (new), in_progress (active work), completed (done).
    Completed epics are hidden by default; use --all to show them.
    """
    _epic_handle(_ns(command="epic", epic_command="list", json=_global["json"], debug=_global["debug"], all=all_epics))


# --- epic status ---
@epic_app.command("status")
def epic_status(
    path: Optional[str] = typer.Argument(None, help="Path to epic folder"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Show epic status and ticket summary.

    Statuses: proposed (new), in_progress (active), completed (done).
    """
    resolved = epic or path
    _epic_handle(_ns(command="epic", epic_command="status", json=_global["json"], debug=_global["debug"], path=resolved))


# --- epic cancel ---
@epic_app.command("cancel")
def epic_cancel(
    path: Optional[str] = typer.Argument(None, help="Epic name or path"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Cancel an active epic."""
    resolved = epic or path
    _epic_handle(_ns(
        command="epic", epic_command="cancel",
        json=_global["json"], debug=_global["debug"],
        path=resolved, force=force,
    ))


# --- epic ticket (nested sub-app) ---
epic_ticket_app = typer.Typer(help="Manage tickets in epic files", no_args_is_help=True)
epic_app.add_typer(epic_ticket_app, name="ticket")


@epic_ticket_app.command("start")
def epic_ticket_start(
    task_id: str = typer.Argument(..., help="Ticket ID"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Mark ticket as in_progress."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="start",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=epic,
    ))


@epic_ticket_app.command("complete")
def epic_ticket_complete(
    task_id: str = typer.Argument(..., help="Ticket ID"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Mark ticket as completed."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="complete",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=epic,
    ))


@epic_ticket_app.command("prefill")
def epic_ticket_prefill(
    preset: Annotated[str, typer.Option("--preset", "-t", help="Preset name")] = ...,
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
):
    """Load preset ticket list from template."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="prefill",
        json=_global["json"], debug=_global["debug"],
        preset=preset, plan=epic, dry_run=dry_run,
    ))


@epic_ticket_app.command("list")
def epic_ticket_list(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    status: Annotated[str, typer.Option("--status", "-s", help="Filter by status", callback=_validate_status)] = "all",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show full details")] = False,
):
    """Show all tickets in current epic folder."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=epic, status=status, verbose=verbose,
    ))


@epic_ticket_app.command("status")
def epic_ticket_status(
    task_id: str = typer.Argument(..., help="Ticket ID"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Show detailed status for a specific ticket."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="status",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=epic,
    ))


@epic_ticket_app.command("add")
def epic_ticket_add(
    description: str = typer.Argument(..., help="Ticket description"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    phase: Annotated[Optional[str], typer.Option("--phase", "-ph", help="Phase ID")] = None,
    id: Annotated[Optional[str], typer.Option("--id", help="Custom ticket ID")] = None,
    priority: Annotated[str, typer.Option("--priority", help="Ticket priority", callback=_validate_priority)] = "medium",
    agent: Annotated[Optional[str], typer.Option("--agent", help="Agent type responsible for this ticket")] = None,
    target_files: Annotated[Optional[str], typer.Option("--target-files", help="Comma-separated list of target files")] = None,
    success_criteria: Annotated[Optional[str], typer.Option("--success-criteria", help="Comma-separated success criteria")] = None,
    guidance: Annotated[Optional[str], typer.Option("--guidance", help="Implementation guidance")] = None,
    inputs: Annotated[Optional[str], typer.Option("--inputs", help="Comma-separated input files/context")] = None,
    story_ids: Annotated[Optional[str], typer.Option("--story-ids", help="Comma-separated user story IDs (e.g. US-CLI-110,US-CLI-111)")] = None,
):
    """Add new ticket to epic."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="add",
        json=_global["json"], debug=_global["debug"],
        description=description, plan=epic, phase=phase, id=id, priority=priority,
        agent=agent, target_files=target_files, success_criteria=success_criteria,
        guidance=guidance, inputs=inputs, story_ids=story_ids,
    ))


@epic_ticket_app.command("update")
def epic_ticket_update(
    task_id: str = typer.Argument(..., help="Ticket ID"),
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="New status")] = None,
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    note: Annotated[Optional[str], typer.Option("--note", "-n", help="Completion note")] = None,
    description: Annotated[Optional[str], typer.Option("--description", help="New ticket description")] = None,
    name: Annotated[Optional[str], typer.Option("--name", help="New ticket name")] = None,
    agent: Annotated[Optional[str], typer.Option("--agent", help="Agent type")] = None,
    target_files: Annotated[Optional[str], typer.Option("--target-files", help="Comma-separated target files")] = None,
    success_criteria: Annotated[Optional[str], typer.Option("--success-criteria", help="Comma-separated success criteria")] = None,
    guidance: Annotated[Optional[str], typer.Option("--guidance", help="Implementation guidance")] = None,
    inputs: Annotated[Optional[str], typer.Option("--inputs", help="Comma-separated inputs")] = None,
    story_ids: Annotated[Optional[str], typer.Option("--story-ids", help="Comma-separated user story IDs (e.g. US-CLI-110,US-CLI-111)")] = None,
):
    """Update ticket fields in epic (status, description, agent, etc.)."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="update",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, status=status, plan=epic, note=note,
        description=description, name=name, agent=agent,
        target_files=target_files, success_criteria=success_criteria,
        guidance=guidance, inputs=inputs, story_ids=story_ids,
    ))


@epic_ticket_app.command("remove")
def epic_ticket_remove(
    task_id: str = typer.Argument(..., help="Ticket ID to remove"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Permanently remove a ticket from the epic."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="remove",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=epic, force=force,
    ))


@epic_ticket_app.command("batch")
def epic_ticket_batch(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    file: Annotated[Optional[str], typer.Option("--file", "-f", help="JSON file path (defaults to stdin)")] = None,
):
    """Bulk import phases and tickets from JSON.

    Reads JSON from --file or stdin. Expected format:
    {"phases": [...], "tickets": [...]}
    """
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="batch",
        json=_global["json"], debug=_global["debug"],
        plan=epic, file=file,
    ))


@epic_ticket_app.command("current")
def epic_ticket_current(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Get the current ticket to work on."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="current",
        json=_global["json"], debug=_global["debug"],
        plan=epic,
    ))


# --- epic phase (nested sub-app) ---
epic_phase_app = typer.Typer(help="Manage epic phases", no_args_is_help=True)
epic_app.add_typer(epic_phase_app, name="phase")


@epic_phase_app.command("add")
def epic_phase_add(
    id: Annotated[str, typer.Option("--id", help="Phase ID")] = ...,
    name: Annotated[str, typer.Option("--name", help="Phase name")] = ...,
    description: Annotated[Optional[str], typer.Option("--description", help="Phase description")] = None,
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    agent: Annotated[Optional[str], typer.Option("--agent", "-a", help="Agent type (e.g. build-python, test-runner)")] = None,
    execution: Annotated[Optional[str], typer.Option("--execution", "-e", help="Execution mode: sequential or parallel")] = None,
    loop_type: Annotated[Optional[str], typer.Option("--loop-type", help="Loop type override")] = None,
    loop_max_iterations: Annotated[Optional[int], typer.Option("--loop-max-iterations", help="Max iterations for the phase")] = None,
    feedback_triggers: Annotated[Optional[str], typer.Option("--feedback-triggers", help="Comma-separated KEY=VALUE pairs (e.g. TEST_FAILURE=Build)")] = None,
    max_turns: Annotated[Optional[int], typer.Option("--max-turns", help="Maximum agentic turns for this phase (overrides default 200)")] = None,
    timeout: Annotated[Optional[int], typer.Option("--timeout", help="Per-phase timeout in seconds (overrides default 1800s/30min)")] = None,
):
    """Add a new phase to the epic in TinyDB."""
    _epic_handle(_ns(
        command="epic", epic_command="phase", phase_action="add",
        json=_global["json"], debug=_global["debug"],
        id=id, name=name, description=description, plan=epic,
        agent=agent, execution=execution, loop_type=loop_type,
        loop_max_iterations=loop_max_iterations, feedback_triggers=feedback_triggers,
        max_turns=max_turns, timeout=timeout,
    ))


@epic_phase_app.command("list")
def epic_phase_list(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """List all phases in the epic."""
    _epic_handle(_ns(
        command="epic", epic_command="phase", phase_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=epic,
    ))


@epic_phase_app.command("update")
def epic_phase_update(
    phase_id: str = typer.Argument(..., help="Phase ID to update"),
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="New status")] = None,
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New name")] = None,
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    agent: Annotated[Optional[str], typer.Option("--agent", "-a", help="Agent type (e.g. build-python, test-runner)")] = None,
    execution: Annotated[Optional[str], typer.Option("--execution", "-e", help="Execution mode: sequential or parallel")] = None,
    loop_type: Annotated[Optional[str], typer.Option("--loop-type", help="Loop type override")] = None,
    loop_max_iterations: Annotated[Optional[int], typer.Option("--loop-max-iterations", help="Max iterations for the phase")] = None,
    feedback_triggers: Annotated[Optional[str], typer.Option("--feedback-triggers", help="Comma-separated KEY=VALUE pairs (e.g. TEST_FAILURE=Build)")] = None,
    max_turns: Annotated[Optional[int], typer.Option("--max-turns", help="Maximum agentic turns for this phase (overrides default 200)")] = None,
    timeout: Annotated[Optional[int], typer.Option("--timeout", help="Per-phase timeout in seconds (overrides default 1800s/30min)")] = None,
):
    """Update a phase in TinyDB."""
    _epic_handle(_ns(
        command="epic", epic_command="phase", phase_action="update",
        json=_global["json"], debug=_global["debug"],
        phase_id=phase_id, status=status, name=name, plan=epic,
        agent=agent, execution=execution, loop_type=loop_type,
        loop_max_iterations=loop_max_iterations, feedback_triggers=feedback_triggers,
        max_turns=max_turns, timeout=timeout,
    ))


@epic_phase_app.command("remove")
def epic_phase_remove(
    phase_id: str = typer.Argument(..., help="Phase ID to remove"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    cascade: Annotated[bool, typer.Option("--cascade", help="Also remove all tickets in this phase")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Remove a phase from the epic.

    Fails if the phase has tickets unless --cascade is used.
    """
    _epic_handle(_ns(
        command="epic", epic_command="phase", phase_action="remove",
        json=_global["json"], debug=_global["debug"],
        phase_id=phase_id, plan=epic, cascade=cascade, force=force,
    ))


# --- epic move (nested sub-app) ---
epic_move_app = typer.Typer(help="Move completed tickets or archive folder", no_args_is_help=True)
epic_app.add_typer(epic_move_app, name="move")


@epic_move_app.command("task")
def epic_move_task(
    task_id: str = typer.Argument(..., help="Ticket ID to move"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Move even with uncommitted changes")] = False,
):
    """Move a single completed ticket."""
    _epic_handle(_ns(
        command="epic", epic_command="move", move_type="task",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=epic, dry_run=dry_run, force=force,
    ))


@epic_move_app.command("tasks")
def epic_move_tasks(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Move even with uncommitted changes")] = False,
):
    """Move all completed tickets."""
    _epic_handle(_ns(
        command="epic", epic_command="move", move_type="tasks",
        json=_global["json"], debug=_global["debug"],
        plan=epic, dry_run=dry_run, force=force,
    ))


@epic_move_app.command("folder")
def epic_move_folder(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Archive even with uncommitted changes")] = False,
):
    """Archive the epic folder."""
    _epic_handle(_ns(
        command="epic", epic_command="move", move_type="folder",
        json=_global["json"], debug=_global["debug"],
        plan=epic, dry_run=dry_run, force=force,
    ))


# --- epic orchestration (nested sub-app) ---
epic_orch_app = typer.Typer(help="Manage epic orchestration MMD files", no_args_is_help=True)
epic_app.add_typer(epic_orch_app, name="orchestration")


@epic_orch_app.command("generate")
def epic_orchestration_generate(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing")] = False,
):
    """Generate orchestration MMD from epic YAML."""
    _epic_handle(_ns(
        command="epic", epic_command="orchestration", orchestration_action="generate",
        json=_global["json"], debug=_global["debug"],
        plan=epic, output=output, force=force,
    ))


@epic_orch_app.command("validate")
def epic_orchestration_validate(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
):
    """Validate orchestration MMD against epic YAML."""
    _epic_handle(_ns(
        command="epic", epic_command="orchestration", orchestration_action="validate",
        json=_global["json"], debug=_global["debug"],
        plan=epic, strict=strict,
    ))


# --- epic stories (nested sub-app) ---
epic_stories_app = typer.Typer(help="Manage user stories in epic files", no_args_is_help=True)
epic_app.add_typer(epic_stories_app, name="stories")


@epic_stories_app.command("list")
def epic_stories_list(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """List user stories from epic YAML."""
    _epic_handle(_ns(
        command="epic", epic_command="stories", stories_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=epic,
    ))


@epic_stories_app.command("test")
def epic_stories_test(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "yaml",
):
    """Generate blind test scenarios from user stories."""
    _epic_handle(_ns(
        command="epic", epic_command="stories", stories_action="test",
        json=_global["json"], debug=_global["debug"],
        plan=epic, output=output, format=format,
    ))


# --- epic db (nested sub-app) ---
epic_db_app = typer.Typer(help="Manage epic TinyDB database", no_args_is_help=True)
epic_app.add_typer(epic_db_app, name="db", hidden=True)


@epic_db_app.command("sync")
def epic_db_sync():
    """[DISABLED] db sync is no longer available. TinyDB is the sole data store."""
    _epic_handle(_ns(command="epic", epic_command="db", db_action="sync", json=_global["json"], debug=_global["debug"]))


@epic_db_app.command("status")
def epic_db_status():
    """Show TinyDB database statistics."""
    _epic_handle(_ns(command="epic", epic_command="db", db_action="status", json=_global["json"], debug=_global["debug"]))


# --- epic replan ---
@epic_app.command("replan")
def epic_replan(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Prepare an epic for new planning.

    Resets all ticket statuses back to 'proposed' and removes
    the orchestration MMD file for a fresh planning cycle.
    """
    _epic_handle(_ns(
        command="epic", epic_command="replan",
        json=_global["json"], debug=_global["debug"],
        plan=epic, force=force,
    ))


# ===========================================================================
# AGENT GROUP (hidden top-level, agent-facing plumbing)
# ===========================================================================

agent_app = typer.Typer(help="Agent plumbing commands", no_args_is_help=True)
app.add_typer(agent_app, name="agent", hidden=False)

# --- agent plan ---
agent_plan_app = typer.Typer(help="Plan management plumbing for agents", no_args_is_help=True)
agent_app.add_typer(agent_plan_app, name="plan")

# --- agent plan task ---
agent_plan_task_app = typer.Typer(help="Manage tasks in plan files", no_args_is_help=True)
agent_plan_app.add_typer(agent_plan_task_app, name="task")


@agent_plan_task_app.command("start")
def agent_plan_task_start(
    task_id: str = typer.Argument(..., help="Task ID"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
):
    """Mark task as in_progress."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="start",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=plan,
    ))


@agent_plan_task_app.command("complete")
def agent_plan_task_complete(
    task_id: str = typer.Argument(..., help="Task ID"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
):
    """Mark task as completed."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="complete",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=plan,
    ))


@agent_plan_task_app.command("prefill")
def agent_plan_task_prefill(
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


@agent_plan_task_app.command("list")
def agent_plan_task_list(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    status: Annotated[str, typer.Option("--status", "-s", help="Filter by status", callback=_validate_status)] = "all",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show full details")] = False,
):
    """Show all tasks in current plan folder."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=plan, status=status, verbose=verbose,
    ))


@agent_plan_task_app.command("status")
def agent_plan_task_status(
    task_id: str = typer.Argument(..., help="Task ID"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
):
    """Show detailed status for a specific task."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="status",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=plan,
    ))


@agent_plan_task_app.command("add")
def agent_plan_task_add(
    description: str = typer.Argument(..., help="Task description"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    phase: Annotated[Optional[str], typer.Option("--phase", "-ph", help="Phase ID")] = None,
    id: Annotated[Optional[str], typer.Option("--id", help="Custom task ID")] = None,
    priority: Annotated[str, typer.Option("--priority", help="Task priority", callback=_validate_priority)] = "medium",
):
    """Add new task to plan."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="add",
        json=_global["json"], debug=_global["debug"],
        description=description, plan=plan, phase=phase, id=id, priority=priority,
    ))


@agent_plan_task_app.command("update")
def agent_plan_task_update(
    task_id: str = typer.Argument(..., help="Task ID"),
    status: Annotated[str, typer.Option("--status", "-s", help="New status")] = ...,
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
    note: Annotated[Optional[str], typer.Option("--note", "-n", help="Completion note")] = None,
):
    """Update task status in plan file."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="update",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, status=status, plan=plan, note=note,
    ))


@agent_plan_task_app.command("current")
def agent_plan_task_current(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan path")] = None,
):
    """Get the current task to work on."""
    _plan_handle(_ns(
        command="plan", plan_command="task", task_action="current",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


# --- agent plan phase ---
agent_plan_phase_app = typer.Typer(help="Manage plan phases", no_args_is_help=True)
agent_plan_app.add_typer(agent_plan_phase_app, name="phase")


@agent_plan_phase_app.command("add")
def agent_plan_phase_add(
    id: Annotated[str, typer.Option("--id", help="Phase ID")] = ...,
    name: Annotated[str, typer.Option("--name", help="Phase name")] = ...,
    description: Annotated[Optional[str], typer.Option("--description", help="Phase description")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
):
    """Add a new phase to the epic in TinyDB."""
    _plan_handle(_ns(
        command="plan", plan_command="phase", phase_action="add",
        json=_global["json"], debug=_global["debug"],
        id=id, name=name, description=description, plan=plan,
    ))


@agent_plan_phase_app.command("list")
def agent_plan_phase_list(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
):
    """List all phases in the plan."""
    _plan_handle(_ns(
        command="plan", plan_command="phase", phase_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


@agent_plan_phase_app.command("update")
def agent_plan_phase_update(
    phase_id: str = typer.Argument(..., help="Phase ID to update"),
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="New status")] = None,
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New name")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
):
    """Update a phase in TinyDB."""
    _plan_handle(_ns(
        command="plan", plan_command="phase", phase_action="update",
        json=_global["json"], debug=_global["debug"],
        phase_id=phase_id, status=status, name=name, plan=plan,
    ))


# --- agent plan move ---
agent_plan_move_app = typer.Typer(help="Move completed tasks or archive folder", no_args_is_help=True)
agent_plan_app.add_typer(agent_plan_move_app, name="move")


@agent_plan_move_app.command("task")
def agent_plan_move_task(
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


@agent_plan_move_app.command("tasks")
def agent_plan_move_tasks(
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


@agent_plan_move_app.command("folder")
def agent_plan_move_folder(
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


# --- agent plan orchestration ---
agent_plan_orch_app = typer.Typer(help="Manage plan orchestration MMD files", no_args_is_help=True)
agent_plan_app.add_typer(agent_plan_orch_app, name="orchestration")


@agent_plan_orch_app.command("generate")
def agent_plan_orchestration_generate(
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


@agent_plan_orch_app.command("validate")
def agent_plan_orchestration_validate(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
):
    """Validate orchestration MMD against plan YAML."""
    _plan_handle(_ns(
        command="plan", plan_command="orchestration", orchestration_action="validate",
        json=_global["json"], debug=_global["debug"],
        plan=plan, strict=strict,
    ))


# --- agent plan stories ---
agent_plan_stories_app = typer.Typer(help="Manage user stories in plan files", no_args_is_help=True)
agent_plan_app.add_typer(agent_plan_stories_app, name="stories")


@agent_plan_stories_app.command("list")
def agent_plan_stories_list(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
):
    """List user stories from plan YAML."""
    _plan_handle(_ns(
        command="plan", plan_command="stories", stories_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


@agent_plan_stories_app.command("test")
def agent_plan_stories_test(
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


# --- agent plan db ---
agent_plan_db_app = typer.Typer(help="Manage plan TinyDB database", no_args_is_help=True)
agent_plan_app.add_typer(agent_plan_db_app, name="db")


@agent_plan_db_app.command("sync")
def agent_plan_db_sync():
    """[DISABLED] db sync is no longer available. TinyDB is the sole data store."""
    _plan_handle(_ns(command="plan", plan_command="db", db_action="sync", json=_global["json"], debug=_global["debug"]))


@agent_plan_db_app.command("status")
def agent_plan_db_status():
    """Show TinyDB database statistics."""
    _plan_handle(_ns(command="plan", plan_command="db", db_action="status", json=_global["json"], debug=_global["debug"]))


# --- agent plan direct commands (archive, unarchive, validate, scaffold, init, bootstrap) ---

@agent_plan_app.command("archive")
def agent_plan_archive(
    path: Optional[str] = typer.Argument(None, help="Path to plan folder to archive"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
):
    """Copy plan to completed folder."""
    resolved = plan or path
    if not resolved:
        from agenticcli.console import print_error
        print_error("Path required.")
        raise typer.Exit(1)
    _plan_handle(_ns(command="plan", plan_command="archive", json=_global["json"], debug=_global["debug"], path=resolved))


@agent_plan_app.command("unarchive")
def agent_plan_unarchive(
    plan: Annotated[str, typer.Option("--plan", "-p", help="Plan folder name")] = ...,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Move plan from completed back to live."""
    _plan_handle(_ns(
        command="plan", plan_command="unarchive",
        json=_global["json"], debug=_global["debug"],
        plan=plan, force=force,
    ))


@agent_plan_app.command("validate")
def agent_plan_validate(
    path: Optional[str] = typer.Argument(None, help="Path to plan folder"),
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Plan folder path")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Fail on stub templates")] = False,
    check_fences: Annotated[bool, typer.Option("--check-fences", help="Validate UAT fence compliance")] = False,
):
    """Validate plan folder structure and YAML."""
    resolved = plan or path
    if not resolved:
        from agenticcli.console import print_error
        print_error("Path is required.")
        raise typer.Exit(1)
    _plan_handle(_ns(
        command="plan", plan_command="validate",
        json=_global["json"], debug=_global["debug"],
        path=resolved, strict=strict, check_fences=check_fences,
    ))


@agent_plan_app.command("scaffold")
def agent_plan_scaffold(
    name: str = typer.Argument(..., help="Folder name"),
):
    """Create planning folder structure."""
    _plan_handle(_ns(
        command="plan", plan_command="scaffold",
        json=_global["json"], debug=_global["debug"],
        name=name,
    ))


@agent_plan_app.command("init")
def agent_plan_init(
    branch: str = typer.Argument(..., help="Branch name for the plan"),
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Plan description")] = None,
    base: Annotated[str, typer.Option("--base", "-b", help="Base branch")] = "main",
    objective: Annotated[Optional[str], typer.Option("--objective", "-o", help="Plan objective")] = None,
):
    """Initialize a plan folder with proper naming convention."""
    _plan_handle(_ns(
        command="plan", plan_command="init",
        json=_global["json"], debug=_global["debug"],
        branch=branch, description=description, base=base, objective=objective,
    ))


@agent_plan_app.command("bootstrap")
def agent_plan_bootstrap(
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


@agent_plan_app.command("new")
def agent_plan_new(
    objective: Annotated[Optional[str], typer.Argument(help="Planning objective description")] = None,
    branch: Annotated[Optional[str], typer.Option("--branch", "-b", help="Git branch name (auto-generated from objective if omitted)")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Plan folder description suffix")] = None,
    base: Annotated[str, typer.Option("--base", help="Base branch for the plan")] = "main",
    execute: Annotated[bool, typer.Option("--execute", "-x", help="Auto-execute after planning completes")] = False,
    max_turns: Annotated[int, typer.Option("--max-turns", help="Max turns for planner agent")] = 25,
    dangerously_skip_permissions: Annotated[bool, typer.Option(
        "--dangerously-skip-permissions", help="Skip permission prompts for spawned sessions")] = False,
):
    """Create plan and spawn planner agent (agent-facing)."""
    if not objective:
        from agenticcli.console import print_error
        print_error("Objective is required. Usage: agentic agent plan new \"your objective\"")
        raise typer.Exit(1)
    _plan_handle(_ns(
        command="plan", plan_command="new",
        json=_global["json"], debug=_global["debug"],
        objective=objective, branch=branch, description=description,
        base=base, execute=execute, max_turns=max_turns,
        dangerously_skip_permissions=dangerously_skip_permissions,
    ))


# --- agent epic ---
agent_epic_app = typer.Typer(help="Epic management plumbing for agents", no_args_is_help=True)
agent_app.add_typer(agent_epic_app, name="epic")

# --- agent epic ticket ---
agent_epic_ticket_app = typer.Typer(help="Manage tickets in epic files", no_args_is_help=True)
agent_epic_app.add_typer(agent_epic_ticket_app, name="ticket")


@agent_epic_ticket_app.command("start")
def agent_epic_ticket_start(
    task_id: str = typer.Argument(..., help="Ticket ID"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Mark ticket as in_progress."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="start",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=epic,
    ))


@agent_epic_ticket_app.command("complete")
def agent_epic_ticket_complete(
    task_id: str = typer.Argument(..., help="Ticket ID"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Mark ticket as completed."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="complete",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=epic,
    ))


@agent_epic_ticket_app.command("prefill")
def agent_epic_ticket_prefill(
    preset: Annotated[str, typer.Option("--preset", "-t", help="Preset name")] = ...,
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
):
    """Load preset ticket list from template."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="prefill",
        json=_global["json"], debug=_global["debug"],
        preset=preset, plan=epic, dry_run=dry_run,
    ))


@agent_epic_ticket_app.command("list")
def agent_epic_ticket_list(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    status: Annotated[str, typer.Option("--status", "-s", help="Filter by status", callback=_validate_status)] = "all",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show full details")] = False,
):
    """Show all tickets in current epic folder."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=epic, status=status, verbose=verbose,
    ))


@agent_epic_ticket_app.command("status")
def agent_epic_ticket_status(
    task_id: str = typer.Argument(..., help="Ticket ID"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Show detailed status for a specific ticket."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="status",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=epic,
    ))


@agent_epic_ticket_app.command("add")
def agent_epic_ticket_add(
    description: str = typer.Argument(..., help="Ticket description"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    phase: Annotated[Optional[str], typer.Option("--phase", "-ph", help="Phase ID")] = None,
    id: Annotated[Optional[str], typer.Option("--id", help="Custom ticket ID")] = None,
    priority: Annotated[str, typer.Option("--priority", help="Ticket priority", callback=_validate_priority)] = "medium",
    agent: Annotated[Optional[str], typer.Option("--agent", help="Agent type responsible for this ticket")] = None,
    target_files: Annotated[Optional[str], typer.Option("--target-files", help="Comma-separated list of target files")] = None,
    success_criteria: Annotated[Optional[str], typer.Option("--success-criteria", help="Comma-separated success criteria")] = None,
    guidance: Annotated[Optional[str], typer.Option("--guidance", help="Implementation guidance")] = None,
    inputs: Annotated[Optional[str], typer.Option("--inputs", help="Comma-separated input files/context")] = None,
    story_ids: Annotated[Optional[str], typer.Option("--story-ids", help="Comma-separated user story IDs (e.g. US-CLI-110,US-CLI-111)")] = None,
):
    """Add new ticket to epic."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="add",
        json=_global["json"], debug=_global["debug"],
        description=description, plan=epic, phase=phase, id=id, priority=priority,
        agent=agent, target_files=target_files, success_criteria=success_criteria,
        guidance=guidance, inputs=inputs, story_ids=story_ids,
    ))


@agent_epic_ticket_app.command("update")
def agent_epic_ticket_update(
    task_id: str = typer.Argument(..., help="Ticket ID"),
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="New status")] = None,
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    note: Annotated[Optional[str], typer.Option("--note", "-n", help="Completion note")] = None,
    description: Annotated[Optional[str], typer.Option("--description", help="New ticket description")] = None,
    name: Annotated[Optional[str], typer.Option("--name", help="New ticket name")] = None,
    agent: Annotated[Optional[str], typer.Option("--agent", help="Agent type")] = None,
    target_files: Annotated[Optional[str], typer.Option("--target-files", help="Comma-separated target files")] = None,
    success_criteria: Annotated[Optional[str], typer.Option("--success-criteria", help="Comma-separated success criteria")] = None,
    guidance: Annotated[Optional[str], typer.Option("--guidance", help="Implementation guidance")] = None,
    inputs: Annotated[Optional[str], typer.Option("--inputs", help="Comma-separated inputs")] = None,
    story_ids: Annotated[Optional[str], typer.Option("--story-ids", help="Comma-separated user story IDs (e.g. US-CLI-110,US-CLI-111)")] = None,
):
    """Update ticket fields in epic (status, description, agent, etc.)."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="update",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, status=status, plan=epic, note=note,
        description=description, name=name, agent=agent,
        target_files=target_files, success_criteria=success_criteria,
        guidance=guidance, inputs=inputs, story_ids=story_ids,
    ))


@agent_epic_ticket_app.command("current")
def agent_epic_ticket_current(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Get the current ticket to work on."""
    _epic_handle(_ns(
        command="epic", epic_command="ticket", ticket_action="current",
        json=_global["json"], debug=_global["debug"],
        plan=epic,
    ))


# --- agent epic phase ---
agent_epic_phase_app = typer.Typer(help="Manage epic phases", no_args_is_help=True)
agent_epic_app.add_typer(agent_epic_phase_app, name="phase")


@agent_epic_phase_app.command("add")
def agent_epic_phase_add(
    id: Annotated[str, typer.Option("--id", help="Phase ID")] = ...,
    name: Annotated[str, typer.Option("--name", help="Phase name")] = ...,
    description: Annotated[Optional[str], typer.Option("--description", help="Phase description")] = None,
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    agent: Annotated[Optional[str], typer.Option("--agent", "-a", help="Agent type (e.g. build-python, test-runner)")] = None,
    execution: Annotated[Optional[str], typer.Option("--execution", "-e", help="Execution mode: sequential or parallel")] = None,
    loop_type: Annotated[Optional[str], typer.Option("--loop-type", help="Loop type override")] = None,
    loop_max_iterations: Annotated[Optional[int], typer.Option("--loop-max-iterations", help="Max iterations for the phase")] = None,
    feedback_triggers: Annotated[Optional[str], typer.Option("--feedback-triggers", help="Comma-separated KEY=VALUE pairs (e.g. TEST_FAILURE=Build)")] = None,
    max_turns: Annotated[Optional[int], typer.Option("--max-turns", help="Maximum agentic turns for this phase (overrides default 200)")] = None,
):
    """Add a new phase to the epic in TinyDB."""
    _epic_handle(_ns(
        command="epic", epic_command="phase", phase_action="add",
        json=_global["json"], debug=_global["debug"],
        id=id, name=name, description=description, plan=epic,
        agent=agent, execution=execution, loop_type=loop_type,
        loop_max_iterations=loop_max_iterations, feedback_triggers=feedback_triggers,
        max_turns=max_turns,
    ))


@agent_epic_phase_app.command("list")
def agent_epic_phase_list(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """List all phases in the epic."""
    _epic_handle(_ns(
        command="epic", epic_command="phase", phase_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=epic,
    ))


@agent_epic_phase_app.command("update")
def agent_epic_phase_update(
    phase_id: str = typer.Argument(..., help="Phase ID to update"),
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="New status")] = None,
    name: Annotated[Optional[str], typer.Option("--name", "-n", help="New name")] = None,
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    agent: Annotated[Optional[str], typer.Option("--agent", "-a", help="Agent type (e.g. build-python, test-runner)")] = None,
    execution: Annotated[Optional[str], typer.Option("--execution", "-e", help="Execution mode: sequential or parallel")] = None,
    loop_type: Annotated[Optional[str], typer.Option("--loop-type", help="Loop type override")] = None,
    loop_max_iterations: Annotated[Optional[int], typer.Option("--loop-max-iterations", help="Max iterations for the phase")] = None,
    feedback_triggers: Annotated[Optional[str], typer.Option("--feedback-triggers", help="Comma-separated KEY=VALUE pairs (e.g. TEST_FAILURE=Build)")] = None,
    max_turns: Annotated[Optional[int], typer.Option("--max-turns", help="Maximum agentic turns for this phase (overrides default 200)")] = None,
):
    """Update a phase in TinyDB."""
    _epic_handle(_ns(
        command="epic", epic_command="phase", phase_action="update",
        json=_global["json"], debug=_global["debug"],
        phase_id=phase_id, status=status, name=name, plan=epic,
        agent=agent, execution=execution, loop_type=loop_type,
        loop_max_iterations=loop_max_iterations, feedback_triggers=feedback_triggers,
        max_turns=max_turns,
    ))


# --- agent epic move ---
agent_epic_move_app = typer.Typer(help="Move completed tickets or archive folder", no_args_is_help=True)
agent_epic_app.add_typer(agent_epic_move_app, name="move")


@agent_epic_move_app.command("task")
def agent_epic_move_task(
    task_id: str = typer.Argument(..., help="Ticket ID to move"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Move even with uncommitted changes")] = False,
):
    """Move a single completed ticket."""
    _epic_handle(_ns(
        command="epic", epic_command="move", move_type="task",
        json=_global["json"], debug=_global["debug"],
        task_id=task_id, plan=epic, dry_run=dry_run, force=force,
    ))


@agent_epic_move_app.command("tasks")
def agent_epic_move_tasks(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Move even with uncommitted changes")] = False,
):
    """Move all completed tickets."""
    _epic_handle(_ns(
        command="epic", epic_command="move", move_type="tasks",
        json=_global["json"], debug=_global["debug"],
        plan=epic, dry_run=dry_run, force=force,
    ))


@agent_epic_move_app.command("folder")
def agent_epic_move_folder(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Archive even with uncommitted changes")] = False,
):
    """Archive the epic folder."""
    _epic_handle(_ns(
        command="epic", epic_command="move", move_type="folder",
        json=_global["json"], debug=_global["debug"],
        plan=epic, dry_run=dry_run, force=force,
    ))


# --- agent epic orchestration ---
agent_epic_orch_app = typer.Typer(help="Manage epic orchestration MMD files", no_args_is_help=True)
agent_epic_app.add_typer(agent_epic_orch_app, name="orchestration")


@agent_epic_orch_app.command("generate")
def agent_epic_orchestration_generate(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing")] = False,
):
    """Generate orchestration MMD from epic YAML."""
    _epic_handle(_ns(
        command="epic", epic_command="orchestration", orchestration_action="generate",
        json=_global["json"], debug=_global["debug"],
        plan=epic, output=output, force=force,
    ))


@agent_epic_orch_app.command("validate")
def agent_epic_orchestration_validate(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
):
    """Validate orchestration MMD against epic YAML."""
    _epic_handle(_ns(
        command="epic", epic_command="orchestration", orchestration_action="validate",
        json=_global["json"], debug=_global["debug"],
        plan=epic, strict=strict,
    ))


# --- agent epic stories ---
agent_epic_stories_app = typer.Typer(help="Manage user stories in epic files", no_args_is_help=True)
agent_epic_app.add_typer(agent_epic_stories_app, name="stories")


@agent_epic_stories_app.command("list")
def agent_epic_stories_list(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """List user stories from epic YAML."""
    _epic_handle(_ns(
        command="epic", epic_command="stories", stories_action="list",
        json=_global["json"], debug=_global["debug"],
        plan=epic,
    ))


@agent_epic_stories_app.command("test")
def agent_epic_stories_test(
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path")] = None,
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "yaml",
):
    """Generate blind test scenarios from user stories."""
    _epic_handle(_ns(
        command="epic", epic_command="stories", stories_action="test",
        json=_global["json"], debug=_global["debug"],
        plan=epic, output=output, format=format,
    ))


# --- agent epic db ---
agent_epic_db_app = typer.Typer(help="Manage epic TinyDB database", no_args_is_help=True)
agent_epic_app.add_typer(agent_epic_db_app, name="db")


@agent_epic_db_app.command("sync")
def agent_epic_db_sync():
    """[DISABLED] db sync is no longer available. TinyDB is the sole data store."""
    _epic_handle(_ns(command="epic", epic_command="db", db_action="sync", json=_global["json"], debug=_global["debug"]))


@agent_epic_db_app.command("status")
def agent_epic_db_status():
    """Show TinyDB database statistics."""
    _epic_handle(_ns(command="epic", epic_command="db", db_action="status", json=_global["json"], debug=_global["debug"]))


# --- agent epic direct commands (archive, unarchive, validate, scaffold, init, bootstrap, new) ---

@agent_epic_app.command("archive")
def agent_epic_archive(
    path: Optional[str] = typer.Argument(None, help="Path to epic folder to archive"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
):
    """Copy epic to completed folder."""
    resolved = epic or path
    if not resolved:
        from agenticcli.console import print_error
        print_error("Path required.")
        raise typer.Exit(1)
    _epic_handle(_ns(command="epic", epic_command="archive", json=_global["json"], debug=_global["debug"], path=resolved))


@agent_epic_app.command("unarchive")
def agent_epic_unarchive(
    epic: Annotated[str, typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = ...,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Move epic from completed back to live."""
    _epic_handle(_ns(
        command="epic", epic_command="unarchive",
        json=_global["json"], debug=_global["debug"],
        plan=epic, force=force,
    ))


@agent_epic_app.command("validate")
def agent_epic_validate(
    path: Optional[str] = typer.Argument(None, help="Path to epic folder"),
    epic: Annotated[Optional[str], typer.Option("--epic", "--plan", "-p", help="--plan/--epic (use --epic, --plan deprecated)")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Fail on stub templates")] = False,
    check_fences: Annotated[bool, typer.Option("--check-fences", help="Validate UAT fence compliance")] = False,
):
    """Validate epic folder structure and YAML."""
    resolved = epic or path
    if not resolved:
        from agenticcli.console import print_error
        print_error("Path is required.")
        raise typer.Exit(1)
    _epic_handle(_ns(
        command="epic", epic_command="validate",
        json=_global["json"], debug=_global["debug"],
        path=resolved, strict=strict, check_fences=check_fences,
    ))


@agent_epic_app.command("scaffold")
def agent_epic_scaffold(
    name: str = typer.Argument(..., help="Folder name"),
):
    """Create epic folder structure."""
    _epic_handle(_ns(
        command="epic", epic_command="scaffold",
        json=_global["json"], debug=_global["debug"],
        name=name,
    ))


@agent_epic_app.command("init")
def agent_epic_init(
    branch: str = typer.Argument(..., help="Branch name for the epic"),
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Epic description")] = None,
    base: Annotated[str, typer.Option("--base", "-b", help="Base branch")] = "main",
    objective: Annotated[Optional[str], typer.Option("--objective", "-o", help="Epic objective")] = None,
):
    """Initialize an epic folder with proper naming convention."""
    _epic_handle(_ns(
        command="epic", epic_command="init",
        json=_global["json"], debug=_global["debug"],
        branch=branch, description=description, base=base, objective=objective,
    ))


@agent_epic_app.command("bootstrap")
def agent_epic_bootstrap(
    branch: str = typer.Argument(..., help="Branch name for the epic"),
    objective: Annotated[str, typer.Option("--objective", "-o", help="Epic objective")] = ...,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Epic description")] = None,
):
    """Bootstrap a new epic with an objective."""
    _epic_handle(_ns(
        command="epic", epic_command="bootstrap",
        json=_global["json"], debug=_global["debug"],
        branch=branch, objective=objective, description=description,
    ))


@agent_epic_app.command("new")
def agent_epic_new(
    objective: Annotated[Optional[str], typer.Argument(help="Epic objective description")] = None,
    branch: Annotated[Optional[str], typer.Option("--branch", "-b", help="Git branch name (auto-generated from objective if omitted)")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Epic folder description suffix")] = None,
    base: Annotated[str, typer.Option("--base", help="Base branch for the epic")] = "main",
    execute: Annotated[bool, typer.Option("--execute", "-x", help="Auto-execute after planning completes")] = False,
    max_turns: Annotated[int, typer.Option("--max-turns", help="Max turns for planner agent")] = 25,
    dangerously_skip_permissions: Annotated[bool, typer.Option(
        "--dangerously-skip-permissions", help="Skip permission prompts for spawned sessions")] = False,
):
    """Create epic and spawn planner agent (agent-facing)."""
    if not objective:
        from agenticcli.console import print_error
        print_error("Objective is required. Usage: agentic agent epic new \"your objective\"")
        raise typer.Exit(1)
    _epic_handle(_ns(
        command="epic", epic_command="new",
        json=_global["json"], debug=_global["debug"],
        objective=objective, branch=branch, description=description,
        base=base, execute=execute, max_turns=max_turns,
        dangerously_skip_permissions=dangerously_skip_permissions,
    ))


# --- agent context ---
agent_context_app = typer.Typer(help="CCI context retrieval for agents", no_args_is_help=True)
agent_app.add_typer(agent_context_app, name="context")


@agent_context_app.command("bootstrap")
def agent_context_bootstrap(
    role: Annotated[Optional[str], typer.Option("--role", "-r", help="Role ID")] = None,
    epic: Annotated[Optional[str], typer.Option("--epic", "-e", help="Epic folder name (skip auto-resolution)")] = None,
):
    """Get Seed Context: Active Task + Role Guidance + Essential Inputs."""
    _context_handle(_ns(
        command="context", context_command="bootstrap",
        json=_global["json"], debug=_global["debug"],
        role=role, epic=epic,
    ))


@agent_context_app.command("role")
def agent_context_role(
    role_id: str = typer.Argument(..., help="Role ID"),
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "yaml",
):
    """Returns process.yml and manifest.yml content for a role."""
    _context_handle(_ns(
        command="context", context_command="role",
        json=_global["json"], debug=_global["debug"],
        role_id=role_id, format=format,
    ))


@agent_context_app.command("task")
def agent_context_task(
    all: Annotated[bool, typer.Option("--all", "-a", help="Show all tasks")] = False,
):
    """Get active task from Main-First plan."""
    _context_handle(_ns(
        command="context", context_command="task",
        json=_global["json"], debug=_global["debug"],
        **{"all": all},
    ))


@agent_context_app.command("inputs")
def agent_context_inputs(
    role: Annotated[Optional[str], typer.Option("--role", "-r", help="Role ID")] = None,
    resolve: Annotated[bool, typer.Option("--resolve", help="Expand layer references")] = False,
):
    """Returns input files for a role with path resolution."""
    _context_handle(_ns(
        command="context", context_command="inputs",
        json=_global["json"], debug=_global["debug"],
        role=role, resolve=resolve,
    ))


@agent_context_app.command("generate-agent")
def agent_context_generate_agent(
    role_id: str = typer.Argument(..., help="Role ID"),
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path")] = None,
):
    """Generate thin-client agent file from bootstrap template."""
    _context_handle(_ns(
        command="context", context_command="generate-agent",
        json=_global["json"], debug=_global["debug"],
        role_id=role_id, output=output,
    ))


# --- agent entrypoint ---
agent_entrypoint_app = typer.Typer(help="Discover and execute workflow entrypoints", no_args_is_help=True)
agent_app.add_typer(agent_entrypoint_app, name="entrypoint")


@agent_entrypoint_app.command("list")
def agent_entrypoint_list():
    """List all available entrypoints."""
    _entrypoint_handle(_ns(command="entrypoint", entrypoint_command="list", json=_global["json"], debug=_global["debug"]))


@agent_entrypoint_app.command("show")
def agent_entrypoint_show(name: str = typer.Argument(..., help="Entrypoint name")):
    """Show contents of an entrypoint file."""
    _entrypoint_handle(_ns(
        command="entrypoint", entrypoint_command="show",
        json=_global["json"], debug=_global["debug"],
        name=name,
    ))


@agent_entrypoint_app.command("execute")
def agent_entrypoint_execute(
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


# --- agent manifest ---
agent_manifest_app = typer.Typer(help="Manage agent manifests", no_args_is_help=True)
agent_app.add_typer(agent_manifest_app, name="manifest")


@agent_manifest_app.command("show")
def agent_manifest_show(path: str = typer.Argument(..., help="Path to agent directory or manifest file")):
    """Display formatted agent manifest."""
    _manifest_handle(_ns(command="manifest", manifest_command="show", json=_global["json"], debug=_global["debug"], path=path))


@agent_manifest_app.command("list")
def agent_manifest_list(path: Optional[str] = typer.Argument(None, help="Base path to search")):
    """List all manifests in the project."""
    _manifest_handle(_ns(command="manifest", manifest_command="list", json=_global["json"], debug=_global["debug"], path=path))


@agent_manifest_app.command("validate")
def agent_manifest_validate(path: str = typer.Argument(..., help="Path to manifest file")):
    """Validate a manifest file."""
    _manifest_handle(_ns(command="manifest", manifest_command="validate", json=_global["json"], debug=_global["debug"], path=path))


# --- agent stories ---
agent_stories_app = typer.Typer(help="Find and manage user stories", no_args_is_help=True)
agent_app.add_typer(agent_stories_app, name="stories")


@agent_stories_app.command("find")
def agent_stories_find(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
    changes: Annotated[Optional[List[str]], typer.Option("--changes", "-c", help="Filter by changed files")] = None,
):
    """Find user stories matching project or changed files."""
    _stories_handle(_ns(
        command="stories", stories_command="find",
        json=_global["json"], debug=_global["debug"],
        project=project, changes=changes,
    ))


@agent_stories_app.command("init")
def agent_stories_init(
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


@agent_stories_app.command("cat")
def agent_stories_cat(id: str = typer.Argument(..., help="Story ID or filename")):
    """Display a user story's content."""
    _stories_handle(_ns(command="stories", stories_command="cat", json=_global["json"], debug=_global["debug"], id=id))


@agent_stories_app.command("status")
def agent_stories_status(id: str = typer.Argument(..., help="Story ID")):
    """View test status for a story."""
    _stories_handle(_ns(command="stories", stories_command="status", json=_global["json"], debug=_global["debug"], id=id))


@agent_stories_app.command("update")
def agent_stories_update(
    id: str = typer.Argument(..., help="Story ID"),
    status: Annotated[str, typer.Option("--status", "-s", help="Test result: pass, fail, skip, regression")] = ...,
    notes: Annotated[Optional[str], typer.Option("--notes", "-n", help="Test notes")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder")] = None,
):
    """Update test status for a story."""
    _stories_handle(_ns(
        command="stories", stories_command="update",
        json=_global["json"], debug=_global["debug"],
        id=id, status=status, notes=notes, plan=plan,
    ))


@agent_stories_app.command("report")
def agent_stories_report(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
    coverage: Annotated[bool, typer.Option("--coverage", help="Cross-reference pytest @pytest.mark.story markers against story inventory")] = False,
):
    """Show pass/fail/untested summary."""
    _stories_handle(_ns(command="stories", stories_command="report", json=_global["json"], debug=_global["debug"], project=project, coverage=coverage))


@agent_stories_app.command("untested")
def agent_stories_untested(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
):
    """List stories needing validation."""
    _stories_handle(_ns(command="stories", stories_command="untested", json=_global["json"], debug=_global["debug"], project=project))


@agent_stories_app.command("batch-update")
def agent_stories_batch_update(
    plan: Annotated[str, typer.Option("--plan", help="Plan folder name")] = ...,
    status: Annotated[str, typer.Option("--status", "-s", help="Test result: pass, fail, skip, regression")] = ...,
    notes: Annotated[Optional[str], typer.Option("--notes", "-n", help="Test notes")] = None,
):
    """Update all affected stories in a plan at once."""
    _stories_handle(_ns(
        command="stories", stories_command="batch-update",
        json=_global["json"], debug=_global["debug"],
        plan=plan, status=status, notes=notes,
    ))


@agent_stories_app.command("affected")
def agent_stories_affected(
    plan: Annotated[str, typer.Option("--plan", help="Plan folder name")] = ...,
):
    """List affected stories for a plan with their test status."""
    _stories_handle(_ns(
        command="stories", stories_command="affected",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


# --- agent question ---
agent_question_app = typer.Typer(help="Question queue plumbing for agents", no_args_is_help=True)
agent_app.add_typer(agent_question_app, name="question")


@agent_question_app.command("ask")
def agent_question_ask(
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


@agent_question_app.command("defer")
def agent_question_defer(
    question_id: str = typer.Argument(..., help="Question ID to defer"),
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Defer a pending question."""
    _question_handle(_ns(
        command="question", question_command="defer",
        json=_global["json"], debug=_global["debug"],
        question_id=question_id, plan=plan,
    ))


@agent_question_app.command("watch")
def agent_question_watch(
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Watch question folders and display updates."""
    _question_handle(_ns(
        command="question", question_command="watch",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


@agent_question_app.command("watch-daemon")
def agent_question_watch_daemon(
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
):
    """Start question watcher in background as daemon."""
    _question_handle(_ns(
        command="question", question_command="watch-daemon",
        json=_global["json"], debug=_global["debug"],
        plan=plan,
    ))


@agent_question_app.command("watch-stop")
def agent_question_watch_stop():
    """Stop running question watcher daemon."""
    _question_handle(_ns(
        command="question", question_command="watch-stop",
        json=_global["json"], debug=_global["debug"],
    ))


# ===========================================================================
# COMMAND CATEGORIES (used by context/require_project checks above)
# ===========================================================================

GLOBAL_COMMANDS = {
    "setup", "configure", "cfg", "session",
    "langsmith", "ls", "question",
}

PROJECT_COMMANDS = {
    "devops", "plan", "epic", "agent",
    "stories", "st", "manifest", "mf",
    "context", "ctx", "entrypoint", "ep",
}


# ===========================================================================
# run_cli() — the public entry point called from entry.py
# ===========================================================================

def run_cli():
    """Main CLI entry point. Invokes the Typer app."""
    app()
