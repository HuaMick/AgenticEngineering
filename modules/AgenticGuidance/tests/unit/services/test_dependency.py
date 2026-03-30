"""Unit tests for DependencyService - cycle detection, blocking, ordering.

Tests the DependencyService for:
- Cycle detection (A->B->C->A, self-reference)
- validate_dependency rejecting cycles and duplicates
- get_blocked_epics / get_ready_epics filtering
- topological_sort / get_execution_order
- get_dependency_graph correctness

Uses tmp_path TinyDB fixture for isolated data.
"""

import pytest

from agenticguidance.services.dependency import DependencyService
from agenticguidance.services.epic_repository import EpicRepository, PRIORITY_WEIGHTS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """Create an isolated EpicRepository backed by tmp_path."""
    db_path = tmp_path / "epics.db"
    r = EpicRepository(db_path=db_path, auto_bootstrap=False)
    yield r
    r.close()


@pytest.fixture
def svc(repo):
    """Create a DependencyService backed by the isolated repo."""
    return DependencyService(repository=repo)


def _create_epic(repo, name, status="in_progress", priority="medium", depends_on=None):
    """Helper to create an epic with sensible defaults."""
    repo.create_epic({
        "epic_folder_name": name,
        "epic_folder": f"/tmp/epics/{name}",
        "name": name,
        "status": status,
        "priority": priority,
        "objective": f"Objective for {name}",
        "depends_on": depends_on or [],
    })


# ---------------------------------------------------------------------------
# Cycle Detection
# ---------------------------------------------------------------------------


class TestDetectCycle:
    """Tests for DependencyService.detect_cycle()."""

    def test_self_reference_is_cycle(self, repo, svc):
        """Adding epic_A -> epic_A should be detected as a cycle."""
        _create_epic(repo, "epic_A")
        assert svc.detect_cycle("epic_A", "epic_A") is True

    def test_no_cycle_for_simple_dependency(self, repo, svc):
        """A -> B with no existing edges should not be a cycle."""
        _create_epic(repo, "epic_A")
        _create_epic(repo, "epic_B")
        assert svc.detect_cycle("epic_A", "epic_B") is False

    def test_direct_back_edge_is_cycle(self, repo, svc):
        """If A depends on B, adding B -> A creates a cycle."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")
        # A already depends on B; now B -> A would cycle
        assert svc.detect_cycle("epic_B", "epic_A") is True

    def test_transitive_cycle_a_b_c_a(self, repo, svc):
        """A -> B -> C already exists; adding C -> A creates a cycle."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B", depends_on=["epic_C"])
        _create_epic(repo, "epic_C")
        # C -> A would close the cycle C -> (via B) -> A
        assert svc.detect_cycle("epic_C", "epic_A") is True

    def test_no_cycle_for_diamond(self, repo, svc):
        """Diamond shape (A -> B, A -> C, B -> D, C -> D) has no cycles."""
        _create_epic(repo, "epic_A", depends_on=["epic_B", "epic_C"])
        _create_epic(repo, "epic_B", depends_on=["epic_D"])
        _create_epic(repo, "epic_C", depends_on=["epic_D"])
        _create_epic(repo, "epic_D")
        # Adding D -> B would cycle, but D -> (new node) is fine
        _create_epic(repo, "epic_E")
        assert svc.detect_cycle("epic_D", "epic_E") is False

    def test_nonexistent_epic_returns_false(self, repo, svc):
        """If either epic doesn't exist, can't form a cycle."""
        _create_epic(repo, "epic_A")
        assert svc.detect_cycle("epic_A", "nonexistent") is False
        assert svc.detect_cycle("nonexistent", "epic_A") is False

    def test_long_chain_no_cycle(self, repo, svc):
        """A -> B -> C -> D -> E with no back-edge; adding A -> E is not a cycle."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B", depends_on=["epic_C"])
        _create_epic(repo, "epic_C", depends_on=["epic_D"])
        _create_epic(repo, "epic_D", depends_on=["epic_E"])
        _create_epic(repo, "epic_E")
        # Adding A -> E is fine (A already transitively depends on E)
        assert svc.detect_cycle("epic_A", "epic_E") is False

    def test_long_chain_cycle(self, repo, svc):
        """A -> B -> C -> D -> E; adding E -> A creates a cycle."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B", depends_on=["epic_C"])
        _create_epic(repo, "epic_C", depends_on=["epic_D"])
        _create_epic(repo, "epic_D", depends_on=["epic_E"])
        _create_epic(repo, "epic_E")
        assert svc.detect_cycle("epic_E", "epic_A") is True


# ---------------------------------------------------------------------------
# validate_dependency
# ---------------------------------------------------------------------------


