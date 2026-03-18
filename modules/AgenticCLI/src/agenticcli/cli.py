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
    add_completion=False,
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
# SETUP GROUP (setup init, setup update, setup rebuild)
# ===========================================================================

setup_group = typer.Typer(help="Setup and package management", no_args_is_help=True)
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


@setup_group.command("health", hidden=True)
def setup_health():
    """[DEPRECATED] Use 'agentic health' instead."""
    import sys as _sys
    print("Warning: 'agentic setup health' is deprecated. Use 'agentic health' instead.", file=_sys.stderr)
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
# CONFIG GROUP (top-level: config show|init|get|set|list|delete|show-path|set-path|clear|env)
# ===========================================================================

config_app = typer.Typer(help="Configuration management", no_args_is_help=True)
setup_group.add_typer(config_app, name="config")
app.add_typer(config_app, name="config", hidden=True)



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
config_app.add_typer(env_app, name="env")



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
# HEALTH (top-level)
# ===========================================================================

@app.command("health")
def health():
    """Check CLI health, dependencies, and configuration status."""
    cli_ctx = _get_ctx(_global["json"], _global["debug"])
    _stability_banner("health")
    from agenticcli.commands import health as _mod
    _mod.handle(_ns(command="health", json=_global["json"], debug=_global["debug"]), ctx=cli_ctx)


# ===========================================================================
# CONFIGURE GROUP (hidden deprecated alias)
# ===========================================================================

configure_group = typer.Typer(
    help="[DEPRECATED] Use 'agentic config', 'agentic health', 'agentic session state'",
    no_args_is_help=True,
    hidden=True,
)
app.add_typer(configure_group, name="configure", hidden=True)
app.add_typer(configure_group, name="cfg", hidden=True)

# Proxy sub-groups to their new locations
configure_group.add_typer(config_app, name="config")
configure_group.add_typer(env_app, name="env")
configure_group.add_typer(state_app, name="state")

# Deprecated preferences aliases — proxy to config (same commands)
configure_group.add_typer(config_app, name="preferences", hidden=True)
configure_group.add_typer(config_app, name="prefs", hidden=True)
configure_group.add_typer(config_app, name="pref", hidden=True)

# Keep _prefs_handle for any remaining internal references
def _prefs_handle(args):
    _dispatch("preferences", args)



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
session_app.add_typer(state_app, name="state")

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



def _epic_handle(args):
    _dispatch("epic", args, require_project=True)


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


