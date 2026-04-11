# story: US-PLN-046
"""Orchestrate command - run automated orchestration planning and execution for epics.

Provides `planning` and `executing` actions for the orchestration lifecycle.
Supports --dry-run mode for testable tmux layout verification.
"""

import json as json_mod
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from agenticcli.utils.session_id import generate_loop_id
from agenticcli.utils.state_store import StateStore


def _get_repo_root() -> Path:
    """Find the repository root via git rev-parse."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: walk up from this file
        p = Path(__file__).resolve()
        while p != p.parent:
            if (p / ".git").exists():
                return p
            p = p.parent
        return Path.cwd()


_store = StateStore("sessions", id_key="session_id")


def _run_planning_loop(args, ctx=None):
    """Run automated planning loop.

    Args:
        args: Parsed arguments with background, max_iterations, etc.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success

    max_iterations = getattr(args, "max_iterations", 10)
    background = getattr(args, "background", False)
    completion_promise = getattr(args, "completion_promise", None)
    project = getattr(args, "project", None)
    plan_folder = getattr(args, "plan", None)
    working_dir = getattr(args, "directory", None) or os.getcwd()
    prompt = getattr(args, "prompt", None)

    loop_id = os.environ.get("AGENTIC_ORCH_LOOP_ID")
    if not loop_id:
        loop_id = generate_loop_id("orch")

    state = {
        "session_id": loop_id,
        "type": "orchestration",
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "pid": None,
        "max_iterations": max_iterations,
        "current_iteration": 0,
        "plans_processed": [],
        "plans_failed": [],
        "current_plan": None,
        "errors": [],
        "completion_promise": completion_promise,
        "directory": working_dir,
        "plan_folder": plan_folder,
    }

    if background:
        # Re-invoke in foreground as a subprocess to detach from the terminal.
        # NOTE: The actual Claude agent invocations inside the loop use the SDK
        # (via PlannerLoopWorkflow._run_role_agent). This subprocess is just
        # the process-control wrapper that allows background detachment.
        cmd = [sys.executable, "-m", "agenticcli.entry", "orchestrate", "session", "plan"]
        cmd.extend(["--max-iterations", str(max_iterations)])
        if completion_promise:
            cmd.extend(["--completion-promise", completion_promise])
        if project:
            cmd.extend(["--project", project])
        if plan_folder:
            cmd.extend(["--plan", plan_folder])
        if prompt:
            cmd.extend(["--prompt", prompt])
        if getattr(args, "dangerously_skip_permissions", False):
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--directory", working_dir])

        logs_dir = _store.get_dir() / loop_id
        logs_dir.mkdir(parents=True, exist_ok=True)

        stdout_log = open(logs_dir / "stdout.log", "w")
        stderr_log = open(logs_dir / "stderr.log", "w")

        from agenticcli.utils.subprocess_utils import get_clean_env
        env = get_clean_env()
        env["AGENTIC_ORCH_LOOP_ID"] = loop_id

        # Record SDK transport metadata so consumers know agent calls use the SDK
        from agenticcli.utils.sdk_runner import SDK_AVAILABLE as _ORCH_SDK_AVAILABLE
        from agenticcli.utils.transport import determine_transport
        state["transport"] = determine_transport(sdk_available=_ORCH_SDK_AVAILABLE)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdin=subprocess.DEVNULL,
                stdout=stdout_log,
                stderr=stderr_log,
                start_new_session=True,
                env=env,
            )
        finally:
            stdout_log.close()
            stderr_log.close()

        state["pid"] = process.pid
        state["status"] = "running"
        _store.save(state)

        if is_json_output():
            print_json({
                "session_id": loop_id,
                "type": "orchestration",
                "pid": process.pid,
                "status": "running",
                "background": True,
                "max_iterations": max_iterations,
                "transport": state["transport"],
            })
        else:
            print_success(f"Orchestration loop {loop_id} started in background (PID: {process.pid})")
            console.print(f"[dim]Max iterations: {max_iterations}[/dim]")
            if state["transport"] in ("sdk", "sdk-tmux"):
                console.print("[dim]Agent invocations use Claude Agent SDK[/dim]")
        return

    # Foreground execution
    state["pid"] = os.getpid()
    state["status"] = "running"
    _store.save(state)

    from agenticcli.workflows.orchestration import PlanningRunner
    from agenticcli.workflows.planner_loop import PlannerLoopWorkflow

    workflow = PlannerLoopWorkflow(working_dir=working_dir, prompt=prompt)
    budget_usd = getattr(args, "budget_usd", 50.0)
    runner = PlanningRunner(
        workflow=workflow, project=project, plan_folder=plan_folder,
        budget_usd=budget_usd,
    )

    try:
        success = runner.run(
            max_iterations=max_iterations,
            completion_promise=completion_promise,
        )
        # Partial-success detection: if the runner reported failure but the
        # target epic has meaningful output in TinyDB (phases and/or tickets),
        # the run was interrupted (e.g., budget exhausted) AFTER producing
        # usable output. Report partial success with actionable next steps
        # instead of opaque "all epics failed". See UAT feedback 2026-04-11.
        partial_success = False
        partial_ready_to_implement = False
        partial_summary = ""
        if not success and plan_folder:
            try:
                from agenticcli.utils.phase_validation import validate_phase_routing
                from agenticguidance.services.epic_repository import EpicRepository
                with EpicRepository() as _repo:
                    _phases = _repo.list_phases(plan_folder)
                    _epic = _repo.get_epic(plan_folder)
                    _tickets = _epic.tasks if _epic else []
                    if _phases or _tickets:
                        partial_success = True
                        is_valid, _reason = validate_phase_routing(_repo, plan_folder)
                        partial_ready_to_implement = bool(is_valid)
                        _routed = sum(1 for p in _phases if getattr(p, "agent", None))
                        partial_summary = (
                            f"{len(_phases)} phase(s) ({_routed} routed), "
                            f"{len(_tickets)} ticket(s)"
                        )
            except Exception:
                pass

        if success:
            state["status"] = "completed"
        elif partial_success:
            state["status"] = "partial"
        else:
            state["status"] = "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["plans_processed"] = runner.state["plans_processed"]
        state["plans_failed"] = runner.state.get("plans_failed", [])
        state["errors"] = runner.state["errors"]
        state["current_iteration"] = runner.state["iteration"]
        _store.save(state)

        if is_json_output():
            print_json({
                "session_id": loop_id,
                "type": "orchestration",
                "status": state["status"],
                "iterations": runner.state["iteration"],
                "plans_processed": runner.state["plans_processed"],
                "plans_failed": runner.state.get("plans_failed", []),
                "errors": runner.state["errors"],
            })
        else:
            if success:
                print_success(f"Orchestration loop {loop_id} completed")
                console.print(f"[dim]Plans processed: {len(runner.state['plans_processed'])}[/dim]")
            elif partial_success:
                if partial_ready_to_implement:
                    print_success(
                        f"Orchestration loop {loop_id} partial: epic '{plan_folder}' "
                        f"has {partial_summary} despite early exit "
                        "(likely budget/iteration cap).\n"
                        "Phases are fully routed — run "
                        "`agentic orchestrate session implement "
                        f"--epic {plan_folder}` to proceed."
                    )
                else:
                    from agenticcli.console import print_warning
                    print_warning(
                        f"Orchestration loop {loop_id} partial: epic '{plan_folder}' "
                        f"has {partial_summary} but planning did not finish "
                        "(likely budget/iteration cap).\n"
                        "Inspect with `agentic epic status --epic "
                        f"{plan_folder}` then re-run plan with a higher "
                        "`--budget` to complete routing."
                    )
                for err in runner.state["errors"]:
                    console.print(f"[yellow]  {err}[/yellow]")
            else:
                print_error(f"Orchestration loop {loop_id} finished with errors")
                for err in runner.state["errors"]:
                    console.print(f"[red]  {err}[/red]")
        if not success and not partial_success:
            sys.exit(1)
    except Exception as e:
        state["status"] = "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["errors"].append(str(e))
        _store.save(state)
        print_error(f"Orchestration loop failed: {e}")
        sys.exit(1)


