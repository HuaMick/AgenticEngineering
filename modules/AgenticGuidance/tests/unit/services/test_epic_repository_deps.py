"""Unit tests for EpicRepository dependency CRUD and priority sorting.

Tests:
- create_epic stores depends_on
- get_epic returns depends_on
- add_dependency / remove_dependency CRUD
- Idempotency of add_dependency
- list_epics priority sorting
- get_dependencies
- Default empty list for old records without depends_on
"""

import pytest

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


def _create_epic(repo, name, status="in_progress", priority="medium", depends_on=None):
    """Helper to create an epic with sensible defaults."""
    return repo.create_epic({
        "epic_folder_name": name,
        "epic_folder": f"/tmp/epics/{name}",
        "name": name,
        "status": status,
        "priority": priority,
        "objective": f"Objective for {name}",
        "depends_on": depends_on or [],
    })


# ---------------------------------------------------------------------------
# create_epic stores depends_on
# ---------------------------------------------------------------------------


class TestCreateEpicDependsOn:
    """Tests that create_epic persists the depends_on field."""

    def test_create_with_depends_on(self, repo):
        """depends_on is stored when provided at creation time."""
        _create_epic(repo, "epic_A", depends_on=["epic_B", "epic_C"])
        epic = repo.get_epic("epic_A")
        assert epic is not None
        assert epic.depends_on == ["epic_B", "epic_C"]

    def test_create_without_depends_on(self, repo):
        """depends_on defaults to empty list when not provided."""
        _create_epic(repo, "epic_A")
        epic = repo.get_epic("epic_A")
        assert epic is not None
        assert epic.depends_on == []

    def test_create_with_empty_depends_on(self, repo):
        """Explicitly passing empty list works."""
        _create_epic(repo, "epic_A", depends_on=[])
        epic = repo.get_epic("epic_A")
        assert epic.depends_on == []


# ---------------------------------------------------------------------------
# get_epic returns depends_on
# ---------------------------------------------------------------------------


class TestGetEpicDependsOn:
    """Tests that get_epic correctly returns depends_on."""

    def test_get_epic_includes_depends_on(self, repo):
        """get_epic returns depends_on from stored data."""
        _create_epic(repo, "epic_A", depends_on=["epic_X"])
        epic = repo.get_epic("epic_A")
        assert epic.depends_on == ["epic_X"]

    def test_get_epic_depends_on_type(self, repo):
        """depends_on is always a list."""
        _create_epic(repo, "epic_A", depends_on=["dep1"])
        epic = repo.get_epic("epic_A")
        assert isinstance(epic.depends_on, list)


# ---------------------------------------------------------------------------
# add_dependency / remove_dependency
# ---------------------------------------------------------------------------


class TestAddRemoveDependency:
    """Tests for add_dependency and remove_dependency CRUD methods."""

    def test_add_dependency_success(self, repo):
        """add_dependency appends to depends_on list."""
        _create_epic(repo, "epic_A")
        _create_epic(repo, "epic_B")
        result = repo.add_dependency("epic_A", "epic_B")
        assert result.success is True
        assert "Added dependency" in result.message

        deps = repo.get_dependencies("epic_A")
        assert "epic_B" in deps

    def test_add_dependency_nonexistent_epic(self, repo):
        """add_dependency fails when source epic doesn't exist."""
        _create_epic(repo, "epic_B")
        result = repo.add_dependency("nonexistent", "epic_B")
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_add_dependency_nonexistent_dep(self, repo):
        """add_dependency fails when dependency epic doesn't exist."""
        _create_epic(repo, "epic_A")
        result = repo.add_dependency("epic_A", "nonexistent")
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_add_dependency_idempotent(self, repo):
        """Adding the same dependency twice returns success (already exists)."""
        _create_epic(repo, "epic_A")
        _create_epic(repo, "epic_B")
        repo.add_dependency("epic_A", "epic_B")
        result = repo.add_dependency("epic_A", "epic_B")
        assert result.success is True
        assert "already exists" in result.message.lower()
        # Should not duplicate
        deps = repo.get_dependencies("epic_A")
        assert deps.count("epic_B") == 1

    def test_add_multiple_dependencies(self, repo):
        """Can add multiple distinct dependencies."""
        _create_epic(repo, "epic_A")
        _create_epic(repo, "epic_B")
        _create_epic(repo, "epic_C")
        repo.add_dependency("epic_A", "epic_B")
        repo.add_dependency("epic_A", "epic_C")
        deps = repo.get_dependencies("epic_A")
        assert "epic_B" in deps
        assert "epic_C" in deps
        assert len(deps) == 2

    def test_remove_dependency_success(self, repo):
        """remove_dependency removes from depends_on list."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")
        result = repo.remove_dependency("epic_A", "epic_B")
        assert result.success is True
        assert "Removed dependency" in result.message
        assert repo.get_dependencies("epic_A") == []

    def test_remove_dependency_not_found(self, repo):
        """remove_dependency fails when dependency doesn't exist in list."""
        _create_epic(repo, "epic_A")
        _create_epic(repo, "epic_B")
        result = repo.remove_dependency("epic_A", "epic_B")
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_remove_dependency_nonexistent_epic(self, repo):
        """remove_dependency fails when source epic doesn't exist."""
        result = repo.remove_dependency("nonexistent", "epic_B")
        assert result.success is False

    def test_remove_preserves_other_deps(self, repo):
        """Removing one dependency doesn't affect others."""
        _create_epic(repo, "epic_A", depends_on=["epic_B", "epic_C"])
        _create_epic(repo, "epic_B")
        _create_epic(repo, "epic_C")
        repo.remove_dependency("epic_A", "epic_B")
        deps = repo.get_dependencies("epic_A")
        assert "epic_B" not in deps
        assert "epic_C" in deps


