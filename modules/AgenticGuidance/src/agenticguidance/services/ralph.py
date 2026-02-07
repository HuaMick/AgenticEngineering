"""Ralph Loop Service - Plan discovery and prioritization.

This service provides the brain of the Ralph Loop system, automatically discovering
plans, analyzing their state, and building a priority queue of actions to take.

The RalphLoopService handles:
- Discovery of all plans in docs/plans/live/
- Analysis of plan state (orchestration MMD, pending tasks, etc.)
- Priority queue building for action execution
- Tracking completion state across all plans

Plan State Detection:
- has_orchestration: True if orchestration_*.mmd file exists
- action_required: 'execute', 'needs_planning', 'blocked', or 'completed'
- pending_tasks: Count of tasks not yet completed
- current_task: The next task to execute (if any)

Priority Order:
1. Plans with action_required='execute' (has MMD, ready to run)
2. Plans with action_required='needs_planning' (needs MMD created)
3. Blocked plans (dependencies not met) - skipped
4. Completed plans - no action needed
"""

import json
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class PlanInfo:
    """Information about a discovered plan."""

    name: str
    path: Path
    status: str  # active, completed, deferred
    has_orchestration: bool  # True if has orchestration_*.mmd file
    action_required: str  # execute, needs_planning, blocked, completed
    dependencies: list[str] = field(default_factory=list)
    pending_tasks: int = 0
    completed_tasks: int = 0
    current_task: Optional[str] = None

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
        }


