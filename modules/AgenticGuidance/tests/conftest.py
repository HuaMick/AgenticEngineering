"""Pytest configuration and fixtures for AgenticGuidance tests."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


def pytest_addoption(parser):
    """Register story_strict ini option."""
    parser.addini(
        "story_strict",
        type="bool",
        default=False,
        help="When true, unknown @pytest.mark.story IDs cause test failure instead of warnings",
    )


def pytest_configure(config):
    """Register custom markers for AgenticGuidance tests."""
    config.addinivalue_line(
        "markers",
        "story(*story_ids): marks tests that validate specific user stories "
        "(format: @pytest.mark.story('US-XXX-NNN'))",
    )


# ---------------------------------------------------------------------------
# Story marker validation plugin
# ---------------------------------------------------------------------------

def _find_repo_root_from_tests():
    """Walk up from this conftest.py to find the repo root (.git dir)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return None


def _load_valid_story_ids():
    """Load all valid story IDs from docs/userstories/ YAML files.

    Returns a dict mapping story ID -> lifecycle state (e.g. {'US-STR-001': 'implemented'}).
    Returns an empty dict if the directory doesn't exist (e.g. in CI).
    """
    repo_root = _find_repo_root_from_tests()
    if not repo_root:
        return {}
    userstories_dir = repo_root / "docs" / "userstories"
    if not userstories_dir.exists():
        return {}

    valid_ids = {}
    for yml_file in userstories_dir.glob("**/*.yml"):
        if yml_file.name == "00_metadata.yml":
            continue
        try:
            content = yaml.safe_load(yml_file.read_text())
        except Exception:
            continue
        if not content or not isinstance(content, dict):
            continue
        for key in ("stories", "user_stories"):
            items = content.get(key, [])
            if not isinstance(items, list):
                continue
            for story in items:
                if isinstance(story, dict) and "id" in story:
                    valid_ids[story["id"]] = story.get("lifecycle", "implemented")
    return valid_ids


# Module-level cache so IDs are loaded at most once per test session.
_VALID_STORY_IDS: dict | None = None


def pytest_collection_modifyitems(config, items):
    """Validate that @pytest.mark.story markers reference known story IDs.

    In default mode: issues pytest warnings for unknown story IDs.
    When story_strict = true in pyproject.toml: unknown story IDs cause test failure.
    Also warns about tests referencing proposal or deprecated stories.
    """
    global _VALID_STORY_IDS  # noqa: PLW0603

    strict_mode = config.getini("story_strict")

    for item in items:
        for marker in item.iter_markers("story"):
            if not marker.args:
                msg = f"@pytest.mark.story on {item.nodeid} has no story IDs"
                if strict_mode:
                    pytest.fail(msg)
                else:
                    item.warn(UserWarning(msg))
                continue

            # Lazy-load valid IDs on first encounter
            if _VALID_STORY_IDS is None:
                _VALID_STORY_IDS = _load_valid_story_ids()

            # Skip validation if we couldn't find the stories directory
            if not _VALID_STORY_IDS:
                return

            for story_id in marker.args:
                if story_id not in _VALID_STORY_IDS:
                    msg = (
                        f"@pytest.mark.story references unknown story ID "
                        f"'{story_id}' — not found in docs/userstories/"
                    )
                    if strict_mode:
                        pytest.fail(msg)
                    else:
                        item.warn(UserWarning(msg))
                else:
                    lifecycle = _VALID_STORY_IDS[story_id]
                    if lifecycle == "proposal":
                        msg = (
                            f"@pytest.mark.story references proposal story "
                            f"'{story_id}' — promote to under-construction before testing"
                        )
                        if strict_mode:
                            pytest.fail(msg)
                        else:
                            item.warn(UserWarning(msg))
                    elif lifecycle == "deprecated":
                        msg = (
                            f"@pytest.mark.story references deprecated story "
                            f"'{story_id}' — consider removing this test marker"
                        )
                        item.warn(UserWarning(msg))


