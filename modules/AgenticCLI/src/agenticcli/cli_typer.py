#!/usr/bin/env python3
"""AgenticCLI Typer-based command structure.

This module defines the Typer application structure that replaces the argparse-based cli.py.
The architecture mirrors the existing 100+ commands while providing:
- Automatic global flag handling (--json, --debug work in ANY position)
- Type-safe command definitions with rich help text
- Cleaner command group organization via sub-applications

Architecture:
    Main app (agentic)
    ├── setup           - Interactive setup wizard
    ├── prefs           - User preferences management
    │   ├── get
    │   ├── set
    │   ├── list
    │   ├── delete
    │   └── clear
    ├── health          - CLI health check
    ├── worktree (wt)   - Git worktree management
    │   ├── create
    │   ├── list
    │   └── remove
    ├── plan            - Planning folder management
    │   ├── init
    │   ├── scaffold
    │   ├── status
    │   ├── validate
    │   ├── archive
    │   ├── unarchive
    │   ├── list
    │   ├── move
    │   │   ├── task
    │   │   ├── tasks
    │   │   └── folder
    │   ├── task
    │   │   ├── start
    │   │   ├── complete
    │   │   ├── prefill
    │   │   ├── list
    │   │   ├── status
    │   │   ├── add
    │   │   ├── update
    │   │   └── current
    │   ├── phase
    │   │   ├── add
    │   │   ├── list
    │   │   └── update
    │   ├── orchestration
    │   │   ├── generate
    │   │   └── validate
    │   └── stories
    │       ├── list
    │       └── test
    ├── config (cfg)    - Configuration management
    │   ├── show
    │   ├── init
    │   ├── get
    │   ├── set
    │   ├── list
    │   └── delete
    ├── update          - Reinstall from source
    ├── rebuild         - Full rebuild
    ├── langsmith (ls)  - LangSmith integration
    │   ├── runs
    │   ├── run
    │   ├── projects
    │   ├── stats
    │   └── friction
    ├── inputs          - Input file validation
    │   ├── validate
    │   └── resolve
    ├── template (tpl)  - Template generation
    │   └── generate
    ├── stories (st)    - User stories
    │   ├── list
    │   └── test
    ├── manifest (mf)   - Agent manifests
    │   ├── show
    │   ├── list
    │   └── validate
    ├── cicd            - CI/CD management
    │   ├── audit
    │   └── generate
    ├── state           - Process state registry
    │   ├── list
    │   ├── get
    │   ├── clear
    │   └── cleanup
    ├── session         - Claude Code sessions
    │   ├── spawn
    │   ├── list
    │   ├── stop
    │   └── status
    ├── loop            - Ralph Loops
    │   ├── start
    │   ├── stop
    │   ├── status
    │   └── history
    ├── env             - Environment variables
    │   ├── show
    │   ├── export
    │   └── run
    ├── context (ctx)   - CCI Context Injection
    │   ├── bootstrap
    │   ├── role
    │   ├── task
    │   ├── inputs
    │   └── generate-agent
    └── entrypoint (ep) - Workflow entrypoints
        ├── list
        ├── show
        └── execute
"""

from typing import Annotated, Optional

import typer

from agenticcli import __version__
from agenticcli.console import console, set_json_mode, set_debug_mode

# =============================================================================
# MAIN APPLICATION
# =============================================================================

app = typer.Typer(
    name="agentic",
    help="AgenticCLI - Command-line interface for AgenticEngineering",
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,  # Let our console handle errors
)


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"agentic {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    json: Annotated[
        bool,
        typer.Option(
            "--json", "-j",
            help="Output in JSON format for scripting/automation",
            is_eager=True,
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug", "-d",
            help="Enable debug logging to console",
            is_eager=True,
        ),
    ] = False,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version", "-v",
            help="Show version information",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
):
    """AgenticCLI - Command-line interface for AgenticEngineering.

    Global flags (--json, --debug) can be placed BEFORE or AFTER subcommands.
    """
    if json:
        set_json_mode(True)
    if debug:
        set_debug_mode(True)


# =============================================================================
# SUB-APPLICATIONS (Command Groups)
# =============================================================================

# --- Setup ---
setup_app = typer.Typer(help="Interactive setup wizard for initial configuration")
app.add_typer(setup_app, name="setup")

