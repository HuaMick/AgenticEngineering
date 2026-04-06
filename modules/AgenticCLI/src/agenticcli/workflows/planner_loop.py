# story: US-GDN-064, US-GDN-070, US-GDN-074, US-GDN-081, US-PLN-046, US-PLN-065
"""Planner Loop workflow for automated orchestration planning.

Encapsulates the orchestration planner logic: discovers epics needing
planning (no phases in TinyDB), spawns specialized planners, validates
planning output, and tracks state throughout execution.

Uses the Claude Agent SDK via SDK-in-tmux for process-isolated agent
invocation. Falls back to SDK-direct when tmux is unavailable.
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from agenticguidance.services.story import get_epic_stories_path
from agenticcli.utils.epic_lock import acquire_epic_lock, release_epic_lock
from agenticcli.utils.phase_validation import validate_phase_routing
from agenticcli.utils.session_id import generate_session_id
from agenticcli.utils.retry import SPAWN_RETRY_BACKOFF, static_backoff
from agenticcli.utils.session_diagnostics import diagnose_quick_exit
from agenticcli.utils.transport import determine_transport, SDK_DIRECT, SDK_TMUX
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


# Shared session state store (same as session.py)
_session_store = StateStore("sessions", id_key="session_id")

# Sentinel value: returned by _try_event_bus_wait() when the event-bus path
# cannot determine session status and the caller should fall back to polling.
_FALLBACK_TO_POLLING = object()

#: Grace period (seconds) to wait for events.jsonl to appear before falling
#: back to session-state-JSON polling.  Must be long enough for the pane runner
#: to start writing but short enough to avoid blocking the orchestrator.
_EVENT_BUS_GRACE_PERIOD = 15

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
    "build-story-writer",
    "planner-build",
    "planner-test",
    "planner-audit",
    "planner-orchestration",
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
        f"Initialize your context by running: agentic -j epic status --epic {epic_folder}",
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

    Uses SDK-in-tmux for process-isolated agent invocation.
    Falls back to SDK-direct when tmux is unavailable.
    """

    def __init__(self, epics_dir: Optional[Path] = None, working_dir: Optional[str] = None, prompt: Optional[str] = None):
        self.epics_dir = epics_dir or Path.cwd() / "docs" / "epics" / "live"
        self.working_dir = working_dir or str(Path.cwd())
        self.prompt = prompt

        # Initialize EpicRepository for TinyDB-based lookups
        self._repository = None
        try:
            from agenticguidance.services.epic_repository import EpicRepository

            self._repository = EpicRepository()
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
        """Find epics with status ``seed`` or ``planning`` — need planning.

        The status is the sole signal for whether planning is needed.
        Preconditions are enforced at transition boundaries, not here.

        Results are priority-sorted (already applied by ``list_epics()``).

        Returns:
            List of epic folder names needing orchestration.
        """
        if self._repository is None:
            logger.error("No EpicRepository available — cannot discover epics needing orchestration")
            return []

        seed_epics = self._repository.list_epics(status="seed")
        planning_epics = self._repository.list_epics(status="planning")

        # Merge and deduplicate while preserving priority order
        seen: set[str] = set()
        needs_work: list[str] = []
        for epic in seed_epics + planning_epics:
            if epic.epic_folder_name not in seen:
                seen.add(epic.epic_folder_name)
                needs_work.append(epic.epic_folder_name)

        # Re-sort by priority since we merged two lists
        all_epics = {e.epic_folder_name: e for e in seed_epics + planning_epics}
        needs_work.sort(
            key=lambda name: (
                _to_int_priority(all_epics[name].priority) if name in all_epics else 3,
                [-ord(c) for c in name],
            ),
        )

        logger.info("Found %d epics needing orchestration: %s", len(needs_work), needs_work)
        return needs_work

    # ── Deprecated: determine_plan_type removed ─────────────────────
    # Epic-creator-first architecture eliminates the need for plan type
    # routing. The epic-creator agent scaffolds ALL phases and tickets
    # in one pass. See _process_plan() for the new flow.
    # ── SDK-first agent execution ──────────────────────────────────────

    def _run_role_agent(self, role: str, epic_folder: str, extra_prompt: Optional[str] = None) -> SessionResult:
        """Run an agent with the given role via the SDK.

        Builds the prompt and options, invokes run_agent_sync(), and
        writes session state for observability.

        Falls back to subprocess spawn + wait when SDK is unavailable.

        Args:
            role: Agent role identifier.
            epic_folder: Epic folder name.
            extra_prompt: Optional per-call extra instructions (e.g. category scope).
                Appended after self.prompt if both are present.

        Returns:
            SessionResult with status and metadata.
        """
        session_id = generate_session_id()
        # Merge loop-level prompt with per-call extra_prompt
        combined_extra: Optional[str]
        if self.prompt and extra_prompt:
            combined_extra = f"{self.prompt}\n\n{extra_prompt}"
        elif extra_prompt:
            combined_extra = extra_prompt
        else:
            combined_extra = self.prompt
        prompt = _build_agent_prompt(role, epic_folder, extra_prompt=combined_extra)

        force_sdk = os.environ.get("AGENTIC_FORCE_SDK_DIRECT") == "1"
        transport = determine_transport(sdk_available=SDK_AVAILABLE, force_sdk_direct=force_sdk)

        if transport == SDK_DIRECT:
            logger.warning("Using SDK-direct path (AGENTIC_FORCE_SDK_DIRECT=1) — zombie bug risk")
            return self._run_via_sdk(session_id, role, epic_folder, prompt)
        elif transport == SDK_TMUX:
            return self._run_via_tmux_sdk(session_id, role, epic_folder, prompt)
        else:
            # SDK available but no tmux — fallback to SDK-direct
            logger.warning("tmux not available, falling back to SDK-direct (zombie bug risk)")
            return self._run_via_sdk(session_id, role, epic_folder, prompt)

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
                backoff = static_backoff(attempt - 1, SPAWN_RETRY_BACKOFF)
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

        # Record session start (context file written by cmd_spawn via
        # _compile_spawn_context which includes role process, inputs, and
        # current ticket — richer than our prompt-only write)
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
        spawned_session_id = session_id  # Default until spawn output overrides
        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                backoff = static_backoff(attempt - 1, SPAWN_RETRY_BACKOFF)
                logger.info(
                    "Retrying sdk-tmux agent (attempt %d/%d): %s — waiting %ds",
                    attempt, max_retries, result.result[:100], backoff,
                )
                time.sleep(backoff)
                # New session_id for retry (new tmux pane)
                session_id = generate_session_id()
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

            # Quick-exit detection (< 30s) with structured diagnostics
            if elapsed < 30 and final_status != "completed":
                logger.warning(
                    "Quick exit detected for %s/%s (%.1fs) — running diagnostics",
                    role, epic_folder, elapsed,
                )
                diagnosis = diagnose_quick_exit(spawned_session_id)
                if diagnosis and not diagnosis.retryable:
                    logger.error(
                        "Quick exit for %s/%s is not retryable (%s): %s",
                        role, epic_folder, diagnosis.error_type.value,
                        diagnosis.detail[:200],
                    )
                    # Build a final result and break — no point retrying
                    sdk_metrics = read_sdk_metrics(spawned_session_id)
                    result = SessionResult(
                        status="failed",
                        result=f"Non-retryable quick exit: {diagnosis.error_type.value}",
                        cost_usd=sdk_metrics["cost_usd"],
                        duration_ms=sdk_metrics["duration_ms"],
                        session_id=sdk_metrics["sdk_session_id"] or spawned_session_id,
                        num_turns=sdk_metrics["num_turns"],
                        usage=sdk_metrics["usage"],
                        is_error=True,
                    )
                    break

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
            "session_id": spawned_session_id,
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

    # ── Public spawn methods (now delegates to _run_role_agent) ────────

    def spawn_story_agent(self, epic_folder: str) -> SessionResult:
        """Run a build-story-writer agent for user story generation.

        Args:
            epic_folder: Epic folder name.

        Returns:
            SessionResult with completion status.
        """
        return self._run_role_agent("build-story-writer", epic_folder)

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

    def _build_category_prompt(self, category: dict) -> str:
        """Build category-scoped prompt for an explore agent.

        Args:
            category: Category dict with keys: name, description, codebase_scope, story_ids.

        Returns:
            Prompt string scoping the agent to this category.
        """
        parts = [
            f"CATEGORY SCOPE: You are exploring category '{category['name']}'.",
            f"Description: {category.get('description', 'N/A')}",
        ]
        if category.get("codebase_scope"):
            scope_paths = ", ".join(category["codebase_scope"])
            parts.append(f"Focus your exploration on these paths: {scope_paths}")
        if category.get("story_ids"):
            ids = ", ".join(category["story_ids"])
            parts.append(f"Relevant story IDs: {ids}")
        parts.append("Only update tickets related to stories in your category.")
        return "\n".join(parts)

    def spawn_explore_agents(self, epic_folder: str, categories: list[dict] | None = None) -> SessionResult:
        """Spawn explore agents — one per category if provided, else single agent.

        Uses ThreadPoolExecutor for parallel spawning. Each agent runs in its own
        tmux pane via sdk-tmux transport (safe for concurrent use).

        Args:
            epic_folder: Epic folder name.
            categories: Optional list of category dicts from the story file. When
                provided and contains more than one entry, one agent is spawned
                per category in parallel.

        Returns:
            SessionResult with completion status (aggregated when parallel).
        """
        if not categories or len(categories) <= 1:
            extra = None
            if categories and len(categories) == 1:
                extra = self._build_category_prompt(categories[0])
            return self._run_role_agent("planner-explore", epic_folder, extra_prompt=extra)

        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = []
        with ThreadPoolExecutor(max_workers=len(categories)) as executor:
            futures = {
                executor.submit(
                    self._run_role_agent, "planner-explore", epic_folder,
                    self._build_category_prompt(cat)
                ): cat["name"]
                for cat in categories
            }
            for future in as_completed(futures):
                cat_name = futures[future]
                try:
                    result = future.result()
                    logger.info("Explore agent for category '%s' completed: %s", cat_name, result.status)
                    results.append(result)
                except Exception as e:
                    logger.error("Explore agent for category '%s' failed: %s", cat_name, e)
                    results.append(SessionResult(
                        status="failed", result=str(e), cost_usd=0.0,
                        duration_ms=0, is_error=True
                    ))

        # Aggregate results
        any_failed = any(r.status != "completed" for r in results)
        total_cost = sum(r.cost_usd for r in results)
        max_duration = max((r.duration_ms for r in results), default=0)
        completed = sum(1 for r in results if r.status == "completed")

        return SessionResult(
            status="completed" if not any_failed else "failed",
            result=f"Parallel explore: {completed}/{len(results)} categories completed",
            cost_usd=total_cost,
            duration_ms=max_duration,
            is_error=any_failed,
        )

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

    def wait_for_session(self, session_id: str, timeout: int = 600, poll_interval: int = 10) -> Optional[str]:
        """Wait for a subprocess or tmux session to complete.

        **Primary path** — event-bus watching (US-260401AG-004):
        If the ``event_bus`` module is available, creates an
        :class:`~agenticcli.utils.event_bus.EventWatcher` and waits for
        ``events.jsonl`` to appear.  Once the file is detected the method
        observes real-time events (tool_use, tool_result, error) and returns
        immediately when a ``CompletedEvent`` arrives.

        **Fallback path** — session-state-JSON polling (US-260401AG-005):
        If the event file does not appear within a grace period, the
        ``event_bus`` module is unavailable, or the event file becomes
        unreadable mid-stream, the method falls back to the original
        StateStore polling loop with full PID liveness checks and tmux
        supplemental probes.

        Args:
            session_id: Session UUID to wait for.
            timeout: Maximum wait time in seconds.
            poll_interval: Seconds between status checks.

        Returns:
            Final status string, or None on timeout.
        """
        QUICK_EXIT_THRESHOLD = 30  # seconds — agent sessions shorter than this are suspicious
        start_time = time.time()

        # --- Event-bus fast path (US-260401AG-004, US-260401AG-005) ----------
        try:
            from agenticcli.utils.event_bus import EventWatcher, EventType  # noqa: F811
            _has_event_bus = True
        except ImportError:
            _has_event_bus = False
            logger.debug("event_bus module unavailable, using session-state polling")

        if _has_event_bus:
            event_result = self._try_event_bus_wait(
                session_id, timeout, start_time, QUICK_EXIT_THRESHOLD,
            )
            if event_result is not _FALLBACK_TO_POLLING:
                # Got a definitive result from the event bus.
                if event_result is None:
                    # Timed out — persist failure in session state.
                    self._persist_timeout_failure(session_id, timeout)
                    logger.warning("Session %s timed out after %ds", session_id[:8], timeout)
                return event_result

        # --- Existing polling fallback ---------------------------------------
        # Adjust deadline for wall-clock time already consumed by the
        # event-bus grace period so the overall budget is honoured.
        elapsed_so_far = time.time() - start_time
        remaining = max(timeout - elapsed_so_far, 0)
        deadline = time.time() + remaining
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
        self._persist_timeout_failure(session_id, timeout)
        logger.warning("Session %s timed out after %ds", session_id[:8], timeout)
        return None

    # -- event-bus wait helpers (US-260401AG-004 / US-260401AG-005) -----------

    def _try_event_bus_wait(
        self,
        session_id: str,
        timeout: int,
        start_time: float,
        quick_exit_threshold: int,
    ) -> "str | None | object":
        """Attempt to wait for session completion via the event-bus side-channel.

        Returns a status string (``"completed"``, ``"failed"``, etc.) when a
        :class:`~agenticcli.utils.event_bus.CompletedEvent` is received, ``None``
        when the overall *timeout* expires, or the module-level sentinel
        :data:`_FALLBACK_TO_POLLING` when the caller should fall back to
        session-state-JSON polling.

        Fallback triggers:
        * ``events.jsonl`` does not appear within :data:`_EVENT_BUS_GRACE_PERIOD`.
        * An unrecoverable I/O error occurs while reading the event file.

        Args:
            session_id: Session UUID to wait for.
            timeout: Overall timeout budget in seconds.
            start_time: ``time.time()`` recorded at the top of
                :meth:`wait_for_session` — used for quick-exit detection.
            quick_exit_threshold: Seconds threshold for suspicious quick exits.

        Returns:
            Status string, ``None`` (timeout), or :data:`_FALLBACK_TO_POLLING`.
        """
        from agenticcli.utils.event_bus import EventWatcher, EventType

        watcher = EventWatcher(session_id)

        # -- Grace period: wait for events.jsonl to appear -------------------
        grace_deadline = time.time() + min(_EVENT_BUS_GRACE_PERIOD, timeout)
        file_appeared = False
        while time.time() < grace_deadline:
            if watcher.path.exists():
                file_appeared = True
                break
            time.sleep(1.0)

        if not file_appeared:
            logger.debug(
                "Session %s: events.jsonl not found within %ds grace period, "
                "falling back to session-state polling",
                session_id[:8],
                _EVENT_BUS_GRACE_PERIOD,
            )
            return _FALLBACK_TO_POLLING

        # -- Event-watching mode ---------------------------------------------
        logger.info(
            "Session %s: events.jsonl detected, using event-bus watching",
            session_id[:8],
        )
        remaining = max(timeout - (time.time() - start_time), 0)

        try:
            for event in watcher.iter_events(timeout=remaining, poll_interval=1.0):
                if event.type == EventType.tool_use:
                    logger.debug(
                        "Session %s: tool_use → %s",
                        session_id[:8],
                        getattr(event, "tool_name", "unknown"),
                    )
                elif event.type == EventType.tool_result:
                    logger.debug(
                        "Session %s: tool_result → %s (error=%s)",
                        session_id[:8],
                        getattr(event, "tool_name", "unknown"),
                        getattr(event, "is_error", False),
                    )
                elif event.type == EventType.error:
                    logger.warning(
                        "Session %s: error event — %s: %s",
                        session_id[:8],
                        getattr(event, "error_type", "unknown"),
                        getattr(event, "error_message", ""),
                    )
                elif event.type == EventType.completed:
                    status = getattr(event, "status", "completed")
                    elapsed = time.time() - start_time
                    if elapsed < quick_exit_threshold:
                        logger.warning(
                            "⚠ Session %s exited in %.1fs (status=%s) — "
                            "suspiciously fast (event-bus path)",
                            session_id[:8],
                            elapsed,
                            status,
                        )
                    else:
                        logger.info(
                            "Session %s finished via event bus: status=%s (%.1fs)",
                            session_id[:8],
                            status,
                            elapsed,
                        )
                    # Normalise to known terminal states.
                    if status in ("completed", "failed", "stopped"):
                        return status
                    return "completed"
        except Exception as exc:
            # Event file became unreadable mid-stream — fall back to polling.
            logger.warning(
                "Session %s: event-bus read failed (%s), "
                "falling back to session-state polling",
                session_id[:8],
                exc,
            )
            return _FALLBACK_TO_POLLING

        # iter_events exhausted without a CompletedEvent — genuine timeout.
        logger.debug(
            "Session %s: event stream ended without CompletedEvent, treating as timeout",
            session_id[:8],
        )
        return None

    @staticmethod
    def _persist_timeout_failure(session_id: str, timeout: int) -> None:
        """Persist timeout failure info into session state (best-effort).

        Writes ``error_code``, ``failure_reason``, ``status``, and
        ``ended_at`` fields to the session state store.  No-ops if the
        session already has a ``failure_reason`` recorded.

        Args:
            session_id: Session UUID.
            timeout: The timeout budget that was exhausted.
        """
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

