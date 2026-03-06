"""Ralph Loop Service - Epic discovery and prioritization.

This service provides the brain of the Ralph Loop system, automatically discovering
epics, analyzing their state, and building a priority queue of actions to take.

The RalphLoopService handles:
- Discovery of all epics in docs/epics/live/
- Analysis of epic state (orchestration MMD, pending tasks, etc.)
- Priority queue building for action execution
- Tracking completion state across all epics

Epic State Detection:
- has_orchestration: True if orchestration_*.mmd file exists
- action_required: 'execute', 'needs_planning', 'blocked', or 'completed'
- pending_tasks: Count of tasks not yet completed
- current_task: The next task to execute (if any)

Priority Order:
1. Epics with action_required='execute' (has MMD, ready to run)
2. Epics with action_required='needs_planning' (needs MMD created)
3. Blocked epics (dependencies not met) - skipped
4. Completed epics - no action needed
"""

import json
import logging
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class EpicInfo:
    """Information about a discovered epic."""

    name: str
    path: Path
    status: str  # active, completed, deferred
    has_orchestration: bool  # True if has orchestration_*.mmd file
    action_required: str  # execute, needs_planning, blocked, completed
    dependencies: list[str] = field(default_factory=list)
    pending_tasks: int = 0
    completed_tasks: int = 0
    current_task: Optional[str] = None
    blocking_questions: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "path": str(self.path),
            "status": self.status,
            "has_orchestration": self.has_orchestration,
            "action_required": self.action_required,
            "dependencies": self.dependencies,
            "pending_tasks": self.pending_tasks,
            "completed_tasks": self.completed_tasks,
            "current_task": self.current_task,
            "blocking_questions": self.blocking_questions,
        }


@dataclass
class EpicAction:
    """A recommended action to take."""

    action: str  # execute, plan, complete, blocked
    plan_name: Optional[str] = None
    plan_path: Optional[Path] = None
    task_id: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "action": self.action,
            "plan": self.plan_name,
            "path": str(self.plan_path) if self.plan_path else None,
            "task": self.task_id,
            "reason": self.reason,
        }


# Backward-compatibility aliases
PlanInfo = EpicInfo
PlanAction = EpicAction


@dataclass
class IterationRecord:
    """Record of a single Ralph loop iteration."""

    number: int
    started_at: float  # timestamp
    ended_at: Optional[float] = None
    action_taken: str = ""  # execute:plan_name, plan:plan_name, none
    result: str = ""  # success, failure, skipped
    plans_completed: list[str] = field(default_factory=list)
    output_file: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "number": self.number,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "action_taken": self.action_taken,
            "result": self.result,
            "plans_completed": self.plans_completed,
            "output_file": self.output_file,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IterationRecord":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            number=data["number"],
            started_at=data["started_at"],
            ended_at=data.get("ended_at"),
            action_taken=data.get("action_taken", ""),
            result=data.get("result", ""),
            plans_completed=data.get("plans_completed", []),
            output_file=data.get("output_file"),
        )