# --- Preferences ---
prefs_app = typer.Typer(help="Manage user preferences")
app.add_typer(prefs_app, name="prefs")
app.add_typer(prefs_app, name="preferences", hidden=True)  # alias
app.add_typer(prefs_app, name="pref", hidden=True)  # alias

# --- Health ---
health_app = typer.Typer(help="Check CLI health, dependencies, and configuration status")
app.add_typer(health_app, name="health")

# --- Worktree ---
worktree_app = typer.Typer(help="Manage git worktrees with planning folder integration")
app.add_typer(worktree_app, name="worktree")
app.add_typer(worktree_app, name="wt", hidden=True)  # alias

# --- Plan ---
plan_app = typer.Typer(help="Manage planning folders, tasks, phases, and orchestration")
app.add_typer(plan_app, name="plan")

# Plan sub-groups
plan_task_app = typer.Typer(help="Task management within plans")
plan_app.add_typer(plan_task_app, name="task")

plan_phase_app = typer.Typer(help="Phase management within plans")
plan_app.add_typer(plan_phase_app, name="phase")

plan_orchestration_app = typer.Typer(help="Orchestration MMD management")
plan_app.add_typer(plan_orchestration_app, name="orchestration")

plan_move_app = typer.Typer(help="Move tasks and folders between plans")
plan_app.add_typer(plan_move_app, name="move")

plan_stories_app = typer.Typer(help="User stories for testing")
plan_app.add_typer(plan_stories_app, name="stories")

# --- Config ---
config_app = typer.Typer(help="Configuration management (show, init, get, set, list, delete)")
app.add_typer(config_app, name="config")
app.add_typer(config_app, name="cfg", hidden=True)  # alias

# --- Update/Rebuild ---
update_app = typer.Typer(help="Reinstall AgenticCLI from source using uv sync")
app.add_typer(update_app, name="update")

rebuild_app = typer.Typer(help="Full rebuild: clean artifacts, rebuild package, reinstall")
app.add_typer(rebuild_app, name="rebuild")

# --- LangSmith ---
langsmith_app = typer.Typer(help="Query LangSmith traces, runs, projects, and statistics")
app.add_typer(langsmith_app, name="langsmith")
app.add_typer(langsmith_app, name="ls", hidden=True)  # alias

# --- Inputs ---
inputs_app = typer.Typer(help="Validate and resolve inputs.yml file references")
app.add_typer(inputs_app, name="inputs")

# --- Template ---
template_app = typer.Typer(help="Generate plan files from templates (build, test, cleanup)")
app.add_typer(template_app, name="template")
app.add_typer(template_app, name="tpl", hidden=True)  # alias

# --- Stories (top-level alias) ---
stories_app = typer.Typer(help="Find and filter user stories for testing")
app.add_typer(stories_app, name="stories")
app.add_typer(stories_app, name="st", hidden=True)  # alias

# --- Manifest ---
manifest_app = typer.Typer(help="Display, list, and validate agent manifests")
app.add_typer(manifest_app, name="manifest")
app.add_typer(manifest_app, name="mf", hidden=True)  # alias

# --- CICD ---
cicd_app = typer.Typer(help="CI/CD configuration management and auditing")
app.add_typer(cicd_app, name="cicd")

# --- State ---
state_app = typer.Typer(help="Manage process state registry for tracking CLI operations")
app.add_typer(state_app, name="state")

# --- Session ---
session_app = typer.Typer(help="Manage Claude Code sessions (spawn, list, stop, status)")
app.add_typer(session_app, name="session")

# --- Loop ---
loop_app = typer.Typer(help="Manage Ralph Loops (start, stop, status, history)")
app.add_typer(loop_app, name="loop")

# --- Env ---
env_app = typer.Typer(help="Environment variable injection (show, export, run)")
app.add_typer(env_app, name="env")

# --- Context (CCI) ---
context_app = typer.Typer(help="CCI context retrieval for agents to self-initialize")
app.add_typer(context_app, name="context")
app.add_typer(context_app, name="ctx", hidden=True)  # alias

# --- Entrypoint ---
entrypoint_app = typer.Typer(help="Discover and execute workflow entrypoints")
app.add_typer(entrypoint_app, name="entrypoint")
app.add_typer(entrypoint_app, name="ep", hidden=True)  # alias


# =============================================================================
# COMMAND IMPLEMENTATIONS (Stubs - to be filled in during migration)
# =============================================================================

