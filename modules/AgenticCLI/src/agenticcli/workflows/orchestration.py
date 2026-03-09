"""Orchestration workflow for plan management.

Extends PlannerLoopWorkflow with phase discovery utilities.
Provides PlanningRunner for planning-only lifecycle and ExecutionRunner for
deterministic phase-by-phase execution backed by TinyDB.
"""

import json
import logging
import time
from typing import Optional

from agenticcli.utils.retry import SPAWN_RETRY_BACKOFF, static_backoff
from agenticcli.utils.session_state import read_sdk_metrics
from agenticcli.utils.spawn_command import build_spawn_command
from agenticcli.workflows.planner_loop import PlannerLoopWorkflow, PlannerLoopRunner

logger = logging.getLogger(__name__)


class OrchestrationWorkflow(PlannerLoopWorkflow):
    """Orchestration workflow extending PlannerLoopWorkflow with phase discovery.

    Provides helpers for discovering plans that need execution or orchestration,
    backed entirely by TinyDB.
    """

    def discover_plans_needing_execution(self) -> list[str]:
        """Find live epics that have phases with pending/in_progress status in TinyDB.

        Queries TinyDB directly instead of scanning MMD files.

        Returns:
            List of plan folder names needing execution.
        """
        repo = self._get_repository()
        if not repo:
            logger.error("No EpicRepository available — cannot discover plans needing execution")
            return []

        epics = repo.list_epics(status="live")
        needs_execution = []
        for epic in epics:
            if repo.has_pending_phases(epic.epic_folder_name):
                needs_execution.append(epic.epic_folder_name)

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
    ):
        """Initialize planning runner.

        Args:
            workflow: OrchestrationWorkflow instance (creates default if None).
            project: Optional project filter for plan discovery.
            plan_folder: Optional plan folder for single-plan mode.
        """
        self.workflow = workflow or OrchestrationWorkflow()
        self.project = project
        self.plan_folder = plan_folder
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
                logger.error("Planning failed for plan: %s", plan)
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
DEFAULT_PHASE_TIMEOUT = 1800  # 30 minutes


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
    ):
        """Initialize execution runner.

        Args:
            workflow: OrchestrationWorkflow instance (creates default if None).
            project: Optional project filter for plan discovery.
            plan_folder: Optional plan folder for single-plan mode.
            dangerously_skip_permissions: Pass --dangerously-skip-permissions to spawned agents.
        """
        self.workflow = workflow or OrchestrationWorkflow()
        self.project = project
        self.plan_folder = plan_folder
        self.dangerously_skip_permissions = dangerously_skip_permissions
        self.total_cost_usd = 0.0
        self.state = {
            "iteration": 0,
            "plans_processed": [],
            "plans_failed": [],
            "phases_completed": [],
            "phases_failed": [],
            "errors": [],
        }

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
            logger.info("Starting execution for plan: %s", plan)
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

        for iteration in range(1, max_iterations + 1):
            self.state["iteration"] = iteration

            # Read phases from TinyDB
            phases = repo.list_phases(plan_folder)
            if not phases:
                self.state["errors"].append(
                    f"No phases found in TinyDB for {plan_folder}"
                )
                return False

            # Find next pending/in_progress phase (order preserved by _order field)
            next_phase = None
            for phase in phases:
                if phase.status in ("pending", "in_progress"):
                    next_phase = phase
                    break

            if not next_phase:
                logger.info("All phases complete for %s", plan_folder)
                return True

            agent_type = next_phase.agent
            if not agent_type:
                logger.error(
                    "Phase %s in %s has no agent field set in TinyDB — skipping with error. "
                    "Use 'agentic epic phase update %s --agent <agent-name>' to fix.",
                    next_phase.name, plan_folder, next_phase.name,
                )
                self.state["errors"].append(
                    f"No agent routing for phase {next_phase.name} in {plan_folder}: "
                    f"agent field must be set in TinyDB"
                )
                repo.update_phase(plan_folder, next_phase.name, {"status": "failed"})
                self.state["phases_failed"].append(f"{plan_folder}:{next_phase.name}")
                return False

            effective_turns = next_phase.max_turns if next_phase.max_turns is not None else DEFAULT_PHASE_MAX_TURNS
            effective_timeout = next_phase.timeout if next_phase.timeout is not None else DEFAULT_PHASE_TIMEOUT
            logger.info(
                "Executing phase %s with agent %s for %s (iteration %d/%d, max_turns=%d, timeout=%ds)",
                next_phase.name, agent_type, plan_folder, iteration, max_iterations,
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

            if success:
                repo.update_phase(plan_folder, next_phase.name, {"status": "completed"})
                self.state["phases_completed"].append(f"{plan_folder}:{next_phase.name}")
                logger.info("Phase %s completed for %s", next_phase.name, plan_folder)
            else:
                # Check feedback triggers from TinyDB PhaseData
                rerun_phase = self._check_feedback_triggers_tinydb(
                    next_phase, plan_folder, repo,
                )
                if rerun_phase:
                    logger.info(
                        "Feedback trigger: re-running phase %s for %s",
                        rerun_phase, plan_folder,
                    )
                    repo.update_phase(plan_folder, next_phase.name, {"status": "failed"})
                    repo.update_phase(plan_folder, rerun_phase, {"status": "pending"})
                    # Continue to next iteration which will pick up the re-run
                    continue

                repo.update_phase(plan_folder, next_phase.name, {"status": "failed"})
                self.state["phases_failed"].append(f"{plan_folder}:{next_phase.name}")
                self.state["errors"].append(
                    f"Phase {next_phase.name} failed for {plan_folder}"
                )
                return False

        logger.warning("Max iterations (%d) reached for %s", max_iterations, plan_folder)
        return False

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
                logger.error(
                    "Exhausted %d retries for %s:%s — giving up",
                    MAX_SPAWN_RETRIES, plan_folder, phase_id,
                )
                return False

            # Quick exit detected — diagnose and decide if retry is worthwhile
            diagnosis = self._diagnose_quick_exit(session_id)
            if diagnosis and not diagnosis.retryable:
                logger.error(
                    "Quick exit for %s:%s is not retryable (%s): %s",
                    plan_folder, phase_id, diagnosis.error_type.value, diagnosis.detail[:200],
                )
                return False

            backoff = static_backoff(attempt, SPAWN_RETRY_BACKOFF)
            logger.warning(
                "Quick exit detected for %s:%s (attempt %d/%d). "
                "Retrying in %ds... (diagnosis: %s)",
                plan_folder, phase_id, attempt + 1, 1 + MAX_SPAWN_RETRIES,
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

        effective_max_turns = max_turns if max_turns is not None else DEFAULT_PHASE_MAX_TURNS

        cmd = build_spawn_command(
            role=agent_type,
            epic_folder=plan_folder,
            max_turns=effective_max_turns,
            skip_permissions=self.dangerously_skip_permissions,
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
            logger.error(
                "Spawn timed out for %s:%s%s (agent=%s, 60s limit)",
                plan_folder, phase_id, retry_label, agent_type,
            )
            self.state["errors"].append(
                f"Spawn timed out for {plan_folder}:{phase_id}{retry_label}"
            )
            return False, None, False
        if result.returncode != 0:
            logger.error(
                "Failed to spawn %s for %s:%s%s: %s",
                agent_type, plan_folder, phase_id, retry_label, result.stderr,
            )
            self.state["errors"].append(
                f"Spawn failed for {plan_folder}:{phase_id}{retry_label}: {result.stderr}"
            )
            return False, None, False

        try:
            data = json.loads(result.stdout)
            session_id = data.get("session_id")
        except (json.JSONDecodeError, KeyError):
            logger.error("Could not parse spawn output for %s:%s%s", plan_folder, phase_id, retry_label)
            return False, None, False

        if not session_id:
            logger.error("No session_id returned for %s:%s%s", plan_folder, phase_id, retry_label)
            return False, None, False

        # Log tmux session name for operator visibility (attach for debugging)
        tmux_session = data.get("tmux_session")
        if tmux_session:
            logger.info(
                "Spawned%s %s for %s:%s -> session %s (tmux: %s, attach: tmux attach -t %s)",
                retry_label, agent_type, plan_folder, phase_id, session_id, tmux_session, tmux_session,
            )
        else:
            logger.info(
                "Spawned%s %s for %s:%s -> session %s",
                retry_label, agent_type, plan_folder, phase_id, session_id,
            )

        # Wait for session to complete (configurable per-phase timeout)
        status = self.workflow.wait_for_session(session_id, timeout=timeout)
        elapsed = _time.monotonic() - spawn_start
        is_quick_exit = elapsed < 30  # QUICK_EXIT_THRESHOLD

        # Extract SDK metrics from session state (written by sdk_pane_runner)
        try:
            sdk_metrics = read_sdk_metrics(session_id)
            if sdk_metrics["cost_usd"] > 0:
                logger.info(
                    "SDK metrics for %s:%s — cost=$%.4f, duration=%dms, turns=%d, transport=%s",
                    plan_folder, phase_id,
                    sdk_metrics["cost_usd"],
                    sdk_metrics["duration_ms"],
                    sdk_metrics["num_turns"],
                    sdk_metrics["transport"],
                )
        except Exception as e:
            logger.debug("Could not read SDK metrics for %s: %s", session_id[:8], e)
            sdk_metrics = {"cost_usd": 0.0}

        self.total_cost_usd += sdk_metrics.get("cost_usd", 0.0)

        if status == "completed":
            return True, session_id, False

        logger.error(
            "Session %s for %s:%s%s ended with status: %s (%.1fs)",
            session_id[:8], plan_folder, phase_id, retry_label, status, elapsed,
        )
        return False, session_id, is_quick_exit

    def _diagnose_quick_exit(self, session_id: Optional[str]):
        """Run session diagnostics on a quick-exit session.

        Diagnoses the session and persists ``failure_reason`` and
        ``error_code`` back into the session state record so Ralph and
        operators can inspect the structured failure data (P6_001/P6_002/P6_003).

        Args:
            session_id: Session UUID to diagnose.

        Returns:
            SessionDiagnosis or None if diagnostics unavailable.
        """
        if not session_id:
            return None
        try:
            from agenticcli.utils.session_diagnostics import (
                diagnose_session_state,
                failure_summary,
            )
            from agenticcli.utils.state_store import StateStore

            store = StateStore("sessions")
            data = store.load(session_id)
            if data:
                diagnosis = diagnose_session_state(data)
                if diagnosis:
                    # Persist structured failure info into session state
                    # so Ralph StateStore and `agentic session status` can surface it
                    summary = failure_summary(diagnosis)
                    data["error_code"] = summary["error_code"]
                    data["failure_reason"] = summary
                    store.save(data)
                    logger.info(
                        "Session %s diagnosed: error_code=%s, retryable=%s",
                        session_id[:8], summary["error_code"], summary["retryable"],
                    )
                return diagnosis
        except Exception as e:
            logger.debug("Failed to diagnose session %s: %s", session_id[:8], e)
        return None

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
                logger.info(
                    "Feedback trigger %s -> %s for %s",
                    failure_key, target, plan_folder,
                )
                return target
            else:
                logger.warning(
                    "Feedback trigger target %s not found in TinyDB for %s",
                    target, plan_folder,
                )

        return None
