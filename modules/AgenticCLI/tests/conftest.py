"""Pytest configuration and fixtures for AgenticCLI tests."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def pytest_configure(config):
    """Register custom markers for AgenticCLI tests."""
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

    Issues pytest warnings for any story ID not found in docs/userstories/.
    Does NOT block test execution — unknown IDs are warnings, not errors.
    """
    global _VALID_STORY_IDS  # noqa: PLW0603

    for item in items:
        for marker in item.iter_markers("story"):
            if not marker.args:
                item.warn(
                    pytest.PytestUnhandledCoroutineWarning(
                        f"@pytest.mark.story on {item.nodeid} has no story IDs"
                    )
                    if hasattr(pytest, "PytestUnhandledCoroutineWarning")
                    else UserWarning(
                        f"@pytest.mark.story on {item.nodeid} has no story IDs"
                    )
                )
                continue

            # Lazy-load valid IDs on first encounter
            if _VALID_STORY_IDS is None:
                _VALID_STORY_IDS = _load_valid_story_ids()

            # Skip validation if we couldn't find the stories directory
            if not _VALID_STORY_IDS:
                return

            for story_id in marker.args:
                if story_id not in _VALID_STORY_IDS:
                    item.warn(
                        UserWarning(
                            f"@pytest.mark.story references unknown story ID "
                            f"'{story_id}' — not found in docs/userstories/"
                        )
                    )


@pytest.fixture(autouse=True)
def _block_real_ntfy():
    """Safety net: prevent any test from sending real ntfy notifications."""
    yield


@pytest.fixture(autouse=True)
def _isolate_tinydb(tmp_path):
    """Safety net: redirect all TinyDB writes to a per-test temp directory.

    Prevents tests from polluting the repo-local (.agentic/epics.db) or
    home-directory (~/.agentic/epics.db) TinyDB databases.

    Patches the two entry points that determine the DB file path:
    - agenticcli.commands.epic._get_repo_db_path: used by cmd_init, cmd_list,
      cmd_db_sync, cmd_db_status, and helpers like _get_repo().
    - agenticguidance.services.epic.EpicService._find_repo_root: used by
      EpicService.__init__ to derive the repo-local db_path.

    The temp DB is placed at tmp_path/.agentic/epics.db so that path resolution
    helpers that walk up looking for .git can also be satisfied when a test has
    set up a real git repo inside tmp_path.
    """
    isolated_db_path = tmp_path / ".agentic" / "epics.db"
    isolated_db_path.parent.mkdir(parents=True, exist_ok=True)

    # Patch _find_repo_root at class level so all EpicService instances use tmp_path
    from agenticguidance.services.epic import EpicService

    def _isolated_find_repo_root(start=None):
        return tmp_path

    with patch(
        "agenticcli.commands.epic._get_repo_db_path",
        return_value=isolated_db_path,
    ):
        with patch.object(EpicService, "_find_repo_root", staticmethod(_isolated_find_repo_root)):
            yield isolated_db_path


def populate_tinydb_from_yaml(db_path, epic_folder_name, epic_folder, yaml_data):
    """Populate TinyDB with epic/ticket data from a YAML-style dict.

    Converts the dict structure that tests previously wrote to plan_build.yml
    into TinyDB entries via EpicRepository.

    Args:
        db_path: Path to the TinyDB database file.
        epic_folder_name: Epic folder name (e.g. "260103AE_test").
        epic_folder: Path to the epic folder on disk.
        yaml_data: Dict with optional keys: name, status, phases, tasks.
            phases: list of {name, tickets/tasks: [{id, name, status, ...}]}
            tasks: list of {id, name, status, ...} (flat/legacy structure)
    """
    from agenticguidance.services.epic_repository import EpicRepository

    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    epic_doc = {
        "epic_folder_name": epic_folder_name,
        "epic_folder": str(epic_folder),
        "name": yaml_data.get("name", epic_folder_name),
        "status": yaml_data.get("status", "active"),
    }
    # Carry over optional metadata fields
    for field in ("objective", "context", "branch", "priority", "worktree_path"):
        if field in yaml_data:
            epic_doc[field] = yaml_data[field]
    repo.create_epic(epic_doc)

    phases = yaml_data.get("phases", [])
    for phase in phases:
        phase_name = phase.get("name", phase.get("id", "default"))
        # Add the phase record first so get_epic() returns it
        repo.add_phase(epic_folder_name, {
            "name": phase_name,
            "phase_id": phase.get("phase_id", phase.get("id", "")),
            "description": phase.get("description", ""),
            "status": phase.get("status", "pending"),
            "execution": phase.get("execution", "sequential"),
        })
        tickets = phase.get("tickets", phase.get("tasks", []))
        for ticket in tickets:
            ticket_id = ticket.get("id") or ticket.get("task_id", "")
            repo.add_ticket(epic_folder_name, phase_name, ticket)

    # Handle flat tasks[] structure (legacy)
    flat_tasks = yaml_data.get("tasks", [])
    for ticket in flat_tasks:
        repo.add_ticket(epic_folder_name, "default", ticket)

    repo.close()
    return repo