# --- Setup Commands ---
@setup_app.callback(invoke_without_command=True)
def setup_main(ctx: typer.Context):
    """Run the interactive setup wizard."""
    if ctx.invoked_subcommand is None:
        from agenticcli.commands import setup
        # Create minimal args object for backward compatibility
        class Args:
            json = False
        setup.handle(Args())


# --- Health Commands ---
@health_app.callback(invoke_without_command=True)
def health_main(ctx: typer.Context):
    """Check CLI health and dependencies."""
    if ctx.invoked_subcommand is None:
        from agenticcli.commands import health
        class Args:
            json = False
            health_command = None
        health.handle(Args())


# --- Plan Commands ---
@plan_app.command("init")
def plan_init(
    branch: Annotated[str, typer.Argument(help="Branch name for the worktree")],
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Plan description")] = None,
    base: Annotated[str, typer.Option("--base", "-b", help="Base branch to create from")] = "main",
):
    """Initialize worktree and plan folder with proper naming convention."""
    from agenticcli.commands import plan
    class Args:
        plan_command = "init"
    args = Args()
    args.branch = branch
    args.description = description
    args.base = base
    plan.handle(args)


@plan_app.command("status")
def plan_status(
    path: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
):
    """Show plan status and task summary."""
    from agenticcli.commands import plan
    class Args:
        plan_command = "status"
    args = Args()
    args.path = path
    plan.handle(args)


@plan_app.command("list")
def plan_list(
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="Filter by status")] = None,
    completed: Annotated[bool, typer.Option("--completed", "-c", help="Include completed plans")] = False,
):
    """List all plans."""
    from agenticcli.commands import plan
    class Args:
        plan_command = "list"
    args = Args()
    args.status = status
    args.completed = completed
    plan.handle(args)


@plan_app.command("scaffold")
def plan_scaffold(
    name: Annotated[str, typer.Argument(help="Folder name (e.g., 260103AE_feature)")],
    worktree: Annotated[Optional[str], typer.Option("--worktree", "-w", help="Worktree path")] = None,
):
    """Create planning folder structure."""
    from agenticcli.commands import plan
    class Args:
        plan_command = "scaffold"
    args = Args()
    args.name = name
    args.worktree = worktree
    plan.handle(args)


@plan_app.command("validate")
def plan_validate(
    path: Annotated[str, typer.Argument(help="Path to plan folder to validate")],
    strict: Annotated[bool, typer.Option("--strict", help="Fail on stub templates")] = False,
):
    """Validate plan folder structure and YAML."""
    from agenticcli.commands import plan
    class Args:
        plan_command = "validate"
    args = Args()
    args.path = path
    args.strict = strict
    plan.handle(args)


@plan_app.command("archive")
def plan_archive(
    path: Annotated[str, typer.Argument(help="Path to plan folder to archive")],
):
    """Copy plan to completed folder."""
    from agenticcli.commands import plan
    class Args:
        plan_command = "archive"
    args = Args()
    args.path = path
    plan.handle(args)


@plan_app.command("unarchive")
def plan_unarchive(
    plan: Annotated[str, typer.Option("--plan", "-p", help="Plan folder name")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Move plan from completed back to live."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "unarchive"
    args = Args()
    args.plan = plan
    args.force = force
    plan_cmd.handle(args)


# --- Plan Task Commands ---
@plan_task_app.command("start")
def plan_task_start(
    task_id: Annotated[str, typer.Argument(help="Task ID (e.g., P1-01)")],
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
):
    """Mark a task as in_progress."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "task"
        task_action = "start"
    args = Args()
    args.task_id = task_id
    args.plan = plan
    plan_cmd.handle(args)


@plan_task_app.command("complete")
def plan_task_complete(
    task_id: Annotated[str, typer.Argument(help="Task ID (e.g., P1-01)")],
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    no_archive: Annotated[bool, typer.Option("--no-archive", help="Skip auto-archival")] = False,
):
    """Mark a task as completed."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "task"
        task_action = "complete"
    args = Args()
    args.task_id = task_id
    args.plan = plan
    args.no_archive = no_archive
    plan_cmd.handle(args)


@plan_task_app.command("list")
def plan_task_list(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="Filter by status")] = None,
):
    """List all tasks in a plan."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "task"
        task_action = "list"
    args = Args()
    args.plan = plan
    args.status = status
    plan_cmd.handle(args)


@plan_task_app.command("current")
def plan_task_current(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
):
    """Get the current/next task to work on."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "task"
        task_action = "current"
    args = Args()
    args.plan = plan
    plan_cmd.handle(args)


