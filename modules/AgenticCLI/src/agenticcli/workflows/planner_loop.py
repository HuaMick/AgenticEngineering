"""Planner Loop workflow for automated orchestration planning.

Encapsulates the orchestration planner logic: discovers plans needing
orchestration MMDs, spawns specialized planners, runs review loops,
generates and validates MMD files, and updates task status.

Uses the Claude Agent SDK (when available) for direct agent invocation,
falling back to subprocess spawning when the SDK is not installed.
"""

import json
import logging
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from agenticcli.utils.sdk_runner import (
    SDK_AVAILABLE,
    SessionResult,
    get_allowed_tools_for_role,
    run_agent_sync,
)
from agenticcli.utils.state_store import StateStore, is_process_running
from agenticcli.utils.subprocess_utils import get_clean_env

logger = logging.getLogger(__name__)

# Shared session state store (same as session.py)
_session_store = StateStore("sessions", id_key="session_id")

# Keywords in plan context that indicate SDK-related work
SDK_CONTEXT_KEYWORDS = [
    "claude-agent-sdk",
    "sdk migration",
    "subprocess replacement",
    "session spawn",
    "query()",
    "async iterator",
]

# Plan type to planner agent mapping
PLAN_TYPE_TO_PLANNER = {
    "build": "planner-build",
    "test": "planner-test",
    "guidance": "planner-guidance",
    "cleaning": "planner-cleaning",
    "guidance-testing": "planner-guidance-testing",
    "sdk": "planner-sdk",
}

DEFAULT_COMPLETION_PROMISE = "Planning complete. All plans have orchestration MMDs."

# Timeout budgets by agent role (seconds).  These are passed to run_agent_sync()
# so the SDK enforces a hard ceiling on each individual agent invocation.
ROLE_TIMEOUT_SECONDS: dict[str, int] = {
    "explore": 600,               # 10 min — lightweight codebase analysis
    "story-generator": 1800,       # 30 min — story generation
    "planner-build": 1800,         # 30 min
    "planner-test": 1800,          # 30 min
    "planner-guidance": 1800,      # 30 min
    "planner-cleaning": 1800,      # 30 min
    "planner-guidance-testing": 1800,
    "planner-sdk": 1800,           # 30 min
    "planner-reviewer": 1800,      # 30 min
    "planner-orchestration": 3600, # 60 min — orchestration MMD generation
}


def _build_agent_prompt(role: str, plan_folder: str, plans_dir: Path) -> str:
    """Build a prompt for an agent with role and plan context.

    Args:
        role: Agent role identifier.
        plan_folder: Plan folder name.
        plans_dir: Path to the plans directory.

    Returns:
        Prompt string for the agent.
    """
    parts = [
        f"You are being spawned as a {role} agent.",
        f"Initialize your context by running: agentic -j agent context bootstrap --role {role}",
        f"Your active plan is: {plan_folder}",
        f"Plan path: {plans_dir / plan_folder}",
        f"List tasks with: agentic -j agent plan task list --plan {plan_folder}",
        "Start by loading your bootstrap context, then work through the plan tasks.",
    ]
    return "\n".join(parts)


def _build_sdk_options(working_dir: str, role: str | None = None) -> object:
    """Build ClaudeAgentOptions for SDK agent runs.

    When a role is provided and has an entry in ROLE_TOOL_ALLOWLIST, the
    allowed_tools list is passed to ClaudeAgentOptions to restrict what the
    agent can invoke. Unknown roles default to all tools (no restriction).

    Args:
        working_dir: Working directory for the agent.
        role: Optional agent role identifier used to look up tool restrictions.

    Returns:
        ClaudeAgentOptions instance, or None if SDK unavailable.
    """
    if not SDK_AVAILABLE:
        return None

    from claude_agent_sdk import ClaudeAgentOptions

    allowed_tools = get_allowed_tools_for_role(role) if role else None

    if allowed_tools is not None:
        return ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            cwd=working_dir,
            allowed_tools=allowed_tools,
        )
    else:
        return ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            cwd=working_dir,
        )