def _run_dry_run(args, ctx=None):
    """Create tmux layout, verify pane count, print JSON, then exit.

    This enables automated testing of the tmux GUI path without needing
    a human to interact with Claude or dashboard processes.
    """
    from agenticcli.utils.tmux_layout import (
        create_orchestration_layout,
        tmux_available,
    )

    if not tmux_available():
        print(json_mod.dumps({"error": "tmux is not available"}), file=sys.stderr)
        sys.exit(1)

    # NOTE: do NOT bulk-kill agentic-orch-* sessions here. That used to race
    # against concurrent orchestration runs and parallel test sessions.
    # create_orchestration_layout() handles the per-session collision check.

    session_name = f"agentic-orch-dryrun-{os.getpid()}"

    try:
        layout = create_orchestration_layout(
            claude_cmd_str="echo dry-run",
            skip_commands=True,
        )
        session_name = layout.session_name

        # Query actual pane count from tmux
        result = subprocess.run(
            ["tmux", "list-panes", "-t", session_name, "-F", "#{pane_id} #{pane_title}"],
            capture_output=True, text=True,
        )
        panes = []
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                parts = line.split(None, 1)
                panes.append({
                    "pane_id": parts[0],
                    "pane_title": parts[1] if len(parts) > 1 else "",
                })

        output = {
            "session_name": layout.session_name,
            "main_pane_id": layout.main_pane_id,
            "status_pane_id": layout.status_pane_id,
            "questions_pane_id": layout.questions_pane_id,
            "created_new_session": layout.created_new_session,
            "pane_count": len(panes),
            "panes": panes,
        }

        print(json_mod.dumps(output, indent=2))

        if len(panes) != 3:
            print(f"ERROR: Expected 3 panes, got {len(panes)}", file=sys.stderr)
            sys.exit(1)

    finally:
        # Always clean up the test session
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
        )

    sys.exit(0)


