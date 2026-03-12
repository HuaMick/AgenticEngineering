"""Planner Loop workflow for automated orchestration planning.

Encapsulates the orchestration planner logic: discovers epics needing
planning (no phases in TinyDB), spawns specialized planners, runs review
loops, and updates task status.

Uses the Claude Agent SDK (when available) for direct agent invocation,
falling back to subprocess spawning when the SDK is not installed.
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from agenticcli.utils.context_file import write_context_file
from agenticcli.utils.session_id import generate_session_id
from agenticcli.utils.retry import exponential_backoff
from agenticcli.utils.sdk_runner import (
    SDK_AVAILABLE,
    SessionResult,
    get_allowed_tools_for_role,
    run_agent_sync,
    ROLE_TIMEOUT_SECONDS,
    get_timeout_for_role,
)
from agenticcli.utils.session_state import read_sdk_metrics
from agenticcli.utils.spawn_command import build_spawn_command
from agenticcli.utils.state_store import StateStore, is_process_running
from agenticcli.utils.subprocess_utils import get_clean_env

logger = logging.getLogger(__name__)

# Shared session state store (same as session.py)
_session_store = StateStore("sessions", id_key="session_id")

DEFAULT_COMPLETION_PROMISE = "Planning complete. All epics have phases in TinyDB."

# Timeout budgets by agent role (seconds) are imported from sdk_runner.
# ROLE_TIMEOUT_SECONDS and get_timeout_for_role are re-exported for callers
# that import them directly from this module.


# Roles that participate in the planning phase — these agents must NEVER
# implement code, write tests, or modify source files.  They only create,
# update, or review tickets/phases/stories/architecture docs.
_PLANNING_PHASE_ROLES = frozenset({
    "epic-creator",
    "planner-explore",
    "explore",
    "story-generator",
    "planner-design",
    "planner-build",
    "planner-test",
    "planner-guidance",
    "planner-cleaning",
    "planner-audit",
    "planner-reviewer",
    "planner-orchestration",
    "planner-sdk",
    "planner-guidance-testing",
})


def _build_agent_prompt(role: str, epic_folder: str, extra_prompt: Optional[str] = None) -> str:
    """Build a prompt for an agent with role and epic context.

    Args:
        role: Agent role identifier.
        epic_folder: Epic folder name (ID), not a filesystem path.
        extra_prompt: Optional additional instructions appended to the prompt.

    Returns:
        Prompt string for the agent.
    """
    parts = [
        f"You are being spawned as a {role} agent.",
        f"Initialize your context by running: agentic -j agent context bootstrap --role {role} --epic {epic_folder}",
        f"Your active epic is: {epic_folder}",
        f"List tickets with: agentic -j epic ticket list --epic {epic_folder}",
    ]

    if role == "epic-creator":
        parts.insert(1, "FIRST: Run 'agentic --help' to learn all available CLI commands.")
        parts.insert(2, "Then run 'agentic epic --help' and 'agentic epic ticket --help' to learn ticket management.")

    if role in _PLANNING_PHASE_ROLES:
        parts.append(
            "IMPORTANT: This is a PLANNING-ONLY session. You must NOT implement code, "
            "write tests, or modify source files. Your job is to create, update, or "
            "review tickets, phases, stories, and architecture documents ONLY. "
            "Read source files for context but do not edit them."
        )
        parts.append(
            "All work products are managed through the epic/ticket system. "
            "Use `agentic epic ticket list` to see current tickets. "
            "Use `agentic epic ticket update` to modify tickets. "
            "Never create files directly — use CLI commands."
        )
        parts.append("Start by loading your bootstrap context, then plan the epic tasks.")
    else:
        parts.append("Start by loading your bootstrap context, then work through the epic tasks.")

    if extra_prompt:
        parts.append("")
        parts.append(f"Additional instructions from the operator:\n{extra_prompt}")
    return "\n".join(parts)


def _build_sdk_options(working_dir: str, role: str | None = None) -> object:
    """Build ClaudeAgentOptions for SDK agent runs.

    When a role is provided and has an entry in ROLE_TOOL_ALLOWLIST, the
    allowed_tools list is passed to ClaudeAgentOptions to restrict what the
    agent can invoke. Unknown roles default to all tools (no restriction).

    Passes a clean environment (CLAUDECODE vars stripped) so spawned agents
    don't trigger the nested-session guard.

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
    clean_env = get_clean_env()

    if allowed_tools is not None:
        return ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            cwd=working_dir,
            allowed_tools=allowed_tools,
            env=clean_env,
        )
    else:
        return ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            cwd=working_dir,
            env=clean_env,
        )


