# story: US-GDN-061, US-GDN-064, US-GDN-097, US-PLN-046, US-PLN-061, US-PLN-065
"""Orchestration workflow for plan management.

Extends PlannerLoopWorkflow with phase discovery utilities.
Provides PlanningRunner for planning-only lifecycle and ExecutionRunner for
deterministic phase-by-phase execution backed by TinyDB.
"""

import json
import logging
import os
import time
from typing import Optional

from agenticcli.utils.epic_lock import acquire_epic_lock, release_epic_lock
from agenticcli.utils.retry import SPAWN_RETRY_BACKOFF, static_backoff
from agenticcli.utils.session_diagnostics import diagnose_quick_exit
from agenticcli.utils.session_state import read_sdk_metrics
from agenticcli.utils.spawn_command import build_spawn_command
from agenticcli.workflows.planner_loop import PlannerLoopWorkflow, PlannerLoopRunner

logger = logging.getLogger(__name__)


# @story US-RES-005
class PhaseLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter that auto-prefixes log messages with phase context.

    Provides consistent structured logging for ExecutionRunner by
    including phase_id, phase_name, and epic_name in every log message.

    Usage::

        phase_log = PhaseLoggerAdapter(logger, epic_name="my_epic", phase_name="P1")
        phase_log.info("Phase started")
        # => "[my_epic:P1] Phase started"

    Extra keys:
        epic_name: Name of the epic being executed.
        phase_name: Name of the current phase.
        phase_id: Optional phase identifier (defaults to phase_name).
    """

    def __init__(
        self,
        base_logger: logging.Logger,
        *,
        epic_name: str,
        phase_name: str,
        phase_id: Optional[str] = None,
    ):
        """Initialize PhaseLoggerAdapter with phase context.

        Args:
            base_logger: The underlying logger to delegate to.
            epic_name: Epic folder name for context.
            phase_name: Phase name for context.
            phase_id: Optional phase ID (defaults to phase_name if not provided).
        """
        extra = {
            "epic_name": epic_name,
            "phase_name": phase_name,
            "phase_id": phase_id or phase_name,
        }
        super().__init__(base_logger, extra)

    def process(self, msg, kwargs):
        """Prefix the log message with [epic:phase] context.

        Args:
            msg: The log message.
            kwargs: Keyword arguments passed to the logging call.

        Returns:
            Tuple of (prefixed_message, kwargs).
        """
        prefix = f"[{self.extra['epic_name']}:{self.extra['phase_name']}]"
        return f"{prefix} {msg}", kwargs


# Map legacy string labels to their numeric equivalents.
# Used by _to_int_priority() during the string→int migration window.
_LABEL_TO_INT: dict[str, int] = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
}


def _to_int_priority(value) -> int:
    """Convert a priority value to int, handling None, int, and legacy strings.

    Args:
        value: Priority from EpicMetadata — may be int, str, or None.

    Returns:
        Integer priority (1-4).  Defaults to 3 (medium) for None or
        unrecognised values.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return _LABEL_TO_INT.get(value.lower(), 3)
    return 3


class OrchestrationWorkflow(PlannerLoopWorkflow):
    """Orchestration workflow extending PlannerLoopWorkflow with phase discovery.

    Provides helpers for discovering plans that need execution or orchestration,
    backed entirely by TinyDB.
    """

    def discover_plans_needing_execution(self) -> list[str]:
        """Find epics with status ``in_progress`` — ready for execution.

        The ``in_progress`` status is the sole readiness signal. Preconditions
        (phases exist, routing valid, deps satisfied) are enforced when
        transitioning INTO ``in_progress`` via ``transition_epic_status()``,
        not as post-hoc filters here.

        Before querying, refreshes blocked/in_progress statuses via the
        dependency service to handle dynamic dep changes.

        Results are sorted by priority (critical first) then by folder name
        (newest first).  The sort order is already applied by
        ``list_epics()``, so no additional sorting is needed.

        Returns:
            List of plan folder names needing execution, priority-sorted.
        """
        repo = self._get_repository()
        if not repo:
            logger.error("No EpicRepository available — cannot discover plans needing execution")
            return []

        # Refresh blocked/in_progress statuses based on current dep state
        try:
            from agenticguidance.services.dependency import DependencyService
            dep_service = DependencyService(repo)
            dep_service.refresh_blocked_statuses()
        except Exception:
            pass

        epics = repo.list_epics(status="in_progress")
        needs_execution = [e.epic_folder_name for e in epics]

        logger.info("Found %d plans needing execution: %s", len(needs_execution), needs_execution)
        return needs_execution

    def _get_repository(self):
        """Get EpicRepository instance, creating if needed.

        Returns:
            EpicRepository instance inherited from PlannerLoopWorkflow, or None.
        """
        return self._repository