def pytest_sessionfinish(session, exitstatus):
    """Print story marker coverage stats at end of test session."""
    marker_count = 0
    total_tests = session.testscollected or 0
    for item in (session.items or []):
        if any(item.iter_markers("story")):
            marker_count += 1
    if total_tests > 0:
        pct = marker_count / total_tests * 100
        tr = session.config.pluginmanager.get_plugin("terminalreporter")
        if tr:
            tr.write_sep("=", "story marker coverage")
            tr.write_line(
                f"  {marker_count}/{total_tests} tests have @pytest.mark.story markers ({pct:.0f}%)"
            )


@pytest.fixture(autouse=True)
def _isolate_tinydb(tmp_path):
    """Redirect all TinyDB writes to a per-test temp directory.

    Patches EpicRepository.__init__ to always use tmp_path/.agentic/epics.db
    when no explicit db_path is provided (i.e. the global default).
    """
    isolated_db_path = tmp_path / ".agentic" / "epics.db"
    isolated_db_path.parent.mkdir(parents=True, exist_ok=True)

    from agenticguidance.services.epic_repository import EpicRepository

    _original_init = EpicRepository.__init__

    def _patched_init(self, db_path=None, epics_base=None, auto_bootstrap=True):
        _original_init(self, db_path=db_path or isolated_db_path, epics_base=epics_base, auto_bootstrap=auto_bootstrap)

    with patch.object(EpicRepository, "__init__", _patched_init):
        with patch("agenticcli.commands.epic._get_repo_db_path", return_value=isolated_db_path):
            yield isolated_db_path


def populate_tinydb_from_yaml(db_path, epic_folder_name, epic_folder, yaml_data):
    """Populate TinyDB with epic/ticket data from a YAML-style dict.

    Args:
        db_path: Path to the TinyDB database file.
        epic_folder_name: Epic folder name.
        epic_folder: Path to the epic folder on disk, or None for folder-free epics.
        yaml_data: Dict with optional keys: name, status, phases, tasks.
    """
    from agenticguidance.services.epic_repository import EpicRepository

    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    repo.create_epic({
        "epic_folder_name": epic_folder_name,
        "epic_folder": str(epic_folder) if epic_folder else "",
        "name": yaml_data.get("name", epic_folder_name),
        "status": yaml_data.get("status", "active"),
    })

    phases = yaml_data.get("phases", [])
    for phase in phases:
        phase_name = phase.get("name", phase.get("id", "default"))
        # Create the phase record so get_epic() returns complete phase data
        repo.add_phase(epic_folder_name, {
            "name": phase_name,
            "phase_id": phase.get("phase_id", phase.get("id", "")),
            "description": phase.get("description", ""),
            "status": phase.get("status", "pending"),
            "execution": phase.get("execution", "sequential"),
        })
        tickets = phase.get("tickets", phase.get("tasks", []))
        for ticket in tickets:
            repo.add_ticket(epic_folder_name, phase_name, ticket)

    flat_tasks = yaml_data.get("tasks", [])
    for ticket in flat_tasks:
        repo.add_ticket(epic_folder_name, "default", ticket)

    repo.close()
    return repo


@pytest.fixture
def tinydb_populator(_isolate_tinydb):
    """Fixture providing a function to populate the isolated TinyDB.

    Usage:
        # With a disk folder:
        tinydb_populator("my_epic", tmp_path / "my_epic", {"name": "My Epic"})

        # Folder-free epic (no disk folder):
        tinydb_populator("my_epic", None, {"name": "My Epic"})
    """
    db_path = _isolate_tinydb

    def _populate(epic_folder_name, epic_folder, yaml_data):
        return populate_tinydb_from_yaml(db_path, epic_folder_name, epic_folder, yaml_data)

    return _populate


@pytest.fixture
def isolated_repo(_isolate_tinydb, tmp_path):
    """Provide a pre-configured EpicRepository pointing at the isolated DB."""
    from agenticguidance.services.epic_repository import EpicRepository
    repo = EpicRepository(db_path=_isolate_tinydb, auto_bootstrap=False)
    yield repo
    repo.close()