class PlannerLoopRunner:
    """Orchestrates the full planning loop.

    Discovers epics without TinyDB phases, spawns planners, validates
    planning output, and tracks state throughout execution.
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

        try:
            return self._run_inner(max_iterations, promise)
        finally:
            if self.workflow._repository:
                self.workflow._repository.close()

    def _run_inner(self, max_iterations: int, promise: str) -> bool:
        """Inner run loop, wrapped by run() for cleanup."""
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
                # Single-epic mode: check if epic already has fully-routed phases
                # and at least one ticket has moved beyond "proposed" status.
                if self.workflow._repository:
                    is_valid, reason = validate_phase_routing(
                        self.workflow._repository, self.epic_folder,
                    )
                    if is_valid:
                        logger.info("Epic %s already has routed phases in TinyDB. %s", self.epic_folder, promise)
                        print(promise)
                        return True
                    logger.info(
                        "Epic %s needs planning: %s",
                        self.epic_folder, reason,
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
                    # In single-epic mode, verify promotion and exit immediately
                    if self.epic_folder and self.workflow._repository:
                        epic_data = self.workflow._repository.get_epic(epic_folder)
                        if epic_data and not any(t.status == "proposed" for t in epic_data.tasks):
                            logger.info("Epic %s fully planned and promoted — exiting loop", epic_folder)
                            print(promise)
                            return True
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

    # Backoff schedule for story file retry (seconds between attempts)
    _STORY_PARSE_BACKOFF = [0.5, 1.0, 2.0]

    # File readiness check: max wait and poll interval (seconds)
    _FILE_READY_TIMEOUT = 5.0
    _FILE_READY_POLL = 0.5

    @staticmethod
    def _wait_for_file_ready(
        path: Path,
        timeout: float = 5.0,
        poll_interval: float = 0.5,
    ) -> bool:
        """Wait for a file to exist and have non-zero size.

        Polls until the file is present and has content, or until timeout.
        This is an upfront guard before attempting to parse — separate from
        the retry logic in ``_parse_story_categories``.

        Args:
            path: File path to check.
            timeout: Maximum time to wait in seconds.
            poll_interval: Time between polls in seconds.

        Returns:
            True if the file is ready (exists and non-empty), False on timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if path.exists() and path.stat().st_size > 0:
                    return True
            except OSError:
                pass  # Transient filesystem error — keep polling
            time.sleep(poll_interval)

        # Final check after timeout
        try:
            return path.exists() and path.stat().st_size > 0
        except OSError:
            return False

    def _parse_story_categories(self, epic_folder: str) -> list[dict] | None:
        """Read categories from the epic story file in docs/userstories/EpicStories/.

        Stories are REQUIRED — the build-story-writer agent must produce a valid
        story file with at least one category before exploration can proceed.

        Retries with exponential backoff (0.5s, 1s, 2s) to handle transient
        file visibility failures — a race condition where the story agent has
        completed but the file is not yet visible or fully flushed to this
        process.

        Retries on: FileNotFoundError, empty file content, YAML parse errors.
        Does NOT retry on: valid YAML with missing ``categories`` key (data
        error, not a race condition).

        Args:
            epic_folder: Epic folder name.

        Returns:
            List of category dicts, or None if the story file is missing/invalid
            after all retry attempts are exhausted.
        """
        import yaml

        stories_path = get_epic_stories_path(epic_folder)

        # Deprecation check: warn if stories.yml still exists at the old location
        old_path = self.workflow.epics_dir / epic_folder / "stories.yml"
        if old_path.exists():
            logger.warning(
                "DEPRECATED: stories.yml found at old location %s — "
                "stories should be at %s. Run migration to consolidate.",
                old_path, stories_path,
            )

        max_retries = len(self._STORY_PARSE_BACKOFF)
        total_attempts = max_retries + 1  # 1 initial + retries

        for attempt in range(total_attempts):
            # Backoff before retry (not before the first attempt)
            if attempt > 0:
                delay = self._STORY_PARSE_BACKOFF[attempt - 1]
                logger.info(
                    "Retry %d/%d for story file read (backoff %.1fs): %s",
                    attempt,
                    max_retries,
                    delay,
                    epic_folder,
                )
                time.sleep(delay)

            # --- Check file exists ---
            if not stories_path.exists():
                if attempt < max_retries:
                    logger.warning(
                        "Story file not found for %s (attempt %d/%d) — retrying",
                        epic_folder,
                        attempt + 1,
                        total_attempts,
                    )
                    continue
                logger.error(
                    "No story file found for %s after %d attempts — stories are required. "
                    "The build-story-writer agent must produce the story file before exploration.",
                    epic_folder,
                    total_attempts,
                )
                return None

            try:
                with open(stories_path) as f:
                    content = f.read()

                # --- Empty content (file visible but not yet flushed) ---
                if not content.strip():
                    if attempt < max_retries:
                        logger.warning(
                            "Story file is empty for %s (attempt %d/%d) — retrying",
                            epic_folder,
                            attempt + 1,
                            total_attempts,
                        )
                        continue
                    logger.error(
                        "Story file is empty for %s after %d attempts",
                        epic_folder,
                        total_attempts,
                    )
                    return None

                data = yaml.safe_load(content)

                # --- Valid YAML, missing categories — data error, do NOT retry ---
                categories = data.get("categories", [])
                if not categories:
                    logger.error(
                        "Story file for %s has no categories — "
                        "build-story-writer must define at least one category.",
                        epic_folder,
                    )
                    return None

                if attempt > 0:
                    logger.info(
                        "Story file parsed successfully on attempt %d/%d for %s",
                        attempt + 1,
                        total_attempts,
                        epic_folder,
                    )
                return categories

            except FileNotFoundError:
                # File disappeared between exists() check and open()
                if attempt < max_retries:
                    logger.warning(
                        "Story file disappeared for %s (attempt %d/%d) — retrying",
                        epic_folder,
                        attempt + 1,
                        total_attempts,
                    )
                    continue
                logger.error(
                    "Story file not found for %s after %d attempts.",
                    epic_folder,
                    total_attempts,
                )
                return None

            except yaml.YAMLError as e:
                # YAML parse error — could be partial write, retry
                if attempt < max_retries:
                    logger.warning(
                        "YAML parse error for story file in %s (attempt %d/%d): %s — retrying",
                        epic_folder,
                        attempt + 1,
                        total_attempts,
                        e,
                    )
                    continue
                logger.error(
                    "Failed to parse story file for %s after %d attempts: %s",
                    epic_folder,
                    total_attempts,
                    e,
                )
                return None

        # Should not be reached — all paths return within the loop
        return None

    def _process_plan(self, epic_folder: str) -> bool:
        """Process a single epic through the full planning workflow.

        Pipeline (5 steps + promotion):
        1. Epic Creator    → scaffold phases + skeleton tickets
        2. Story Writer    → generate user stories + categories → docs/userstories/EpicStories/
        3. Parallel Explore → N agents, one per category
        4. Pre-flight      → Python validation (advisory, replaces design+review)
        5. Orchestration   → add agent routing to phases
        6. Ticket Promotion → proposed → pending

        Uses SDK-first agent execution — no spawn+wait pattern needed.
        Each agent call blocks until completion and returns a SessionResult.

        Args:
            epic_folder: Epic folder name.

        Returns:
            True if epic was processed successfully.
        """
        if not acquire_epic_lock(epic_folder):
            self.state["errors"].append({
                "plan": epic_folder,
                "error": "Another orchestration process is already running for this epic",
                "phase": "pre_check",
            })
            return False

        try:
            return self._process_plan_inner(epic_folder)
        finally:
            release_epic_lock(epic_folder)

    def _validate_planning_output(self, epic_folder: str) -> tuple[bool, list[str]]:
        """Pre-flight validation replacing planner-design and planner-reviewer.

        Checks ticket quality after explore agents finish. Returns (False, errors)
        for blocking issues (missing tickets, missing story references on build/test
        epics). Advisory warnings are logged but do not block.

        Args:
            epic_folder: Epic folder name.

        Returns:
            Tuple of (valid, issues). valid is False when blocking checks fail.
        """
        warnings: list[str] = []
        errors: list[str] = []
        repo = self.workflow._get_repository()
        if not repo:
            errors.append("No repository available — cannot validate")
            return False, errors

        epic_data = repo.get_epic(epic_folder)
        if not epic_data:
            errors.append(f"Epic {epic_folder} not found in TinyDB")
            return False, errors

        tickets = epic_data.tasks
        if not tickets:
            errors.append(f"No tickets found for {epic_folder} — planning produced no tickets")
            return False, errors

        # Check target_files (advisory)
        for t in tickets:
            target_files = getattr(t, "target_files", None) or getattr(t, "target_file", None)
            if not target_files:
                warnings.append(f"Ticket {t.id} missing target_files")

        # Check guidance/success_criteria (advisory)
        for t in tickets:
            guidance = getattr(t, "guidance", None) or ""
            criteria = getattr(t, "success_criteria", None) or ""
            if not guidance.strip() and not criteria.strip():
                warnings.append(f"Ticket {t.id} missing both guidance and success_criteria")

        # Check agent_type references (advisory)
        known_agents = {
            "build-python", "build-flutter", "build-story-writer", "build-docs-writer",
            "test-builder", "test-audit", "test-uat", "trace-explorer",
            "teacher-update-guidance", "teacher-update-assets",
            "planner-audit", "deploy-cicd",
        }
        for t in tickets:
            agent = getattr(t, "agent", None) or getattr(t, "agent_type", None) or ""
            if agent and agent not in known_agents:
                warnings.append(f"Ticket {t.id} references unknown agent '{agent}'")

        # @story US-003
        # BLOCKING: Story references required per-ticket for build-plan epics
        # Per planning-standard.yml FENCE: STORY-FIRST PLANNING
        # At this point, build-story-writer has succeeded and the story file exists.
        # Explore agents should have populated story_ids on tickets.
        try:
            from agenticguidance.services.epic import EpicService

            epic_svc = EpicService()
            is_build = epic_svc.is_build_plan(epic_folder)
        except ImportError:
            is_build = False

        if is_build:
            for t in tickets:
                ticket_stories = getattr(t, "story_ids", None) or []
                if not ticket_stories:
                    errors.append(
                        f"Ticket {t.id} missing story_ids — "
                        "required for build-plan epics "
                        "(per FENCE: STORY-FIRST PLANNING in planning-standard.yml)"
                    )

        for w in warnings:
            logger.warning("Pre-flight validation: %s", w)
        for e in errors:
            logger.error("Pre-flight validation: %s", e)

        if errors:
            logger.error("Pre-flight validation FAILED for %s: %d errors", epic_folder, len(errors))
            return False, errors

        if not warnings:
            logger.info("Pre-flight validation passed for %s", epic_folder)
        else:
            logger.info("Pre-flight validation: %d warnings for %s", len(warnings), epic_folder)

        return True, warnings

    def _enrich_tickets_from_stories(self, epic_folder: str) -> tuple[int, int]:
        """Enrich tickets with target_files derived from story→code mappings.

        Runs `agentic stories sync` to populate TinyDB with story→code node IDs,
        then for each ticket that has story_ids set, resolves the associated source
        files and writes them back as target_files.

        Args:
            epic_folder: Epic folder name.

        Returns:
            Tuple of (enriched_count, unenriched_count). enriched = tickets that
            received target_files from story tags; unenriched = tickets with no
            story tags or no code matches.
        """
        # Sync story→code mappings into TinyDB first
        sync_result = subprocess.run(
            ["agentic", "stories", "sync"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=self.workflow.working_dir,
        )
        if sync_result.returncode != 0:
            logger.warning(
                "stories sync returned non-zero (%d) — proceeding anyway: %s",
                sync_result.returncode,
                sync_result.stderr[:200],
            )

        repo = self.workflow._get_repository()
        if repo is None:
            logger.warning("No EpicRepository available — cannot enrich tickets from stories")
            return (0, 0)

        epic_data = repo.get_epic(epic_folder)
        if epic_data is None:
            logger.warning("Epic %s not found in TinyDB — cannot enrich tickets", epic_folder)
            return (0, 0)

        tickets = epic_data.tasks or []
        enriched_count = 0
        unenriched_count = 0

        for ticket in tickets:
            story_ids = getattr(ticket, "story_ids", None) or []
            if not story_ids:
                unenriched_count += 1
                continue

            # Collect unique file paths from all story node IDs
            file_paths: set[str] = set()
            for story_id in story_ids:
                try:
                    nodeids = repo.get_code_for_story(story_id)
                    for nodeid in nodeids:
                        file_paths.add(nodeid.split("::")[0])
                except Exception as e:
                    logger.debug(
                        "get_code_for_story(%s) failed for ticket %s: %s",
                        story_id, ticket.id, e,
                    )

            if not file_paths:
                unenriched_count += 1
                continue

            files = sorted(file_paths)
            updated = repo.update_ticket(epic_folder, ticket.id, {"target_files": files})
            if updated:
                enriched_count += 1
                logger.debug(
                    "Enriched ticket %s with %d target files from story tags",
                    ticket.id, len(files),
                )
            else:
                logger.warning(
                    "Failed to update target_files for ticket %s in %s",
                    ticket.id, epic_folder,
                )
                unenriched_count += 1

        logger.info(
            "Ticket enrichment for %s: enriched=%d, unenriched=%d",
            epic_folder, enriched_count, unenriched_count,
        )
        return (enriched_count, unenriched_count)

    def _process_plan_inner(self, epic_folder: str) -> bool:
        """Inner implementation of _process_plan (lock already held).

        Pipeline (5 steps + promotion):
        1. Epic Creator    → scaffold phases + skeleton tickets
        2. Story Writer    → generate user stories + categories → docs/userstories/EpicStories/
        3. Parallel Explore → N agents, one per category
        4. Pre-flight      → Python validation (advisory, replaces design+review)
        5. Orchestration   → create TinyDB phase records with agent routing
        6. Ticket Promotion → proposed → pending
        """
        logger.info("Processing epic: %s", epic_folder)

        # Auto-register epic in TinyDB if not already registered
        repo = self.workflow._get_repository()
        if repo:
            from agenticcli.commands.epic import _ensure_epic_in_db
            epic_path = self.workflow.epics_dir / epic_folder
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

        # Refresh TinyDB cache — epic-creator wrote tickets from a separate process
        if self.workflow._repository:
            self.workflow._repository.refresh()

        # Ensure EpicStories directory exists for story agent output.
        stories_dir = get_epic_stories_path(epic_folder).parent
        stories_dir.mkdir(parents=True, exist_ok=True)

        # 2. Story generation: run story agent
        story_result = self.workflow.spawn_story_agent(epic_folder)
        self.workflow._validate_result(story_result, "build-story-writer")
        if self._track_cost(story_result):
            return False
        if story_result.status != "completed":
            self.state["errors"].append({
                "plan": epic_folder,
                "error": f"Story agent failed: {story_result.result[:200]}",
                "phase": "story_generation",
            })
            return False

        # File readiness gate: wait for story file to exist and have content
        # before attempting to parse.  This guards against filesystem sync delay
        # after the story agent process exits (separate from parse retry logic).
        stories_path = get_epic_stories_path(epic_folder)
        if not self._wait_for_file_ready(stories_path):
            self.state["errors"].append({
                "plan": epic_folder,
                "error": (
                    "Story file not ready after build-story-writer completed — "
                    "file missing or empty"
                ),
                "phase": "story_parsing",
            })
            return False

        # Parse categories from story file (written by the story agent).
        # Stories are REQUIRED — if missing or empty, abort the pipeline.
        story_categories = self._parse_story_categories(epic_folder)
        if story_categories is None:
            self.state["errors"].append({
                "plan": epic_folder,
                "error": "Story file missing or invalid after build-story-writer completed — stories are required",
                "phase": "story_parsing",
            })
            return False
        if not story_categories:
            self.state["errors"].append({
                "plan": epic_folder,
                "error": "Story file has no categories — build-story-writer must define at least one category",
                "phase": "story_parsing",
            })
            return False

        # Refresh TinyDB cache — build-story-writer may have modified data from a separate process
        if self.workflow._repository:
            self.workflow._repository.refresh()

        # 3. Explore: optionally skip if all tickets already enriched from story tags
        _skip_explore = False
        try:
            enriched, unenriched = self._enrich_tickets_from_stories(epic_folder)
            if unenriched == 0 and enriched > 0:
                logger.info(
                    "All tickets enriched from story tags — skipping explore (%d tickets enriched)",
                    enriched,
                )
                _skip_explore = True
            else:
                logger.info(
                    "Story enrichment: %d enriched, %d unenriched — proceeding with explore",
                    enriched, unenriched,
                )
        except Exception as e:
            logger.warning("Story enrichment failed (%s) — falling through to explore", e)

        if not _skip_explore:
            explore_result = self.workflow.spawn_explore_agents(epic_folder, categories=story_categories)
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

        # Refresh TinyDB cache — explore agents wrote tickets from separate processes
        if self.workflow._repository:
            self.workflow._repository.refresh()

        # 4. Pre-flight validation (blocking for story requirements)
        valid, issues = self._validate_planning_output(epic_folder)
        if not valid:
            self.state["errors"].append({
                "plan": epic_folder,
                "error": f"Pre-flight validation failed: {'; '.join(issues[:3])}",
                "phase": "validation",
            })
            return False

        # 5. Orchestration: create TinyDB phase records with agent routing
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

        # 6. Promote all "proposed" tickets to "pending" to signal planning is done.
        # Without this, the loop's termination check (all tickets proposed → re-plan)
        # would rediscover this epic and create an infinite re-planning loop.
        if self.workflow._repository:
            # Refresh after orchestration agent wrote from a separate process
            self.workflow._repository.refresh()
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
                    if still_proposed > 0:
                        logger.warning(
                            "Promotion incomplete: %d tickets still proposed, force-retrying",
                            still_proposed,
                        )
                        for t in epic_data_after.tasks:
                            if t.status == "proposed":
                                self.workflow._repository.update_ticket(
                                    epic_folder, t.id, {"status": "pending"}
                                )

        # Promote epic status: planning → in_progress (if preconditions met)
        # or planning → blocked (if deps unsatisfied)
        if self.workflow._repository:
            try:
                self.workflow._repository.transition_epic_status(epic_folder, "in_progress")
                logger.info("Epic %s promoted to in_progress", epic_folder)
            except Exception as e:
                # If in_progress fails (e.g. blocked deps), try blocked
                logger.info(
                    "Cannot promote %s to in_progress (%s), trying blocked",
                    epic_folder, e,
                )
                try:
                    self.workflow._repository.transition_epic_status(epic_folder, "blocked")
                    logger.info("Epic %s set to blocked", epic_folder)
                except Exception:
                    logger.warning("Could not transition %s after planning", epic_folder)

        logger.info("Epic %s processed successfully (with orchestration phases)", epic_folder)
        return True