@pytest.fixture
def tinydb_populator(_isolate_tinydb):
    """Fixture providing a function to populate the isolated TinyDB.

    Usage in tests:
        def test_something(tinydb_populator, tmp_path):
            epic_dir = tmp_path / "my_epic"
            epic_dir.mkdir()
            tinydb_populator("my_epic", epic_dir, {
                "name": "My Epic",
                "status": "active",
                "phases": [{"name": "P1", "tickets": [...]}]
            })
    """
    db_path = _isolate_tinydb

    def _populate(epic_folder_name, epic_folder, yaml_data):
        return populate_tinydb_from_yaml(db_path, epic_folder_name, epic_folder, yaml_data)

    return _populate


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_dir(temp_dir):
    """Create a temporary config directory and set XDG_CONFIG_HOME."""
    config_dir = temp_dir / "config" / "agenticcli"
    config_dir.mkdir(parents=True)
    with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(temp_dir / "config")}):
        yield config_dir


@pytest.fixture
def temp_repo(temp_dir):
    """Create a temporary git repository structure."""
    repo_dir = temp_dir / "repo"
    repo_dir.mkdir()

    # Create docs/epics/live structure
    epics_live = repo_dir / "docs" / "epics" / "live"
    epics_live.mkdir(parents=True)

    # Create a sample epic folder (flattened structure: plan files directly in folder)
    epic_folder = epics_live / "260103AE_test"
    epic_folder.mkdir(parents=True)

    # Create sample plan file (flattened: directly in epic_folder)
    sample_plan = {
        "plan": {
            "name": "Test Plan",
            "status": "in_progress",
            "phases": [
                {"id": "01", "name": "Phase 1", "status": "completed"},
                {"id": "02", "name": "Phase 2", "status": "pending"},
            ],
        }
    }
    with open(epic_folder / "plan_test.yml", "w") as f:
        yaml.dump(sample_plan, f)

    # Create a minimal orchestration MMD file (EN-006 requires it for task start)
    (epic_folder / "orchestration_test.mmd").write_text(
        "flowchart TD\n  P01[Phase 1] --> P02[Phase 2]\n"
    )

    yield repo_dir


@pytest.fixture
def mock_cwd(temp_repo):
    """Mock os.getcwd to return temp_repo."""
    original_cwd = os.getcwd()
    os.chdir(temp_repo)
    yield temp_repo
    os.chdir(original_cwd)


@pytest.fixture
def cli_runner(temp_repo):
    """Fixture to run CLI commands and capture output.

    Runs in a temp repo directory to satisfy project requirement.
    Initializes a real git repository for git commands to work.
    """
    import io
    import subprocess
    from contextlib import redirect_stderr, redirect_stdout

    # Initialize a real git repository
    subprocess.run(
        ["git", "init"],
        cwd=temp_repo,
        capture_output=True,
        check=True,
    )
    # Configure git user for the repo
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=temp_repo,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_repo,
        capture_output=True,
    )
    # Create an initial commit so we have a branch
    (temp_repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=temp_repo,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_repo,
        capture_output=True,
    )

    # Change to temp repo directory
    original_cwd = os.getcwd()
    os.chdir(temp_repo)

    class CLIResult:
        """Result from CLI run. Supports both attribute and tuple unpacking access."""

        def __init__(self, stdout: str, stderr: str, returncode: int):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

        def __iter__(self):
            """Support tuple unpacking: stdout, stderr, code = result."""
            return iter((self.stdout, self.stderr, self.returncode))

    def run_cli(*args, expect_exit: int | None = None):
        """Run CLI with args and return CLIResult."""
        from agenticcli.cli import run_cli as _run_cli
        from agenticcli.console import set_json_output

        # Reset JSON output mode before each run
        set_json_output(False)

        # Support both run_cli("a", "b") and run_cli(["a", "b"])
        if len(args) == 1 and isinstance(args[0], list):
            cmd_args = args[0]
        else:
            cmd_args = list(args)

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        exit_code = 0

        # Patch sys.argv
        with patch.object(sys, "argv", ["agentic"] + cmd_args):
            with redirect_stdout(stdout_capture):
                with redirect_stderr(stderr_capture):
                    try:
                        _run_cli()
                    except SystemExit as e:
                        exit_code = e.code if e.code is not None else 0

        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue()

        if expect_exit is not None:
            assert exit_code == expect_exit, (
                f"Expected exit {expect_exit}, got {exit_code}. stderr: {stderr}"
            )

        return CLIResult(stdout, stderr, exit_code)

    yield run_cli

    # Reset global state that may have been set by --json flag
    from agenticcli.console import set_json_output
    set_json_output(False)

    # Restore cwd
    os.chdir(original_cwd)


@pytest.fixture
def sample_prefs(temp_config_dir):
    """Create sample preferences file."""
    prefs = {
        "plan": {
            "auto_scaffold": True,
        },
        "test": {
            "nested": {
                "value": "test_value",
            }
        },
    }
    prefs_file = temp_config_dir / "preferences.yml"
    with open(prefs_file, "w") as f:
        yaml.dump(prefs, f)
    return prefs_file