# --- epic new ---
@epic_app.command("new")
def epic_new(
    objective: Annotated[Optional[str], typer.Argument(help="Epic objective description")] = None,
    branch: Annotated[Optional[str], typer.Option("--branch", "-b", help="Git branch name (auto-generated from objective if omitted)")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Epic folder description suffix")] = None,
    base: Annotated[str, typer.Option("--base", help="Base branch for the epic")] = "main",
    execute: Annotated[bool, typer.Option("--execute", "-x", help="Auto-execute after planning completes")] = False,
    max_turns: Annotated[int, typer.Option("--max-turns", help="Max turns for planner agent")] = 25,
    dangerously_skip_permissions: Annotated[bool, typer.Option(
        "--dangerously-skip-permissions", help="Skip permission prompts for spawned sessions")] = False,
):
    """Create epic folder and spawn planner agent."""
    if not objective:
        from agenticcli.console import print_error
        print_error("Objective is required. Usage: agentic epic new \"your objective\"")
        raise typer.Exit(1)
    _epic_handle(_ns(
        command="epic", epic_command="new",
        json=_global["json"], debug=_global["debug"],
        objective=objective, branch=branch, description=description,
        base=base, execute=execute, max_turns=max_turns,
        dangerously_skip_permissions=dangerously_skip_permissions,
    ))


# --- epic validate ---
@epic_app.command("validate")
def epic_validate(
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


# --- epic archive ---
@epic_app.command("archive")
def epic_archive(
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


# --- epic scaffold ---
@epic_app.command("scaffold")
def epic_scaffold(
    name: str = typer.Argument(..., help="Folder name"),
):
    """Create epic folder structure."""
    _epic_handle(_ns(
        command="epic", epic_command="scaffold",
        json=_global["json"], debug=_global["debug"],
        name=name,
    ))


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
# STORIES GROUP (top-level: stories find|sync|coverage|run|report|...)
# ===========================================================================

stories_app = typer.Typer(help="User story discovery, test tracking, and coverage", no_args_is_help=True)
app.add_typer(stories_app, name="stories")


def _stories_handle(args):
    _dispatch("stories", args)


@stories_app.command("find")
def stories_find(
    query: Annotated[Optional[str], typer.Argument(help="Search query (ID, title, or keyword)")] = None,
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
    tag: Annotated[Optional[str], typer.Option("--tag", "-t", help="Filter by tag")] = None,
):
    """Search user stories by ID, title, or keyword."""
    _stories_handle(_ns(
        stories_command="find", query=query, project=project, tag=tag,
        json=_global["json"], debug=_global["debug"],
    ))


@stories_app.command("report")
def stories_report(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
    coverage: Annotated[bool, typer.Option("--coverage", help="Include pytest marker coverage analysis")] = False,
):
    """Show test status summary across stories."""
    _stories_handle(_ns(
        stories_command="report", project=project, coverage=coverage,
        json=_global["json"], debug=_global["debug"],
    ))


@stories_app.command("sync")
def stories_sync():
    """Scan test files for @pytest.mark.story markers and sync to TinyDB index."""
    _stories_handle(_ns(
        stories_command="sync",
        json=_global["json"], debug=_global["debug"],
    ))


@stories_app.command("coverage")
def stories_coverage(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
    min_pct: Annotated[Optional[float], typer.Option("--min-pct", help="Minimum coverage percentage")] = None,
    exit_code: Annotated[bool, typer.Option("--exit-code", help="Exit 1 if below --min-pct")] = False,
):
    """Show story-to-test coverage from the TinyDB index."""
    _stories_handle(_ns(
        stories_command="coverage", project=project, min_pct=min_pct, exit_code=exit_code,
        json=_global["json"], debug=_global["debug"],
    ))


@stories_app.command("run")
def stories_run(
    story_id: str = typer.Argument(..., help="Story ID to run tests for (e.g. US-CLI-110)"),
    module: Annotated[Optional[str], typer.Option("--module", "-m", help="Filter to specific module")] = None,
    testmon: Annotated[bool, typer.Option("--testmon", help="Use testmon for change detection")] = False,
):
    """Run tests linked to a specific story ID."""
    _stories_handle(_ns(
        stories_command="run", story_id=story_id, module=module, testmon=testmon,
        json=_global["json"], debug=_global["debug"],
    ))


@stories_app.command("status")
def stories_status(
    story_id: str = typer.Argument(..., help="Story ID to check"),
):
    """Show test status for a specific story."""
    _stories_handle(_ns(
        stories_command="status", story_id=story_id,
        json=_global["json"], debug=_global["debug"],
    ))


@stories_app.command("untested")
def stories_untested(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Filter by project")] = None,
):
    """List stories that have no test status or are marked untested."""
    _stories_handle(_ns(
        stories_command="untested", project=project,
        json=_global["json"], debug=_global["debug"],
    ))


@stories_app.command("affected")
def stories_affected(
    plan: Annotated[Optional[str], typer.Argument(help="Epic/plan folder name")] = None,
    changes: Annotated[Optional[str], typer.Option("--changes", help="Comma-separated changed files, or 'git' for git diff")] = None,
):
    """List affected stories for a plan or by file changes (via testmon)."""
    if not plan and not changes:
        from agenticcli.console import print_error
        print_error("Provide either a plan folder name or --changes flag")
        raise typer.Exit(1)
    _stories_handle(_ns(
        stories_command="affected", plan=plan, changes=changes,
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
    "devops", "epic", "stories",
}


# ===========================================================================
# run_cli() — the public entry point called from entry.py
# ===========================================================================

def run_cli():
    """Main CLI entry point. Invokes the Typer app."""
    app()
