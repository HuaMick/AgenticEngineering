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

    Returns a frozenset of story ID strings (e.g. 'US-CLI-110').
    Returns an empty set if the directory doesn't exist (e.g. in CI).
    """
    repo_root = _find_repo_root_from_tests()
    if not repo_root:
        return frozenset()
    userstories_dir = repo_root / "docs" / "userstories"
    if not userstories_dir.exists():
        return frozenset()

    valid_ids = set()
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
                    valid_ids.add(story["id"])
    return frozenset(valid_ids)


# Module-level cache so IDs are loaded at most once per test session.
_VALID_STORY_IDS: frozenset | None = None


def pytest_collection_modifyitems(config, items):
    """Validate that @pytest.mark.story markers reference known story IDs.

    In default mode: issues pytest warnings for unknown story IDs.
    When story_strict = true in pyproject.toml: unknown story IDs cause test failure.
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
    """Redirect all TinyDB writes to a per-test temp directory."""
    isolated_db_path = tmp_path / ".agentic" / "epics.db"
    isolated_db_path.parent.mkdir(parents=True, exist_ok=True)

    from agenticguidance.services.epic import EpicService

    def _isolated_find_repo_root(start=None):
        return tmp_path

    with patch.object(EpicService, "_find_repo_root", staticmethod(_isolated_find_repo_root)):
        yield isolated_db_path


def populate_tinydb_from_yaml(db_path, epic_folder_name, epic_folder, yaml_data):
    """Populate TinyDB with epic/ticket data from a YAML-style dict.

    Args:
        db_path: Path to the TinyDB database file.
        epic_folder_name: Epic folder name.
        epic_folder: Path to the epic folder on disk.
        yaml_data: Dict with optional keys: name, status, phases, tasks.
    """
    from agenticguidance.services.epic_repository import EpicRepository

    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    repo.create_epic({
        "epic_folder_name": epic_folder_name,
        "epic_folder": str(epic_folder),
        "name": yaml_data.get("name", epic_folder_name),
        "status": yaml_data.get("status", "active"),
    })

    phases = yaml_data.get("phases", [])
    for phase in phases:
        phase_name = phase.get("name", phase.get("id", "default"))
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
    """Fixture providing a function to populate the isolated TinyDB."""
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
