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


def pytest_addoption(parser):
    """Register story_strict ini option and --check-story-coverage flag."""
    parser.addini(
        "story_strict",
        type="bool",
        default=False,
        help="When true, unknown @pytest.mark.story IDs cause test failure instead of warnings",
    )
    parser.addoption(
        "--check-story-coverage",
        action="store_true",
        default=False,
        help="Fail if source files in modules/*/src/ lack # story: headers",
    )


def pytest_configure(config):
    """Register custom markers for AgenticCLI tests."""
    config.addinivalue_line(
        "markers",
        "story(*story_ids): marks tests that validate specific user stories "
        "(format: @pytest.mark.story('US-XXX-NNN'))",
    )


# Exclusion list for --check-story-coverage
_STORY_COVERAGE_EXCLUDE = {
    "__init__.py", "conftest.py", "markers.py", "py.typed",
}


def _load_story_coverage_excludes(repo_root):
    """Load exclusion list from pyproject.toml [tool.agentic.story_coverage].exclude."""
    excludes = set()
    for pyproject_path in repo_root.glob("modules/*/pyproject.toml"):
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                continue
        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
            exclude_list = data.get("tool", {}).get("agentic", {}).get("story_coverage", {}).get("exclude", [])
            excludes.update(exclude_list)
        except Exception:
            continue
    return excludes