class PlannerLoopWorkflow:
    """Core workflow methods for the planner loop.

    Uses the SDK for direct agent invocation when available,
    falling back to subprocess spawning otherwise.
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

        If the plan type is "build", checks the plan context for SDK-related
        keywords and returns "sdk" instead when detected.

        Args:
            plan_folder: Plan folder name.

        Returns:
            Plan type string (build, test, sdk, etc.) or None if not found.
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
                    # If type is "build", check if SDK routing applies
                    if plan_type == "build" and self.detect_sdk_objective(plan_folder):
                        logger.info("Plan %s detected as SDK-related, routing to planner-sdk", plan_folder)
                        return "sdk"
                    return plan_type

        return None

    def detect_sdk_objective(self, plan_folder: str) -> bool:
        """Detect if a plan's objective is SDK-related by checking its context.

        Reads plan_build.yml and checks the context field for SDK-related
        keywords. This enables automatic routing to planner-sdk for plans
        that describe SDK migration or integration work.

        Args:
            plan_folder: Plan folder name.

        Returns:
            True if the plan context contains SDK-related keywords.
        """
        import yaml

        plan_build = self.plans_dir / plan_folder / "plan_build.yml"
        if not plan_build.exists():
            return False

        try:
            content = yaml.safe_load(plan_build.read_text()) or {}
        except Exception:
            logger.debug("Could not parse %s for SDK detection", plan_build)
            return False

        context = content.get("context", "")
        if not isinstance(context, str):
            return False

        context_lower = context.lower()
        for keyword in SDK_CONTEXT_KEYWORDS:
            if keyword.lower() in context_lower:
                logger.debug("SDK keyword '%s' found in %s context", keyword, plan_folder)
                return True

        return False

    # ── SDK-first agent execution ──────────────────────────────────────

    def _run_role_agent(self, role: str, plan_folder: str) -> SessionResult:
        """Run an agent with the given role via the SDK.

        Builds the prompt and options, invokes run_agent_sync(), and
        writes session state for observability.

        Falls back to subprocess spawn + wait when SDK is unavailable.

        Args:
            role: Agent role identifier.
            plan_folder: Plan folder name.

        Returns:
            SessionResult with status and metadata.
        """
        session_id = str(uuid.uuid4())
        prompt = _build_agent_prompt(role, plan_folder, self.plans_dir)

        if SDK_AVAILABLE:
            return self._run_via_sdk(session_id, role, plan_folder, prompt)
        else:
            return self._run_via_subprocess(session_id, role, plan_folder)

    def _run_via_sdk(
        self,
        session_id: str,
        role: str,
        plan_folder: str,
        prompt: str,
        max_retries: int = 3,
    ) -> SessionResult:
        """Execute an agent via the SDK and record session state.

        Retries failed SDK calls up to max_retries times with exponential
        backoff (2s, 4s between attempts). Each retry is logged at INFO level.
        KeyboardInterrupt is never retried.

        Args:
            session_id: Pre-generated session ID for state tracking.
            role: Agent role identifier.
            plan_folder: Plan folder name.
            prompt: Compiled prompt for the agent.
            max_retries: Maximum number of attempts (default: 3).

        Returns:
            SessionResult from the SDK run (last attempt result on exhaustion).
        """
        options = _build_sdk_options(self.working_dir, role=role)
        timeout = ROLE_TIMEOUT_SECONDS.get(role, 1800)

        # Record session start for observability
        session_data = {
            "session_id": session_id,
            "pid": None,
            "prompt": prompt[:500],
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "background": False,
            "working_dir": self.working_dir,
            "role": role,
            "plan_folder": plan_folder,
            "transport": "sdk",
        }
        _session_store.save(session_data)
        logger.info(
            "Running %s agent for %s via SDK (session %s, timeout=%ds)",
            role, plan_folder, session_id[:8], timeout,
        )

        result: SessionResult = SessionResult(status="failed", result="No attempt made")
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                backoff = 2 ** (attempt - 1)  # 2s, 4s, 8s, ...
                logger.info(
                    "Retrying SDK agent (attempt %d/%d): %s — waiting %ds",
                    attempt, max_retries, result.result[:100], backoff,
                )
                time.sleep(backoff)

            try:
                result = run_agent_sync(prompt, options, timeout_seconds=timeout)
            except KeyboardInterrupt:
                logger.info("SDK agent run cancelled by user (KeyboardInterrupt)")
                raise

            if result.status == "completed":
                break

            logger.info(
                "SDK agent attempt %d/%d failed for %s/%s: %s",
                attempt, max_retries, role, plan_folder, result.result[:100],
            )

        # Update session state with SDK-determined status
        session_data["status"] = result.status
        session_data["ended_at"] = datetime.now().isoformat()
        session_data["cost_usd"] = result.cost_usd
        session_data["duration_ms"] = result.duration_ms
        session_data["sdk_session_id"] = result.session_id
        _session_store.save(session_data)

        logger.info(
            "%s agent for %s finished: status=%s, cost=$%.4f, duration=%dms",
            role, plan_folder, result.status, result.cost_usd, result.duration_ms,
        )
        return result

    def _run_via_subprocess(
        self, session_id: str, role: str, plan_folder: str,
    ) -> SessionResult:
        """Fallback: spawn an agent via subprocess and wait for completion.

        Args:
            session_id: Pre-generated session ID (unused in subprocess path,
                        actual session ID comes from CLI output).
            role: Agent role identifier.
            plan_folder: Plan folder name.

        Returns:
            SessionResult synthesized from subprocess outcome.
        """
        cmd = [
            "agentic", "-j", "session", "spawn",
            "--role", role,
            "--plan", plan_folder,
            "-b",
            "--dangerously-skip-permissions",
        ]

        spawn_result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if spawn_result.returncode != 0:
            logger.error("Failed to spawn %s agent for %s: %s", role, plan_folder, spawn_result.stderr)
            return SessionResult(
                status="failed",
                result=f"Spawn failed: {spawn_result.stderr}",
                is_error=True,
            )

        try:
            data = json.loads(spawn_result.stdout)
            spawned_session_id = data.get("session_id", session_id)
        except (json.JSONDecodeError, KeyError):
            logger.error("Could not parse spawn output for %s/%s", role, plan_folder)
            return SessionResult(
                status="failed",
                result="Could not parse spawn output",
                is_error=True,
            )

        logger.info("Spawned %s for %s via subprocess: session %s", role, plan_folder, spawned_session_id[:8])

        # Wait for subprocess session to complete
        final_status = self.wait_for_session(spawned_session_id)
        return SessionResult(
            status=final_status or "failed",
            result=f"Subprocess session {spawned_session_id[:8]} ended with status: {final_status}",
            session_id=spawned_session_id,
            is_error=(final_status != "completed"),
        )

    # ── Public spawn methods (now delegates to _run_role_agent) ────────

    def spawn_explore_agent(self, plan_folder: str) -> SessionResult:
        """Run an explore agent to analyze the codebase and update the plan YAML.

        Args:
            plan_folder: Plan folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("explore", plan_folder)

    def spawn_story_agent(self, plan_folder: str) -> SessionResult:
        """Run a story-generator agent for user story generation.

        Args:
            plan_folder: Plan folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("story-generator", plan_folder)

    def spawn_planner(self, plan_folder: str, plan_type: str) -> SessionResult:
        """Run appropriate planner agent for a plan.

        Args:
            plan_folder: Plan folder name.
            plan_type: Plan type (build, test, etc.).

        Returns:
            SessionResult with completion status.
        """
        planner_role = PLAN_TYPE_TO_PLANNER.get(plan_type, "planner-build")
        return self._run_role_agent(planner_role, plan_folder)

    def spawn_reviewer(self, plan_folder: str) -> SessionResult:
        """Run planner-reviewer agent for a plan.

        Args:
            plan_folder: Plan folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("planner-reviewer", plan_folder)

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

    def wait_for_session(self, session_id: str, timeout: int = 600, poll_interval: int = 10) -> Optional[str]:
        """Wait for a subprocess session to complete.

        Polls the session state store directly (no CLI call required).
        Short-circuits on consecutive read failures to avoid wasting the
        full timeout when the session process dies before writing state.

        Note: This method is only used in the subprocess fallback path.
        SDK sessions complete synchronously and don't need polling.

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
                # sessions that died without updating their state file.
                if status == "running":
                    data = _session_store.load(session_id)
                    if data:
                        pid = data.get("pid")
                        if pid and not is_process_running(pid):
                            exit_code = data.get("exit_code")
                            if exit_code is not None and exit_code != 0:
                                final_status = "failed"
                            else:
                                final_status = "completed"
                            logger.info(
                                "Session %s PID %d dead, status='running' -> resolving as '%s' (exit_code=%s)",
                                session_id[:8], pid, final_status, exit_code,
                            )
                            data["status"] = final_status
                            data["ended_at"] = datetime.now().isoformat()
                            _session_store.save(data)
                            return final_status
            time.sleep(poll_interval)

        logger.warning("Session %s timed out after %ds", session_id[:8], timeout)
        return None

    def _get_session_status(self, session_id: str) -> Optional[str]:
        """Get current session status by reading the state store directly.

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
        """Run review loop: run reviewer agent, handle approve/reject.

        Args:
            plan_folder: Plan folder name.
            max_reviews: Maximum review iterations.

        Returns:
            Tuple of (approved, iterations_used, feedback).
        """
        for attempt in range(1, max_reviews + 1):
            logger.info("Review cycle %d/%d for %s", attempt, max_reviews, plan_folder)

            result = self.spawn_reviewer(plan_folder)
            if result.status != "completed":
                return False, attempt, f"Reviewer session ended with status: {result.status}"

            logger.info("Review cycle %d approved for %s", attempt, plan_folder)
            return True, attempt, "approved"

        logger.warning("Max review iterations reached for %s", plan_folder)
        return False, max_reviews, "Max review iterations reached"

    def generate_mmd(self, plan_folder: str) -> bool:
        """Generate orchestration MMD for a plan.

        Tries CLI first, falls back to planner-orchestration agent.

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

        # Fall back to planner-orchestration agent
        logger.warning("CLI MMD generation failed for %s, trying planner-orchestration", plan_folder)
        agent_result = self._run_role_agent("planner-orchestration", plan_folder)
        return agent_result.status == "completed"

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
        """Get the status of a plan.

        The YAML ``status:`` field takes priority.  Task-completion counting is
        used only as a fallback when the YAML status is absent or already set to
        ``"completed"``.  This prevents a fully-tasked-out plan that still has
        ``status: active`` from being prematurely archived.

        Priority order:
        1. If the YAML ``status:`` field is present and is NOT ``"completed"``,
           return it as-is (e.g. ``"active"`` is respected).
        2. If the YAML ``status:`` field is ``"completed"``, or is absent, fall
           back to task-counting: return ``"completed"`` when all tasks are done
           (pending == 0 and completed > 0).
        3. If task counts are inconclusive, return whatever the YAML says (may
           be ``None`` when the field is absent).

        Args:
            plan_folder: Plan folder name.

        Returns:
            The resolved status string, or None if not found.
        """
        import yaml
        plan_dir = self.plans_dir / plan_folder
        if not plan_dir.exists():
            return None

        plan_build = plan_dir / "plan_build.yml"
        if plan_build.exists():
            try:
                content = yaml.safe_load(plan_build.read_text()) or {}
                yaml_status = content.get("status")

                # If the YAML explicitly declares a non-completed status, honour it
                # and skip task-counting entirely.
                if yaml_status is not None and yaml_status != "completed":
                    return yaml_status

                # YAML status is absent or already "completed" – use task counting
                # as a secondary signal to detect completion.
                pending = 0
                completed = 0
                for phase in content.get("phases", []):
                    for task in phase.get("tasks", []):
                        status = task.get("status", "pending")
                        if status == "completed":
                            completed += 1
                        else:
                            pending += 1

                if pending == 0 and completed > 0:
                    return "completed"

                # Task counts are inconclusive – fall back to whatever YAML says.
                return yaml_status
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

    def _validate_result(self, result: SessionResult, role_name: str) -> None:
        """Validate a SessionResult and log suspicious outcomes.

        Logs a WARNING when the result looks suspicious (empty text or zero
        duration) but does NOT reject it — the retry logic in _run_via_sdk()
        already handles actual failures. This method is purely for observability.

        Args:
            result: The SessionResult to validate.
            role_name: Human-readable role label for log messages.
        """
        # Always log a result summary at INFO level
        logger.info(
            "Agent %s completed in %dms, %d chars output",
            role_name, result.duration_ms, len(result.result),
        )

        # Warn on suspicious results
        if not result.result.strip():
            logger.warning(
                "Agent %s returned empty output (suspicious result)",
                role_name,
            )
        if result.duration_ms == 0:
            logger.warning(
                "Agent %s reported zero duration (suspicious result — "
                "may indicate a mocked or stalled run)",
                role_name,
            )

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

        Uses SDK-first agent execution — no spawn+wait pattern needed.
        Each agent call blocks until completion and returns a SessionResult.

        Args:
            plan_folder: Plan folder name.

        Returns:
            True if plan was processed successfully.
        """
        logger.info("Processing plan: %s", plan_folder)

        # 1. Explore: run explore agent to analyze codebase
        explore_result = self.workflow.spawn_explore_agent(plan_folder)
        self.workflow._validate_result(explore_result, "explore")
        if explore_result.status != "completed":
            self.state["errors"].append({
                "plan": plan_folder,
                "error": f"Explore agent failed: {explore_result.result[:200]}",
                "phase": "explore",
            })
            return False

        # 2. Story generation: run story agent
        story_result = self.workflow.spawn_story_agent(plan_folder)
        self.workflow._validate_result(story_result, "story-generator")
        if story_result.status != "completed":
            self.state["errors"].append({
                "plan": plan_folder,
                "error": f"Story agent failed: {story_result.result[:200]}",
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

        # 4. Run planner (type-specific: build, test, etc.)
        planner_result = self.workflow.spawn_planner(plan_folder, plan_type)
        self.workflow._validate_result(planner_result, f"planner-{plan_type}")
        if planner_result.status != "completed":
            self.state["errors"].append({
                "plan": plan_folder,
                "error": f"Planner failed: {planner_result.result[:200]}",
                "phase": "planner",
            })
            return False

        # 5. Review cycle
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

        # 6. Generate MMD
        if not self.workflow.generate_mmd(plan_folder):
            self.state["errors"].append({
                "plan": plan_folder,
                "error": "MMD generation failed",
                "phase": "generate_mmd",
            })
            return False

        # 7. Validate MMD
        if not self.workflow.validate_mmd(plan_folder):
            self.state["errors"].append({
                "plan": plan_folder,
                "error": "MMD validation failed after retries",
                "phase": "validate_mmd",
            })
            return False

        logger.info("Plan %s processed successfully", plan_folder)
        return True