@dataclass
class RalphState:
    """State of a Ralph loop session."""

    loop_id: str
    started_at: float
    current_iteration: int
    max_iterations: int
    status: str  # running, completed, stopped, failed
    prompt_file: Optional[str] = None
    tmux_session: Optional[str] = None
    iterations: list[IterationRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "loop_id": self.loop_id,
            "started_at": self.started_at,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "status": self.status,
            "prompt_file": self.prompt_file,
            "tmux_session": self.tmux_session,
            "iterations": [it.to_dict() for it in self.iterations],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RalphState":
        """Create from dictionary (JSON deserialization)."""
        iterations = [
            IterationRecord.from_dict(it_data) for it_data in data.get("iterations", [])
        ]
        return cls(
            loop_id=data["loop_id"],
            started_at=data["started_at"],
            current_iteration=data["current_iteration"],
            max_iterations=data["max_iterations"],
            status=data["status"],
            prompt_file=data.get("prompt_file"),
            tmux_session=data.get("tmux_session"),
            iterations=iterations,
        )


class RalphLoopService:
    """Service for Ralph Loop epic discovery and prioritization.

    Provides automated epic discovery, state analysis, and action prioritization
    for the Ralph Loop orchestration system.
    """

    def __init__(self, epics_dir: Optional[Path] = None):
        """Initialize Ralph Loop service.

        Args:
            epics_dir: Path to epics directory. Defaults to docs/epics/live
                      relative to git repository root.
        """
        if epics_dir is None:
            # Find git repo root
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                repo_root = Path(result.stdout.strip())
                epics_dir = repo_root / "docs" / "epics" / "live"
            except subprocess.CalledProcessError:
                # Fallback to current directory
                epics_dir = Path.cwd() / "docs" / "epics" / "live"

        self.epics_dir = epics_dir
        self.state_dir = Path.home() / ".agentic" / "ralph"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _has_orchestration_file(self, plan_path: Path) -> bool:
        """Check if plan has orchestration MMD file.

        Args:
            plan_path: Path to plan folder.

        Returns:
            True if orchestration_*.mmd file exists.
        """
        return len(list(plan_path.glob("orchestration_*.mmd"))) > 0

    def _has_blocking_questions(self, plan_path: Path) -> tuple[bool, int]:
        """Check whether a plan has pending blocking questions.

        Args:
            plan_path: Path to plan folder.

        Returns:
            Tuple of (has_blocking, count). Returns (False, 0) if the
            questions directory doesn't exist, there are no blocking
            questions, or the QuestionQueue service is unavailable.
        """
        try:
            from agenticguidance.services.question import QuestionQueue
        except ImportError:
            logger.warning("QuestionQueue service unavailable — skipping blocking question check")
            return (False, 0)

        try:
            queue = QuestionQueue(plan_path)
            blocking = queue.list_pending_questions(severity_filter="blocking")
            count = len(blocking)
            return (count > 0, count)
        except Exception:
            logger.warning(
                "Failed to check blocking questions for %s", plan_path.name, exc_info=True
            )
            return (False, 0)

    def _get_plan_status_from_cli(self, plan_name: str) -> dict:
        """Get plan status using agentic CLI.

        Args:
            plan_name: Name of the plan folder.

        Returns:
            Dictionary with plan status info from CLI.
            Returns empty dict on error.
        """
        try:
            result = subprocess.run(
                ["agentic", "--json", "plan", "status", "--plan", plan_name],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            return {}

    def _analyze_plan_file(self, plan_path: Path) -> tuple[int, int, Optional[str]]:
        """Analyze plan_build.yml for task counts and current task.

        Args:
            plan_path: Path to plan folder.

        Returns:
            Tuple of (pending_tasks, completed_tasks, current_task_id).
        """
        plan_build = plan_path / "plan_build.yml"
        if not plan_build.exists():
            return (0, 0, None)

        try:
            content = yaml.safe_load(plan_build.read_text())
        except yaml.YAMLError:
            return (0, 0, None)

        if not content:
            return (0, 0, None)

        pending = 0
        completed = 0
        current_task = None

        # Extract tasks from phases structure
        phases = content.get("phases", [])
        for phase in phases:
            tasks = phase.get("tickets", [])
            for task in tasks:
                status = task.get("status", "pending")
                if status == "completed":
                    completed += 1
                elif status == "in_progress":
                    pending += 1
                    if current_task is None:
                        current_task = task.get("id")
                else:  # pending
                    pending += 1
                    if current_task is None and status == "pending":
                        current_task = task.get("id")

        return (pending, completed, current_task)

    def _parse_dependencies(self, plan_path: Path) -> list[str]:
        """Parse depends_on from plan YAML files.

        Looks for:
        - dependencies.depends_on in plan_build.yml
        - Returns list of plan IDs that must complete first

        Args:
            plan_path: Path to plan folder.

        Returns:
            List of plan IDs (folder names) that this plan depends on.
        """
        plan_build = plan_path / "plan_build.yml"
        if not plan_build.exists():
            return []

        try:
            content = yaml.safe_load(plan_build.read_text())
        except yaml.YAMLError:
            return []

        if not content:
            return []

        dependencies_section = content.get("dependencies", {})

        # Handle different formats:
        # 1. dependencies: {depends_on: [...], required_by: [...]}  <- most common
        # 2. dependencies: [...]  <- code dependencies (not plan dependencies)
        if isinstance(dependencies_section, list):
            # This is a code dependencies list, not plan dependencies
            return []

        if not isinstance(dependencies_section, dict):
            return []

        depends_on = dependencies_section.get("depends_on", [])

        if not depends_on:
            return []

        # Handle both formats:
        # 1. List of strings: ["260203QF", "260203PS"]
        # 2. List of dicts: [{"plan_id": "260203QF", "description": "..."}]
        plan_ids = []
        for dep in depends_on:
            if isinstance(dep, str):
                plan_ids.append(dep)
            elif isinstance(dep, dict):
                plan_id = dep.get("plan_id")
                if plan_id:
                    plan_ids.append(plan_id)

        return plan_ids

    def _dependencies_met(
        self, plan_name: str, dependencies: list[str], completed_plans: set[str]
    ) -> bool:
        """Check if all dependencies for a plan are satisfied.

        Args:
            plan_name: Name of the plan to check.
            dependencies: List of plan IDs this plan depends on.
            completed_plans: Set of plan names that are completed.

        Returns:
            True if all dependencies are satisfied, False otherwise.
        """
        if not dependencies:
            return True

        for dep in dependencies:
            # Dependency can be either full folder name (260203QF_question_foundation)
            # or just plan ID (260203QF). Check both.
            matched = False
            for completed in completed_plans:
                if completed == dep or completed.startswith(f"{dep}_"):
                    matched = True
                    break
            if not matched:
                return False

        return True

    def _build_dependency_graph(self) -> dict[str, list[str]]:
        """Build graph of epic dependencies for topological ordering.

        Returns:
            Dictionary mapping epic names to list of epics they depend on.
        """
        graph = {}
        epics = self.discover_epics()

        for epic in epics:
            graph[epic.name] = epic.dependencies

        return graph

    def _detect_cycles(self) -> list[list[str]]:
        """Detect any cycles in the dependency graph.

        Returns:
            List of cycles, where each cycle is a list of epic names.
            Empty list if no cycles detected.
        """
        graph = self._build_dependency_graph()
        cycles = []

        # Track visited nodes and recursion stack
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> bool:
            """DFS to detect cycles. Returns True if cycle found."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            # Visit dependencies
            for dep in graph.get(node, []):
                # Find the full epic name for this dependency
                dep_full_name = None
                for epic_name in graph.keys():
                    if epic_name == dep or epic_name.startswith(f"{dep}_"):
                        dep_full_name = epic_name
                        break

                if dep_full_name is None:
                    # Dependency not found in graph - might be completed or missing
                    continue

                if dep_full_name not in visited:
                    if dfs(dep_full_name):
                        return True
                elif dep_full_name in rec_stack:
                    # Found a cycle - extract it from path
                    cycle_start_idx = path.index(dep_full_name)
                    cycle = path[cycle_start_idx:] + [dep_full_name]
                    cycles.append(cycle)
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        # Check each unvisited node
        for node in graph.keys():
            if node not in visited:
                dfs(node)

        return cycles

    def _get_completed_epics(self) -> set[str]:
        """Get set of plan names that are completed.

        Returns:
            Set of plan folder names that have all tasks completed.
        """
        completed = set()

        if not self.epics_dir.exists():
            return completed

        for epic_dir in self.epics_dir.iterdir():
            if not epic_dir.is_dir():
                continue

            # Skip hidden directories
            if epic_dir.name.startswith("."):
                continue

            # Check if it has plan_build.yml
            plan_build = epic_dir / "plan_build.yml"
            if not plan_build.exists():
                continue

            # Analyze for completion
            pending_tasks, completed_tasks, _ = self._analyze_plan_file(epic_dir)

            # Also check has_orchestration
            has_orchestration = self._has_orchestration_file(epic_dir)

            # Determine action
            action = self._determine_action_required(
                has_orchestration,
                pending_tasks,
                completed_tasks,
            )

            if action == "completed":
                completed.add(epic_dir.name)

        return completed

    def _determine_action_required(
        self,
        has_orchestration: bool,
        pending_tasks: int,
        completed_tasks: int,
    ) -> str:
        """Determine what action is required for a plan.

        Args:
            has_orchestration: Whether plan has orchestration MMD file.
            pending_tasks: Number of pending tasks.
            completed_tasks: Number of completed tasks.

        Returns:
            Action required: 'execute', 'needs_planning', 'blocked', or 'completed'.
        """
        # Check if all tasks are completed
        total_tasks = pending_tasks + completed_tasks

        # Empty plans: if no orchestration, they still need planning
        if total_tasks == 0 and not has_orchestration:
            return "needs_planning"

        if total_tasks == 0:
            return "completed"

        if pending_tasks == 0:
            return "completed"

        # Has orchestration and pending tasks - ready to execute
        if has_orchestration and pending_tasks > 0:
            return "execute"

        # No orchestration - needs planning
        if not has_orchestration:
            return "needs_planning"

        # Has orchestration but no pending tasks (might be empty plan)
        if has_orchestration and pending_tasks == 0:
            return "completed"

        # Default fallback
        return "needs_planning"

    def discover_epics(self) -> list[EpicInfo]:
        """Discover all epics in live/ directory.

        Returns:
            List of EpicInfo with status, has_orchestration, action_required, etc.
        """
        epics = []

        if not self.epics_dir.exists():
            return epics

        for epic_dir in self.epics_dir.iterdir():
            if not epic_dir.is_dir():
                continue

            # Skip hidden directories and non-epic folders
            if epic_dir.name.startswith("."):
                continue

            # Check if it has plan_build.yml (or any plan_*.yml)
            has_plan_file = len(list(epic_dir.glob("plan_*.yml"))) > 0
            if not has_plan_file:
                continue

            # Check for orchestration file
            has_orchestration = self._has_orchestration_file(epic_dir)

            # Analyze plan file for task counts
            pending_tasks, completed_tasks, current_task = self._analyze_plan_file(epic_dir)

            # Determine action required
            action_required = self._determine_action_required(
                has_orchestration,
                pending_tasks,
                completed_tasks,
            )

            # Get status from plan_build.yml
            plan_build = epic_dir / "plan_build.yml"
            status = "active"
            if plan_build.exists():
                try:
                    content = yaml.safe_load(plan_build.read_text())
                    if content:
                        status = content.get("status", "active")
                except yaml.YAMLError:
                    pass

            # Parse dependencies
            dependencies = self._parse_dependencies(epic_dir)

            # Check if dependencies are met
            completed_epics = self._get_completed_epics()
            if not self._dependencies_met(epic_dir.name, dependencies, completed_epics):
                # Override action to blocked if dependencies not met
                action_required = "blocked"

            # Check for blocking questions
            has_blocking, blocking_count = self._has_blocking_questions(epic_dir)
            if has_blocking and action_required not in ("completed",):
                action_required = "blocked"

            epic_info = EpicInfo(
                name=epic_dir.name,
                path=epic_dir,
                status=status,
                has_orchestration=has_orchestration,
                action_required=action_required,
                dependencies=dependencies,
                pending_tasks=pending_tasks,
                completed_tasks=completed_tasks,
                current_task=current_task,
                blocking_questions=blocking_count,
            )

            epics.append(epic_info)

        return epics

    def get_priority_queue(self) -> list[EpicAction]:
        """Build prioritized queue of actions.

        Priority order:
        1. Epics with action_required='execute' (has MMD, ready to run)
        2. Epics with action_required='needs_planning' (needs MMD created)
        3. Blocked epics (dependencies not met) - skip

        Returns:
            List of EpicAction ordered by priority.
        """
        epics = self.discover_epics()
        actions = []

        # Priority 1: Execute actions
        for epic in epics:
            if epic.action_required == "execute":
                actions.append(
                    EpicAction(
                        action="execute",
                        plan_name=epic.name,
                        plan_path=epic.path,
                        task_id=epic.current_task,
                        reason=f"Epic has orchestration and {epic.pending_tasks} pending task(s)",
                    )
                )

        # Priority 2: Needs planning actions
        for epic in epics:
            if epic.action_required == "needs_planning":
                actions.append(
                    EpicAction(
                        action="plan",
                        plan_name=epic.name,
                        plan_path=epic.path,
                        task_id=None,
                        reason="Epic needs orchestration MMD file",
                    )
                )

        # Priority 3: Blocked actions (for visibility, but not executable)
        for epic in epics:
            if epic.action_required == "blocked":
                # Find which dependencies are not yet completed
                completed_epics = self._get_completed_epics()
                unmet_deps = []
                for dep in epic.dependencies:
                    matched = False
                    for completed in completed_epics:
                        if completed == dep or completed.startswith(f"{dep}_"):
                            matched = True
                            break
                    if not matched:
                        unmet_deps.append(dep)

                reasons = []
                if unmet_deps:
                    reasons.append(f"Waiting for: {', '.join(unmet_deps)}")
                if epic.blocking_questions > 0:
                    q = epic.blocking_questions
                    if unmet_deps:
                        reasons.append(f"also blocked by {q} question(s)")
                    else:
                        reasons.append(f"Blocked by {q} pending blocking question(s)")
                reason = "; ".join(reasons) if reasons else "Blocked"

                actions.append(
                    EpicAction(
                        action="blocked",
                        plan_name=epic.name,
                        plan_path=epic.path,
                        task_id=None,
                        reason=reason,
                    )
                )

        return actions

    def get_next_action(self) -> Optional[EpicAction]:
        """Get the single highest-priority action to take.

        Returns:
            EpicAction or None if all epics complete.
        """
        queue = self.get_priority_queue()

        # Filter out blocked actions
        executable_actions = [a for a in queue if a.action != "blocked"]

        if not executable_actions:
            return None

        return executable_actions[0]

    def start_loop(
        self, prompt_file: Optional[str] = None, max_iterations: int = 20
    ) -> RalphState:
        """Initialize a new Ralph loop.

        Creates state directory if needed.
        Generates unique loop_id.
        Saves initial state to ~/.agentic/ralph/state.json

        Args:
            prompt_file: Optional path to prompt file for the loop.
            max_iterations: Maximum iterations for the loop (default 20).

        Returns:
            RalphState: The initialized loop state.

        Raises:
            RuntimeError: If a loop is already running.
        """
        # Check if a loop is already running
        existing_state = self._load_state()
        if existing_state and existing_state.status == "running":
            raise RuntimeError(
                f"A Ralph loop is already running (loop_id: {existing_state.loop_id}). "
                "Stop it first with stop_loop()."
            )

        # Generate unique loop ID
        loop_id = uuid.uuid4().hex[:12]

        # Create new state
        state = RalphState(
            loop_id=loop_id,
            started_at=time.time(),
            current_iteration=0,
            max_iterations=max_iterations,
            status="running",
            prompt_file=prompt_file,
            tmux_session=None,  # Can be set later if using tmux
            iterations=[],
        )

        # Save initial state
        self._save_state(state)

        return state

    def record_iteration(self, action: EpicAction, result: str) -> None:
        """Record what happened in this iteration.

        Updates current_iteration.
        Appends to iterations list.
        Saves state.

        Args:
            action: The action that was taken.
            result: Result of the action (success, failure, skipped).
        """
        state = self._load_state()
        if not state:
            raise RuntimeError("No active Ralph loop state found.")

        # Increment iteration counter
        state.current_iteration += 1

        # Build action_taken string
        action_taken = f"{action.action}"
        if action.plan_name:
            action_taken = f"{action.action}:{action.plan_name}"

        # Create iteration record
        iteration = IterationRecord(
            number=state.current_iteration,
            started_at=time.time(),
            ended_at=time.time(),  # Set immediately for now
            action_taken=action_taken,
            result=result,
            plans_completed=[],  # Can be updated later if needed
            output_file=None,  # Can be set if logs are saved
        )

        state.iterations.append(iteration)

        # Save updated state
        self._save_state(state)

    def get_state(self) -> Optional[RalphState]:
        """Get current loop state from file.

        Returns:
            RalphState or None if no loop state file exists.
        """
        return self._load_state()

    def stop_loop(self, reason: str = "user_requested") -> None:
        """Stop the running loop.

        Sets status to 'stopped'.
        Records stop reason.

        Args:
            reason: Reason for stopping (user_requested, completed, failed, max_iterations).
        """
        state = self._load_state()
        if not state:
            raise RuntimeError("No active Ralph loop state found.")

        # Determine final status based on reason
        if reason == "completed":
            state.status = "completed"
        elif reason == "failed":
            state.status = "failed"
        else:
            state.status = "stopped"

        # Save final state
        self._save_state(state)

    def _save_state(self, state: RalphState) -> None:
        """Atomic save of state to file.

        Uses temp file + rename pattern for atomic writes.

        Args:
            state: The RalphState to save.
        """
        state_file = self.state_dir / "state.json"
        temp_file = self.state_dir / f"state.json.tmp.{uuid.uuid4().hex[:8]}"

        try:
            # Write to temp file
            temp_file.write_text(json.dumps(state.to_dict(), indent=2))

            # Atomic rename
            temp_file.rename(state_file)
        except Exception:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            raise

    def _load_state(self) -> Optional[RalphState]:
        """Load state from file.

        Returns:
            RalphState or None if file doesn't exist or is invalid.
        """
        state_file = self.state_dir / "state.json"

        if not state_file.exists():
            return None

        try:
            data = json.loads(state_file.read_text())
            return RalphState.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            # Invalid state file
            return None

    def check_all_complete(self) -> bool:
        """Verify all epics are genuinely complete.

        Returns:
            True only if:
            - No epics with action_required='execute'
            - No epics with action_required='needs_planning'
            - All epics either completed or explicitly blocked
        """
        epics = self.discover_epics()

        for epic in epics:
            if epic.action_required in ("execute", "needs_planning"):
                return False

        return True

    def get_completion_status(self) -> dict:
        """Get detailed completion status across all epics.

        Returns:
            Dictionary with keys:
            - all_complete: bool - True if every epic is completed or blocked
            - blocked_by_deps: int - count of epics blocked by unmet dependencies
            - blocked_by_questions: int - count of epics blocked by questions
            - in_progress: int - count of epics with execute/needs_planning
            - completed: int - count of completed epics
            - can_emit_promise: bool - True only when in_progress==0 and
              blocked_by_questions==0 (dep-blocked is OK since those deps
              might be in other repos or already archived)
        """
        epics = self.discover_epics()
        completed_epics = self._get_completed_epics()

        in_progress = 0
        blocked_by_deps = 0
        blocked_by_questions = 0
        completed = 0

        for epic in epics:
            if epic.action_required in ("execute", "needs_planning"):
                in_progress += 1
            elif epic.action_required == "completed":
                completed += 1
            elif epic.action_required == "blocked":
                # Determine blocking reason(s) — an epic can be both
                has_unmet_deps = (
                    epic.dependencies
                    and not self._dependencies_met(
                        epic.name, epic.dependencies, completed_epics
                    )
                )
                if has_unmet_deps:
                    blocked_by_deps += 1
                if epic.blocking_questions > 0:
                    blocked_by_questions += 1

        all_complete = in_progress == 0 and blocked_by_deps == 0 and blocked_by_questions == 0

        return {
            "all_complete": all_complete,
            "blocked_by_deps": blocked_by_deps,
            "blocked_by_questions": blocked_by_questions,
            "in_progress": in_progress,
            "completed": completed,
            "can_emit_promise": in_progress == 0 and blocked_by_questions == 0,
        }