class TestValidateDependency:
    """Tests for DependencyService.validate_dependency()."""

    def test_valid_dependency(self, repo, svc):
        """A -> B when both exist and no cycle is valid."""
        _create_epic(repo, "epic_A")
        _create_epic(repo, "epic_B")
        valid, msg = svc.validate_dependency("epic_A", "epic_B")
        assert valid is True
        assert "valid" in msg.lower()

    def test_rejects_self_dependency(self, repo, svc):
        """An epic cannot depend on itself."""
        _create_epic(repo, "epic_A")
        valid, msg = svc.validate_dependency("epic_A", "epic_A")
        assert valid is False
        assert "itself" in msg.lower()

    def test_rejects_missing_epic(self, repo, svc):
        """If the source epic doesn't exist, validation fails."""
        _create_epic(repo, "epic_B")
        valid, msg = svc.validate_dependency("nonexistent", "epic_B")
        assert valid is False
        assert "not found" in msg.lower()

    def test_rejects_missing_dep(self, repo, svc):
        """If the dependency epic doesn't exist, validation fails."""
        _create_epic(repo, "epic_A")
        valid, msg = svc.validate_dependency("epic_A", "nonexistent")
        assert valid is False
        assert "not found" in msg.lower()

    def test_rejects_cycle(self, repo, svc):
        """Cycle-producing dependency is rejected."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")
        valid, msg = svc.validate_dependency("epic_B", "epic_A")
        assert valid is False
        assert "cycle" in msg.lower()

    def test_rejects_duplicate_dependency(self, repo, svc):
        """Adding a dependency that already exists is rejected."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")
        valid, msg = svc.validate_dependency("epic_A", "epic_B")
        assert valid is False
        assert "already exists" in msg.lower()


# ---------------------------------------------------------------------------
# get_dependency_graph
# ---------------------------------------------------------------------------


class TestGetDependencyGraph:
    """Tests for DependencyService.get_dependency_graph()."""

    def test_empty_graph(self, repo, svc):
        """No epics -> empty graph."""
        assert svc.get_dependency_graph() == {}

    def test_single_epic_no_deps(self, repo, svc):
        """One epic with no dependencies returns empty list."""
        _create_epic(repo, "epic_A")
        graph = svc.get_dependency_graph()
        assert graph == {"epic_A": []}

    def test_chain_graph(self, repo, svc):
        """A -> B -> C."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B", depends_on=["epic_C"])
        _create_epic(repo, "epic_C")
        graph = svc.get_dependency_graph()
        assert graph["epic_A"] == ["epic_B"]
        assert graph["epic_B"] == ["epic_C"]
        assert graph["epic_C"] == []

    def test_only_live_epics_included(self, repo, svc):
        """Completed epics should not appear in the dependency graph."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B", status="completed")
        graph = svc.get_dependency_graph()
        # Only live epic_A should be in graph
        assert "epic_A" in graph
        assert "epic_B" not in graph


# ---------------------------------------------------------------------------
# Blocked / Ready Queries
# ---------------------------------------------------------------------------