class PlannerLoopWorkflow:
    """Core workflow methods for the planner loop.

    Uses the SDK for direct agent invocation when available,
    falling back to subprocess spawning otherwise.
    """

    def __init__(self, epics_dir: Optional[Path] = None, working_dir: Optional[str] = None, prompt: Optional[str] = None):
        self.epics_dir = epics_dir or Path.cwd() / "docs" / "epics" / "live"
        self.working_dir = working_dir or str(Path.cwd())
        self.prompt = prompt

        # Initialize EpicRepository for TinyDB-based lookups
        self._repository = None
        try:
            from agenticguidance.services.epic_repository import EpicRepository

            repo_root = self.epics_dir
            while repo_root != repo_root.parent:
                if (repo_root / ".git").exists():
                    break
                repo_root = repo_root.parent
            db_path = repo_root / ".agentic" / "epics.db"
            self._repository = EpicRepository(db_path=db_path)
        except Exception:
            logger.warning("Failed to initialize EpicRepository for PlannerLoopWorkflow")

    def _get_repository(self):
        """Get EpicRepository instance.

        Returns:
            EpicRepository instance, or None if not available.
        """
        return self._repository

    def run_health_check(self) -> None:
        """Run health check: agentic --version && agentic epic list.

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
            ["agentic", "epic", "list"],
            capture_output=True, text=True, timeout=30,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Health check failed: agentic epic list returned {result.returncode}")

        logger.info("Health check passed")

    def discover_plans_needing_orchestration(self) -> list[str]:
        """Find live epics that need planning.

        An epic needs orchestration when:
        - It has no phases in TinyDB, OR
        - Not all phases have an agent routing set, OR
        - All phases are still in 'proposed' status (skeleton created but
          real planning hasn't happened yet).

        Returns:
            List of epic folder names needing orchestration.
        """
        if self._repository is None:
            logger.error("No EpicRepository available — cannot discover epics needing orchestration")
            return []

        epics = self._repository.list_epics(status="live")

        needs_work = []
        for epic in epics:
            phases = self._repository.list_phases(epic.epic_folder_name)
            if not phases or not all(p.agent for p in phases):
                needs_work.append(epic.epic_folder_name)
            else:
                # Phases are routed — check if all tickets are still "proposed".
                # "proposed" = skeleton only (pre-planning); "pending" = planning completed.
                # Planning promotes proposed→pending on success, so only proposed triggers re-plan.
                epic_data = self._repository.get_epic(epic.epic_folder_name)
                tickets = epic_data.tasks if epic_data else []
                if tickets and all(t.status == "proposed" for t in tickets):
                    logger.info(
                        "Epic %s has routed phases but all %d tickets are 'proposed' — needs planning",
                        epic.epic_folder_name, len(tickets),
                    )
                    needs_work.append(epic.epic_folder_name)

        logger.info("Found %d epics needing orchestration: %s", len(needs_work), needs_work)
        return needs_work

    # ── Deprecated: determine_plan_type removed ─────────────────────
    # Epic-creator-first architecture eliminates the need for plan type
    # routing. The epic-creator agent scaffolds ALL phases and tickets
    # in one pass. See _process_plan() for the new flow.
    # ── SDK-first agent execution ──────────────────────────────────────

    def _run_role_agent(self, role: str, epic_folder: str) -> SessionResult:
        """Run an agent with the given role via the SDK.

        Builds the prompt and options, invokes run_agent_sync(), and
        writes session state for observability.

        Falls back to subprocess spawn + wait when SDK is unavailable.

        Args:
            role: Agent role identifier.
            epic_folder: Epic folder name.

        Returns:
            SessionResult with status and metadata.
        """
        session_id = generate_session_id()
        prompt = _build_agent_prompt(role, epic_folder, extra_prompt=self.prompt)

        # This function intentionally does NOT use determine_transport() from
        # agenticcli.utils.transport — it has special AGENTIC_FORCE_SDK_DIRECT
        # override logic and SDK-direct fallbacks that differ from the standard
        # priority order (sdk-tmux > tmux > subprocess).
        import shutil
        force_sdk_direct = os.environ.get("AGENTIC_FORCE_SDK_DIRECT") == "1"

        if force_sdk_direct and SDK_AVAILABLE:
            logger.warning("Using SDK-direct path (AGENTIC_FORCE_SDK_DIRECT=1) — zombie bug risk")
            return self._run_via_sdk(session_id, role, epic_folder, prompt)
        elif SDK_AVAILABLE and shutil.which("tmux"):
            return self._run_via_tmux_sdk(session_id, role, epic_folder, prompt)
        elif SDK_AVAILABLE:
            logger.warning("tmux not available, falling back to SDK-direct (zombie bug risk)")
            return self._run_via_sdk(session_id, role, epic_folder, prompt)
        else:
            return self._run_via_subprocess(session_id, role, epic_folder)

    def _run_via_sdk(
        self,
        session_id: str,
        role: str,
        epic_folder: str,
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
            epic_folder: Epic folder name.
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
            "epic_folder": epic_folder,
            "transport": "sdk",
        }
        _session_store.save(session_data)
        logger.info(
            "Running %s agent for %s via SDK (session %s, timeout=%ds)",
            role, epic_folder, session_id[:8], timeout,
        )

        result: SessionResult = SessionResult(status="failed", result="No attempt made")
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                backoff = exponential_backoff(attempt - 1)  # 2s, 4s, 8s, ...
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
                attempt, max_retries, role, epic_folder, result.result[:100],
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
            role, epic_folder, result.status, result.cost_usd, result.duration_ms,
        )
        return result

    def _run_via_tmux_sdk(
        self,
        session_id: str,
        role: str,
        epic_folder: str,
        prompt: str,
        max_retries: int = 3,
    ) -> SessionResult:
        """Execute an agent via SDK-in-tmux for process isolation.

        Spawns the agent in a tmux pane running sdk_pane_runner.py, which
        calls query() exactly once (fresh process, no zombie issue).

        Retries failed runs up to max_retries times with exponential backoff.

        Args:
            session_id: Pre-generated session ID for state tracking.
            role: Agent role identifier.
            epic_folder: Epic folder name.
            prompt: Compiled prompt for the agent.
            max_retries: Maximum number of attempts (default: 3).

        Returns:
            SessionResult from the pane runner (last attempt result on exhaustion).
        """
        timeout = get_timeout_for_role(role)

        # Write context file for the pane runner
        write_context_file(session_id, prompt)

        # Record session start
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
            "epic_folder": epic_folder,
            "transport": "sdk-tmux",
        }

        logger.info(
            "Running %s agent for %s via sdk-tmux (session %s, timeout=%ds)",
            role, epic_folder, session_id[:8], timeout,
        )

        result = SessionResult(status="failed", result="No attempt made")
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                backoff = exponential_backoff(attempt - 1)
                logger.info(
                    "Retrying sdk-tmux agent (attempt %d/%d): %s — waiting %ds",
                    attempt, max_retries, result.result[:100], backoff,
                )
                time.sleep(backoff)
                # New session_id for retry (new tmux pane)
                session_id = generate_session_id()
                write_context_file(session_id, prompt)
                session_data["session_id"] = session_id
                session_data["status"] = "running"
                session_data["started_at"] = datetime.now().isoformat()

            # Spawn via CLI (routes to sdk-tmux path)
            spawn_cmd = build_spawn_command(
                role=role,
                epic_folder=epic_folder,
                skip_permissions=True,
            )

            try:
                spawn_result = subprocess.run(
                    spawn_cmd, capture_output=True, text=True, timeout=60,
                    cwd=self.working_dir,
                )
            except subprocess.TimeoutExpired:
                logger.error("Spawn timed out for %s/%s", role, epic_folder)
                result = SessionResult(
                    status="failed", result="Spawn command timed out", is_error=True,
                )
                continue
            except KeyboardInterrupt:
                logger.info("SDK-tmux agent run cancelled by user")
                raise

            if spawn_result.returncode != 0:
                logger.error("Spawn failed for %s/%s: %s", role, epic_folder, spawn_result.stderr)
                result = SessionResult(
                    status="failed", result=f"Spawn failed: {spawn_result.stderr}", is_error=True,
                )
                continue

            try:
                data = json.loads(spawn_result.stdout)
                spawned_session_id = data.get("session_id", session_id)
            except (json.JSONDecodeError, KeyError):
                logger.error("Could not parse spawn output for %s/%s", role, epic_folder)
                result = SessionResult(
                    status="failed", result="Could not parse spawn output", is_error=True,
                )
                continue

            # Merge planner-loop metadata into the session record written
            # by the spawn command.  The spawn command's record has critical
            # fields (pid, tmux_session) that wait_for_session needs — we
            # must NOT overwrite them.
            existing = _session_store.load(spawned_session_id) or {}
            existing.update({
                "epic_folder": epic_folder,
                "role": role,
                "prompt": session_data.get("prompt", "")[:500],
                "transport": "sdk-tmux",
            })
            _session_store.save(existing)

            logger.info(
                "Spawned %s for %s via sdk-tmux: session %s",
                role, epic_folder, spawned_session_id[:8],
            )

            # Wait for completion
            start_wait = time.monotonic()
            final_status = self.wait_for_session(spawned_session_id, timeout=timeout)
            elapsed = time.monotonic() - start_wait

            # Quick-exit detection (< 30s)
            if elapsed < 30 and final_status != "completed":
                logger.warning(
                    "Quick exit detected for %s/%s (%.1fs) — may be retryable",
                    role, epic_folder, elapsed,
                )

            # Read SDK metrics from session state
            sdk_metrics = read_sdk_metrics(spawned_session_id)

            result = SessionResult(
                status=final_status or "failed",
                result=f"sdk-tmux session {spawned_session_id[:8]} ended: {final_status}",
                cost_usd=sdk_metrics["cost_usd"],
                duration_ms=sdk_metrics["duration_ms"],
                session_id=sdk_metrics["sdk_session_id"] or spawned_session_id,
                num_turns=sdk_metrics["num_turns"],
                usage=sdk_metrics["usage"],
                is_error=(final_status != "completed"),
            )

            if result.status == "completed":
                break

            # Kill orphaned tmux session on failure to prevent collision on retry
            if result.status != "completed":
                from agenticcli.utils.session_id import tmux_session_name
                from agenticcli.utils.tmux import kill_session
                tmux_name = tmux_session_name(spawned_session_id, epic_folder=epic_folder, role=role)
                if kill_session(tmux_name):
                    logger.info("Killed orphaned tmux session %s", tmux_name)

            logger.info(
                "sdk-tmux attempt %d/%d failed for %s/%s: %s",
                attempt, max_retries, role, epic_folder, result.result[:100],
            )

        # Update session state with final result (merge, don't overwrite)
        final_state = _session_store.load(spawned_session_id) or {}
        final_state.update({
            "status": result.status,
            "ended_at": datetime.now().isoformat(),
            "cost_usd": result.cost_usd,
            "duration_ms": result.duration_ms,
            "sdk_session_id": result.session_id,
        })
        _session_store.save(final_state)

        logger.info(
            "%s agent for %s finished via sdk-tmux: status=%s, cost=$%.4f, duration=%dms",
            role, epic_folder, result.status, result.cost_usd, result.duration_ms,
        )
        return result

    def _run_via_subprocess(
        self, session_id: str, role: str, epic_folder: str,
    ) -> SessionResult:
        """Fallback: spawn an agent via subprocess and wait for completion.

        Args:
            session_id: Pre-generated session ID (unused in subprocess path,
                        actual session ID comes from CLI output).
            role: Agent role identifier.
            epic_folder: Epic folder name.

        Returns:
            SessionResult synthesized from subprocess outcome.
        """
        cmd = build_spawn_command(
            role=role,
            epic_folder=epic_folder,
            skip_permissions=True,
        )

        spawn_result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
            cwd=self.working_dir,
        )
        if spawn_result.returncode != 0:
            logger.error("Failed to spawn %s agent for %s: %s", role, epic_folder, spawn_result.stderr)
            return SessionResult(
                status="failed",
                result=f"Spawn failed: {spawn_result.stderr}",
                is_error=True,
            )

        try:
            data = json.loads(spawn_result.stdout)
            spawned_session_id = data.get("session_id", session_id)
        except (json.JSONDecodeError, KeyError):
            logger.error("Could not parse spawn output for %s/%s", role, epic_folder)
            return SessionResult(
                status="failed",
                result="Could not parse spawn output",
                is_error=True,
            )

        logger.info("Spawned %s for %s via subprocess: session %s", role, epic_folder, spawned_session_id[:8])

        # Wait for subprocess session to complete
        final_status = self.wait_for_session(spawned_session_id)
        return SessionResult(
            status=final_status or "failed",
            result=f"Subprocess session {spawned_session_id[:8]} ended with status: {final_status}",
            session_id=spawned_session_id,
            is_error=(final_status != "completed"),
        )

    # ── Public spawn methods (now delegates to _run_role_agent) ────────

    def spawn_explore_agent(self, epic_folder: str) -> SessionResult:
        """Run an explore agent to analyze the codebase and update the epic YAML.

        Args:
            epic_folder: Epic folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("explore", epic_folder)

    def spawn_story_agent(self, epic_folder: str) -> SessionResult:
        """Run a story-generator agent for user story generation.

        Args:
            epic_folder: Epic folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("story-generator", epic_folder)

    def spawn_design_agent(self, epic_folder: str) -> SessionResult:
        """Run a planner-design agent for solution architecture scaffolding.

        Maps user stories to phases, defines cross-phase contracts, and outputs
        structured design_context.yml for downstream planners.

        Args:
            epic_folder: Epic folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("planner-design", epic_folder)

    def spawn_epic_creator(self, epic_folder: str) -> SessionResult:
        """Run epic-creator agent to scaffold phases and skeleton tickets.

        This is the FIRST step in the planning flow. Creates the epic
        structure that all downstream agents work within.

        Args:
            epic_folder: Epic folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("epic-creator", epic_folder)

    def spawn_explore_agents(self, epic_folder: str) -> SessionResult:
        """Run planner-explore agent(s) to analyze codebase and enrich tickets.

        Spawns a planning-aware explore agent that updates skeleton tickets
        with target-files, guidance, and success criteria.

        Args:
            epic_folder: Epic folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("planner-explore", epic_folder)

    def parse_design_status(self, result: SessionResult) -> str:
        """Parse design agent's status from its output.

        Looks for DESIGN_STATUS: line in the agent's result text.
        Valid statuses: approved, needs_explore, needs_stories.

        Args:
            result: SessionResult from the design agent.

        Returns:
            Status string. Defaults to "approved" if no status found.
        """
        for line in result.result.splitlines():
            if line.startswith("DESIGN_STATUS:"):
                return line.split(":", 1)[1].strip()
        return "approved"  # Default to approved if no status found

    def parse_review_status(self, result: SessionResult) -> str:
        """Parse reviewer agent's status from its output.

        Looks for REVIEW_STATUS: line in the agent's result text.
        Valid statuses: APPROVED, REJECTED, NEEDS_REVISION.

        Args:
            result: SessionResult from the reviewer agent.

        Returns:
            Status string. Defaults to "APPROVED" if no status found.
        """
        for line in result.result.splitlines():
            if line.startswith("REVIEW_STATUS:"):
                return line.split(":", 1)[1].strip().upper()
        # Legacy: check for decision keywords in output
        text = result.result.upper()
        if "REJECT" in text:
            return "REJECTED"
        if "NEEDS_REVISION" in text or "NEEDS REVISION" in text:
            return "NEEDS_REVISION"
        return "APPROVED"

    def spawn_reviewer(self, epic_folder: str) -> SessionResult:
        """Run planner-reviewer agent for an epic.

        Args:
            epic_folder: Epic folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("planner-reviewer", epic_folder)

    def spawn_orchestration_agent(self, epic_folder: str) -> SessionResult:
        """Run planner-orchestration agent to create TinyDB phase records.

        This step is critical: it creates phase records with agent routing
        in TinyDB. Without it, discover_plans_needing_orchestration() will
        keep finding the epic as needing work (no phases with agent field).

        Args:
            epic_folder: Epic folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("planner-orchestration", epic_folder)

    def discover_stories(self, epic_folder: str, project: Optional[str] = None) -> list[dict]:
        """Run story discovery for an epic.

        Args:
            epic_folder: Epic folder name.
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
            logger.warning("Story discovery failed for %s: %s", epic_folder, result.stderr)
            return []

        try:
            data = json.loads(result.stdout)
            stories = data if isinstance(data, list) else data.get("stories", [])
            logger.info("Discovered %d stories for %s", len(stories), epic_folder)
            return stories
        except (json.JSONDecodeError, KeyError):
            logger.warning("Could not parse story discovery output for %s", epic_folder)
            return []

    def wait_for_session(self, session_id: str, timeout: int = 600, poll_interval: int = 10) -> Optional[str]:
        """Wait for a subprocess or tmux session to complete.

        Polls the session state store directly (no CLI call required).
        Short-circuits on consecutive read failures to avoid wasting the
        full timeout when the session process dies before writing state.

        For tmux-spawned sessions, also checks tmux session existence as a
        supplemental liveness probe. The PID check remains primary; tmux
        existence is used to catch edge cases (PID reuse, orphaned state).

        Note: This method is only used in the subprocess/tmux fallback path.
        SDK sessions complete synchronously and don't need polling.

        Args:
            session_id: Session UUID to wait for.
            timeout: Maximum wait time in seconds.
            poll_interval: Seconds between status checks.

        Returns:
            Final status string, or None on timeout.
        """
        QUICK_EXIT_THRESHOLD = 30  # seconds — agent sessions shorter than this are suspicious
        start_time = time.time()
        deadline = start_time + timeout
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
                    elapsed = time.time() - start_time
                    if elapsed < QUICK_EXIT_THRESHOLD:
                        logger.warning(
                            "⚠ Session %s exited in %.1fs (status=%s) — "
                            "this is suspiciously fast and may indicate the agent "
                            "did not run properly (env isolation issue, missing "
                            "--max-turns, or prompt error)",
                            session_id[:8], elapsed, status,
                        )
                    else:
                        logger.info("Session %s finished with status: %s (%.1fs)", session_id[:8], status, elapsed)
                    return status
                # If still running, check if PID is actually alive to detect
                # sessions that died without updating their state file.
                if status == "running":
                    data = _session_store.load(session_id)
                    if data:
                        pid = data.get("pid")
                        # If PID is None, we can't check liveness via PID.
                        # Fall through to tmux check; if no tmux either,
                        # continue polling (the pane runner will update status).
                        pid_alive = pid is not None and is_process_running(pid)

                        # Supplemental tmux liveness check (if tmux-spawned)
                        tmux_session_name = data.get("tmux_session")
                        tmux_alive = False
                        if tmux_session_name:
                            try:
                                from agenticcli.utils.tmux import session_exists as _tmux_session_exists
                                tmux_alive = _tmux_session_exists(tmux_session_name)
                            except Exception:
                                # tmux check failed (binary gone, etc.) — skip it,
                                # fall back to PID-only detection
                                tmux_alive = True  # assume alive on error to avoid false positives

                        # Resolve as dead only when we have positive evidence:
                        # - PID dead AND tmux session gone -> definitely dead
                        # - PID dead AND no tmux field -> PID-only (existing behavior)
                        # - PID None AND no tmux field -> UNKNOWN, keep polling
                        #   (pane runner hasn't written state yet)
                        if pid is None and not tmux_session_name:
                            # No PID and no tmux session name — we can't determine
                            # liveness. Continue polling; the pane runner will update
                            # the status field when it finishes.
                            logger.debug(
                                "Session %s has no PID or tmux_session yet, continuing poll",
                                session_id[:8],
                            )
                        elif not pid_alive:
                            if tmux_session_name and tmux_alive:
                                # PID dead but tmux session still exists — continue polling
                                # (tmux may still be running a different process)
                                logger.debug(
                                    "Session %s PID %s dead but tmux session %s still alive, continuing poll",
                                    session_id[:8], pid, tmux_session_name,
                                )
                            else:
                                # Both dead (or PID dead + no tmux) -> resolve
                                exit_code = data.get("exit_code")
                                if exit_code is not None and exit_code != 0:
                                    final_status = "failed"
                                else:
                                    final_status = "completed"
                                elapsed = time.time() - start_time
                                if elapsed < QUICK_EXIT_THRESHOLD:
                                    logger.warning(
                                        "⚠ Session %s PID %s died after %.1fs (< %ds) "
                                        "— agent may not have run properly",
                                        session_id[:8], pid, elapsed, QUICK_EXIT_THRESHOLD,
                                    )
                                logger.info(
                                    "Session %s PID %s dead%s, status='running' -> resolving as '%s' (exit_code=%s)",
                                    session_id[:8], pid,
                                    f" + tmux session {tmux_session_name} gone" if tmux_session_name else "",
                                    final_status, exit_code,
                                )
                                data["status"] = final_status
                                data["ended_at"] = datetime.now().isoformat()
                                # Add structured failure info for dead-PID resolution (P6_001/P6_003)
                                if final_status == "failed" and "failure_reason" not in data:
                                    data["error_code"] = "pid_died"
                                    data["failure_reason"] = {
                                        "error_code": "pid_died",
                                        "error_type": "unknown",
                                        "suggested_action": "escalate",
                                        "detail": f"PID {pid} died with exit_code={exit_code} after {elapsed:.1f}s",
                                        "retryable": elapsed < QUICK_EXIT_THRESHOLD,
                                        "matched_pattern": "",
                                    }
                                _session_store.save(data)
                                return final_status
            time.sleep(poll_interval)

        # Persist timeout failure into session state (P6_001/P6_003)
        try:
            data = _session_store.load(session_id)
            if data and "failure_reason" not in data:
                data["error_code"] = "timeout"
                data["failure_reason"] = {
                    "error_code": "timeout",
                    "error_type": "unknown",
                    "suggested_action": "escalate",
                    "detail": f"Session timed out after {timeout}s",
                    "retryable": False,
                    "matched_pattern": "",
                }
                data["status"] = "failed"
                data["ended_at"] = datetime.now().isoformat()
                _session_store.save(data)
        except Exception:
            pass  # Best-effort; don't mask the timeout
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

    def run_review_cycle(self, epic_folder: str, max_reviews: int = 3) -> tuple[bool, int, str]:
        """Run review loop: run reviewer agent, handle approve/reject.

        Parses the reviewer's output for REVIEW_STATUS: APPROVED/REJECTED/NEEDS_REVISION.
        On NEEDS_REVISION, loops back to re-run the reviewer (up to max_reviews).
        On REJECTED, returns immediately with failure.

        Args:
            epic_folder: Epic folder name.
            max_reviews: Maximum review iterations.

        Returns:
            Tuple of (approved, iterations_used, feedback).
        """
        for attempt in range(1, max_reviews + 1):
            logger.info("Review cycle %d/%d for %s", attempt, max_reviews, epic_folder)

            result = self.spawn_reviewer(epic_folder)
            if result.status != "completed":
                return False, attempt, f"Reviewer session ended with status: {result.status}"

            review_status = self.parse_review_status(result)
            if review_status == "APPROVED":
                logger.info("Review cycle %d approved for %s", attempt, epic_folder)
                return True, attempt, "approved"
            elif review_status == "REJECTED":
                logger.warning("Review cycle %d rejected for %s", attempt, epic_folder)
                return False, attempt, f"Reviewer rejected: {result.result[:200]}"
            else:
                # NEEDS_REVISION — loop back
                logger.info(
                    "Review cycle %d needs revision for %s — looping back",
                    attempt, epic_folder,
                )
                continue

        logger.warning("Max review iterations reached for %s", epic_folder)
        return False, max_reviews, "Max review iterations reached"

    def update_task_status(self, task_id: str, action: str, epic_folder: str) -> bool:
        """Update task status via CLI.

        Args:
            task_id: Task identifier.
            action: 'start' or 'complete'.
            epic_folder: Epic folder name.

        Returns:
            True if update succeeded.
        """
        cmd = [
            "agentic", "agent", "plan", "task", action,
            task_id,
            "--plan", epic_folder,
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            cwd=self.working_dir,
        )
        if result.returncode != 0:
            logger.error("Failed to update task %s to %s: %s", task_id, action, result.stderr)
            return False
        return True

    def get_plan_status(self, epic_folder: str) -> Optional[str]:
        """Get the status of an epic from TinyDB.

        The epic ``status`` field takes priority.  Task-completion counting is
        used only as a fallback when the status is absent or already set to
        ``"completed"``.  This prevents a fully-tasked-out epic that still has
        ``status: active`` from being prematurely archived.

        Priority order:
        1. If the epic status is present and is NOT ``"completed"``,
           return it as-is (e.g. ``"active"`` is respected).
        2. If the status is ``"completed"``, or is absent, fall back to
           task-counting: return ``"completed"`` when all tasks are done
           (pending == 0 and completed > 0).
        3. If task counts are inconclusive, return whatever the status says
           (may be ``None`` when absent).

        Args:
            epic_folder: Epic folder name.

        Returns:
            The resolved status string, or None if not found.
        """
        if self._repository is None:
            return None

        try:
            epic_data = self._repository.get_epic(epic_folder)
        except Exception:
            return None

        if not epic_data:
            return None

        epic_status = epic_data.status

        # If the epic explicitly declares a non-completed status, honour it
        # and skip task-counting entirely.
        if epic_status is not None and epic_status != "completed":
            return epic_status

        # Status is absent or already "completed" – use task counting
        # as a secondary signal to detect completion.
        try:
            counts = self._repository.get_ticket_counts(epic_folder)
            pending = counts.get("pending", 0) + counts.get("in_progress", 0)
            completed = counts.get("completed", 0)

            if pending == 0 and completed > 0:
                return "completed"
        except Exception:
            pass

        # Task counts are inconclusive – fall back to whatever status says.
        return epic_status

    def archive_plan(self, epic_folder: str) -> bool:
        """Archive a completed epic by setting status=completed in TinyDB.

        No filesystem operations are performed. The TinyDB status field is
        the sole source of truth for epic lifecycle state.

        Args:
            epic_folder: Epic folder name.

        Returns:
            True if the DB status was updated successfully.
        """
        try:
            if self._repository is None:
                logger.error("TinyDB repository not available; cannot archive epic %s", epic_folder)
                return False
            result = self._repository.archive_epic(epic_folder)
            if result.success:
                logger.info("Archived epic %s (TinyDB status=completed)", epic_folder)
                return True
            logger.error("Failed to archive epic %s: %s", epic_folder, result.message)
            return False
        except Exception as e:
            logger.error("Exception archiving epic %s: %s", epic_folder, e)
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

    Discovers epics without TinyDB phases, spawns planners, runs reviews,
    and tracks state throughout execution.
    """

    def __init__(
        self,
        workflow: Optional[PlannerLoopWorkflow] = None,
        project: Optional[str] = None,
        epic_folder: Optional[str] = None,
        budget_usd: float = 50.0,
    ):
        self.workflow = workflow or PlannerLoopWorkflow()
        self.project = project
        self.epic_folder = epic_folder
        self.budget_usd: float = budget_usd
        self.total_cost_usd: float = 0.0
        self.state = {
            "iteration": 0,
            "plans_processed": [],
            "plans_skipped": [],
            "errors": [],
            "current_plan": None,
        }

    def _acquire_epic_lock(self, epic_folder: str) -> bool:
        """Acquire a file-based lock to prevent concurrent orchestration.

        Args:
            epic_folder: Epic folder name.

        Returns:
            True if lock acquired, False if another process holds it.
        """
        lock_dir = Path.home() / ".agentic" / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_file = lock_dir / f"orchestrate_{epic_folder}.lock"
        if lock_file.exists():
            try:
                data = json.loads(lock_file.read_text())
                pid = data.get("pid")
                if pid and is_process_running(pid):
                    logger.error(
                        "Epic %s already being orchestrated by PID %d (started %s)",
                        epic_folder, pid, data.get("started_at", "unknown"),
                    )
                    return False
                # Stale lock — owner process is dead
                logger.warning(
                    "Clearing stale lock for %s (PID %d no longer running)",
                    epic_folder, pid,
                )
            except (json.JSONDecodeError, OSError):
                pass  # Corrupt lock file — overwrite it
        lock_file.write_text(json.dumps({
            "pid": os.getpid(),
            "started_at": datetime.now().isoformat(),
        }))
        return True

    def _release_epic_lock(self, epic_folder: str):
        """Release the file-based orchestration lock.

        Args:
            epic_folder: Epic folder name.
        """
        lock_file = Path.home() / ".agentic" / "locks" / f"orchestrate_{epic_folder}.lock"
        lock_file.unlink(missing_ok=True)

    def _track_cost(self, result) -> bool:
        """Accumulate cost from a SessionResult and check budget.

        Args:
            result: SessionResult from an agent spawn.

        Returns:
            True if budget is exhausted (caller should abort).
        """
        self.total_cost_usd += getattr(result, "cost_usd", 0.0)
        if self.budget_usd and self.total_cost_usd >= self.budget_usd:
            logger.error(
                "Budget exhausted: $%.2f >= $%.2f limit",
                self.total_cost_usd, self.budget_usd,
            )
            return True
        return False

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

        # Track epics that failed/skipped within this run to avoid
        # rediscovering and retrying them every iteration.
        failed_this_run: set[str] = set()

        for iteration in range(1, max_iterations + 1):
            self.state["iteration"] = iteration
            logger.info("=== Planner loop iteration %d/%d ===", iteration, max_iterations)

            # Archive completed epics so they aren't left pending
            if not self.epic_folder:
                if self.workflow._repository:
                    for epic in self.workflow._repository.list_epics(status="live"):
                        if self.workflow.get_plan_status(epic.epic_folder_name) == "completed":
                            logger.info("Archiving completed epic: %s", epic.epic_folder_name)
                            self.workflow.archive_plan(epic.epic_folder_name)
            else:
                status = self.workflow.get_plan_status(self.epic_folder)
                if status == "completed":
                    logger.info("Epic %s is already completed/archived — nothing to plan. "
                                "Use 'agentic epic unarchive' to reopen it.", self.epic_folder)
                    return True

            if self.epic_folder:
                # Single-epic mode: check if epic already has fully-routed phases in TinyDB.
                # Also require that at least one ticket has moved beyond "proposed" status —
                # all-proposed tickets means the skeleton was created but planning hasn't
                # run yet (planning promotes proposed→pending on success).
                # "pending" means planning completed; "proposed" means skeleton-only.
                if self.workflow._repository:
                    phases = self.workflow._repository.list_phases(self.epic_folder)
                    all_routed = phases and all(p.agent for p in phases)
                    if all_routed:
                        epic_data = self.workflow._repository.get_epic(self.epic_folder)
                        tickets = epic_data.tasks if epic_data else []
                        all_tickets_proposed = tickets and all(
                            t.status == "proposed" for t in tickets
                        )
                        if not all_tickets_proposed:
                            logger.info("Epic %s already has routed phases in TinyDB. %s", self.epic_folder, promise)
                            print(promise)
                            return True
                        logger.info(
                            "Epic %s has routed phases but all %d tickets are still 'proposed' — "
                            "re-planning to update tickets.", self.epic_folder, len(tickets),
                        )
                plans = [self.epic_folder]
            else:
                plans = self.workflow.discover_plans_needing_orchestration()
                # Exclude epics that already failed in this run
                if failed_this_run:
                    before = len(plans)
                    plans = [p for p in plans if p not in failed_this_run]
                    if before != len(plans):
                        logger.info(
                            "Excluded %d previously-failed epic(s) from rediscovery: %s",
                            before - len(plans), failed_this_run,
                        )
            if not plans:
                logger.info("All epics have phases in TinyDB. %s", promise)
                print(promise)
                return True

            for epic_folder in plans:
                self.state["current_plan"] = epic_folder
                success = self._process_plan(epic_folder)
                if success:
                    self.state["plans_processed"].append(epic_folder)
                else:
                    self.state["plans_skipped"].append(epic_folder)
                    failed_this_run.add(epic_folder)

            self.state["current_plan"] = None
            logger.info("Iteration %d complete: processed=%d, skipped=%d",
                         iteration,
                         len(self.state["plans_processed"]),
                         len(self.state["plans_skipped"]))

            # If every discovered plan failed, stop early — retrying won't help
            if failed_this_run and not self.state["plans_processed"]:
                logger.error(
                    "All discovered epics failed planning — stopping early. "
                    "Failed: %s", list(failed_this_run),
                )
                return False

        logger.warning("Max iterations (%d) reached without completion", max_iterations)
        return False

    def _process_plan(self, epic_folder: str) -> bool:
        """Process a single epic through the full planning workflow.

        Epic-creator-first architecture (7 steps):
        1. Epic Creator    → scaffold phases + skeleton tickets (ALL types)
        2. Story Generator → generate user stories
        3. Explore         → analyze codebase, update tickets via CLI
        4. Design          → review gate: tie stories to tickets, can loop back
        5. Review          → validate completeness
        6. Orchestration   → add agent routing to phases
        7. Ticket Promotion → proposed → pending

        Uses SDK-first agent execution — no spawn+wait pattern needed.
        Each agent call blocks until completion and returns a SessionResult.

        Args:
            epic_folder: Epic folder name.

        Returns:
            True if epic was processed successfully.
        """
        if not self._acquire_epic_lock(epic_folder):
            self.state["errors"].append({
                "plan": epic_folder,
                "error": "Another orchestration process is already running for this epic",
                "phase": "pre_check",
            })
            return False

        try:
            return self._process_plan_inner(epic_folder)
        finally:
            self._release_epic_lock(epic_folder)

    def _process_plan_inner(self, epic_folder: str) -> bool:
        """Inner implementation of _process_plan (lock already held)."""
        logger.info("Processing epic: %s", epic_folder)

        # Auto-register epic in TinyDB if folder exists on disk but isn't registered
        repo = self.workflow._get_repository()
        if repo:
            from agenticcli.commands.epic import _ensure_epic_in_db
            epic_path = self.workflow.epics_dir / epic_folder
            if epic_path.is_dir():
                _ensure_epic_in_db(repo, epic_path)

        # Guard: detect already-completed or archived epics via TinyDB status
        status = self.workflow.get_plan_status(epic_folder)
        if status == "completed":
            logger.info(
                "Epic %s is already completed/archived — skipping. "
                "Use 'agentic epic unarchive' to reopen it for re-planning.",
                epic_folder,
            )
            return True  # Not an error — just nothing to do
        if status is None:
            logger.error(
                "Epic %s not found in TinyDB — cannot plan. "
                "Create it first with 'agentic epic init'.",
                epic_folder,
            )
            self.state["errors"].append({
                "plan": epic_folder,
                "error": "Epic not found in TinyDB",
                "phase": "pre_check",
            })
            return False

        # Mark epic as 'planning' now that the planner loop is actively processing it
        try:
            repo = self.workflow._get_repository()
            if repo:
                repo.update_epic(epic_folder, {"status": "planning"})
        except Exception:
            pass  # Non-fatal — status update is best-effort

        # 1. Epic Creator: scaffold ALL phases + skeleton tickets
        creator_result = self.workflow.spawn_epic_creator(epic_folder)
        self.workflow._validate_result(creator_result, "epic-creator")
        if self._track_cost(creator_result):
            return False
        if creator_result.status != "completed":
            self.state["errors"].append({
                "plan": epic_folder,
                "error": f"Epic creator failed: {creator_result.result[:200]}",
                "phase": "epic_creator",
            })
            return False

        # 2. Story generation: run story agent
        story_result = self.workflow.spawn_story_agent(epic_folder)
        self.workflow._validate_result(story_result, "story-generator")
        if self._track_cost(story_result):
            return False
        if story_result.status != "completed":
            self.state["errors"].append({
                "plan": epic_folder,
                "error": f"Story agent failed: {story_result.result[:200]}",
                "phase": "story_generation",
            })
            return False

        # 3-4. Explore + Design (with loop-back support)
        max_design_loops = 2
        for design_iter in range(max_design_loops + 1):
            # 3. Explore: run planner-explore to analyze codebase and enrich tickets
            explore_result = self.workflow.spawn_explore_agents(epic_folder)
            self.workflow._validate_result(explore_result, "planner-explore")
            if self._track_cost(explore_result):
                return False
            if explore_result.status != "completed":
                self.state["errors"].append({
                    "plan": epic_folder,
                    "error": f"Explore agent failed: {explore_result.result[:200]}",
                    "phase": "explore",
                })
                return False

            # 4. Design (review gate): validate story-to-ticket mapping
            design_result = self.workflow.spawn_design_agent(epic_folder)
            self.workflow._validate_result(design_result, "planner-design")
            if self._track_cost(design_result):
                return False
            if design_result.status != "completed":
                self.state["errors"].append({
                    "plan": epic_folder,
                    "error": f"Design agent failed: {design_result.result[:200]}",
                    "phase": "design",
                })
                return False  # Design is now fatal

            design_status = self.workflow.parse_design_status(design_result)
            if design_status == "approved":
                logger.info("Design gate approved for %s on iteration %d", epic_folder, design_iter + 1)
                break
            elif design_status == "needs_stories" and design_iter < max_design_loops:
                logger.info(
                    "Design gate needs stories for %s — re-running story generator (iteration %d)",
                    epic_folder, design_iter + 1,
                )
                self.workflow.spawn_story_agent(epic_folder)
                continue
            elif design_status == "needs_explore" and design_iter < max_design_loops:
                logger.info(
                    "Design gate needs more exploration for %s — looping back (iteration %d)",
                    epic_folder, design_iter + 1,
                )
                continue
            else:
                # Max loops reached or unknown status — proceed anyway
                logger.warning(
                    "Design gate not fully approved after %d iterations for %s (status=%s)",
                    design_iter + 1, epic_folder, design_status,
                )
                break

        # 5. Review cycle
        approved, review_iters, feedback = self.workflow.run_review_cycle(epic_folder)
        if not approved:
            logger.warning("Epic %s not approved after %d reviews: %s",
                           epic_folder, review_iters, feedback)
            self.state["errors"].append({
                "plan": epic_folder,
                "error": f"Review rejected: {feedback}",
                "phase": "review",
            })
            return False

        # 6. Orchestration: create TinyDB phase records with agent routing
        #    Without this step, discover_plans_needing_orchestration() will
        #    keep finding this epic (no phases with agent field) → infinite loop.
        orch_result = self.workflow.spawn_orchestration_agent(epic_folder)
        self.workflow._validate_result(orch_result, "planner-orchestration")
        if self._track_cost(orch_result):
            return False
        if orch_result.status != "completed":
            self.state["errors"].append({
                "plan": epic_folder,
                "error": f"Orchestration agent failed: {orch_result.result[:200]}",
                "phase": "orchestration",
            })
            return False

        # 7. Promote all "proposed" tickets to "pending" to signal planning is done.
        # Without this, the loop's termination check (all tickets proposed → re-plan)
        # would rediscover this epic and create an infinite re-planning loop.
        if self.workflow._repository:
            epic_data = self.workflow._repository.get_epic(epic_folder)
            if epic_data:
                promoted = 0
                for ticket in epic_data.tasks:
                    if ticket.status == "proposed":
                        updated = self.workflow._repository.update_ticket(
                            epic_folder, ticket.id, {"status": "pending"}
                        )
                        if updated:
                            promoted += 1
                        else:
                            logger.warning(
                                "Failed to promote ticket %s from 'proposed' to 'pending' for %s",
                                ticket.id, epic_folder,
                            )
                if promoted:
                    logger.info(
                        "Promoted %d tickets from 'proposed' to 'pending' for %s",
                        promoted, epic_folder,
                    )

                # Post-promotion verification: ensure no proposed tickets remain
                epic_data_after = self.workflow._repository.get_epic(epic_folder)
                if epic_data_after:
                    still_proposed = sum(
                        1 for t in epic_data_after.tasks if t.status == "proposed"
                    )
                    if still_proposed > 0 and promoted == 0:
                        logger.error(
                            "Ticket promotion failed for %s: %d tickets still in 'proposed' state "
                            "after promotion attempt. Aborting to prevent infinite re-planning loop.",
                            epic_folder, still_proposed,
                        )
                        return False

        logger.info("Epic %s processed successfully (with orchestration phases)", epic_folder)
        return True
