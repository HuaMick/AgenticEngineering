"""Dependency Service - Cross-epic dependency management.

Provides cycle detection, validation, blocked/ready queries, and
topological sorting for epic dependency graphs. Uses EpicRepository
as the sole data store.
"""

import logging
from typing import Optional

from .epic_repository import EpicRepository, DEFAULT_PRIORITY, normalize_priority

logger = logging.getLogger(__name__)


class DependencyService:
    """Service for managing cross-epic dependencies.

    Provides dependency validation (cycle detection), blocked/ready
    queries, and topological execution ordering over the epic
    dependency graph stored in TinyDB.

    Args:
        repository: EpicRepository instance for data access.
    """

    def __init__(self, repository: EpicRepository):
        self._repo = repository

    # ------------------------------------------------------------------
    # Cycle Detection & Validation
    # ------------------------------------------------------------------

    def detect_cycle(self, epic_name: str, new_dep: str) -> bool:
        """Check whether adding a dependency would create a cycle.

        Performs a DFS from ``new_dep`` following existing depends_on
        edges to see if we can reach ``epic_name``. If so, adding
        ``epic_name -> new_dep`` would create a cycle.

        Args:
            epic_name: The epic that would gain a new dependency.
            new_dep: The epic that ``epic_name`` would depend on.

        Returns:
            True if adding the dependency would create a cycle.
        """
        # Resolve to actual folder names
        epic_doc = self._repo._find_epic_doc(epic_name)
        dep_doc = self._repo._find_epic_doc(new_dep)
        if not epic_doc or not dep_doc:
            return False  # Can't form a cycle if either doesn't exist

        actual_epic = epic_doc["epic_folder_name"]
        actual_dep = dep_doc["epic_folder_name"]

        # Self-dependency is always a cycle
        if actual_epic == actual_dep:
            return True

        # Build the full dependency graph
        graph = self.get_dependency_graph()

        # Simulate adding the new edge: actual_epic -> actual_dep
        # Then check if actual_dep can reach actual_epic via existing edges
        visited: set[str] = set()
        stack = [actual_dep]

        while stack:
            current = stack.pop()
            if current == actual_epic:
                return True
            if current in visited:
                continue
            visited.add(current)
            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    stack.append(neighbor)

        return False

    def validate_dependency(
        self, epic_name: str, dep_name: str
    ) -> tuple[bool, str]:
        """Validate whether a dependency can be added.

        Checks:
        1. Both epics exist.
        2. Not a self-dependency.
        3. Would not create a cycle.
        4. Dependency is not already present.

        Args:
            epic_name: The epic that would depend on another.
            dep_name: The proposed dependency.

        Returns:
            Tuple of (valid, message). If valid is False, message
            explains why.
        """
        epic_doc = self._repo._find_epic_doc(epic_name)
        if not epic_doc:
            return False, f"Epic not found: {epic_name}"

        dep_doc = self._repo._find_epic_doc(dep_name)
        if not dep_doc:
            return False, f"Dependency epic not found: {dep_name}"

        actual_epic = epic_doc["epic_folder_name"]
        actual_dep = dep_doc["epic_folder_name"]

        if actual_epic == actual_dep:
            return False, "An epic cannot depend on itself"

        # Check if already present
        current_deps = self._repo.get_dependencies(actual_epic)
        if actual_dep in current_deps:
            return False, f"Dependency already exists: {actual_epic} -> {actual_dep}"

        # Check for cycle
        if self.detect_cycle(actual_epic, actual_dep):
            return False, (
                f"Adding dependency would create a cycle: "
                f"{actual_epic} -> {actual_dep} -> ... -> {actual_epic}"
            )

        return True, "Dependency is valid"

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """Build an adjacency list of all epic dependencies for live epics.

        Returns:
            Dict mapping epic_folder_name to list of epic_folder_names
            it depends on. Epics with no dependencies have an empty list.
        """
        epics = self._repo.list_epics(status="live")
        graph: dict[str, list[str]] = {}
        for epic in epics:
            graph[epic.epic_folder_name] = list(epic.depends_on or [])
        return graph

    # ------------------------------------------------------------------
    # Blocked / Ready Queries
    # ------------------------------------------------------------------

    def _get_completed_epic_names(self) -> set[str]:
        """Return the set of epic_folder_names with status 'completed'."""
        completed = self._repo.list_epics(status="completed")
        return {e.epic_folder_name for e in completed}

    def is_blocked(self, epic_name: str) -> tuple[bool, list[str]]:
        """Check whether an epic is blocked by unsatisfied dependencies.

        An epic is blocked if any of its ``depends_on`` entries reference
        epics that are NOT completed.

        Args:
            epic_name: Epic folder name or short ID.

        Returns:
            Tuple of (is_blocked, unsatisfied_deps). ``unsatisfied_deps``
            contains the epic_folder_names of dependencies that are not
            yet completed.
        """
        deps = self._repo.get_dependencies(epic_name)
        if not deps:
            return False, []

        completed = self._get_completed_epic_names()
        unsatisfied = [d for d in deps if d not in completed]
        return bool(unsatisfied), unsatisfied

    def get_blocked_epics(self) -> list[str]:
        """Return epic_folder_names of all live epics that are blocked.

        An epic is blocked when at least one of its ``depends_on``
        entries has not yet reached 'completed' status.

        Returns:
            List of blocked epic_folder_names.
        """
        completed = self._get_completed_epic_names()
        graph = self.get_dependency_graph()
        blocked: list[str] = []
        for epic_name, deps in graph.items():
            if deps and any(d not in completed for d in deps):
                blocked.append(epic_name)
        return blocked

    def get_ready_epics(self) -> list[str]:
        """Return epic_folder_names of all live epics that are ready to execute.

        An epic is ready when all its dependencies are completed (or it
        has no dependencies).

        Returns:
            List of ready epic_folder_names.
        """
        completed = self._get_completed_epic_names()
        graph = self.get_dependency_graph()
        ready: list[str] = []
        for epic_name, deps in graph.items():
            if not deps or all(d in completed for d in deps):
                ready.append(epic_name)
        return ready

    # ------------------------------------------------------------------
    # Topological Sort / Execution Ordering
    # ------------------------------------------------------------------

    def get_execution_order(self) -> list[str]:
        """Return live epics in topological order respecting dependencies.

        Uses Kahn's algorithm. Epics with no dependencies come first.
        Within the same topological level, epics are sorted by priority
        weight (critical first) then by folder name (newest first).

        Returns:
            List of epic_folder_names in execution order. If a cycle
            exists, the cyclic epics are appended at the end.
        """
        graph = self.get_dependency_graph()
        all_nodes = set(graph.keys())

        # Build in-degree counts (only count edges within live epics)
        in_degree: dict[str, int] = {n: 0 for n in all_nodes}
        for node, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] = in_degree.get(dep, 0)  # ensure present
                    # Actually, in_degree tracks "who depends on me" — wrong direction.
                    # We need: for each node, count how many of its deps are in the live set.
                    pass

        # Recompute correctly: in_degree[n] = number of live deps n has
        in_degree = {n: 0 for n in all_nodes}
        # Reverse: for each node, count its live dependencies
        for node, deps in graph.items():
            live_deps = [d for d in deps if d in all_nodes]
            in_degree[node] = len(live_deps)

        # Get priority info for sorting within levels
        epics_meta = {e.epic_folder_name: e for e in self._repo.list_epics(status="live")}

        def _sort_key(name: str) -> tuple:
            meta = epics_meta.get(name)
            p = meta.priority if meta and meta.priority is not None else DEFAULT_PRIORITY
            return (
                p,
                [-ord(c) for c in name],
            )

        # Kahn's algorithm with priority-sorted queue
        queue = sorted(
            [n for n in all_nodes if in_degree[n] == 0],
            key=_sort_key,
        )
        result: list[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            # Find all nodes that depend on this node
            for other, deps in graph.items():
                if node in deps and other in in_degree:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        # Insert sorted
                        queue.append(other)
                        queue.sort(key=_sort_key)

        # Any remaining nodes are part of a cycle
        remaining = [n for n in all_nodes if n not in result]
        if remaining:
            remaining.sort(key=_sort_key)
            result.extend(remaining)

        return result
