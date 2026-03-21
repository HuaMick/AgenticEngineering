"""Integration tests for EpicService with real epic folders in the repo."""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.story("US-PLN-082")

from agenticguidance.services.epic import EpicService


class TestEpicServiceIntegration:
    """Integration tests using real epic folders in the repository."""

    @pytest.fixture
    def repo_root(self):
        """Get the repository root directory."""
        # Find repo root by looking for .git directory
        current = Path(__file__).resolve()
        while current != current.parent:
            if (current / ".git").exists():
                return current
            current = current.parent
        pytest.skip("Not in a git repository")

    @pytest.fixture
    def service(self, repo_root):
        """Create EpicService instance with real repo path."""
        return EpicService(repo_path=repo_root)

    def test_list_epics_returns_existing_live_epics(self, service, repo_root):
        """Test list_epics returns existing live epics from the repo."""
        epics_dir = repo_root / "docs" / "epics" / "live"

        if not epics_dir.exists():
            pytest.skip("No docs/epics/live directory in repository")

        # Get actual epic folders
        actual_folders = [
            d.name for d in epics_dir.iterdir()
            if d.is_dir() and "_" in d.name and len(d.name.split("_")[0]) == 8
        ]

        if not actual_folders:
            pytest.skip("No live epics in repository")

        # List epics via service (TinyDB is the sole source of truth)
        epics = service.list_epics(status="live")

        # Skip if TinyDB has no live epic entries — folders may exist but not be
        # registered in TinyDB yet (e.g. in a fresh clone or during migration).
        if not epics:
            pytest.skip("No live epics registered in TinyDB")

        # Verify returned epic folder names are a subset of actual filesystem folders
        returned_names = {p.epic_folder_name for p in epics}
        for name in returned_names:
            assert name in actual_folders, (
                f"TinyDB epic {name!r} has no matching folder in docs/epics/live"
            )

    def test_get_epic_on_real_epic_returns_valid_data(self, service, repo_root):
        """Test get_epic on a real epic returns valid data."""
        epics_dir = repo_root / "docs" / "epics" / "live"

        if not epics_dir.exists():
            pytest.skip("No docs/epics/live directory in repository")

        # Find first valid epic folder
        epic_folder = None
        for d in epics_dir.iterdir():
            if d.is_dir() and "_" in d.name and len(d.name.split("_")[0]) == 8:
                # Check if it has epic files
                if list(d.glob("plan_*.yml")):
                    epic_folder = d
                    break

        if not epic_folder:
            pytest.skip("No valid epic with plan_*.yml files found")

        # Get epic by short ID
        epic_id = epic_folder.name.split("_")[0]
        epic = service.get_epic(epic_id)

        # Verify we got valid epic data
        assert epic is not None, f"Should retrieve epic {epic_id}"
        assert epic.epic_folder_name == epic_folder.name
        assert epic.epic_folder == epic_folder
        assert isinstance(epic.phases, list)
        assert isinstance(epic.tasks, list)

    def test_validate_real_epic_structure_passes(self, service, repo_root):
        """Test validate on all real epic structures passes."""
        epics_dir = repo_root / "docs" / "epics" / "live"

        if not epics_dir.exists():
            pytest.skip("No docs/epics/live directory in repository")

        epic_folders = [
            d for d in epics_dir.iterdir()
            if d.is_dir() and "_" in d.name
            and len(d.name.split("_")[0]) == 8
            and list(d.glob("plan_*.yml"))
        ]

        if not epic_folders:
            pytest.skip("No valid epic with plan_*.yml files found")

        failures = []
        for epic_folder in epic_folders:
            result = service.validate_epic_structure(epic_folder)
            if not result.valid:
                errors = "; ".join(result.errors)
                failures.append(f"{epic_folder.name}: {errors}")

        if failures:
            pytest.fail("Epic validation failed:\n" + "\n".join(f"  - {f}" for f in failures))

    def test_list_completed_epics(self, service, repo_root):
        """Test list_epics returns completed epics if they exist."""
        completed_dir = repo_root / "docs" / "epics" / "completed"

        if not completed_dir.exists():
            pytest.skip("No docs/epics/completed directory in repository")

        epics = service.list_epics(status="completed")

        # If there are completed folders, we should get results
        actual_folders = [
            d.name for d in completed_dir.iterdir()
            if d.is_dir() and "_" in d.name
        ]

        if actual_folders:
            assert len(epics) > 0, "Should return completed epics"

    def test_list_deferred_epics(self, service, repo_root):
        """Test list_epics returns deferred epics if they exist."""
        deferred_dir = repo_root / "docs" / "epics" / "deferred"

        if not deferred_dir.exists():
            pytest.skip("No docs/epics/deferred directory in repository")

        epics = service.list_epics(status="deferred")

        # If there are deferred folders, we should get results
        actual_folders = [
            d.name for d in deferred_dir.iterdir()
            if d.is_dir() and "_" in d.name
        ]

        if actual_folders:
            assert len(epics) > 0, "Should return deferred epics"

    def test_get_epic_tickets_from_real_epic(self, service, repo_root):
        """Test get_epic_tickets extracts tickets from a real epic."""
        epics_dir = repo_root / "docs" / "epics" / "live"

        if not epics_dir.exists():
            pytest.skip("No docs/epics/live directory in repository")

        # Find first epic with tickets
        epic_id = None
        for d in epics_dir.iterdir():
            if d.is_dir() and "_" in d.name and len(d.name.split("_")[0]) == 8:
                if list(d.glob("plan_*.yml")):
                    # Quick check if epic has tickets
                    epic_data = service.get_epic(d.name.split("_")[0])
                    if epic_data and epic_data.tasks:
                        epic_id = d.name.split("_")[0]
                        break

        if not epic_id:
            pytest.skip("No epic with tickets found")

        # Get tickets
        tasks = service.get_epic_tickets(epic_id)

        assert len(tasks) > 0, "Should extract tickets from epic"
        assert all(hasattr(t, "id") for t in tasks), "All tickets should have IDs"
        assert all(hasattr(t, "name") for t in tasks), "All tickets should have names"

    def test_resolve_epic_by_multiple_methods(self, service, repo_root):
        """Test epic can be resolved by ID, folder name, and path."""
        epics_dir = repo_root / "docs" / "epics" / "live"

        if not epics_dir.exists():
            pytest.skip("No docs/epics/live directory in repository")

        # Find first valid epic
        epic_folder = None
        for d in epics_dir.iterdir():
            if d.is_dir() and "_" in d.name and len(d.name.split("_")[0]) == 8:
                if list(d.glob("plan_*.yml")):
                    epic_folder = d
                    break

        if not epic_folder:
            pytest.skip("No valid epic found")

        epic_id = epic_folder.name.split("_")[0]
        folder_name = epic_folder.name

        # Test all resolution methods
        by_id = service.get_epic(epic_id)
        by_folder = service.get_epic(folder_name)
        by_rel_path = service.get_epic(f"docs/epics/live/{folder_name}")
        by_abs_path = service.get_epic(str(epic_folder))

        # All should resolve to the same epic
        assert by_id is not None
        assert by_folder is not None
        assert by_rel_path is not None
        assert by_abs_path is not None

        assert by_id.epic_folder_name == folder_name
        assert by_folder.epic_folder_name == folder_name
        assert by_rel_path.epic_folder_name == folder_name
        assert by_abs_path.epic_folder_name == folder_name

    def test_validate_nesting_no_false_positives_on_existing_epics(
        self, service, repo_root, tmp_path
    ):
        """Validate that nesting checks produce no false positives on existing epics.

        Creates tmp copies of existing live epics and runs validate_epic_structure()
        to confirm no spurious root-level-tasks errors are raised.
        """
        import shutil
        import yaml

        epics_dir = repo_root / "docs" / "epics" / "live"
        if not epics_dir.exists():
            pytest.skip("No docs/epics/live directory in repository")

        epic_folders = [
            d for d in epics_dir.iterdir()
            if d.is_dir()
            and "_" in d.name
            and len(d.name.split("_")[0]) == 8
            and list(d.glob("plan_*.yml"))
        ]

        if not epic_folders:
            pytest.skip("No valid epic with plan_*.yml files found")

        # Create a tmp repo structure and copy epics into it
        tmp_repo = tmp_path / "repo"
        tmp_repo.mkdir()
        (tmp_repo / ".git").mkdir()
        tmp_live = tmp_repo / "docs" / "epics" / "live"
        tmp_live.mkdir(parents=True)

        tmp_service = EpicService(repo_path=tmp_repo)

        false_positives = []
        for epic_folder in epic_folders:
            dst = tmp_live / epic_folder.name
            shutil.copytree(epic_folder, dst)

            result = tmp_service.validate_epic_structure(dst)

            # Check specifically for root-level task errors (nesting false positives)
            root_task_errors = [
                e for e in result.errors
                if "root" in e.lower() and "task" in e.lower()
            ]
            if root_task_errors:
                false_positives.append(
                    f"{epic_folder.name}: {'; '.join(root_task_errors)}"
                )

        if false_positives:
            pytest.fail(
                "Nesting validation false positives on existing epics:\n"
                + "\n".join(f"  - {fp}" for fp in false_positives)
            )