@dataclass
class PlanAction:
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
    """Service for Ralph Loop plan discovery and prioritization.

    Provides automated plan discovery, state analysis, and action prioritization
    for the Ralph Loop orchestration system.
    """

    def __init__(self, plans_dir: Optional[Path] = None):
        """Initialize Ralph Loop service.

        Args:
            plans_dir: Path to plans directory. Defaults to docs/plans/live
                      relative to git repository root.
        """
        if plans_dir is None:
            # Find git repo root
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                repo_root = Path(result.stdout.strip())
                plans_dir = repo_root / "docs" / "plans" / "live"
            except subprocess.CalledProcessError:
                # Fallback to current directory
                plans_dir = Path.cwd() / "docs" / "plans" / "live"

        self.plans_dir = plans_dir
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
                ["agentic", "plan", "status", "--plan", plan_name, "-j"],
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
            tasks = phase.get("tasks", [])
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
        """Build graph of plan dependencies for topological ordering.

        Returns:
            Dictionary mapping plan names to list of plans they depend on.
        """
        graph = {}
        plans = self.discover_plans()

        for plan in plans:
            graph[plan.name] = plan.dependencies

        return graph

    def _detect_cycles(self) -> list[list[str]]:
        """Detect any cycles in the dependency graph.

        Returns:
            List of cycles, where each cycle is a list of plan names.
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
                # Find the full plan name for this dependency
                dep_full_name = None
                for plan_name in graph.keys():
                    if plan_name == dep or plan_name.startswith(f"{dep}_"):
                        dep_full_name = plan_name
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

    def _get_completed_plans(self) -> set[str]:
        """Get set of plan names that are completed.

        Returns:
            Set of plan folder names that have all tasks completed.
        """
        completed = set()

        if not self.plans_dir.exists():
            return completed

        for plan_dir in self.plans_dir.iterdir():
            if not plan_dir.is_dir():
                continue

            # Skip hidden directories
            if plan_dir.name.startswith("."):
                continue

            # Check if it has plan_build.yml
            plan_build = plan_dir / "plan_build.yml"
            if not plan_build.exists():
                continue

            # Analyze for completion
            pending_tasks, completed_tasks, _ = self._analyze_plan_file(plan_dir)

            # Also check has_orchestration
            has_orchestration = self._has_orchestration_file(plan_dir)

            # Determine action
            action = self._determine_action_required(
                has_orchestration,
                pending_tasks,
                completed_tasks,
            )

            if action == "completed":
                completed.add(plan_dir.name)

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

        # Empty or corrupted plans (no tasks) are treated as completed
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

    def discover_plans(self) -> list[PlanInfo]:
        """Discover all plans in live/ directory.

        Returns:
            List of PlanInfo with status, has_orchestration, action_required, etc.
        """
        plans = []

        if not self.plans_dir.exists():
            return plans

        for plan_dir in self.plans_dir.iterdir():
            if not plan_dir.is_dir():
                continue

            # Skip hidden directories and non-plan folders
            if plan_dir.name.startswith("."):
                continue

            # Check if it has plan_build.yml (or any plan_*.yml)
            has_plan_file = len(list(plan_dir.glob("plan_*.yml"))) > 0
            if not has_plan_file:
                continue

            # Check for orchestration file
            has_orchestration = self._has_orchestration_file(plan_dir)

            # Analyze plan file for task counts
            pending_tasks, completed_tasks, current_task = self._analyze_plan_file(plan_dir)

            # Determine action required
            action_required = self._determine_action_required(
                has_orchestration,
                pending_tasks,
                completed_tasks,
            )

            # Get status from plan_build.yml
            plan_build = plan_dir / "plan_build.yml"
            status = "active"
            if plan_build.exists():
                try:
                    content = yaml.safe_load(plan_build.read_text())
                    if content:
                        status = content.get("status", "active")
                except yaml.YAMLError:
                    pass

            # Parse dependencies
            dependencies = self._parse_dependencies(plan_dir)

            # Check if dependencies are met
            completed_plans = self._get_completed_plans()
            if not self._dependencies_met(plan_dir.name, dependencies, completed_plans):
                # Override action to blocked if dependencies not met
                action_required = "blocked"

            plan_info = PlanInfo(
                name=plan_dir.name,
                path=plan_dir,
                status=status,
                has_orchestration=has_orchestration,
                action_required=action_required,
                dependencies=dependencies,
                pending_tasks=pending_tasks,
                completed_tasks=completed_tasks,
                current_task=current_task,
            )

            plans.append(plan_info)

        return plans

    def get_priority_queue(self) -> list[PlanAction]:
        """Build prioritized queue of actions.

        Priority order:
        1. Plans with action_required='execute' (has MMD, ready to run)
        2. Plans with action_required='needs_planning' (needs MMD created)
        3. Blocked plans (dependencies not met) - skip

        Returns:
            List of PlanAction ordered by priority.
        """
        plans = self.discover_plans()
        actions = []

        # Priority 1: Execute actions
        for plan in plans:
            if plan.action_required == "execute":
                actions.append(
                    PlanAction(
                        action="execute",
                        plan_name=plan.name,
                        plan_path=plan.path,
                        task_id=plan.current_task,
                        reason=f"Plan has orchestration and {plan.pending_tasks} pending task(s)",
                    )
                )

        # Priority 2: Needs planning actions
        for plan in plans:
            if plan.action_required == "needs_planning":
                actions.append(
                    PlanAction(
                        action="plan",
                        plan_name=plan.name,
                        plan_path=plan.path,
                        task_id=None,
                        reason="Plan needs orchestration MMD file",
                    )
                )

        # Priority 3: Blocked actions (for visibility, but not executable)
        for plan in plans:
            if plan.action_required == "blocked":
                # Find which dependencies are not yet completed
                completed_plans = self._get_completed_plans()
                unmet_deps = []
                for dep in plan.dependencies:
                    matched = False
                    for completed in completed_plans:
                        if completed == dep or completed.startswith(f"{dep}_"):
                            matched = True
                            break
                    if not matched:
                        unmet_deps.append(dep)

                reason = f"Waiting for: {', '.join(unmet_deps)}"
                actions.append(
                    PlanAction(
                        action="blocked",
                        plan_name=plan.name,
                        plan_path=plan.path,
                        task_id=None,
                        reason=reason,
                    )
                )

        return actions

    def get_next_action(self) -> Optional[PlanAction]:
        """Get the single highest-priority action to take.

        Returns:
            PlanAction or None if all plans complete.
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

    def record_iteration(self, action: PlanAction, result: str) -> None:
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
        """Verify all plans are genuinely complete.

        Returns:
            True only if:
            - No plans with action_required='execute'
            - No plans with action_required='needs_planning'
            - All plans either completed or explicitly blocked
        """
        plans = self.discover_plans()

        for plan in plans:
            if plan.action_required in ("execute", "needs_planning"):
                return False

        return True
