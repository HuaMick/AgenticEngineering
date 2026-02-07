"""Typer wrapper for AgenticCLI providing shell auto-completion.

This module creates a Typer application that wraps the existing argparse-based CLI,
providing shell auto-completion without requiring a full migration.

Architecture:
- All command implementations remain in cli.py and commands/ modules
- Typer commands delegate to the existing argparse handlers via run_cli()
- Shell completion is enabled via Typer's built-in completion support
- No breaking changes to existing CLI behavior

Usage:
    agentic --install-completion  # Install shell completion
    agentic <TAB><TAB>             # Auto-complete commands
"""

import sys
from typing import Optional, List

import typer
from typing_extensions import Annotated

app = typer.Typer(
    name="agentic",
    help="AgenticCLI - Command-line interface for AgenticEngineering",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
)


def delegate_to_argparse(command_args: List[str]):
    """Delegate command to existing argparse CLI.

    Args:
        command_args: Command arguments to pass to argparse CLI
    """
    from agenticcli.cli import run_cli

    # Replace sys.argv with our command args
    original_argv = sys.argv
    sys.argv = ["agentic"] + command_args

    try:
        run_cli()
    finally:
        sys.argv = original_argv


# Global callback for global options
@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option("--version", "-v", help="Show version")] = False,
    json: Annotated[bool, typer.Option("--json", "-j", help="Output in JSON format")] = False,
    debug: Annotated[bool, typer.Option("--debug", "-d", help="Enable debug logging")] = False,
):
    """AgenticCLI - Command-line interface for AgenticEngineering."""
    if version:
        from agenticcli import __version__
        print(f"agentic {__version__}")
        raise typer.Exit()

    # Store global options in context for subcommands
    if ctx.obj is None:
        ctx.obj = {}
    ctx.obj["json"] = json
    ctx.obj["debug"] = debug


# Setup command
@app.command()
def setup(ctx: typer.Context):
    """Interactive setup wizard for initial configuration."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["setup"] + args)


# Health command
@app.command()
def health(ctx: typer.Context):
    """Check CLI health, dependencies, and configuration status."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["health"] + args)


# Preferences commands
preferences_app = typer.Typer(help="Manage user preferences")
app.add_typer(preferences_app, name="preferences")
app.add_typer(preferences_app, name="prefs")
app.add_typer(preferences_app, name="pref")


@preferences_app.command("show")
def prefs_show(ctx: typer.Context):
    """Show current preferences."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["preferences", "show"] + args)


@preferences_app.command("set")
def prefs_set(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Preference key"),
    value: str = typer.Argument(..., help="Preference value"),
):
    """Set a preference value."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["preferences", "set", key, value] + args)


# Worktree commands
worktree_app = typer.Typer(help="Manage git worktrees with planning folder integration")
app.add_typer(worktree_app, name="worktree")
app.add_typer(worktree_app, name="wt")


@worktree_app.command("list")
def wt_list(ctx: typer.Context):
    """List all worktrees."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["worktree", "list"] + args)


@worktree_app.command("create")
def wt_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Worktree name"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch name"),
):
    """Create a new worktree."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if branch:
        args.extend(["--branch", branch])
    delegate_to_argparse(["worktree", "create", name] + args)


@worktree_app.command("remove")
def wt_remove(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Worktree name"),
):
    """Remove a worktree."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["worktree", "remove", name] + args)


# Plan commands
plan_app = typer.Typer(help="Create, validate, and manage planning folders")
app.add_typer(plan_app, name="plan")


@plan_app.command("init")
def plan_init(
    ctx: typer.Context,
    plan_name: Optional[str] = typer.Argument(None, help="Plan folder name"),
):
    """Initialize a new plan folder."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if plan_name:
        args.append(plan_name)
    delegate_to_argparse(["plan", "init"] + args)


@plan_app.command("list")
def plan_list(ctx: typer.Context):
    """List all plans in the repository."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["plan", "list"] + args)


@plan_app.command("validate")
def plan_validate(
    ctx: typer.Context,
    plan_path: Optional[str] = typer.Argument(None, help="Path to plan folder"),
):
    """Validate a plan folder structure."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if plan_path:
        args.append(plan_path)
    delegate_to_argparse(["plan", "validate"] + args)


# Plan task commands
plan_task_app = typer.Typer(help="Manage plan tasks")
plan_app.add_typer(plan_task_app, name="task")


@plan_task_app.command("list")
def plan_task_list(
    ctx: typer.Context,
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
):
    """List all tasks in the plan."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if status:
        args.extend(["--status", status])
    delegate_to_argparse(["plan", "task", "list"] + args)


@plan_task_app.command("current")
def plan_task_current(ctx: typer.Context):
    """Get current/next task to work on."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["plan", "task", "current"] + args)


# Session commands
session_app = typer.Typer(help="Manage Claude Code sessions")
app.add_typer(session_app, name="session")