@plan_task_app.command("prefill")
def plan_task_prefill(
    preset: Annotated[str, typer.Option("--preset", "-t", help="Preset name")],
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
):
    """Load preset task list from template."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "task"
        task_action = "prefill"
    args = Args()
    args.preset = preset
    args.plan = plan
    args.dry_run = dry_run
    plan_cmd.handle(args)


@plan_task_app.command("status")
def plan_task_status(
    task_id: Annotated[str, typer.Argument(help="Task ID")],
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
):
    """Show detailed status for a specific task."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "task"
        task_action = "status"
    args = Args()
    args.task_id = task_id
    args.plan = plan
    plan_cmd.handle(args)


@plan_task_app.command("add")
def plan_task_add(
    description: Annotated[str, typer.Argument(help="Task description")],
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    phase: Annotated[Optional[str], typer.Option("--phase", "-ph", help="Phase ID")] = None,
    id: Annotated[Optional[str], typer.Option("--id", help="Custom task ID")] = None,
    priority: Annotated[str, typer.Option("--priority", help="Task priority")] = "medium",
):
    """Add new task to plan."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "task"
        task_action = "add"
    args = Args()
    args.description = description
    args.plan = plan
    args.phase = phase
    args.id = id
    args.priority = priority
    plan_cmd.handle(args)


@plan_task_app.command("update")
def plan_task_update(
    task_id: Annotated[str, typer.Argument(help="Task ID")],
    status: Annotated[str, typer.Option("--status", "-s", help="New status")],
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    note: Annotated[Optional[str], typer.Option("--note", "-n", help="Completion note")] = None,
    no_archive: Annotated[bool, typer.Option("--no-archive", help="Skip auto-archival")] = False,
):
    """Update task status in plan file."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "task"
        task_action = "update"
    args = Args()
    args.task_id = task_id
    args.status = status
    args.plan = plan
    args.note = note
    args.no_archive = no_archive
    plan_cmd.handle(args)


# --- Plan Phase Commands ---
@plan_phase_app.command("list")
def plan_phase_list(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
):
    """Show all phases with task counts."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "phase"
        phase_action = "list"
    args = Args()
    args.plan = plan
    plan_cmd.handle(args)


@plan_phase_app.command("add")
def plan_phase_add(
    id: Annotated[str, typer.Option("--id", help="Phase ID (e.g., P3)")],
    name: Annotated[str, typer.Option("--name", "-n", help="Phase name")],
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    description: Annotated[Optional[str], typer.Option("--description", "-d", help="Phase description")] = None,
):
    """Add a new phase to plan."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "phase"
        phase_action = "add"
    args = Args()
    args.id = id
    args.name = name
    args.plan = plan
    args.description = description
    plan_cmd.handle(args)


@plan_phase_app.command("update")
def plan_phase_update(
    phase_id: Annotated[str, typer.Argument(help="Phase ID")],
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="New status")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
):
    """Update phase status."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "phase"
        phase_action = "update"
    args = Args()
    args.phase_id = phase_id
    args.status = status
    args.plan = plan
    plan_cmd.handle(args)


# --- Plan Orchestration Commands ---
@plan_orchestration_app.command("generate")
def plan_orchestration_generate(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output filename")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing")] = False,
):
    """Generate orchestration MMD from plan YAML."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "orchestration"
        orchestration_action = "generate"
    args = Args()
    args.plan = plan
    args.output = output
    args.force = force
    plan_cmd.handle(args)


@plan_orchestration_app.command("validate")
def plan_orchestration_validate(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Treat warnings as errors")] = False,
):
    """Validate orchestration MMD against plan YAML."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "orchestration"
        orchestration_action = "validate"
    args = Args()
    args.plan = plan
    args.strict = strict
    plan_cmd.handle(args)


# --- Plan Move Commands ---
@plan_move_app.command("task")
def plan_move_task(
    task_id: Annotated[str, typer.Argument(help="Task ID to move")],
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Move even if uncommitted changes")] = False,
):
    """Move a single completed task."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "move"
        move_type = "task"
    args = Args()
    args.task_id = task_id
    args.plan = plan
    args.dry_run = dry_run
    args.force = force
    plan_cmd.handle(args)