def _run_executing_loop(args, ctx=None):
    """Run automated execution loop.

    Args:
        args: Parsed arguments with background, max_iterations, etc.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success

    max_iterations = getattr(args, "max_iterations", 10)
    background = getattr(args, "background", False)
    completion_promise = getattr(args, "completion_promise", None)
    project = getattr(args, "project", None)
    plan_folder = getattr(args, "plan", None)
    working_dir = getattr(args, "directory", None) or os.getcwd()
    skip_perms = getattr(args, "dangerously_skip_permissions", False)

    loop_id = os.environ.get("AGENTIC_EXEC_LOOP_ID")
    if not loop_id:
        loop_id = generate_loop_id("exec")

    state = {
        "session_id": loop_id,
        "type": "execution",
        "status": "starting",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "pid": None,
        "max_iterations": max_iterations,
        "current_iteration": 0,
        "plans_processed": [],
        "plans_failed": [],
        "phases_completed": [],
        "phases_failed": [],
        "errors": [],
        "completion_promise": completion_promise,
        "directory": working_dir,
        "plan_folder": plan_folder,
    }

    if background:
        # Re-invoke in foreground as a subprocess to detach from the terminal.
        # NOTE: The actual Claude agent invocations inside the loop use the SDK
        # (via OrchestrationWorkflow). This subprocess is just the process-control
        # wrapper that allows background detachment.
        cmd = [sys.executable, "-m", "agenticcli.entry", "orchestrate", "session", "implement"]
        cmd.extend(["--max-iterations", str(max_iterations)])
        if completion_promise:
            cmd.extend(["--completion-promise", completion_promise])
        if project:
            cmd.extend(["--project", project])
        if plan_folder:
            cmd.extend(["--plan", plan_folder])
        if skip_perms:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["--directory", working_dir])

        logs_dir = _store.get_dir() / loop_id
        logs_dir.mkdir(parents=True, exist_ok=True)

        stdout_log = open(logs_dir / "stdout.log", "w")
        stderr_log = open(logs_dir / "stderr.log", "w")

        from agenticcli.utils.subprocess_utils import get_clean_env
        env = get_clean_env()
        env["AGENTIC_EXEC_LOOP_ID"] = loop_id

        # Record SDK transport metadata so consumers know agent calls use the SDK
        from agenticcli.utils.sdk_runner import SDK_AVAILABLE as _EXEC_SDK_AVAILABLE
        from agenticcli.utils.transport import determine_transport
        state["transport"] = determine_transport(sdk_available=_EXEC_SDK_AVAILABLE)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                stdin=subprocess.DEVNULL,
                stdout=stdout_log,
                stderr=stderr_log,
                start_new_session=True,
                env=env,
            )
        finally:
            stdout_log.close()
            stderr_log.close()

        state["pid"] = process.pid
        state["status"] = "running"
        _store.save(state)

        if is_json_output():
            print_json({
                "session_id": loop_id,
                "type": "execution",
                "pid": process.pid,
                "status": "running",
                "background": True,
                "max_iterations": max_iterations,
                "transport": state["transport"],
            })
        else:
            print_success(f"Execution loop {loop_id} started in background (PID: {process.pid})")
            console.print(f"[dim]Max iterations: {max_iterations}[/dim]")
            if state["transport"] in ("sdk", "sdk-tmux"):
                console.print("[dim]Agent invocations use Claude Agent SDK[/dim]")
        return

    # Foreground execution
    state["pid"] = os.getpid()
    state["status"] = "running"
    _store.save(state)

    from agenticcli.workflows.orchestration import ExecutionRunner, OrchestrationWorkflow

    workflow = OrchestrationWorkflow(working_dir=working_dir)
    budget_usd = getattr(args, "budget_usd", 50.0)
    runner = ExecutionRunner(
        workflow=workflow,
        project=project,
        plan_folder=plan_folder,
        dangerously_skip_permissions=skip_perms,
        budget_usd=budget_usd,
    )

    try:
        success = runner.run(
            max_iterations=max_iterations,
            completion_promise=completion_promise,
        )
        state["status"] = "completed" if success else "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["plans_processed"] = runner.state["plans_processed"]
        state["plans_failed"] = runner.state.get("plans_failed", [])
        state["phases_completed"] = runner.state.get("phases_completed", [])
        state["phases_failed"] = runner.state.get("phases_failed", [])
        state["errors"] = runner.state["errors"]
        state["current_iteration"] = runner.state["iteration"]
        _store.save(state)

        if is_json_output():
            print_json({
                "session_id": loop_id,
                "type": "execution",
                "status": state["status"],
                "iterations": runner.state["iteration"],
                "plans_processed": runner.state["plans_processed"],
                "plans_failed": runner.state.get("plans_failed", []),
                "phases_completed": runner.state.get("phases_completed", []),
                "phases_failed": runner.state.get("phases_failed", []),
                "errors": runner.state["errors"],
            })
        else:
            if success:
                print_success(f"Execution loop {loop_id} completed")
                console.print(f"[dim]Plans processed: {len(runner.state['plans_processed'])}[/dim]")
                console.print(f"[dim]Phases completed: {len(runner.state.get('phases_completed', []))}[/dim]")
            else:
                print_error(f"Execution loop {loop_id} finished with errors")
                for err in runner.state["errors"]:
                    console.print(f"[red]  {err}[/red]")
        if not success:
            sys.exit(1)
    except Exception as e:
        state["status"] = "failed"
        state["completed_at"] = datetime.now().isoformat()
        state["errors"].append(str(e))
        _store.save(state)
        print_error(f"Execution loop failed: {e}")
        sys.exit(1)


def _get_current_branch() -> Optional[str]:
    """Return the current git branch name, or None if git fails / not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        branch = result.stdout.strip()
        return branch if branch else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _resolve_epic_from_branch(args) -> None:
    """Auto-detect the active epic from the current git branch when --epic is absent.

    Mutates args.plan in-place with the resolved epic folder name.
    Exits non-zero if auto-detection fails (no match, multiple matches, or no
    branch info).
    """
    from agenticcli.console import print_error
    from agenticguidance.services.epic_repository import EpicRepository

    branch = _get_current_branch()
    if not branch:
        print_error("cannot infer epic — pass --epic <folder>")
        sys.exit(1)

    repo = EpicRepository()
    all_epics = repo.list_epics()
    matches = [
        m for m in all_epics
        if m.branch and m.branch.strip() == branch
    ]

    if len(matches) == 1:
        folder_name = matches[0].epic_folder_name
        print(f"auto-detected epic {folder_name} from branch {branch}")
        args.plan = folder_name
        return

    if len(matches) == 0:
        print_error(f"cannot infer epic — pass --epic <folder>")
        sys.exit(1)

    # Multiple matches — name them all
    candidates = ", ".join(m.epic_folder_name for m in matches)
    print_error(
        f"cannot infer epic — pass --epic <folder> "
        f"(multiple epics match branch '{branch}': {candidates})"
    )
    sys.exit(1)