@session_app.command("spawn")
def session_spawn(
    ctx: typer.Context,
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Task prompt"),
    background: bool = typer.Option(False, "--background", help="Run in background"),
):
    """Start a new Claude Code session."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if prompt:
        args.extend(["--prompt", prompt])
    if background:
        args.append("--background")
    delegate_to_argparse(["session", "spawn"] + args)


@session_app.command("list")
def session_list(
    ctx: typer.Context,
    active: bool = typer.Option(False, "--active", help="Show only active sessions"),
):
    """List all sessions."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if active:
        args.append("--active")
    delegate_to_argparse(["session", "list"] + args)


@session_app.command("status")
def session_status(
    ctx: typer.Context,
    session_id: str = typer.Argument(..., help="Session ID"),
):
    """Get session status."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["session", "status", session_id] + args)


@session_app.command("stop")
def session_stop(
    ctx: typer.Context,
    session_id: str = typer.Argument(..., help="Session ID"),
):
    """Stop a running session."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["session", "stop", session_id] + args)


# Loop commands
loop_app = typer.Typer(help="Manage Ralph loops")
app.add_typer(loop_app, name="loop")


@loop_app.command("start")
def loop_start(
    ctx: typer.Context,
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Task prompt"),
    entrypoint: Optional[str] = typer.Option(None, "--entrypoint", "-e", help="Entrypoint name"),
    background: bool = typer.Option(False, "--background", help="Run in background"),
):
    """Start a new Ralph loop."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if prompt:
        args.extend(["--prompt", prompt])
    if entrypoint:
        args.extend(["--entrypoint", entrypoint])
    if background:
        args.append("--background")
    delegate_to_argparse(["loop", "start"] + args)


@loop_app.command("status")
def loop_status(
    ctx: typer.Context,
    loop_id: str = typer.Argument(..., help="Loop ID"),
):
    """Get loop status and progress."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["loop", "status", loop_id] + args)


@loop_app.command("stop")
def loop_stop(
    ctx: typer.Context,
    loop_id: str = typer.Argument(..., help="Loop ID"),
):
    """Stop a running loop."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["loop", "stop", loop_id] + args)


@loop_app.command("history")
def loop_history(
    ctx: typer.Context,
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
):
    """Show past loop executions."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if status:
        args.extend(["--status", status])
    delegate_to_argparse(["loop", "history"] + args)


# Context commands
context_app = typer.Typer(help="CCI context retrieval for agents")
app.add_typer(context_app, name="context")
app.add_typer(context_app, name="ctx")


@context_app.command("bootstrap")
def context_bootstrap(
    ctx: typer.Context,
    role: Optional[str] = typer.Option(None, "--role", help="Agent role"),
):
    """Get Seed Context: Active Task + Role Guidance + Essential Inputs."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if role:
        args.extend(["--role", role])
    delegate_to_argparse(["context", "bootstrap"] + args)


@context_app.command("task")
def context_task(
    ctx: typer.Context,
    all_tasks: bool = typer.Option(False, "--all", help="Show all tasks"),
):
    """Get active task from Main-First plan."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if all_tasks:
        args.append("--all")
    delegate_to_argparse(["context", "task"] + args)


# Config commands
config_app = typer.Typer(help="Configuration management")
app.add_typer(config_app, name="config")
app.add_typer(config_app, name="cfg")


@config_app.command("show")
def config_show(ctx: typer.Context):
    """Show current configuration."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["config", "show"] + args)


# Update command
@app.command()
def update(ctx: typer.Context):
    """Reinstall AgenticCLI from source using uv sync."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["update"] + args)


# Rebuild command
@app.command()
def rebuild(ctx: typer.Context):
    """Full rebuild: clean artifacts, rebuild package, reinstall."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["rebuild"] + args)


# State command
@app.command()
def state(ctx: typer.Context, subcommand: Optional[str] = typer.Argument(None)):
    """Manage process state registry for tracking CLI operations."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if subcommand:
        args.append(subcommand)
    delegate_to_argparse(["state"] + args)


# Langsmith commands
langsmith_app = typer.Typer(help="Query LangSmith traces, runs, projects, and statistics")
app.add_typer(langsmith_app, name="langsmith")
app.add_typer(langsmith_app, name="ls")


@langsmith_app.command("list")
def langsmith_list(ctx: typer.Context):
    """List LangSmith traces."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["langsmith", "list"] + args)


# Entrypoint commands
entrypoint_app = typer.Typer(help="Discover and execute workflow entrypoints")
app.add_typer(entrypoint_app, name="entrypoint")
app.add_typer(entrypoint_app, name="ep")


@entrypoint_app.command("list")
def entrypoint_list(ctx: typer.Context):
    """List all available entrypoints."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["entrypoint", "list"] + args)


@entrypoint_app.command("show")
def entrypoint_show(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Entrypoint name"),
):
    """Display contents of an entrypoint file by name."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    delegate_to_argparse(["entrypoint", "show", name] + args)


@entrypoint_app.command("execute")
def entrypoint_execute(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Entrypoint name"),
    compile: bool = typer.Option(False, "--compile", help="Compile with dependencies"),
):
    """Execute entrypoint with variable substitution."""
    args = []
    if ctx.obj and ctx.obj.get("json"):
        args.append("--json")
    if ctx.obj and ctx.obj.get("debug"):
        args.append("--debug")
    if compile:
        args.append("--compile")
    delegate_to_argparse(["entrypoint", "execute", name] + args)


if __name__ == "__main__":
    app()