class TestBlockedReadyQueries:
    """Tests for is_blocked, get_blocked_epics, get_ready_epics."""

    def test_no_deps_is_not_blocked(self, repo, svc):
        """An epic with no dependencies is never blocked."""
        _create_epic(repo, "epic_A")
        blocked, unsatisfied = svc.is_blocked("epic_A")
        assert blocked is False
        assert unsatisfied == []

    def test_blocked_when_dep_incomplete(self, repo, svc):
        """An epic is blocked when its dependency is not completed."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")  # status=in_progress (not completed)
        blocked, unsatisfied = svc.is_blocked("epic_A")
        assert blocked is True
        assert "epic_B" in unsatisfied

    def test_not_blocked_when_dep_completed(self, repo, svc):
        """An epic is not blocked when its dependency is completed."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B", status="completed")
        blocked, unsatisfied = svc.is_blocked("epic_A")
        assert blocked is False
        assert unsatisfied == []

    def test_partially_blocked(self, repo, svc):
        """An epic with one satisfied and one unsatisfied dep is blocked."""
        _create_epic(repo, "epic_A", depends_on=["epic_B", "epic_C"])
        _create_epic(repo, "epic_B", status="completed")
        _create_epic(repo, "epic_C")  # in_progress
        blocked, unsatisfied = svc.is_blocked("epic_A")
        assert blocked is True
        assert unsatisfied == ["epic_C"]

    def test_get_blocked_epics(self, repo, svc):
        """get_blocked_epics returns only epics with unsatisfied deps."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")  # live, not completed
        _create_epic(repo, "epic_C")  # no deps
        blocked = svc.get_blocked_epics()
        assert "epic_A" in blocked
        assert "epic_B" not in blocked
        assert "epic_C" not in blocked

    def test_get_ready_epics(self, repo, svc):
        """get_ready_epics returns epics whose deps are all satisfied."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")  # live, not completed
        _create_epic(repo, "epic_C")  # no deps, ready
        ready = svc.get_ready_epics()
        assert "epic_A" not in ready
        assert "epic_B" in ready
        assert "epic_C" in ready

    def test_get_ready_epics_with_completed_deps(self, repo, svc):
        """Ready includes epics whose deps are all completed."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B", status="completed")
        _create_epic(repo, "epic_C")
        ready = svc.get_ready_epics()
        # epic_A should be ready since epic_B is completed
        assert "epic_A" in ready
        assert "epic_C" in ready

    def test_empty_returns_no_blocked(self, repo, svc):
        """No epics -> no blocked epics."""
        assert svc.get_blocked_epics() == []

    def test_empty_returns_no_ready(self, repo, svc):
        """No epics -> no ready epics."""
        assert svc.get_ready_epics() == []


# ---------------------------------------------------------------------------
# Topological Sort / Execution Ordering
# ---------------------------------------------------------------------------


class TestGetExecutionOrder:
    """Tests for DependencyService.get_execution_order()."""

    def test_empty_returns_empty(self, repo, svc):
        """No live epics -> empty execution order."""
        assert svc.get_execution_order() == []

    def test_single_epic(self, repo, svc):
        """One epic returns just that epic."""
        _create_epic(repo, "epic_A")
        order = svc.get_execution_order()
        assert order == ["epic_A"]

    def test_independent_epics_sorted_by_priority(self, repo, svc):
        """Independent epics should be sorted by priority weight."""
        _create_epic(repo, "epic_low", priority="low")
        _create_epic(repo, "epic_high", priority="high")
        _create_epic(repo, "epic_critical", priority="critical")
        _create_epic(repo, "epic_medium", priority="medium")
        order = svc.get_execution_order()
        # critical (1) < high (2) < medium (3) < low (4)
        assert order.index("epic_critical") < order.index("epic_high")
        assert order.index("epic_high") < order.index("epic_medium")
        assert order.index("epic_medium") < order.index("epic_low")

    def test_chain_respects_dependency_order(self, repo, svc):
        """A -> B -> C: C must come before B, B before A."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B", depends_on=["epic_C"])
        _create_epic(repo, "epic_C")
        order = svc.get_execution_order()
        assert order.index("epic_C") < order.index("epic_B")
        assert order.index("epic_B") < order.index("epic_A")

    def test_diamond_respects_ordering(self, repo, svc):
        """Diamond: A -> B, A -> C, B -> D, C -> D.
        D must come before B and C, B and C before A.
        """
        _create_epic(repo, "epic_A", depends_on=["epic_B", "epic_C"])
        _create_epic(repo, "epic_B", depends_on=["epic_D"])
        _create_epic(repo, "epic_C", depends_on=["epic_D"])
        _create_epic(repo, "epic_D")
        order = svc.get_execution_order()
        assert order.index("epic_D") < order.index("epic_B")
        assert order.index("epic_D") < order.index("epic_C")
        assert order.index("epic_B") < order.index("epic_A")
        assert order.index("epic_C") < order.index("epic_A")

    def test_priority_within_same_topo_level(self, repo, svc):
        """At the same topological level, higher priority comes first."""
        _create_epic(repo, "epic_base")
        _create_epic(repo, "epic_low", depends_on=["epic_base"], priority="low")
        _create_epic(repo, "epic_high", depends_on=["epic_base"], priority="high")
        order = svc.get_execution_order()
        # Both depend on base, so they're at the same level
        # high should come before low
        assert order[0] == "epic_base"
        assert order.index("epic_high") < order.index("epic_low")

    def test_cyclic_epics_appended_at_end(self, repo, svc):
        """If a cycle exists in the data, cyclic nodes are appended at end."""
        # Manually create a cycle by setting depends_on directly
        _create_epic(repo, "epic_X", depends_on=["epic_Y"])
        _create_epic(repo, "epic_Y", depends_on=["epic_X"])
        _create_epic(repo, "epic_Z")  # no deps, should come first
        order = svc.get_execution_order()
        # epic_Z has no deps so it comes first
        assert order[0] == "epic_Z"
        # The cyclic pair should still be in the list
        assert "epic_X" in order
        assert "epic_Y" in order
        assert len(order) == 3

    def test_all_epics_present_in_order(self, repo, svc):
        """All live epics appear in the execution order."""
        names = ["epic_A", "epic_B", "epic_C", "epic_D"]
        for name in names:
            _create_epic(repo, name)
        order = svc.get_execution_order()
        assert set(order) == set(names)

    def test_completed_epics_not_in_order(self, repo, svc):
        """Completed epics should not appear in execution order."""
        _create_epic(repo, "epic_A")
        _create_epic(repo, "epic_done", status="completed")
        order = svc.get_execution_order()
        assert "epic_A" in order
        assert "epic_done" not in order
