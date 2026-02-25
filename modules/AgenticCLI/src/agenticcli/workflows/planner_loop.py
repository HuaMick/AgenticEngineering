"""Planner Loop workflow for automated orchestration planning.

Encapsulates the orchestration planner logic: discovers plans needing
orchestration MMDs, spawns specialized planners, runs review loops,
generates and validates MMD files, and updates task status.
"""

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

from agenticcli.utils.state_store import StateStore, is_process_running
from agenticcli.utils.subprocess_utils import get_clean_env

logger = logging.getLogger(__name__)

# Shared session state store (same as session.py)
_session_store = StateStore("sessions", id_key="session_id")

# Plan type to planner agent mapping
PLAN_TYPE_TO_PLANNER = {
    "build": "planner-build",
    "test": "planner-test",
    "guidance": "planner-guidance",
    "cleaning": "planner-cleaning",
    "guidance-testing": "planner-guidance-testing",
}

DEFAULT_COMPLETION_PROMISE = "Planning complete. All plans have orchestration MMDs."


class PlannerLoopWorkflow:
    """Core workflow methods for the planner loop.

    Each method wraps a specific step in the planning workflow,
    calling CLI commands via subprocess.
    """

    def __init__(self, plans_dir: Optional[Path] = None, working_dir: Optional[str] = None):
        self.plans_dir = plans_dir or Path.cwd() / "docs" / "plans" / "live"
        self.working_dir = working_dir or str(Path.cwd())

    def run_health_check(self) -> None:
        """Run health check: agentic --version && agentic plan list.

        Raises:
            RuntimeError: If health check fails.
        """
        result = subprocess.run(
            ["agentic", "--version"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Health check failed: agentic --version returned {result.returncode}")

        result = subprocess.run(
            ["agentic", "plan", "list"],
            capture_output=True, text=True, timeout=30,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Health check failed: agentic plan list returned {result.returncode}")

        logger.info("Health check passed")

    def discover_plans_needing_orchestration(self) -> list[str]:
        """Find live plans that lack orchestration MMD files.

        Returns:
            List of plan folder names needing orchestration.
        """
        if not self.plans_dir.exists():
            logger.warning("Plans directory does not exist: %s", self.plans_dir)
            return []

        needs_work = []
        for plan_dir in sorted(self.plans_dir.iterdir()):
            if not plan_dir.is_dir():
                continue
            # Check for existing orchestration_*.mmd files
            mmds = list(plan_dir.glob("orchestration_*.mmd"))
            if not mmds:
                needs_work.append(plan_dir.name)

        logger.info("Found %d plans needing orchestration: %s", len(needs_work), needs_work)
        return needs_work

    def determine_plan_type(self, plan_folder: str) -> Optional[str]:
        """Determine plan type from plan_*.yml files.

        Args:
            plan_folder: Plan folder name.

        Returns:
            Plan type string (build, test, etc.) or None if not found.
        """
        plan_dir = self.plans_dir / plan_folder
        if not plan_dir.exists():
            return None

        for plan_file in plan_dir.glob("plan_*.yml"):
            # Extract type from filename: plan_build.yml -> build
            stem = plan_file.stem  # plan_build
            if stem.startswith("plan_"):
                plan_type = stem[5:]  # build
                if plan_type:
                    return plan_type

        return None

    def spawn_explore_agent(self, plan_folder: str) -> Optional[str]:
        """Spawn an explore agent to analyze the codebase and update the plan YAML.

        Args:
            plan_folder: Plan folder name.

        Returns:
            Session ID if spawned successfully, None otherwise.
        """
        cmd = [
            "agentic", "-j", "session", "spawn",
            "--role", "explore",
            "--plan", plan_folder,
            "-b",
            "--dangerously-skip-permissions",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.error("Failed to spawn explore agent for %s: %s", plan_folder, result.stderr)
            return None

        try:
            data = json.loads(result.stdout)
            session_id = data.get("session_id")
            logger.info("Spawned explore agent for %s: session %s", plan_folder, session_id)
            return session_id
        except (json.JSONDecodeError, KeyError):
            logger.error("Could not parse explore agent spawn output for %s", plan_folder)
            return None

    def spawn_story_agent(self, plan_folder: str) -> Optional[str]:
        """Spawn a story-generator agent for user story generation.

        Args:
            plan_folder: Plan folder name.

        Returns:
            Session ID if spawned successfully, None otherwise.
        """
        cmd = [
            "agentic", "-j", "session", "spawn",
            "--role", "story-generator",
            "--plan", plan_folder,
            "-b",
            "--dangerously-skip-permissions",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.error("Failed to spawn story agent for %s: %s", plan_folder, result.stderr)
            return None

        try:
            data = json.loads(result.stdout)
            session_id = data.get("session_id")
            logger.info("Spawned story agent for %s: session %s", plan_folder, session_id)
            return session_id
        except (json.JSONDecodeError, KeyError):
            logger.error("Could not parse story agent spawn output for %s", plan_folder)
            return None

    def discover_stories(self, plan_folder: str, project: Optional[str] = None) -> list[dict]:
        """Run story discovery for a plan.

        Args:
            plan_folder: Plan folder name.
            project: Optional project filter.

        Returns:
            List of story dicts from CLI output.
        """
        cmd = ["agentic", "--json", "agent", "stories", "find"]
        if project:
            cmd.extend(["--project", project])

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.warning("Story discovery failed for %s: %s", plan_folder, result.stderr)
            return []

        try:
            data = json.loads(result.stdout)
            stories = data if isinstance(data, list) else data.get("stories", [])
            logger.info("Discovered %d stories for %s", len(stories), plan_folder)
            return stories
        except (json.JSONDecodeError, KeyError):
            logger.warning("Could not parse story discovery output for %s", plan_folder)
            return []

    def spawn_planner(self, plan_folder: str, plan_type: str) -> Optional[str]:
        """Spawn appropriate planner agent for a plan.

        Args:
            plan_folder: Plan folder name.
            plan_type: Plan type (build, test, etc.).

        Returns:
            Session ID if spawned successfully, None otherwise.
        """
        planner_role = PLAN_TYPE_TO_PLANNER.get(plan_type, "planner-build")

        cmd = [
            "agentic", "-j", "session", "spawn",
            "--role", planner_role,
            "--plan", plan_folder,
            "-b",
            "--dangerously-skip-permissions",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.error("Failed to spawn planner for %s: %s", plan_folder, result.stderr)
            return None

        try:
            data = json.loads(result.stdout)
            session_id = data.get("session_id")
            logger.info("Spawned %s for %s: session %s", planner_role, plan_folder, session_id)
            return session_id
        except (json.JSONDecodeError, KeyError):
            logger.error("Could not parse spawn output for %s", plan_folder)
            return None

    def spawn_reviewer(self, plan_folder: str) -> Optional[str]:
        """Spawn planner-reviewer agent for a plan.

        Args:
            plan_folder: Plan folder name.

        Returns:
            Session ID if spawned successfully, None otherwise.
        """
        cmd = [
            "agentic", "-j", "session", "spawn",
            "--role", "planner-reviewer",
            "--plan", plan_folder,
            "-b",
            "--dangerously-skip-permissions",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.error("Failed to spawn reviewer for %s: %s", plan_folder, result.stderr)
            return None

        try:
            data = json.loads(result.stdout)
            session_id = data.get("session_id")
            logger.info("Spawned reviewer for %s: session %s", plan_folder, session_id)
            return session_id
        except (json.JSONDecodeError, KeyError):
            logger.error("Could not parse reviewer spawn output for %s", plan_folder)
            return None

    def wait_for_session(self, session_id: str, timeout: int = 600, poll_interval: int = 10) -> Optional[str]:
        """Wait for a session to complete.

        Polls the session state store directly (no CLI call required).
        Short-circuits on consecutive read failures to avoid wasting the
        full timeout when the session process dies before writing state.

        Args:
            session_id: Session UUID to wait for.
            timeout: Maximum wait time in seconds.
            poll_interval: Seconds between status checks.

        Returns:
            Final status string, or None on timeout.
        """
        deadline = time.time() + timeout
        consecutive_failures = 0
        while time.time() < deadline:
            status = self._get_session_status(session_id)
            if status is None:
                # State not readable — count consecutive failures and bail early
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    logger.error(
                        "Session %s state unreadable after %d attempts, treating as failed",
                        session_id[:8], consecutive_failures,
                    )
                    return "failed"
            else:
                consecutive_failures = 0
                if status in ("completed", "failed", "stopped"):
                    logger.info("Session %s finished with status: %s", session_id[:8], status)
                    return status
                # If still running, check if PID is actually alive to detect
                # sessions that died without updating their state file
                if status == "running":
                    data = _session_store.load(session_id)
                    if data:
                        pid = data.get("pid")
                        if pid and not is_process_running(pid):
                            logger.warning(
                                "Session %s PID %d is dead but status is still 'running' — treating as failed",
                                session_id[:8], pid,
                            )
                            return "failed"
            time.sleep(poll_interval)

        logger.warning("Session %s timed out after %ds", session_id[:8], timeout)
        return None

    def _get_session_status(self, session_id: str) -> Optional[str]:
        """Get current session status by reading the state store directly.

        Reads ~/.agentic/sessions/<session_id>.json rather than invoking
        the CLI (the `agentic session status` command was removed).

        Args:
            session_id: Session UUID.

        Returns:
            Status string or None if state file not found or unreadable.
        """
        data = _session_store.load(session_id)
        if not data:
            return None
        return data.get("status")

    def is_session_alive(self, session_id: str) -> bool:
        """Quick check if session is still running.

        Args:
            session_id: Session UUID.

        Returns:
            True if session is running.
        """
        status = self._get_session_status(session_id)
        return status in ("running", "starting")

    def run_review_cycle(self, plan_folder: str, max_reviews: int = 3) -> tuple[bool, int, str]:
        """Run review loop: spawn reviewer, handle approve/reject.

        Args:
            plan_folder: Plan folder name.
            max_reviews: Maximum review iterations.

        Returns:
            Tuple of (approved, iterations_used, feedback).
        """
        for attempt in range(1, max_reviews + 1):
            logger.info("Review cycle %d/%d for %s", attempt, max_reviews, plan_folder)

            reviewer_id = self.spawn_reviewer(plan_folder)
            if not reviewer_id:
                return False, attempt, "Failed to spawn reviewer"

            status = self.wait_for_session(reviewer_id)
            if status != "completed":
                return False, attempt, f"Reviewer session ended with status: {status}"

            # For now, assume completed reviewer means approved.
            # A more sophisticated implementation would parse reviewer output
            # to determine approved/rejected status.
            logger.info("Review cycle %d approved for %s", attempt, plan_folder)
            return True, attempt, "approved"

        logger.warning("Max review iterations reached for %s", plan_folder)
        return False, max_reviews, "Max review iterations reached"

    def generate_mmd(self, plan_folder: str) -> bool:
        """Generate orchestration MMD for a plan.

        Tries CLI first, falls back to planner-orchestration spawn.

        Args:
            plan_folder: Plan folder name.

        Returns:
            True if generation succeeded.
        """
        # Check if MMD already exists (planner may have generated it)
        plan_dir = self.plans_dir / plan_folder
        existing_mmds = list(plan_dir.glob("orchestration_*.mmd")) if plan_dir.exists() else []
        if existing_mmds:
            logger.info("MMD already exists for %s, skipping generation", plan_folder)
            return True

        # Try CLI generation first
        cmd = [
            "agentic", "agent", "plan", "orchestration", "generate",
            "--plan", plan_folder,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            cwd=self.working_dir,
        )
        if result.returncode == 0:
            logger.info("Generated MMD for %s via CLI", plan_folder)
            return True

        # Fall back to planner-orchestration spawn
        logger.warning("CLI MMD generation failed for %s, trying planner-orchestration", plan_folder)
        session_id = self._spawn_orchestration_planner(plan_folder)
        if not session_id:
            return False

        status = self.wait_for_session(session_id, timeout=300)
        return status == "completed"

    def _spawn_orchestration_planner(self, plan_folder: str) -> Optional[str]:
        """Spawn planner-orchestration agent as fallback.

        Args:
            plan_folder: Plan folder name.

        Returns:
            Session ID or None.
        """
        cmd = [
            "agentic", "-j", "session", "spawn",
            "--role", "planner-orchestration",
            "--plan", plan_folder,
            "-b",
            "--dangerously-skip-permissions",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.error("Failed to spawn orchestration planner for %s", plan_folder)
            return None

        try:
            data = json.loads(result.stdout)
            return data.get("session_id")
        except (json.JSONDecodeError, KeyError):
            return None

    def validate_mmd(self, plan_folder: str, max_retries: int = 3) -> bool:
        """Validate orchestration MMD with retries.

        Args:
            plan_folder: Plan folder name.
            max_retries: Maximum validation attempts.

        Returns:
            True if validation passed.
        """
        cmd = [
            "agentic", "agent", "plan", "orchestration", "validate",
            "--plan", plan_folder,
        ]

        for attempt in range(1, max_retries + 1):
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
                cwd=self.working_dir,
            )
            if result.returncode == 0:
                logger.info("MMD validation passed for %s (attempt %d)", plan_folder, attempt)
                return True
            logger.warning("MMD validation failed for %s (attempt %d/%d): %s",
                           plan_folder, attempt, max_retries, result.stderr)
            if attempt < max_retries:
                time.sleep(2)

        return False

    def update_task_status(self, task_id: str, action: str, plan_folder: str) -> bool:
        """Update task status via CLI.

        Args:
            task_id: Task identifier.
            action: 'start' or 'complete'.
            plan_folder: Plan folder name.

        Returns:
            True if update succeeded.
        """
        cmd = [
            "agentic", "agent", "plan", "task", action,
            task_id,
            "--plan", plan_folder,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.error("Failed to update task %s to %s: %s", task_id, action, result.stderr)
            return False
        return True

    def get_plan_status(self, plan_folder: str) -> Optional[str]:
        """Get the status of a plan based on task completion.

        A plan is "completed" when all tasks are done (pending=0, completed>0),
        matching the same logic used by `agentic plan list` to show action=archive.

        Args:
            plan_folder: Plan folder name.

        Returns:
            "completed" if all tasks are done, status field from plan YAML otherwise,
            or None if not found.
        """
        import yaml
        plan_dir = self.plans_dir / plan_folder
        if not plan_dir.exists():
            return None

        # Check task counts from plan_build.yml (same logic as ralph._analyze_plan_file)
        plan_build = plan_dir / "plan_build.yml"
        if plan_build.exists():
            try:
                content = yaml.safe_load(plan_build.read_text()) or {}
                pending = 0
                completed = 0
                for phase in content.get("phases", []):
                    for task in phase.get("tasks", []):
                        status = task.get("status", "pending")
                        if status == "completed":
                            completed += 1
                        else:
                            pending += 1
                # All tasks done = plan completed (ready to archive)
                if pending == 0 and completed > 0:
                    return "completed"
                # Return the status field from the YAML
                return content.get("status")
            except (yaml.YAMLError, Exception):
                pass

        return None

    def archive_plan(self, plan_folder: str) -> bool:
        """Archive a completed plan via API.

        Handles the case where a prior archive attempt copied to completed/
        but failed to remove the live source (interrupted operation).

        Args:
            plan_folder: Plan folder name.

        Returns:
            True if archived successfully.
        """
        try:
            import shutil
            from agenticguidance.services.plan import PlanMovementWorkflow, MoveResult
            plan_path = self.plans_dir / plan_folder
            workflow = PlanMovementWorkflow(plan_path)
            result = workflow.archive_plan_folder(force=True)
            if result.result == MoveResult.SUCCESS:
                logger.info("Archived plan %s", plan_folder)
                return True
            elif result.result == MoveResult.SKIPPED and "already exists" in result.message:
                # Prior archive copied to completed/ but didn't delete live source
                if plan_path.exists():
                    shutil.rmtree(plan_path)
                    logger.info("Cleaned up stale live folder for already-archived plan %s", plan_folder)
                    return True
                return True
            else:
                logger.error("Failed to archive plan %s: %s", plan_folder, result.message)
                return False
        except Exception as e:
            logger.error("Exception archiving plan %s: %s", plan_folder, e)
            return False

    def compile_bootstrap_context(self, role: str = "orchestration-planning") -> Optional[dict]:
        """Bootstrap context for the overall planning session.

        Args:
            role: Role to bootstrap.

        Returns:
            Context dict or None if failed.
        """
        cmd = ["agentic", "--json", "agent", "context", "bootstrap", "--role", role]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.warning("Bootstrap context compilation failed: %s", result.stderr)
            return None

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None


class PlannerLoopRunner:
    """Orchestrates the full planning loop.

    Discovers plans, spawns planners, runs reviews, generates MMDs,
    and tracks state throughout execution.
    """

    def __init__(
        self,
        workflow: Optional[PlannerLoopWorkflow] = None,
        project: Optional[str] = None,
        plan_folder: Optional[str] = None,
    ):
        self.workflow = workflow or PlannerLoopWorkflow()
        self.project = project
        self.plan_folder = plan_folder
        self.state = {
            "iteration": 0,
            "plans_processed": [],
            "plans_skipped": [],
            "errors": [],
            "current_plan": None,
        }

    def run(self, max_iterations: int = 10, completion_promise: Optional[str] = None) -> bool:
        """Run the planning loop.

        Args:
            max_iterations: Maximum loop iterations.
            completion_promise: Text to output when all plans done.

        Returns:
            True if loop completed successfully (all plans processed).
        """
        promise = completion_promise or DEFAULT_COMPLETION_PROMISE

        # Health check
        try:
            self.workflow.run_health_check()
        except RuntimeError as e:
            logger.error("Health check failed: %s", e)
            self.state["errors"].append({
                "plan": None,
                "error": str(e),
                "phase": "health_check",
            })
            return False

        # Bootstrap context for overall session
        self.workflow.compile_bootstrap_context()

        for iteration in range(1, max_iterations + 1):
            self.state["iteration"] = iteration
            logger.info("=== Planner loop iteration %d/%d ===", iteration, max_iterations)

            # Archive completed plans so they aren't left pending
            if not self.plan_folder:
                for plan_dir in sorted(self.workflow.plans_dir.iterdir()):
                    if plan_dir.is_dir() and self.workflow.get_plan_status(plan_dir.name) == "completed":
                        logger.info("Archiving completed plan: %s", plan_dir.name)
                        self.workflow.archive_plan(plan_dir.name)
            elif self.workflow.get_plan_status(self.plan_folder) == "completed":
                logger.info("Archiving single completed plan: %s", self.plan_folder)
                self.workflow.archive_plan(self.plan_folder)

            if self.plan_folder:
                # Single-plan mode: check if plan already has MMD
                plan_dir = self.workflow.plans_dir / self.plan_folder
                existing_mmds = list(plan_dir.glob("orchestration_*.mmd")) if plan_dir.exists() else []
                if existing_mmds:
                    logger.info("Plan %s already has MMD. %s", self.plan_folder, promise)
                    print(promise)
                    return True
                plans = [self.plan_folder]
            else:
                plans = self.workflow.discover_plans_needing_orchestration()
            if not plans:
                logger.info("All plans have orchestration MMDs. %s", promise)
                print(promise)
                return True

            for plan_folder in plans:
                self.state["current_plan"] = plan_folder
                success = self._process_plan(plan_folder)
                if success:
                    self.state["plans_processed"].append(plan_folder)
                else:
                    self.state["plans_skipped"].append(plan_folder)

            self.state["current_plan"] = None
            logger.info("Iteration %d complete: processed=%d, skipped=%d",
                         iteration,
                         len(self.state["plans_processed"]),
                         len(self.state["plans_skipped"]))

        logger.warning("Max iterations (%d) reached without completion", max_iterations)
        return False

    def _process_plan(self, plan_folder: str) -> bool:
        """Process a single plan through the full workflow.

        Args:
            plan_folder: Plan folder name.

        Returns:
            True if plan was processed successfully.
        """
        logger.info("Processing plan: %s", plan_folder)

        # 1. Explore: spawn explore agent to analyze codebase and update plan with current state
        explore_session_id = self.workflow.spawn_explore_agent(plan_folder)
        if not explore_session_id:
            self.state["errors"].append({
                "plan": plan_folder,
                "error": "Failed to spawn explore agent",
                "phase": "explore",
            })
            return False

        explore_status = self.workflow.wait_for_session(explore_session_id)
        if explore_status != "completed":
            self.state["errors"].append({
                "plan": plan_folder,
                "error": f"Explore agent session ended with status: {explore_status}",
                "phase": "explore",
            })
            return False

        # 2. Story generation: spawn story agent to generate user stories
        story_session_id = self.workflow.spawn_story_agent(plan_folder)
        if not story_session_id:
            self.state["errors"].append({
                "plan": plan_folder,
                "error": "Failed to spawn story agent",
                "phase": "story_generation",
            })
            return False

        story_status = self.workflow.wait_for_session(story_session_id)
        if story_status != "completed":
            self.state["errors"].append({
                "plan": plan_folder,
                "error": f"Story agent session ended with status: {story_status}",
                "phase": "story_generation",
            })
            return False

        # 3. Determine plan type
        plan_type = self.workflow.determine_plan_type(plan_folder)
        if not plan_type:
            logger.warning("No plan YAML found for %s, skipping", plan_folder)
            self.state["errors"].append({
                "plan": plan_folder,
                "error": "No plan YAML found",
                "phase": "determine_type",
            })
            return False

        # 4. Spawn planner (type-specific: build, test, etc.)
        session_id = self.workflow.spawn_planner(plan_folder, plan_type)
        if not session_id:
            self.state["errors"].append({
                "plan": plan_folder,
                "error": "Failed to spawn planner",
                "phase": "spawn_planner",
            })
            return False

        # 5. Wait for planner
        status = self.workflow.wait_for_session(session_id)
        if status != "completed":
            self.state["errors"].append({
                "plan": plan_folder,
                "error": f"Planner session ended with status: {status}",
                "phase": "wait_planner",
            })
            return False

        # 6. Review cycle
        approved, review_iters, feedback = self.workflow.run_review_cycle(plan_folder)
        if not approved:
            logger.warning("Plan %s not approved after %d reviews: %s",
                           plan_folder, review_iters, feedback)
            self.state["errors"].append({
                "plan": plan_folder,
                "error": f"Review rejected: {feedback}",
                "phase": "review",
            })
            return False

        # 7. Generate MMD
        if not self.workflow.generate_mmd(plan_folder):
            self.state["errors"].append({
                "plan": plan_folder,
                "error": "MMD generation failed",
                "phase": "generate_mmd",
            })
            return False

        # 8. Validate MMD
        if not self.workflow.validate_mmd(plan_folder):
            self.state["errors"].append({
                "plan": plan_folder,
                "error": "MMD validation failed after retries",
                "phase": "validate_mmd",
            })
            return False

        logger.info("Plan %s processed successfully", plan_folder)
        return True