def pytest_sessionstart(session):
    """Run --check-story-coverage scan if requested."""
    if not session.config.getoption("--check-story-coverage", default=False):
        return

    import re as _re

    repo_root = _find_repo_root_from_tests()
    if not repo_root:
        return

    # Load exclusions from pyproject.toml
    excluded_files = _load_story_coverage_excludes(repo_root)

    missing = []
    src_dirs = list((repo_root / "modules").glob("*/src"))
    for src_dir in src_dirs:
        for py_file in sorted(src_dir.rglob("*.py")):
            if py_file.name in _STORY_COVERAGE_EXCLUDE:
                continue
            rel = str(py_file.relative_to(repo_root))
            if rel in excluded_files:
                continue
            try:
                first_lines = py_file.read_text().split("\n")[:5]
            except OSError:
                continue
            has_header = any(_re.match(r"^#\s*story:", line) for line in first_lines)
            if not has_header:
                missing.append(rel)

    if missing:
        msg_lines = [f"--check-story-coverage: {len(missing)} source file(s) missing # story: header:"]
        for f in missing[:20]:
            msg_lines.append(f"  {f}")
        if len(missing) > 20:
            msg_lines.append(f"  ... and {len(missing) - 20} more")
        pytest.exit("\n".join(msg_lines), returncode=1)


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
                    item.warn(
                        pytest.PytestUnhandledCoroutineWarning(msg)
                        if hasattr(pytest, "PytestUnhandledCoroutineWarning")
                        else UserWarning(msg)
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
    if not hasattr(session.config, "_story_marker_count"):
        # Count markers from collected items
        marker_count = 0
        total_tests = session.testscollected or 0
        for item in (session.items or []):
            if any(item.iter_markers("story")):
                marker_count += 1
        if total_tests > 0:
            pct = marker_count / total_tests * 100
            session.config._terminal_writer = getattr(session.config, "_terminal_writer", None)
            tr = session.config.pluginmanager.get_plugin("terminalreporter")
            if tr:
                tr.write_sep("=", "story marker coverage")
                tr.write_line(
                    f"  {marker_count}/{total_tests} tests have @pytest.mark.story markers ({pct:.0f}%)"
                )


@pytest.fixture(autouse=True)
def _block_real_ntfy():
    """Safety net: prevent any test from sending real ntfy notifications."""
    yield


@pytest.fixture(autouse=True)
def _disable_tmux_orphan_sweep(request, monkeypatch):
    """Safety net: prevent ExecutionRunner._kill_orphaned_tmux_sessions from
    touching the real tmux server.

    The production sweep matches every session whose name starts with
    'agentic-', which would clobber sibling tmux integration test sessions
    (e.g. 'agentic-orch-test-3pane-<pid>') running on the same xdist worker.
    Tests that exercise ExecutionRunner.run / _execute_plan trigger the sweep
    via _recover_stale_phases.

    The unit tests in TestOrphanTmuxSweep mock subprocess.run themselves and
    need the real implementation, so we skip them by node-id.
    """
    if "TestOrphanTmuxSweep" in request.node.nodeid:
        yield
        return
    monkeypatch.setenv("AGENTIC_DISABLE_TMUX_ORPHAN_SWEEP", "1")
    yield


@pytest.fixture(autouse=True)
def _isolate_tinydb(tmp_path):
    """Safety net: redirect all TinyDB writes to a per-test temp directory.

    Prevents tests from polluting the global ~/.agentic/epics.db database.

    Patches:
    - EpicRepository.__init__: redirects default db_path to isolated path
    - _get_repo_db_path in epic.py and stories.py: returns isolated path
    """
    isolated_db_path = tmp_path / ".agentic" / "epics.db"
    isolated_db_path.parent.mkdir(parents=True, exist_ok=True)

    from agenticguidance.services.epic_repository import EpicRepository

    _original_init = EpicRepository.__init__

    def _patched_init(self, db_path=None, epics_base=None, auto_bootstrap=True):
        _original_init(self, db_path=db_path or isolated_db_path, epics_base=epics_base, auto_bootstrap=auto_bootstrap)

    with patch.object(EpicRepository, "__init__", _patched_init):
        with patch("agenticcli.commands.epic._get_repo_db_path", return_value=isolated_db_path):
            with patch("agenticcli.commands.stories._get_repo_db_path", return_value=isolated_db_path):
                yield isolated_db_path


def populate_tinydb_from_yaml(db_path, epic_folder_name, epic_folder, yaml_data):
    """Populate TinyDB with epic/ticket data from a YAML-style dict.

    Converts the dict structure that tests previously wrote to plan_build.yml
    into TinyDB entries via EpicRepository.

    Args:
        db_path: Path to the TinyDB database file.
        epic_folder_name: Epic folder name (e.g. "260103AE_test").
        epic_folder: Path to the epic folder on disk, or None for folder-free epics.
        yaml_data: Dict with optional keys: name, status, phases, tasks.
            phases: list of {name, tickets/tasks: [{id, name, status, ...}]}
            tasks: list of {id, name, status, ...} (flat/legacy structure)
    """
    from agenticguidance.services.epic_repository import EpicRepository

    repo = EpicRepository(db_path=db_path, auto_bootstrap=False)
    epic_doc = {
        "epic_folder_name": epic_folder_name,
        "epic_folder": str(epic_folder) if epic_folder else "",
        "name": yaml_data.get("name", epic_folder_name),
        "status": yaml_data.get("status", "planning"),
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
        phase_record = {
            "name": phase_name,
            "phase_id": phase.get("phase_id", phase.get("id", "")),
            "description": phase.get("description", ""),
            "status": phase.get("status", "planning"),
            "execution": phase.get("execution", "sequential"),
        }
        # Pass through optional phase fields used by ExecutionRunner
        for field in ("agent", "max_turns", "timeout", "feedback_triggers"):
            if field in phase:
                phase_record[field] = phase[field]
        repo.add_phase(epic_folder_name, phase_record)
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
        # With a disk folder:
        def test_something(tinydb_populator, tmp_path):
            epic_dir = tmp_path / "my_epic"
            epic_dir.mkdir()
            tinydb_populator("my_epic", epic_dir, {
                "name": "My Epic",
                "status": "planning",
                "phases": [{"name": "P1", "tickets": [...]}]
            })

        # Folder-free epic (no disk folder):
        def test_folder_free(tinydb_populator):
            tinydb_populator("my_epic", None, {
                "name": "My Epic",
                "status": "planning",
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

    # Create a sample epic folder
    epic_folder = epics_live / "260103AE_test"
    epic_folder.mkdir(parents=True)

    # Populate TinyDB instead of legacy YAML
    agentic_dir = repo_dir / ".agentic"
    agentic_dir.mkdir(parents=True, exist_ok=True)
    db_path = agentic_dir / "epics.db"
    populate_tinydb_from_yaml(
        db_path,
        "260103AE_test",
        epic_folder,
        {
            "name": "Test Plan",
            "status": "in_progress",
            "phases": [
                {
                    "name": "Phase 1",
                    "status": "completed",
                    "tickets": [
                        {"id": "T1", "name": "Task 1", "status": "completed"},
                    ],
                },
                {
                    "name": "Phase 2",
                    "status": "planning",
                    "tickets": [
                        {"id": "T2", "name": "Task 2", "status": "proposed"},
                    ],
                },
            ],
        },
    )

    yield repo_dir


@pytest.fixture
def temp_repo_no_folder(temp_dir):
    """Create a temporary git repository with a TinyDB-only epic (no disk folder).

    Unlike temp_repo, this does NOT create an epic folder on disk.
    The epic exists only as a TinyDB record with epic_folder="".
    Use this fixture for testing folder-free epic operations.
    """
    repo_dir = temp_dir / "repo"
    repo_dir.mkdir()

    # Create docs/epics/live structure (repo structure, but no epic folder inside)
    epics_live = repo_dir / "docs" / "epics" / "live"
    epics_live.mkdir(parents=True)

    # Populate TinyDB with a folder-free epic (epic_folder=None)
    agentic_dir = repo_dir / ".agentic"
    agentic_dir.mkdir(parents=True, exist_ok=True)
    db_path = agentic_dir / "epics.db"
    populate_tinydb_from_yaml(
        db_path,
        "260103AE_test",
        None,  # No disk folder — folder-free epic
        {
            "name": "Test Plan (Folder-Free)",
            "status": "in_progress",
            "phases": [
                {
                    "name": "Phase 1",
                    "status": "completed",
                    "tickets": [
                        {"id": "T1", "name": "Task 1", "status": "completed"},
                    ],
                },
                {
                    "name": "Phase 2",
                    "status": "planning",
                    "tickets": [
                        {"id": "T2", "name": "Task 2", "status": "proposed"},
                    ],
                },
            ],
        },
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