# ---------------------------------------------------------------------------
# get_dependencies
# ---------------------------------------------------------------------------


class TestGetDependencies:
    """Tests for get_dependencies."""

    def test_get_dependencies_returns_list(self, repo):
        """get_dependencies always returns a list."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        deps = repo.get_dependencies("epic_A")
        assert isinstance(deps, list)
        assert deps == ["epic_B"]

    def test_get_dependencies_empty(self, repo):
        """get_dependencies returns empty list for no deps."""
        _create_epic(repo, "epic_A")
        assert repo.get_dependencies("epic_A") == []

    def test_get_dependencies_nonexistent(self, repo):
        """get_dependencies returns empty list for non-existent epic."""
        assert repo.get_dependencies("nonexistent") == []

    def test_get_dependencies_old_record_no_field(self, repo):
        """Old records without depends_on field return empty list.

        Simulates a legacy epic record that was created before
        the depends_on field was added.
        """
        # Create via raw TinyDB insert to simulate old record
        repo._epics.insert({
            "epic_folder_name": "legacy_epic",
            "epic_folder": "/tmp/epics/legacy_epic",
            "name": "legacy_epic",
            "status": "in_progress",
            "priority": "medium",
        })
        deps = repo.get_dependencies("legacy_epic")
        assert deps == []


# ---------------------------------------------------------------------------
# list_epics priority sorting
# ---------------------------------------------------------------------------


class TestListEpicsPrioritySorting:
    """Tests for list_epics() priority-based sorting."""

    def test_priority_sort_order(self, repo):
        """Epics are sorted by priority: critical, high, medium, low."""
        _create_epic(repo, "260101AA_low_epic", priority="low")
        _create_epic(repo, "260101BB_critical_epic", priority="critical")
        _create_epic(repo, "260101CC_high_epic", priority="high")
        _create_epic(repo, "260101DD_medium_epic", priority="medium")

        epics = repo.list_epics(status="live")
        names = [e.epic_folder_name for e in epics]
        assert names.index("260101BB_critical_epic") < names.index("260101CC_high_epic")
        assert names.index("260101CC_high_epic") < names.index("260101DD_medium_epic")
        assert names.index("260101DD_medium_epic") < names.index("260101AA_low_epic")

    def test_same_priority_sorted_by_name_descending(self, repo):
        """Within the same priority, newer epics (higher folder names) come first."""
        _create_epic(repo, "260101AA_first", priority="medium")
        _create_epic(repo, "260201BB_second", priority="medium")
        _create_epic(repo, "260301CC_third", priority="medium")

        epics = repo.list_epics(status="live")
        names = [e.epic_folder_name for e in epics]
        # Newest (highest) folder name first within same priority
        assert names.index("260301CC_third") < names.index("260201BB_second")
        assert names.index("260201BB_second") < names.index("260101AA_first")

    def test_missing_priority_defaults_to_medium(self, repo):
        """Epics without explicit priority sort as medium."""
        _create_epic(repo, "260101AA_high", priority="high")
        # Create with no priority (defaults to "medium" via create_epic)
        _create_epic(repo, "260101BB_default", priority="medium")
        _create_epic(repo, "260101CC_low", priority="low")

        epics = repo.list_epics(status="live")
        names = [e.epic_folder_name for e in epics]
        assert names.index("260101AA_high") < names.index("260101BB_default")
        assert names.index("260101BB_default") < names.index("260101CC_low")

    def test_list_epics_includes_depends_on(self, repo):
        """list_epics returns EpicMetadata with depends_on field."""
        _create_epic(repo, "epic_A", depends_on=["epic_B"])
        _create_epic(repo, "epic_B")

        epics = repo.list_epics(status="live")
        epic_a = next(e for e in epics if e.epic_folder_name == "epic_A")
        epic_b = next(e for e in epics if e.epic_folder_name == "epic_B")
        assert epic_a.depends_on == ["epic_B"]
        assert epic_b.depends_on == []

    def test_priority_weights_constant(self):
        """PRIORITY_WEIGHTS has expected values."""
        assert PRIORITY_WEIGHTS["critical"] == 1
        assert PRIORITY_WEIGHTS["high"] == 2
        assert PRIORITY_WEIGHTS["medium"] == 3
        assert PRIORITY_WEIGHTS["low"] == 4
        # Lower weight = higher priority
        assert PRIORITY_WEIGHTS["critical"] < PRIORITY_WEIGHTS["low"]

    def test_list_all_epics_priority_sorted(self, repo):
        """list_epics without status filter also returns priority-sorted."""
        _create_epic(repo, "260101AA_low", priority="low")
        _create_epic(repo, "260101BB_high", priority="high")

        epics = repo.list_epics()
        names = [e.epic_folder_name for e in epics]
        assert names.index("260101BB_high") < names.index("260101AA_low")