@plan_move_app.command("tasks")
def plan_move_tasks(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Move even if uncommitted changes")] = False,
):
    """Move all completed tasks."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "move"
        move_type = "tasks"
    args = Args()
    args.plan = plan
    args.dry_run = dry_run
    args.force = force
    plan_cmd.handle(args)


@plan_move_app.command("folder")
def plan_move_folder(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help="Show without changes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Archive even if uncommitted changes")] = False,
):
    """Archive the plan folder."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "move"
        move_type = "folder"
    args = Args()
    args.plan = plan
    args.dry_run = dry_run
    args.force = force
    plan_cmd.handle(args)


# --- Plan Stories Commands ---
@plan_stories_app.command("list")
def plan_stories_list(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
):
    """List user stories."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "stories"
        stories_action = "list"
    args = Args()
    args.plan = plan
    plan_cmd.handle(args)


@plan_stories_app.command("test")
def plan_stories_test(
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
):
    """Test user stories."""
    from agenticcli.commands import plan as plan_cmd
    class Args:
        plan_command = "stories"
        stories_action = "test"
    args = Args()
    args.plan = plan
    plan_cmd.handle(args)


# --- Context Commands ---
@context_app.command("bootstrap")
def context_bootstrap(
    role: Annotated[Optional[str], typer.Option("--role", "-r", help="Agent role ID")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", "-p", help="Path to plan folder")] = None,
):
    """Get Seed Context: Active Task + Role Guidance + Essential Inputs."""
    from agenticcli.commands import context
    class Args:
        context_command = "bootstrap"
    args = Args()
    args.role = role
    args.plan = plan
    context.handle(args)


@context_app.command("role")
def context_role(
    role_id: Annotated[str, typer.Argument(help="Role ID (e.g., planner-build)")],
    format: Annotated[str, typer.Option("--format", "-f", help="Output format")] = "yaml",
):
    """Returns process.yml and manifest.yml content for a specific role."""
    from agenticcli.commands import context
    class Args:
        context_command = "role"
    args = Args()
    args.role_id = role_id
    args.format = format
    context.handle(args)


@context_app.command("task")
def context_task(
    all: Annotated[bool, typer.Option("--all", "-a", help="Show all tasks")] = False,
):
    """Crawls docs/plans/live/ to find active task."""
    from agenticcli.commands import context
    class Args:
        context_command = "task"
    args = Args()
    args.all = all
    context.handle(args)


@context_app.command("inputs")
def context_inputs(
    role: Annotated[str, typer.Option("--role", "-r", help="Role ID")],
    resolve: Annotated[bool, typer.Option("--resolve", help="Expand layer references")] = False,
):
    """Returns input files for a role with path resolution."""
    from agenticcli.commands import context
    class Args:
        context_command = "inputs"
    args = Args()
    args.role = role
    args.resolve = resolve
    context.handle(args)


@context_app.command("generate-agent")
def context_generate_agent(
    role_id: Annotated[str, typer.Argument(help="Role ID")],
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path")] = None,
):
    """Generate thin-client agent file from bootstrap template."""
    from agenticcli.commands import context
    class Args:
        context_command = "generate-agent"
    args = Args()
    args.role_id = role_id
    args.output = output
    context.handle(args)


# --- Worktree Commands ---
@worktree_app.command("create")
def worktree_create(
    branch: Annotated[str, typer.Argument(help="Branch name for worktree")],
    base: Annotated[str, typer.Option("--base", "-b", help="Base branch")] = "main",
):
    """Create a new git worktree."""
    from agenticcli.commands import worktree
    class Args:
        worktree_command = "create"
    args = Args()
    args.branch = branch
    args.base = base
    worktree.handle(args)


@worktree_app.command("list")
def worktree_list():
    """List all worktrees."""
    from agenticcli.commands import worktree
    class Args:
        worktree_command = "list"
    args = Args()
    worktree.handle(args)


@worktree_app.command("remove")
def worktree_remove(
    branch: Annotated[str, typer.Argument(help="Branch name to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Force removal")] = False,
):
    """Remove a worktree."""
    from agenticcli.commands import worktree
    class Args:
        worktree_command = "remove"
    args = Args()
    args.branch = branch
    args.force = force
    worktree.handle(args)


@worktree_app.command("status")
def worktree_status():
    """Show detailed status of current worktree."""
    from agenticcli.commands import worktree
    class Args:
        worktree_command = "status"
    args = Args()
    worktree.handle(args)


@worktree_app.command("validate")
def worktree_validate():
    """Validate worktree-plan synchronization."""
    from agenticcli.commands import worktree
    class Args:
        worktree_command = "validate"
    args = Args()
    worktree.handle(args)


@worktree_app.command("sync")
def worktree_sync():
    """Synchronize workspace file with actual worktrees."""
    from agenticcli.commands import worktree
    class Args:
        worktree_command = "sync"
    args = Args()
    worktree.handle(args)


# --- Prefs Commands ---
@prefs_app.command("get")
def prefs_get(
    key: Annotated[str, typer.Argument(help="Preference key")],
):
    """Get a preference value."""
    from agenticcli.commands import preferences
    class Args:
        prefs_command = "get"
    args = Args()
    args.key = key
    preferences.handle(args)


@prefs_app.command("set")
def prefs_set(
    key: Annotated[str, typer.Argument(help="Preference key")],
    value: Annotated[str, typer.Argument(help="Preference value")],
):
    """Set a preference value."""
    from agenticcli.commands import preferences
    class Args:
        prefs_command = "set"
    args = Args()
    args.key = key
    args.value = value
    preferences.handle(args)


@prefs_app.command("list")
def prefs_list():
    """List all preferences."""
    from agenticcli.commands import preferences
    class Args:
        prefs_command = "list"
    args = Args()
    preferences.handle(args)


@prefs_app.command("delete")
def prefs_delete(
    key: Annotated[str, typer.Argument(help="Preference key to delete")],
):
    """Delete a preference."""
    from agenticcli.commands import preferences
    class Args:
        prefs_command = "delete"
    args = Args()
    args.key = key
    preferences.handle(args)


# --- Session Commands ---
@session_app.command("spawn")
def session_spawn(
    prompt: Annotated[Optional[str], typer.Option("--prompt", "-p", help="Session prompt")] = None,
    role: Annotated[Optional[str], typer.Option("--role", "-r", help="Agent role")] = None,
    plan: Annotated[Optional[str], typer.Option("--plan", help="Plan folder path")] = None,
    background: Annotated[bool, typer.Option("--background", "-b", help="Run in background")] = False,
):
    """Start new Claude Code session."""
    from agenticcli.commands import session
    class Args:
        session_command = "spawn"
    args = Args()
    args.prompt = prompt
    args.role = role
    args.plan = plan
    args.background = background
    session.handle(args)


@session_app.command("list")
def session_list(
    active: Annotated[bool, typer.Option("--active", "-a", help="Show only running")] = False,
):
    """List all sessions."""
    from agenticcli.commands import session
    class Args:
        session_command = "list"
    args = Args()
    args.active = active
    session.handle(args)


@session_app.command("status")
def session_status(
    session_id: Annotated[str, typer.Argument(help="Session ID")],
):
    """Get session status."""
    from agenticcli.commands import session
    class Args:
        session_command = "status"
    args = Args()
    args.session_id = session_id
    session.handle(args)


@session_app.command("stop")
def session_stop(
    session_id: Annotated[str, typer.Argument(help="Session ID")],
):
    """Stop a running session."""
    from agenticcli.commands import session
    class Args:
        session_command = "stop"
    args = Args()
    args.session_id = session_id
    session.handle(args)


# --- Loop Commands ---
@loop_app.command("start")
def loop_start(
    prompt: Annotated[Optional[str], typer.Option("--prompt", "-p", help="Loop prompt")] = None,
    entrypoint: Annotated[Optional[str], typer.Option("--entrypoint", "-e", help="Entrypoint name")] = None,
    file: Annotated[Optional[str], typer.Option("--file", "-f", help="Prompt file")] = None,
    background: Annotated[bool, typer.Option("--background", "-b", help="Run in background")] = False,
):
    """Start a new Ralph Loop."""
    from agenticcli.commands import loop
    class Args:
        loop_command = "start"
    args = Args()
    args.prompt = prompt
    args.entrypoint = entrypoint
    args.file = file
    args.background = background
    loop.handle(args)


@loop_app.command("stop")
def loop_stop(
    loop_id: Annotated[str, typer.Argument(help="Loop ID")],
):
    """Stop a running loop."""
    from agenticcli.commands import loop
    class Args:
        loop_command = "stop"
    args = Args()
    args.loop_id = loop_id
    loop.handle(args)


@loop_app.command("status")
def loop_status(
    loop_id: Annotated[str, typer.Argument(help="Loop ID")],
):
    """Get loop status."""
    from agenticcli.commands import loop
    class Args:
        loop_command = "status"
    args = Args()
    args.loop_id = loop_id
    loop.handle(args)


@loop_app.command("history")
def loop_history(
    status: Annotated[Optional[str], typer.Option("--status", "-s", help="Filter by status")] = None,
):
    """Show loop history."""
    from agenticcli.commands import loop
    class Args:
        loop_command = "history"
    args = Args()
    args.status = status
    loop.handle(args)


# --- Entrypoint Commands ---
@entrypoint_app.command("list")
def entrypoint_list():
    """List all available entrypoints."""
    from agenticcli.commands import entrypoint
    class Args:
        entrypoint_command = "list"
    args = Args()
    entrypoint.handle(args)


@entrypoint_app.command("show")
def entrypoint_show(
    name: Annotated[str, typer.Argument(help="Entrypoint name")],
):
    """Display entrypoint contents."""
    from agenticcli.commands import entrypoint
    class Args:
        entrypoint_command = "show"
    args = Args()
    args.name = name
    entrypoint.handle(args)


@entrypoint_app.command("execute")
def entrypoint_execute(
    name: Annotated[str, typer.Argument(help="Entrypoint name")],
    compile: Annotated[bool, typer.Option("--compile", help="Compile with dependencies")] = False,
    context: Annotated[Optional[str], typer.Option("--context", help="Additional context")] = None,
):
    """Execute an entrypoint."""
    from agenticcli.commands import entrypoint
    class Args:
        entrypoint_command = "execute"
    args = Args()
    args.name = name
    args.compile = compile
    args.context = context
    entrypoint.handle(args)


# --- Config Commands ---
@config_app.command("show")
def config_show():
    """Show current configuration."""
    from agenticcli.commands import config
    class Args:
        config_command = "show"
    args = Args()
    config.handle(args)


@config_app.command("get")
def config_get(
    key: Annotated[str, typer.Argument(help="Config key")],
):
    """Get a configuration value."""
    from agenticcli.commands import config
    class Args:
        config_command = "get"
    args = Args()
    args.key = key
    config.handle(args)


@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Config key")],
    value: Annotated[str, typer.Argument(help="Config value")],
):
    """Set a configuration value."""
    from agenticcli.commands import config
    class Args:
        config_command = "set"
    args = Args()
    args.key = key
    args.value = value
    config.handle(args)


# --- Update/Rebuild Commands ---
@update_app.callback(invoke_without_command=True)
def update_main(ctx: typer.Context):
    """Reinstall AgenticCLI from source."""
    if ctx.invoked_subcommand is None:
        from agenticcli.commands import update
        class Args:
            update_command = None
        update.handle(Args())


@rebuild_app.callback(invoke_without_command=True)
def rebuild_main(ctx: typer.Context):
    """Full rebuild of AgenticCLI."""
    if ctx.invoked_subcommand is None:
        from agenticcli.commands import rebuild
        class Args:
            rebuild_command = None
        rebuild.handle(Args())


# --- LangSmith Commands ---
@langsmith_app.command("runs")
def langsmith_runs(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Project name")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Max results")] = 10,
):
    """List LangSmith runs."""
    from agenticcli.commands import langsmith
    class Args:
        langsmith_command = "runs"
    args = Args()
    args.project = project
    args.limit = limit
    langsmith.handle(args)


@langsmith_app.command("stats")
def langsmith_stats(
    project: Annotated[Optional[str], typer.Option("--project", "-p", help="Project name")] = None,
):
    """Show LangSmith statistics."""
    from agenticcli.commands import langsmith
    class Args:
        langsmith_command = "stats"
    args = Args()
    args.project = project
    langsmith.handle(args)


# =============================================================================
# ENTRY POINT
# =============================================================================

def main_typer():
    """Entry point for Typer-based CLI."""
    app()


if __name__ == "__main__":
    main_typer()
