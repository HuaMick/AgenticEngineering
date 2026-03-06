"""Orchestration workflow for plan management.

Extends PlannerLoopWorkflow with MMD loading and routing metadata parsing.
Provides PlanningRunner for planning-only lifecycle and ExecutionRunner for
deterministic phase-by-phase execution.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from agenticcli.workflows.planner_loop import PlannerLoopWorkflow, PlannerLoopRunner

logger = logging.getLogger(__name__)


def _parse_json_like_block(content: str, key: str) -> Optional[dict]:
    """Parse a JSON-like block from MMD YAML front matter.

    Handles multiline blocks like:
        AGENT_ROUTING: {
          "Build": "build-python",
          "Test": "test-runner"
        }

    Args:
        content: Full MMD content.
        key: Header key to look for (e.g. "AGENT_ROUTING", "STATUS").

    Returns:
        Parsed dict, or None if not found or unparseable.
    """
    # Match "KEY: {" followed by content up to closing "}"
    pattern = rf'{key}:\s*\{{([^}}]*)\}}'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads("{" + match.group(1) + "}")
    except json.JSONDecodeError:
        return None


def parse_mmd_routing(mmd_content: str) -> dict:
    """Parse MMD header to extract routing metadata.

    Supports two formats:
    1. Comment-based (old): ``%% STATUS: Build=pending, Test=pending``
    2. YAML front matter with JSON-like blocks (new):
       ``STATUS: { "Build": "pending", "Test": "pending" }``

    Args:
        mmd_content: Raw MMD file content.

    Returns:
        dict with keys:
            agent_routing: dict mapping phase_id -> agent_type
            status: dict mapping phase_id -> status_string
            feedback_triggers: dict mapping trigger -> action
            phases: list of dicts with id and description
    """
    result = {
        "agent_routing": {},
        "status": {},
        "feedback_triggers": {},
        "phases": [],
    }

    if not mmd_content:
        return result

    # --- AGENT_ROUTING ---
    # Try JSON-like block first (new format)
    json_routing = _parse_json_like_block(mmd_content, "AGENT_ROUTING")
    if json_routing:
        result["agent_routing"] = json_routing
    else:
        # Fall back to comment-based format
        # Format: "phase_1 -> build-python, phase_2 -> test-builder"
        # or: "phase_1=build-python, phase_2=test-builder"
        routing_match = re.search(r"(?:%%|#)\s*AGENT_ROUTING:\s*(.+)", mmd_content)
        if routing_match:
            routing_str = routing_match.group(1).strip()
            for mapping in routing_str.split(","):
                mapping = mapping.strip()
                if "->" in mapping:
                    phase, agent = mapping.split("->", 1)
                    result["agent_routing"][phase.strip()] = agent.strip()
                elif "=" in mapping:
                    phase, agent = mapping.split("=", 1)
                    result["agent_routing"][phase.strip()] = agent.strip()

    # --- STATUS ---
    json_status = _parse_json_like_block(mmd_content, "STATUS")
    if json_status:
        result["status"] = json_status
    else:
        # Format: "phase_1=pending, phase_2=pending"
        status_match = re.search(r"(?:%%|#)\s*STATUS:\s*(.+)", mmd_content)
        if status_match:
            status_str = status_match.group(1).strip()
            for mapping in status_str.split(","):
                mapping = mapping.strip()
                if "=" in mapping:
                    phase, status = mapping.split("=", 1)
                    result["status"][phase.strip()] = status.strip()

    # --- FEEDBACK_TRIGGERS / FEEDBACK_TRIGGER ---
    json_triggers = _parse_json_like_block(mmd_content, "FEEDBACK_TRIGGER(?:S)?")
    if json_triggers:
        result["feedback_triggers"] = json_triggers
    else:
        triggers_match = re.search(r"(?:%%|#)\s*FEEDBACK_TRIGGER(?:S)?:\s*(.+)", mmd_content)
        if triggers_match:
            triggers_str = triggers_match.group(1).strip()
            for mapping in triggers_str.split(","):
                mapping = mapping.strip()
                if "->" in mapping:
                    trigger, action = mapping.split("->", 1)
                    result["feedback_triggers"][trigger.strip()] = action.strip()
                elif "=" in mapping:
                    trigger, action = mapping.split("=", 1)
                    result["feedback_triggers"][trigger.strip()] = action.strip()

    # --- PHASES ---
    # Try JSON-like array first: PHASES: [Build, Teach, Test, UAT]
    phases_match = re.search(r"PHASES:\s*\[([^\]]+)\]", mmd_content)
    if phases_match:
        phases_str = phases_match.group(1)
        for phase_name in phases_str.split(","):
            phase_name = phase_name.strip().strip('"').strip("'")
            if phase_name:
                result["phases"].append({"id": phase_name, "description": phase_name})
    else:
        # Format: "%%   1. phase_1 - Build components"
        phase_pattern = r"(?:%%|#)\s+\d+\.\s+(\S+)\s*-\s*(.+)"
        for match in re.finditer(phase_pattern, mmd_content):
            phase_id = match.group(1).strip()
            description = match.group(2).strip()
            result["phases"].append({
                "id": phase_id,
                "description": description,
            })

    # Parse per-phase AGENT_ROUTING comments (inside subgraphs)
    # Format: "%% AGENT_ROUTING: build-python agent"
    per_phase_pattern = r"(?:%%|#)\s*AGENT_ROUTING:\s*(\S+)\s+agent"
    for match in re.finditer(per_phase_pattern, mmd_content):
        agent_type = match.group(1).strip()
        logger.debug("Found per-phase AGENT_ROUTING: %s", agent_type)

    return result


class OrchestrationWorkflow(PlannerLoopWorkflow):
    """Orchestration workflow extending PlannerLoopWorkflow with MMD utilities.

    Adds methods for loading MMD files and parsing routing metadata.
    """

    def load_mmd(self, plan_folder: str) -> Optional[str]:
        """Load orchestration MMD content from epic folder.

        Args:
            plan_folder: Epic folder name.

        Returns:
            MMD file content string or None if not found.
        """
        plan_dir = self.epics_dir / plan_folder
        if not plan_dir.exists():
            logger.warning("Plan folder does not exist: %s", plan_dir)
            return None

        # Find orchestration_*.mmd files
        mmds = list(plan_dir.glob("orchestration_*.mmd"))
        if not mmds:
            logger.warning("No orchestration MMD found in %s", plan_folder)
            return None

        # Read first match
        mmd_path = mmds[0]
        try:
            content = mmd_path.read_text()
            logger.info("Loaded MMD from %s", mmd_path)
            return content
        except Exception as e:
            logger.error("Failed to read MMD %s: %s", mmd_path, e)
            return None

    def parse_routing(self, mmd_content: str) -> dict:
        """Parse MMD routing metadata.

        Args:
            mmd_content: Raw MMD file content.

        Returns:
            Routing metadata dict (delegates to parse_mmd_routing).
        """
        return parse_mmd_routing(mmd_content)

    def get_mmd_path(self, plan_folder: str) -> Optional[Path]:
        """Get the path to the orchestration MMD file for a plan.

        Args:
            plan_folder: Plan folder name.

        Returns:
            Path to MMD file or None if not found.
        """
        plan_dir = self.epics_dir / plan_folder
        if not plan_dir.exists():
            return None
        mmds = list(plan_dir.glob("orchestration_*.mmd"))
        return mmds[0] if mmds else None

    def update_mmd_status(self, plan_folder: str, phase_id: str, new_status: str) -> bool:
        """Update the STATUS of a single phase in the MMD file on disk.

        Handles both JSON-like and comment-based STATUS formats.

        Args:
            plan_folder: Plan folder name.
            phase_id: Phase identifier to update.
            new_status: New status value (pending, in_progress, completed, failed).

        Returns:
            True if update succeeded.
        """
        mmd_path = self.get_mmd_path(plan_folder)
        if not mmd_path:
            logger.error("No MMD file found for %s", plan_folder)
            return False

        try:
            content = mmd_path.read_text()
        except Exception as e:
            logger.error("Failed to read MMD %s: %s", mmd_path, e)
            return False

        updated = False

        # Try JSON-like format: "Phase": "old_status" -> "Phase": "new_status"
        json_pattern = rf'("{re.escape(phase_id)}":\s*")([^"]*?)(")'
        json_match = re.search(json_pattern, content)
        if json_match:
            content = re.sub(json_pattern, rf'\g<1>{new_status}\3', content)
            updated = True
        else:
            # Try comment-based format: Phase=old_status
            comment_pattern = rf'({re.escape(phase_id)}=)\w+'
            if re.search(comment_pattern, content):
                content = re.sub(comment_pattern, rf'\g<1>{new_status}', content)
                updated = True

        if not updated:
            logger.error("Phase %s not found in MMD STATUS for %s", phase_id, plan_folder)
            return False

        try:
            mmd_path.write_text(content)
            logger.info("Updated MMD status: %s.%s = %s", plan_folder, phase_id, new_status)
            return True
        except Exception as e:
            logger.error("Failed to write MMD %s: %s", mmd_path, e)
            return False

    def discover_plans_needing_execution(self) -> list[str]:
        """Find live plans that have an orchestration MMD with pending phases.

        Returns:
            List of plan folder names needing execution.
        """
        if not self.epics_dir.exists():
            logger.warning("Plans directory does not exist: %s", self.epics_dir)
            return []

        needs_execution = []
        for plan_dir in sorted(self.epics_dir.iterdir()):
            if not plan_dir.is_dir():
                continue
            mmds = list(plan_dir.glob("orchestration_*.mmd"))
            if not mmds:
                continue
            # Check if any phase is still pending
            try:
                content = mmds[0].read_text()
            except Exception:
                continue
            routing = parse_mmd_routing(content)
            if any(s == "pending" for s in routing["status"].values()):
                needs_execution.append(plan_dir.name)

        logger.info("Found %d plans needing execution: %s", len(needs_execution), needs_execution)
        return needs_execution


class PlanningRunner:
    """Planning-only runner with no execution phase.

    Discovers plans needing orchestration (or targets a single plan) and
    runs the PlannerLoopRunner for each, which handles the full planning
    workflow: explore, story generation, planning, review, MMD generation
    and validation.

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

        # Archive completed plans
        for plan_dir in sorted(self.workflow.epics_dir.iterdir()):
            if plan_dir.is_dir() and self.workflow.get_plan_status(plan_dir.name) == "completed":
                logger.info("Archiving completed plan: %s", plan_dir.name)
                self.workflow.archive_plan(plan_dir.name)

        # Determine plans to process
        if self.plan_folder:
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


