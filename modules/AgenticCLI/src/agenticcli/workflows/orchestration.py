"""Orchestration workflow for automated plan execution.

Extends PlannerLoopWorkflow to add execution phase: parses MMD routing metadata,
spawns appropriate agents per phase, tracks execution status, and archives plans.
"""

import json
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from agenticcli.workflows.planner_loop import PlannerLoopWorkflow, PlannerLoopRunner

logger = logging.getLogger(__name__)


def parse_mmd_routing(mmd_content: str) -> dict:
    """Parse MMD header to extract routing metadata.

    Extracts structured metadata from MMD file header comments (both %% and # styles).

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

    # Parse AGENT_ROUTING line (header level)
    # Format: "phase_1 -> build-python, phase_2 -> test-builder"
    routing_match = re.search(r"(?:%%|#)\s*AGENT_ROUTING:\s*(.+)", mmd_content)
    if routing_match:
        routing_str = routing_match.group(1).strip()
        # Split by comma, then parse each "phase -> agent"
        for mapping in routing_str.split(","):
            mapping = mapping.strip()
            if "->" in mapping:
                phase, agent = mapping.split("->", 1)
                result["agent_routing"][phase.strip()] = agent.strip()

    # Parse STATUS line
    # Format: "phase_1=pending, phase_2=pending"
    status_match = re.search(r"(?:%%|#)\s*STATUS:\s*(.+)", mmd_content)
    if status_match:
        status_str = status_match.group(1).strip()
        for mapping in status_str.split(","):
            mapping = mapping.strip()
            if "=" in mapping:
                phase, status = mapping.split("=", 1)
                result["status"][phase.strip()] = status.strip()

    # Parse FEEDBACK_TRIGGERS line
    # Format: "TEST_FAILURE -> test-fix-loop, BUILD_FAILURE -> escalate"
    triggers_match = re.search(r"(?:%%|#)\s*FEEDBACK_TRIGGERS:\s*(.+)", mmd_content)
    if triggers_match:
        triggers_str = triggers_match.group(1).strip()
        for mapping in triggers_str.split(","):
            mapping = mapping.strip()
            if "->" in mapping:
                trigger, action = mapping.split("->", 1)
                result["feedback_triggers"][trigger.strip()] = action.strip()

    # Parse PHASES lines from header
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
        # This is a fallback if header-level routing didn't capture it
        # We don't have phase context here, so this is informational only
        logger.debug("Found per-phase AGENT_ROUTING: %s", agent_type)

    return result


class OrchestrationWorkflow(PlannerLoopWorkflow):
    """Orchestration workflow extending PlannerLoopWorkflow with execution methods.

    Adds methods for loading MMD files, parsing routing metadata, spawning
    execution agents, and archiving completed plans.
    """

    def load_mmd(self, plan_folder: str) -> Optional[str]:
        """Load orchestration MMD content from plan folder.

        Args:
            plan_folder: Plan folder name.

        Returns:
            MMD file content string or None if not found.
        """
        plan_dir = self.plans_dir / plan_folder
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

    def spawn_execution_agent(
        self, plan_folder: str, phase_id: str, agent_type: str
    ) -> Optional[str]:
        """Spawn agent for a specific phase execution.

        Args:
            plan_folder: Plan folder name.
            phase_id: Phase identifier.
            agent_type: Agent type to spawn (e.g., build-python, test-runner).

        Returns:
            Session ID if spawned successfully, None otherwise.
        """
        cmd = [
            "agentic", "session", "spawn",
            "--role", agent_type,
            "--plan", plan_folder,
            "-b",
            "--dangerously-skip-permissions",
            "--json",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.error(
                "Failed to spawn %s for %s phase %s: %s",
                agent_type, plan_folder, phase_id, result.stderr
            )
            return None

        try:
            data = json.loads(result.stdout)
            session_id = data.get("session_id")
            logger.info(
                "Spawned %s for %s phase %s: session %s",
                agent_type, plan_folder, phase_id, session_id
            )
            return session_id
        except (json.JSONDecodeError, KeyError):
            logger.error(
                "Could not parse spawn output for %s phase %s",
                plan_folder, phase_id
            )
            return None

    def archive_plan(self, plan_folder: str) -> bool:
        """Archive plan after successful execution.

        Args:
            plan_folder: Plan folder name.

        Returns:
            True if archived successfully, False otherwise.
        """
        cmd = ["agentic", "plan", "archive", plan_folder]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.error("Failed to archive %s: %s", plan_folder, result.stderr)
            return False

        logger.info("Archived plan %s", plan_folder)
        return True


class OrchestrationRunner:
    """Orchestration runner with two-phase lifecycle (plan-then-execute).

    Runs the full orchestration workflow:
    1. Planning phase: discover plans, spawn planners, review, generate MMD
    2. Execution phase: parse MMD routing, execute phases sequentially
    3. Archive: move completed plans to archive

    Supports single-plan mode (--plan flag) and discovery mode (all plans).
    Includes phase-level retry for execution failures.
    """

    def __init__(
        self,
        workflow: Optional[OrchestrationWorkflow] = None,
        project: Optional[str] = None,
        plan_folder: Optional[str] = None,
    ):
        """Initialize orchestration runner.

        Args:
            workflow: OrchestrationWorkflow instance (creates default if None).
            project: Optional project filter for story discovery.
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
            "current_plan": None,
            "current_phase": None,
            "execution_results": {},  # plan_folder -> {phase_id: status}
        }

    def run(
        self,
        max_iterations: int = 10,
        completion_promise: Optional[str] = None,
        max_phase_retries: int = 2,
    ) -> bool:
        """Run full orchestration: plan phase then execute phase.

        Args:
            max_iterations: Max iterations for planning phase.
            completion_promise: Completion text for planning phase.
            max_phase_retries: Max retries per execution phase.

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

        # Determine plans to process
        if self.plan_folder:
            plans_to_process = [self.plan_folder]
        else:
            plans_to_process = self.workflow.discover_plans_needing_orchestration()
            if not plans_to_process:
                logger.info("No plans needing orchestration")
                return True

        logger.info("Processing %d plans: %s", len(plans_to_process), plans_to_process)

        # Process each plan
        all_success = True
        for plan in plans_to_process:
            self.state["current_plan"] = plan
            logger.info("Processing plan: %s", plan)

            # Phase 1: Planning
            planning_success = self._run_planning_phase(
                plan, max_iterations, completion_promise or ""
            )
            if not planning_success:
                logger.error("Planning phase failed for %s", plan)
                self.state["plans_failed"].append(plan)
                all_success = False
                continue

            # Phase 2: Execution
            execution_success = self._run_execution_phase(plan, max_phase_retries)
            if not execution_success:
                logger.error("Execution phase failed for %s", plan)
                self.state["plans_failed"].append(plan)
                all_success = False
                continue

            # Archive on success
            if self.workflow.archive_plan(plan):
                self.state["plans_processed"].append(plan)
                logger.info("Successfully completed plan: %s", plan)
            else:
                logger.warning("Plan %s completed but archiving failed", plan)
                self.state["plans_failed"].append(plan)
                all_success = False

        self.state["current_plan"] = None
        return all_success

    def _run_planning_phase(
        self, plan_folder: str, max_iterations: int, completion_promise: str
    ) -> bool:
        """Phase 1: discover, plan, review, generate MMD.

        Delegates to PlannerLoopRunner for the planning workflow.

        Args:
            plan_folder: Plan folder name.
            max_iterations: Max planning loop iterations.
            completion_promise: Completion text.

        Returns:
            True if planning succeeded, False otherwise.
        """
        logger.info("Starting planning phase for %s", plan_folder)

        # Create PlannerLoopRunner for this plan
        planner_runner = PlannerLoopRunner(
            workflow=self.workflow,  # Reuse workflow instance
            project=self.project,
            plan_folder=plan_folder,
        )

        # Run planning loop
        try:
            success = planner_runner.run(
                max_iterations=max_iterations,
                completion_promise=completion_promise,
            )
            if success:
                logger.info("Planning phase completed for %s", plan_folder)
                return True
            else:
                logger.error("Planning phase failed for %s", plan_folder)
                self.state["errors"].append(
                    f"Planning failed for {plan_folder}"
                )
                return False
        except Exception as e:
            logger.error("Planning phase exception for %s: %s", plan_folder, e)
            self.state["errors"].append(
                f"Planning exception for {plan_folder}: {e}"
            )
            return False

    def _run_execution_phase(self, plan_folder: str, max_phase_retries: int) -> bool:
        """Phase 2: parse MMD routing, execute each phase sequentially.

        Args:
            plan_folder: Plan folder name.
            max_phase_retries: Max retries per phase.

        Returns:
            True if all phases executed successfully, False otherwise.
        """
        logger.info("Starting execution phase for %s", plan_folder)

        # Load MMD
        mmd_content = self.workflow.load_mmd(plan_folder)
        if not mmd_content:
            logger.error("Could not load MMD for %s", plan_folder)
            self.state["errors"].append(f"MMD load failed for {plan_folder}")
            return False

        # Parse routing
        routing = self.workflow.parse_routing(mmd_content)
        agent_routing = routing.get("agent_routing", {})
        phases = routing.get("phases", [])

        if not agent_routing:
            logger.error("No agent routing found in MMD for %s", plan_folder)
            self.state["errors"].append(
                f"No agent routing in MMD for {plan_folder}"
            )
            return False

        # Initialize execution results
        self.state["execution_results"][plan_folder] = {}

        # Execute each phase sequentially
        for phase in phases:
            phase_id = phase["id"]
            agent_type = agent_routing.get(phase_id)

            if not agent_type:
                logger.warning(
                    "No agent routing for phase %s in %s, skipping",
                    phase_id, plan_folder
                )
                continue

            self.state["current_phase"] = phase_id
            logger.info(
                "Executing phase %s with %s for %s",
                phase_id, agent_type, plan_folder
            )

            # Retry loop for phase execution
            success = False
            for retry in range(max_phase_retries + 1):
                if retry > 0:
                    logger.info(
                        "Retrying phase %s (attempt %d/%d)",
                        phase_id, retry + 1, max_phase_retries + 1
                    )

                phase_success = self._execute_phase(
                    plan_folder, phase_id, agent_type
                )
                if phase_success:
                    success = True
                    break

                logger.warning(
                    "Phase %s failed (attempt %d/%d)",
                    phase_id, retry + 1, max_phase_retries + 1
                )

            # Record result
            self.state["execution_results"][plan_folder][phase_id] = (
                "success" if success else "failed"
            )

            if not success:
                logger.error(
                    "Phase %s failed after %d retries for %s",
                    phase_id, max_phase_retries, plan_folder
                )
                self.state["errors"].append(
                    f"Phase {phase_id} failed for {plan_folder}"
                )
                return False

        self.state["current_phase"] = None
        logger.info("Execution phase completed for %s", plan_folder)
        return True

    def _execute_phase(
        self, plan_folder: str, phase_id: str, agent_type: str
    ) -> bool:
        """Execute a single phase: spawn agent, wait, check status.

        Args:
            plan_folder: Plan folder name.
            phase_id: Phase identifier.
            agent_type: Agent type to spawn.

        Returns:
            True if phase succeeded, False otherwise.
        """
        # Spawn agent
        session_id = self.workflow.spawn_execution_agent(
            plan_folder, phase_id, agent_type
        )
        if not session_id:
            logger.error(
                "Failed to spawn agent for phase %s in %s",
                phase_id, plan_folder
            )
            return False

        # Wait for session to complete (with timeout)
        # For now, we'll use a simple polling approach
        # TODO: Implement proper session status checking via CLI
        max_wait = 600  # 10 minutes
        poll_interval = 10  # seconds
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            # Check session status
            cmd = ["agentic", "session", "status", session_id, "--json"]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=self.workflow.working_dir,
            )

            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    status = data.get("status")
                    if status == "completed":
                        logger.info(
                            "Phase %s completed successfully for %s",
                            phase_id, plan_folder
                        )
                        return True
                    elif status in ["failed", "error"]:
                        logger.error(
                            "Phase %s failed for %s",
                            phase_id, plan_folder
                        )
                        return False
                    # If status is "running", continue waiting
                except (json.JSONDecodeError, KeyError):
                    logger.warning("Could not parse session status")

        logger.error(
            "Phase %s timed out after %d seconds for %s",
            phase_id, max_wait, plan_folder
        )
        return False