class PlanningRunner:
    """Planning-only runner with no execution phase.

    Discovers plans needing orchestration (or targets a single plan) and
    runs the PlannerLoopRunner for each, which handles the full planning
    workflow: explore, story generation, planning, review, and validation.

    No execution phase, no archiving.
    """

    def __init__(
        self,
        workflow: Optional[OrchestrationWorkflow] = None,
        project: Optional[str] = None,
        plan_folder: Optional[str] = None,
        budget_usd: float = 50.0,
    ):
        """Initialize planning runner.

        Args:
            workflow: OrchestrationWorkflow instance (creates default if None).
            project: Optional project filter for plan discovery.
            plan_folder: Optional plan folder for single-plan mode.
            budget_usd: Maximum USD cost before halting.
        """
        self.workflow = workflow or OrchestrationWorkflow()
        self.project = project
        self.plan_folder = plan_folder
        self.budget_usd = budget_usd
        self.state = {
            "iteration": 0,
            "plans_processed": [],
            "plans_failed": [],
            "errors": [],
        }

    def run(
        self,
        max_iterations: int = 10,
        completion_promise: Optional[str] = None,
    ) -> bool:
        """Run planning-only workflow for all discovered or specified plans.

        Args:
            max_iterations: Max iterations for the planning loop per plan.
            completion_promise: Completion text passed to PlannerLoopRunner.

        Returns:
            True if all plans processed successfully, False otherwise.
        """
        # Health check
        try:
            self.workflow.run_health_check()
        except RuntimeError as e:
            logger.error("Health check failed: %s", e)
            self.state["errors"].append(str(e))
            return False

        # Archive completed plans (query TinyDB, not filesystem)
        repo = self.workflow._get_repository()
        if repo:
            for epic in repo.list_epics(status="live"):
                if self.workflow.get_plan_status(epic.epic_folder_name) == "completed":
                    logger.info("Archiving completed plan: %s", epic.epic_folder_name)
                    self.workflow.archive_plan(epic.epic_folder_name)

        # Determine plans to process
        if self.plan_folder:
            # Early exit: detect already-completed/archived epics
            status = self.workflow.get_plan_status(self.plan_folder)
            if status == "completed":
                logger.info(
                    "Epic %s is already completed/archived — nothing to plan. "
                    "Use 'agentic epic unarchive' to reopen it.",
                    self.plan_folder,
                )
                return True
            plans_to_process = [self.plan_folder]
        else:
            plans_to_process = self.workflow.discover_plans_needing_orchestration()
            if not plans_to_process:
                logger.info("No plans needing orchestration")
                return True

        logger.info("Processing %d plans: %s", len(plans_to_process), plans_to_process)

        all_success = True
        for plan in plans_to_process:
            logger.info("Starting planning for plan: %s", plan)

            planner_runner = PlannerLoopRunner(
                workflow=self.workflow,
                project=self.project,
                epic_folder=plan,
                budget_usd=self.budget_usd,
            )

            try:
                success = planner_runner.run(
                    max_iterations=max_iterations,
                    completion_promise=completion_promise,
                )
            except Exception as e:
                logger.error("Planning runner raised exception for %s: %s", plan, e)
                self.state["errors"].append(f"Exception for {plan}: {e}")
                success = False

            if success:
                self.state["plans_processed"].append(plan)
                logger.info("Planning completed for plan: %s", plan)
            else:
                self.state["plans_failed"].append(plan)
                # Propagate child runner errors into our state
                for err in planner_runner.state.get("errors", []):
                    self.state["errors"].append(err)
                # Downgraded to warning: CLI wrapper re-inspects TinyDB and
                # may still report partial success (see orchestrate.py).
                logger.warning("Planner loop for plan did not complete: %s", plan)
                all_success = False

        self.state["iteration"] += 1
        return all_success


DEFAULT_EXECUTION_PROMISE = "Execution complete. All phases finished."