class ExecutionRunner:
    """Deterministic execution runner for orchestrated plans.

    Reads the orchestration MMD, finds the next pending phase, spawns the
    corresponding agent, waits for completion, updates the MMD status, and
    iterates until all phases are complete or an error occurs.
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

        # Archive completed plans
        for plan_dir in sorted(self.workflow.epics_dir.iterdir()):
            if plan_dir.is_dir() and self.workflow.get_plan_status(plan_dir.name) == "completed":
                logger.info("Archiving completed plan: %s", plan_dir.name)
                self.workflow.archive_plan(plan_dir.name)

        # Determine plans to process
        if self.plan_folder:
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

        Args:
            plan_folder: Plan folder name.
            max_iterations: Max phase executions for this plan.

        Returns:
            True if all phases completed successfully.
        """
        for iteration in range(1, max_iterations + 1):
            self.state["iteration"] = iteration

            # Reload MMD each iteration to pick up status changes
            mmd_content = self.workflow.load_mmd(plan_folder)
            if not mmd_content:
                self.state["errors"].append(f"No MMD found for {plan_folder}")
                return False

            routing = self.workflow.parse_routing(mmd_content)
            if not routing["status"]:
                self.state["errors"].append(f"No STATUS in MMD for {plan_folder}")
                return False

            # Find next pending phase (respect PHASES order if available)
            next_phase = self._find_next_pending_phase(routing)
            if not next_phase:
                logger.info("All phases complete for %s", plan_folder)
                return True

            phase_id = next_phase
            agent_type = routing["agent_routing"].get(phase_id)
            if not agent_type:
                self.state["errors"].append(
                    f"No agent routing for phase {phase_id} in {plan_folder}"
                )
                return False

            logger.info(
                "Executing phase %s with agent %s for %s (iteration %d/%d)",
                phase_id, agent_type, plan_folder, iteration, max_iterations,
            )

            # Mark phase as in_progress
            self.workflow.update_mmd_status(plan_folder, phase_id, "in_progress")

            # Spawn agent and wait
            success = self._run_phase(plan_folder, phase_id, agent_type, routing)

            if success:
                self.workflow.update_mmd_status(plan_folder, phase_id, "completed")
                self.state["phases_completed"].append(f"{plan_folder}:{phase_id}")
                logger.info("Phase %s completed for %s", phase_id, plan_folder)
            else:
                # Check feedback triggers for re-run rules
                rerun_phase = self._check_feedback_triggers(
                    routing, phase_id, plan_folder,
                )
                if rerun_phase:
                    logger.info(
                        "Feedback trigger: re-running phase %s for %s",
                        rerun_phase, plan_folder,
                    )
                    self.workflow.update_mmd_status(plan_folder, phase_id, "failed")
                    self.workflow.update_mmd_status(plan_folder, rerun_phase, "pending")
                    # Continue to next iteration which will pick up the re-run
                    continue

                self.workflow.update_mmd_status(plan_folder, phase_id, "failed")
                self.state["phases_failed"].append(f"{plan_folder}:{phase_id}")
                self.state["errors"].append(
                    f"Phase {phase_id} failed for {plan_folder}"
                )
                return False

        logger.warning("Max iterations (%d) reached for %s", max_iterations, plan_folder)
        return False

    def _find_next_pending_phase(self, routing: dict) -> Optional[str]:
        """Find the next pending phase respecting PHASES order.

        Args:
            routing: Parsed routing metadata.

        Returns:
            Phase ID of next pending phase, or None if all complete.
        """
        # If PHASES order is available, use it
        if routing["phases"]:
            phase_order = [p["id"] for p in routing["phases"]]
        else:
            # Fall back to STATUS dict key order
            phase_order = list(routing["status"].keys())

        for phase_id in phase_order:
            status = routing["status"].get(phase_id, "")
            if status == "pending":
                return phase_id

        return None

    def _run_phase(
        self,
        plan_folder: str,
        phase_id: str,
        agent_type: str,
        routing: dict,
    ) -> bool:
        """Spawn agent for a phase and wait for completion.

        Args:
            plan_folder: Plan folder name.
            phase_id: Phase identifier.
            agent_type: Agent role to spawn.
            routing: Full routing metadata.

        Returns:
            True if agent completed successfully.
        """
        import subprocess

        cmd = [
            "agentic", "-j", "session", "spawn",
            "--role", agent_type,
            "--plan", plan_folder,
            "-b",
        ]
        if self.dangerously_skip_permissions:
            cmd.append("--dangerously-skip-permissions")

        # Unset CLAUDECODE to allow spawning from within orchestration
        # workflows that may themselves run inside a Claude Code session.
        import os
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.workflow.working_dir,
            env=env,
        )
        if result.returncode != 0:
            logger.error(
                "Failed to spawn %s for %s:%s: %s",
                agent_type, plan_folder, phase_id, result.stderr,
            )
            self.state["errors"].append(
                f"Spawn failed for {plan_folder}:{phase_id}: {result.stderr}"
            )
            return False

        try:
            data = json.loads(result.stdout)
            session_id = data.get("session_id")
        except (json.JSONDecodeError, KeyError):
            logger.error("Could not parse spawn output for %s:%s", plan_folder, phase_id)
            return False

        if not session_id:
            logger.error("No session_id returned for %s:%s", plan_folder, phase_id)
            return False

        logger.info(
            "Spawned %s for %s:%s -> session %s",
            agent_type, plan_folder, phase_id, session_id,
        )

        # Wait for session to complete (10 min timeout per phase)
        status = self.workflow.wait_for_session(session_id, timeout=600)
        if status == "completed":
            return True

        logger.error(
            "Session %s for %s:%s ended with status: %s",
            session_id[:8], plan_folder, phase_id, status,
        )
        return False

    def _check_feedback_triggers(
        self,
        routing: dict,
        failed_phase: str,
        plan_folder: str,
    ) -> Optional[str]:
        """Check if a feedback trigger maps to a re-run phase.

        Looks for triggers like TEST_FAILURE -> Test or UAT_FAILURE -> UAT.
        The convention is {PHASE_NAME}_FAILURE -> target_phase.

        Args:
            routing: Parsed routing metadata.
            failed_phase: Phase that failed.
            plan_folder: Plan folder name (for logging).

        Returns:
            Phase ID to re-run, or None if no applicable trigger.
        """
        triggers = routing.get("feedback_triggers", {})
        if not triggers:
            return None

        # Look for a trigger matching this phase failure
        # Common patterns: TEST_FAILURE, UAT_FAILURE, BUILD_FAILURE
        failure_key = f"{failed_phase.upper()}_FAILURE"
        target = triggers.get(failure_key)
        if target:
            # Verify the target phase exists in routing
            if target in routing["status"]:
                logger.info(
                    "Feedback trigger %s -> %s for %s",
                    failure_key, target, plan_folder,
                )
                return target
            else:
                logger.warning(
                    "Feedback trigger target %s not found in STATUS for %s",
                    target, plan_folder,
                )

        return None