def cmd_orchestrate(args, ctx=None):
    """Run automated orchestration planning or execution for epics.

    Args:
        args: Parsed arguments with action, epic, background, max_iterations, etc.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import print_error

    dry_run = getattr(args, "dry_run", False)
    action = getattr(args, "action", None)

    # UAT owns its own dry-run semantics (report resolved story set).
    if dry_run and action != "uat":
        _run_dry_run(args, ctx)
        return

    # Auto-detect epic from git branch when --epic is not supplied.
    # dry_run is exempt because it doesn't target a specific epic.
    # UAT workflow is also exempt — it can be scoped by --story or --stale
    # with no epic context at all.
    plan_folder = getattr(args, "plan", None)
    if not plan_folder and action != "uat":
        _resolve_epic_from_branch(args)
    if action == "planning":
        _run_planning_loop(args, ctx)
    elif action == "executing":
        _run_executing_loop(args, ctx)
    elif action == "uat":
        _run_uat_loop(args, ctx)
    else:
        print_error(f"Unknown action '{action}'. Valid actions: planning, executing, uat")
        sys.exit(1)


def _run_uat_loop(args, ctx=None):
    """Run the decoupled UAT workflow (US-PLN-048).

    Args:
        args: Parsed arguments with story, epic, stale, dry_run.
        ctx: Optional CLIContext.
    """
    from agenticcli.console import console, is_json_output, print_error, print_json, print_success
    from agenticcli.workflows.uat import UatRunner

    story_id = getattr(args, "story", None)
    epic_folder = getattr(args, "plan", None)
    stale = getattr(args, "stale", False)
    dry_run = getattr(args, "dry_run", False)
    skip_perms = getattr(args, "dangerously_skip_permissions", False)
    working_dir = getattr(args, "directory", None) or os.getcwd()

    # Require exactly one scope flag
    scope_flags = [bool(story_id), bool(epic_folder), bool(stale)]
    if sum(scope_flags) == 0:
        print_error("One of --story, --epic, or --stale is required for session uat")
        sys.exit(1)
    if sum(scope_flags) > 1:
        print_error("--story, --epic, and --stale are mutually exclusive")
        sys.exit(1)

    runner = UatRunner(
        story_id=story_id,
        epic_folder=epic_folder,
        stale=stale,
        dry_run=dry_run,
        dangerously_skip_permissions=skip_perms,
        working_dir=working_dir,
    )

    # --dry-run: print resolved target set and exit without spawning
    if dry_run:
        targets = runner.resolve_stories()
        if is_json_output():
            print_json({
                "type": "uat",
                "dry_run": True,
                "resolved": [s.id for s in targets],
                "errors": runner.state["errors"],
            })
        else:
            if targets:
                console.print(f"[dim]Would run test-uat for {len(targets)} story(ies):[/dim]")
                for s in targets:
                    console.print(f"  {s.id} — {s.title}")
            else:
                console.print("[yellow]No stories resolved for scope[/yellow]")
            for err in runner.state["errors"]:
                console.print(f"[red]  {err}[/red]")
        return

    try:
        success = runner.run()
    except Exception as e:
        print_error(f"UAT runner failed: {e}")
        sys.exit(1)

    if is_json_output():
        print_json({
            "type": "uat",
            "status": "completed" if success else "failed",
            "passed": runner.state["passed"],
            "failed": runner.state["failed"],
            "skipped": runner.state["skipped"],
            "commits": runner.state["commits"],
            "errors": runner.state["errors"],
        })
    else:
        if success:
            print_success(
                f"UAT complete: {len(runner.state['passed'])} passed, "
                f"{len(runner.state['failed'])} failed, "
                f"{len(runner.state['skipped'])} skipped"
            )
        else:
            print_error(
                f"UAT finished with failures: "
                f"{len(runner.state['passed'])} passed, "
                f"{len(runner.state['failed'])} failed, "
                f"{len(runner.state['skipped'])} skipped"
            )
        for sid in runner.state["passed"]:
            commit = runner.state["commits"].get(sid, "")
            console.print(f"  [green]PASS[/green] {sid}{' @ ' + commit[:7] if commit else ''}")
        for sid in runner.state["failed"]:
            console.print(f"  [red]FAIL[/red] {sid}")
        for sid in runner.state["skipped"]:
            console.print(f"  [yellow]SKIP[/yellow] {sid} (missing uat_plan)")
        for err in runner.state["errors"]:
            console.print(f"[red]  {err}[/red]")

    if not success:
        sys.exit(1)