# Default --max-turns passed to spawned agents when no per-phase override is set.
# Prevents agents from exiting prematurely (~9s) due to missing turn budget.
# 200 turns ≈ a substantial coding session; individual phases can override via
# PhaseData.max_turns or the --max-turns flag on `agentic epic phase add`.
DEFAULT_PHASE_MAX_TURNS = 200

# Auto-retry configuration for quick-exit sessions.
# When an agent exits in < QUICK_EXIT_THRESHOLD, _run_phase retries up to
# MAX_SPAWN_RETRIES times with static backoff (delays from SPAWN_RETRY_BACKOFF).
MAX_SPAWN_RETRIES = 2
# Backoff schedule re-exported for backward compatibility (sourced from retry.py).
RETRY_BACKOFF_SECONDS = SPAWN_RETRY_BACKOFF

# Default per-phase wait timeout in seconds.
# Individual phases can override via PhaseData.timeout.
DEFAULT_PHASE_TIMEOUT = 3600  # 60 minutes (implementation default)


class ExecutionRunner:
    """Deterministic execution runner for orchestrated plans.

    Reads phase data from TinyDB, finds the next pending phase, spawns the
    corresponding agent, waits for completion, updates phase status in TinyDB,
    and iterates until all phases are complete or an error occurs.
    """

    def __init__(
        self,
        workflow: Optional[OrchestrationWorkflow] = None,
        project: Optional[str] = None,
        plan_folder: Optional[str] = None,
        dangerously_skip_permissions: bool = False,
        budget_usd: float = 50.0,
    ):
        """Initialize execution runner.

        Args:
            workflow: OrchestrationWorkflow instance (creates default if None).
            project: Optional project filter for plan discovery.
            plan_folder: Optional plan folder for single-plan mode.
            dangerously_skip_permissions: Pass --dangerously-skip-permissions to spawned agents.
            budget_usd: Maximum USD cost before halting execution.
        """
        self.workflow = workflow or OrchestrationWorkflow()
        self.project = project
        self.plan_folder = plan_folder
        self.dangerously_skip_permissions = dangerously_skip_permissions
        self.budget_usd: float = budget_usd
        self.total_cost_usd = 0.0
        self._phase_log: logging.LoggerAdapter = logger  # type: ignore[assignment]
        self.state = {
            "iteration": 0,
            "plans_processed": [],
            "plans_failed": [],
            "phases_completed": [],
            "phases_failed": [],
            "errors": [],
        }

    def _make_phase_logger(
        self, epic_name: str, phase_name: str, phase_id: Optional[str] = None,
    ) -> PhaseLoggerAdapter:
        """Create a PhaseLoggerAdapter for the given phase context.

        Args:
            epic_name: Epic folder name.
            phase_name: Phase display name.
            phase_id: Optional phase identifier (defaults to phase_name).

        Returns:
            PhaseLoggerAdapter wrapping the module logger.
        """
        return PhaseLoggerAdapter(
            logger,
            epic_name=epic_name,
            phase_name=phase_name,
            phase_id=phase_id,
        )

    def run(
        self,
        max_iterations: int = 10,
        completion_promise: Optional[str] = None,
    ) -> bool:
        """Run execution for all discovered or specified plans.

        Each iteration processes one phase of one plan. Continues until all
        plans have all phases completed, or max_iterations is reached.

        Args:
            max_iterations: Max total phase executions across all plans.
            completion_promise: Completion text to print when done.

        Returns:
            True if all plans executed successfully, False otherwise.
        """
        promise = completion_promise or DEFAULT_EXECUTION_PROMISE

        # Health check
        try:
            self.workflow.run_health_check()
        except RuntimeError as e:
            logger.error("Health check failed: %s", e)
            self.state["errors"].append(str(e))
            return False

        # Archive completed plans (query TinyDB, not filesystem)
        repo = self.workflow._get_repository()
        if repo:
            for epic in repo.list_epics(status="live"):
                if self.workflow.get_plan_status(epic.epic_folder_name) == "completed":
                    logger.info("Archiving completed plan: %s", epic.epic_folder_name)
                    self.workflow.archive_plan(epic.epic_folder_name)

        # Determine plans to process
        if self.plan_folder:
            # Early exit: detect already-completed/archived epics
            status = self.workflow.get_plan_status(self.plan_folder)
            if status == "completed":
                logger.info(
                    "Epic %s is already completed/archived — nothing to execute. "
                    "Use 'agentic epic unarchive' to reopen it.",
                    self.plan_folder,
                )
                return True
            plans_to_process = [self.plan_folder]
        else:
            plans_to_process = self.workflow.discover_plans_needing_execution()
            if not plans_to_process:
                logger.info("No plans needing execution. %s", promise)
                print(promise)
                return True

        logger.info("Executing %d plans: %s", len(plans_to_process), plans_to_process)

        all_success = True
        for plan in plans_to_process:
            if not acquire_epic_lock(plan):
                logger.error(
                    "Cannot execute %s — another orchestration process holds the lock", plan,
                )
                self.state["errors"].append(
                    f"Lock held by another process for {plan}"
                )
                self.state["plans_failed"].append(plan)
                all_success = False
                continue

            try:
                logger.info("Starting execution for plan: %s", plan)
                # Confirm epic is in_progress (should already be from discovery)
                try:
                    repo_exec = self.workflow._get_repository()
                    if repo_exec:
                        epic_data = repo_exec.get_epic(plan)
                        if epic_data and epic_data.status != "in_progress":
                            repo_exec.transition_epic_status(plan, "in_progress", force=True)
                except Exception:
                    pass  # Non-fatal — status update is best-effort
                try:
                    success = self._execute_plan(plan, max_iterations)
                except Exception as e:
                    logger.error("Execution raised exception for %s: %s", plan, e)
                    self.state["errors"].append(f"Exception for {plan}: {e}")
                    success = False

                if success:
                    self.state["plans_processed"].append(plan)
                    logger.info("Execution completed for plan: %s", plan)
                else:
                    self.state["plans_failed"].append(plan)
                    logger.error("Execution failed for plan: %s", plan)
                    all_success = False
            finally:
                release_epic_lock(plan)

        # Close repository to release file handles
        repo_final = self.workflow._get_repository()
        if repo_final:
            repo_final.close()

        if all_success:
            print(promise)
        return all_success

    def _execute_plan(self, plan_folder: str, max_iterations: int) -> bool:
        """Execute all pending phases of a single plan sequentially.

        Reads phase data directly from TinyDB (via EpicRepository).

        Args:
            plan_folder: Plan folder name.
            max_iterations: Max phase executions for this plan.

        Returns:
            True if all phases completed successfully.
        """
        repo = self.workflow._get_repository()
        if not repo:
            self.state["errors"].append(
                f"No EpicRepository available for {plan_folder}"
            )
            return False

        # Recovery sweep: reset stale in_progress phases from prior interrupted runs
        self._recover_stale_phases(repo, plan_folder)

        for iteration in range(1, max_iterations + 1):
            self.state["iteration"] = iteration

            # Read phases from TinyDB
            phases = repo.list_phases(plan_folder)
            if not phases:
                self.state["errors"].append(
                    f"No phases found in TinyDB for {plan_folder}"
                )
                return False

            # Bail out if any phase is blocked (terminal after retry exhaustion)
            blocked = [p for p in phases if p.status == "blocked"]
            if blocked:
                names = ", ".join(p.name for p in blocked)
                for bp in blocked:
                    reason = getattr(bp, "blocked_reason", None) or "no reason recorded"
                    blocked_log = self._make_phase_logger(plan_folder, bp.name)
                    blocked_log.error(
                        "Execution halted — blocked (reason: %s)", reason,
                    )
                self.state["errors"].append(
                    f"Blocked phase(s) in {plan_folder}: {names}"
                )
                return False

            # Find next planning/in_progress phase (order preserved by _order field)
            next_phase = None
            for phase in phases:
                if phase.status in ("planning", "in_progress"):
                    next_phase = phase
                    break

            if not next_phase:
                logger.info("All phases complete for %s", plan_folder)
                # Mark the epic as completed in TinyDB
                try:
                    repo.transition_epic_status(plan_folder, "completed")
                    logger.info("Epic %s marked as completed", plan_folder)
                except Exception as e:
                    logger.warning("Failed to mark epic %s as completed: %s", plan_folder, e)
                return True

            agent_type = next_phase.agent

            # Create structured phase logger for this phase iteration
            self._phase_log = self._make_phase_logger(
                plan_folder, next_phase.name,
            )

            if not agent_type:
                self._phase_log.error(
                    "No agent field set in TinyDB — skipping with error. "
                    "Use 'agentic epic phase update %s --agent <agent-name>' to fix.",
                    next_phase.name,
                )
                phase_label = next_phase.phase_id or next_phase.name
                self.state["errors"].append(
                    f"No agent routing for phase {phase_label} in {plan_folder}: "
                    f"agent field must be set in TinyDB"
                )
                repo.update_phase(plan_folder, next_phase.name, {"status": "failed"})
                self.state["phases_failed"].append(f"{plan_folder}:{next_phase.name}")
                return False

            effective_turns = next_phase.max_turns if next_phase.max_turns is not None else DEFAULT_PHASE_MAX_TURNS
            effective_timeout = next_phase.timeout if next_phase.timeout is not None else DEFAULT_PHASE_TIMEOUT
            self._phase_log.info(
                "Executing with agent %s (iteration %d/%d, max_turns=%d, timeout=%ds)",
                agent_type, iteration, max_iterations,
                effective_turns, effective_timeout,
            )

            # Mark phase as in_progress in TinyDB
            repo.update_phase(plan_folder, next_phase.name, {"status": "in_progress"})

            # Spawn agent and wait (per-phase max_turns and timeout override defaults)
            success = self._run_phase(
                plan_folder, next_phase.name, agent_type, {},
                max_turns=next_phase.max_turns,
                timeout=next_phase.timeout,
            )

            # Refresh TinyDB cache — the agent ran in a separate process
            # and may have updated tickets/phases in the shared DB file.
            repo.refresh()

            if success:
                # Verify all tickets in this phase are completed before advancing
                incomplete = self._check_phase_tickets_complete(
                    repo, plan_folder, next_phase.name,
                )
                if incomplete:
                    self._phase_log.warning(
                        "Agent reported success but %d ticket(s) still incomplete: %s",
                        len(incomplete),
                        ", ".join(incomplete[:5]),
                    )

                repo.update_phase(plan_folder, next_phase.name, {"status": "completed"})
                self.state["phases_completed"].append(f"{plan_folder}:{next_phase.name}")
                self._phase_log.info("Phase completed")

                self._record_story_pass_for_phase(
                    repo, plan_folder, next_phase.name,
                )
            else:
                # Check feedback triggers from TinyDB PhaseData
                rerun_phase = self._check_feedback_triggers_tinydb(
                    next_phase, plan_folder, repo,
                )
                if rerun_phase:
                    self._phase_log.info(
                        "Feedback trigger: re-running phase %s", rerun_phase,
                    )
                    repo.update_phase(plan_folder, next_phase.name, {"status": "failed"})
                    repo.update_phase(plan_folder, rerun_phase, {"status": "planning"})
                    # Continue to next iteration which will pick up the re-run
                    continue

                repo.update_phase(plan_folder, next_phase.name, {"status": "failed"})
                self.state["phases_failed"].append(f"{plan_folder}:{next_phase.name}")
                self.state["errors"].append(
                    f"Phase {next_phase.name} failed for {plan_folder}"
                )
                self._phase_log.error("Phase failed")
                return False

        logger.warning("Max iterations (%d) reached for %s", max_iterations, plan_folder)
        return False

    def _recover_stale_phases(self, repo, plan_folder: str) -> None:
        """Reset in_progress phases left by interrupted prior runs.

        On startup, any phase stuck in in_progress without an active tmux
        session is presumed orphaned and marked as failed so the normal
        retry/feedback logic can handle it.

        Also kills orphaned agentic-* tmux sessions that don't belong to
        any running session in the state store — prevents concurrent TinyDB
        access from zombie agents.
        """
        phases = repo.list_phases(plan_folder)
        for phase in phases:
            if phase.status != "in_progress":
                continue
            recovery_log = self._make_phase_logger(plan_folder, phase.name)
            recovery_log.warning(
                "Recovery sweep: stuck in_progress — resetting to planning",
            )
            repo.update_phase(plan_folder, phase.name, {"status": "planning"})

        # Kill orphaned tmux sessions from prior interrupted runs
        self._kill_orphaned_tmux_sessions()

    def _run_phase(
        self,
        plan_folder: str,
        phase_id: str,
        agent_type: str,
        routing: dict,
        max_turns: Optional[int] = None,
        timeout: Optional[int] = None,
    ) -> bool:
        """Spawn agent for a phase and wait for completion.

        Includes auto-retry logic: when a session exits suspiciously fast
        (< 30 seconds), the logs are checked for known error patterns.  If
        the error is retryable, the spawn is retried up to MAX_SPAWN_RETRIES
        times with exponential backoff.

        Args:
            plan_folder: Plan folder name.
            phase_id: Phase identifier.
            agent_type: Agent role to spawn.
            routing: Reserved for future use (currently unused).
            max_turns: Maximum agentic turns for this phase.  Falls back to
                DEFAULT_PHASE_MAX_TURNS when ``None``.
            timeout: Per-phase wait timeout in seconds.  Falls back to
                DEFAULT_PHASE_TIMEOUT when ``None``.

        Returns:
            True if agent completed successfully.
        """
        effective_timeout = timeout if timeout is not None else DEFAULT_PHASE_TIMEOUT
        plog = self._phase_log
        last_diagnosis = None
        for attempt in range(1 + MAX_SPAWN_RETRIES):
            retry_label = f" (retry {attempt}/{MAX_SPAWN_RETRIES})" if attempt > 0 else ""
            success, session_id, is_quick_exit = self._spawn_and_wait(
                plan_folder, phase_id, agent_type, max_turns, retry_label,
                timeout=effective_timeout,
            )
            if success:
                return True
            if not is_quick_exit:
                # Not a quick exit — no point retrying
                return False
            if attempt >= MAX_SPAWN_RETRIES:
                plog.error(
                    "BLOCKED: Exhausted %d retries — "
                    "failures=%d, last_diagnosis=%s",
                    MAX_SPAWN_RETRIES,
                    attempt + 1,
                    last_diagnosis.error_type.value if last_diagnosis else "unknown",
                )
                # Mark phase as blocked so _execute_plan treats it as terminal
                self._mark_phase_blocked(plan_folder, phase_id)
                return False

            # Quick exit detected — diagnose and decide if retry is worthwhile
            diagnosis = self._diagnose_quick_exit(session_id)
            last_diagnosis = diagnosis
            if diagnosis and not diagnosis.retryable:
                plog.error(
                    "Quick exit is not retryable (%s): %s",
                    diagnosis.error_type.value, diagnosis.detail[:200],
                )
                return False

            backoff = static_backoff(attempt, SPAWN_RETRY_BACKOFF)
            plog.warning(
                "Quick exit detected (attempt %d/%d). "
                "Retrying in %ds... (diagnosis: %s)",
                attempt + 1, 1 + MAX_SPAWN_RETRIES,
                backoff,
                diagnosis.error_type.value if diagnosis else "unknown",
            )
            time.sleep(backoff)

        return False

    def _spawn_and_wait(
        self,
        plan_folder: str,
        phase_id: str,
        agent_type: str,
        max_turns: Optional[int],
        retry_label: str = "",
        timeout: int = DEFAULT_PHASE_TIMEOUT,
    ) -> tuple[bool, Optional[str], bool]:
        """Spawn an agent and wait for completion.

        Returns:
            Tuple of (success, session_id, is_quick_exit).
            session_id is provided even on failure for diagnostics.
            is_quick_exit is True when the session ended in < 30 seconds.
        """
        import subprocess
        import time as _time

        plog = self._phase_log
        effective_max_turns = max_turns if max_turns is not None else DEFAULT_PHASE_MAX_TURNS

        cmd = build_spawn_command(
            role=agent_type,
            epic_folder=plan_folder,
            max_turns=effective_max_turns,
            skip_permissions=self.dangerously_skip_permissions,
            phase_id=phase_id,
        )

        # SDK-in-tmux: spawn uses sdk_pane_runner.py inside tmux pane for
        # process isolation. Returns immediately with session_id.
        # wait_for_session() below handles the long wait.
        spawn_start = _time.monotonic()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
                cwd=self.workflow.working_dir,
            )
        except subprocess.TimeoutExpired:
            plog.error(
                "Spawn timed out%s (agent=%s, 60s limit)",
                retry_label, agent_type,
            )
            self.state["errors"].append(
                f"Spawn timed out for {plan_folder}:{phase_id}{retry_label}"
            )
            return False, None, False
        if result.returncode != 0:
            plog.error(
                "Failed to spawn %s%s: %s",
                agent_type, retry_label, result.stderr,
            )
            self.state["errors"].append(
                f"Spawn failed for {plan_folder}:{phase_id}{retry_label}: {result.stderr}"
            )
            return False, None, False

        try:
            data = json.loads(result.stdout)
            session_id = data.get("session_id")
        except (json.JSONDecodeError, KeyError):
            plog.error("Could not parse spawn output%s", retry_label)
            return False, None, False

        if not session_id:
            plog.error("No session_id returned%s", retry_label)
            return False, None, False

        # Log tmux session name for operator visibility (attach for debugging)
        tmux_session = data.get("tmux_session")
        if tmux_session:
            plog.info(
                "Spawned%s %s -> session %s (tmux: %s, attach: tmux attach -t %s)",
                retry_label, agent_type, session_id, tmux_session, tmux_session,
            )
        else:
            plog.info(
                "Spawned%s %s -> session %s",
                retry_label, agent_type, session_id,
            )

        # Wait for session to complete (configurable per-phase timeout)
        status = self.workflow.wait_for_session(session_id, timeout=timeout)
        elapsed = _time.monotonic() - spawn_start
        is_quick_exit = elapsed < 30  # QUICK_EXIT_THRESHOLD

        # Extract SDK metrics from session state (written by sdk_pane_runner)
        try:
            sdk_metrics = read_sdk_metrics(session_id)
            if sdk_metrics["cost_usd"] > 0:
                plog.info(
                    "SDK metrics — cost=$%.4f, duration=%dms, turns=%d, transport=%s",
                    sdk_metrics["cost_usd"],
                    sdk_metrics["duration_ms"],
                    sdk_metrics["num_turns"],
                    sdk_metrics["transport"],
                )
        except Exception as e:
            plog.debug("Could not read SDK metrics for %s: %s", session_id[:8], e)
            sdk_metrics = {"cost_usd": 0.0}

        self.total_cost_usd += sdk_metrics.get("cost_usd", 0.0)
        if self.budget_usd and self.total_cost_usd >= self.budget_usd:
            plog.error(
                "Budget exhausted: $%.2f >= $%.2f limit",
                self.total_cost_usd, self.budget_usd,
            )
            return False, session_id, False

        if status == "completed":
            return True, session_id, False

        plog.error(
            "Session %s%s ended with status: %s (%.1fs)",
            session_id[:8], retry_label, status, elapsed,
        )
        return False, session_id, is_quick_exit

    def _record_story_pass_for_phase(
        self,
        repo,
        plan_folder: str,
        phase_name: str,
    ) -> None:
        """Record `last_pass_commit` for every story covered by this phase.

        Runs after a phase is marked completed. Resolves the story set from
        ticket.story_ids (primary) and falls back to a pytest marker scan
        when tickets carry none. Writes go through `record_story_pass`
        which uses `StoryService.update_test_status(..., commit_kind="test")`
        in-process — no subprocess, no agent involvement.

        Silent failure: a broken pass-hash hook must never block phase
        completion. Errors are logged and swallowed.
        """
        try:
            story_ids: set[str] = set()
            try:
                tickets = repo.list_tickets(plan_folder)
            except Exception:
                tickets = []
            for t in tickets:
                if getattr(t, "phase_name", None) != phase_name:
                    continue
                for sid in getattr(t, "story_ids", None) or []:
                    if sid:
                        story_ids.add(sid)

            if not story_ids:
                from agenticcli.commands.stories import _scan_pytest_story_markers
                try:
                    story_ids = _scan_pytest_story_markers()
                except Exception:
                    story_ids = set()

            if not story_ids:
                self._phase_log.debug(
                    "No story IDs resolved for phase %s — skipping pass-hash record",
                    phase_name,
                )
                return

            from agenticcli.commands.stories import record_story_pass
            result = record_story_pass(
                sorted(story_ids),
                commit_kind="test",
                tested_by=f"executor:{plan_folder}:{phase_name}",
            )
            self._phase_log.info(
                "Recorded last_pass_commit for %d/%d stories (commit=%s)",
                len(result.get("updated") or []),
                len(story_ids),
                (result.get("commit") or "")[:7],
            )
            if result.get("missing"):
                self._phase_log.debug(
                    "Pass-hash: could not update %s",
                    ", ".join(result["missing"]),
                )
        except Exception as e:
            self._phase_log.warning(
                "Pass-hash hook failed (non-fatal): %s", e,
            )

    def _check_phase_tickets_complete(
        self,
        repo,
        plan_folder: str,
        phase_name: str,
    ) -> list[str]:
        """Check if all tickets in a phase are completed.

        Args:
            repo: EpicRepository instance.
            plan_folder: Plan folder name.
            phase_name: Phase name to check.

        Returns:
            List of incomplete ticket IDs. Empty list means all complete.
        """
        try:
            tickets = repo.list_tickets(plan_folder)
            incomplete = []
            for t in tickets:
                if t.phase_name == phase_name and t.status != "completed":
                    incomplete.append(t.id)
            return incomplete
        except Exception as e:
            logger.debug("Could not check phase tickets: %s", e)
            return []

    def _kill_orphaned_tmux_sessions(self) -> int:
        """Kill agentic-* tmux sessions not backed by a running session record.

        Reuses the cross-referencing logic from SessionCleanupService but runs
        inline during recovery to prevent orphaned agents from concurrent
        TinyDB writes.

        Returns:
            Number of tmux sessions killed.
        """
        import subprocess

        # Test-only escape hatch: tests that exercise ExecutionRunner.run() must
        # NOT touch the real tmux server, because the prefix match below
        # ('agentic-') is broad enough to clobber sibling tmux integration test
        # sessions (e.g. 'agentic-orch-test-*'). Honoured only when explicitly
        # set; production never sets this var.
        if os.environ.get("AGENTIC_DISABLE_TMUX_ORPHAN_SWEEP"):
            return 0

        # Collect tmux session names for sessions with alive PIDs
        from agenticcli.utils.state_store import StateStore, is_process_running
        store = StateStore("sessions", id_key="session_id")
        protected_tmux: set[str] = set()
        for record in store.list_all():
            status = record.get("status", "")
            pid = record.get("pid")
            tmux_name = record.get("tmux_session", "")
            if status in ("running", "starting") and pid and is_process_running(pid) and tmux_name:
                protected_tmux.add(tmux_name)

        # List all tmux sessions
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return 0

        killed = 0
        for session_name in result.stdout.strip().splitlines():
            if not session_name.startswith("agentic-"):
                continue
            if session_name in protected_tmux:
                continue
            try:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session_name],
                    capture_output=True, timeout=5,
                )
                killed += 1
                logger.warning("Killed orphaned tmux session: %s", session_name)
            except (subprocess.TimeoutExpired, OSError):
                logger.debug("Failed to kill tmux session %s", session_name)

        if killed:
            logger.info("Recovery sweep killed %d orphaned tmux session(s)", killed)
        return killed

    def _mark_phase_blocked(self, plan_folder: str, phase_id: str) -> None:
        """Mark a phase as 'blocked' in TinyDB after retry exhaustion.

        Blocked is a terminal status — _execute_plan will not retry it.
        """
        repo = self.workflow._get_repository()
        if repo:
            repo.update_phase(plan_folder, phase_id, {"status": "blocked"})
            self._phase_log.info("Marked as blocked")

    def _diagnose_quick_exit(self, session_id: Optional[str]):
        """Run session diagnostics on a quick-exit session.

        Delegates to the shared ``diagnose_quick_exit()`` free function
        in ``agenticcli.utils.session_diagnostics``.

        Args:
            session_id: Session UUID to diagnose.

        Returns:
            SessionDiagnosis or None if diagnostics unavailable.
        """
        return diagnose_quick_exit(session_id) if session_id else None

    def _check_feedback_triggers_tinydb(
        self,
        failed_phase,
        plan_folder: str,
        repo,
    ) -> Optional[str]:
        """Check feedback triggers from TinyDB PhaseData.

        Reads feedback_triggers from the PhaseData object (stored in TinyDB)
        and verifies the target phase exists before returning it.

        Args:
            failed_phase: PhaseData object for the phase that failed.
            plan_folder: Plan folder name (for logging and phase lookup).
            repo: EpicRepository instance to verify target phase existence.

        Returns:
            Phase name to re-run, or None if no applicable trigger.
        """
        triggers = failed_phase.feedback_triggers or {}
        if not triggers:
            return None

        failure_key = f"{failed_phase.name.upper()}_FAILURE"
        target = triggers.get(failure_key)
        if target:
            # Verify target phase exists in TinyDB
            target_phase = repo.get_phase(plan_folder, target)
            if target_phase:
                self._phase_log.info(
                    "Feedback trigger %s -> %s", failure_key, target,
                )
                return target
            else:
                self._phase_log.warning(
                    "Feedback trigger target %s not found in TinyDB",
                    target,
                )

        return None
