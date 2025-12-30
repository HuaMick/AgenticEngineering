"""Pytest configuration and plugins for MyAgents tests.

This conftest.py file is automatically loaded by pytest and provides:
- Workflow health reporting plugin registration
- Custom command-line options for health reporting
- Pytest markers for workflow categorization
- Test isolation environment setup
- Automatic API key loading from preferences

The workflow health reporter replaces standard "X tests passed" output with
workflow-based health status reporting.
"""

import os
import sys
from pathlib import Path
import pytest

# Import the health reporter plugin hooks
# This makes the plugin available to pytest automatically
pytest_plugins = ["tests.utils.health_reporter"]

# Add src directory to sys.path to ensure imports work
_project_root = Path(__file__).parent.parent
_src_dir = _project_root / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


@pytest.fixture(scope="session", autouse=True)
def setup_api_keys_from_preferences():
    """Load API keys from preferences into environment.

    This fixture automatically loads API keys from ~/.myagents/preferences.json
    and injects them into the test environment (os.environ) before tests run.
    This enables work-from-anywhere testing without manual API key setup.

    Behavior:
    - Loads API keys from preferences using PreferencesManager
    - Only sets keys that are NOT already in environment (allows manual override)
    - Runs before all tests (session-scoped, autouse=True)
    - Compatible with existing test isolation and fixtures

    Example preferences.json structure:
    {
        "api_keys": {
            "GOOGLE_API_KEY": "...",
            "LANGSMITH_API_KEY": "...",
            "LANGSMITH_TRACING": "true",
            "LANGSMITH_PROJECT": "myagents-cli-chat"
        }
    }
    """
    try:
        from myagents.backend.services.preferences.domains.preferences_manager.manager import PreferencesManager

        manager = PreferencesManager()
        api_keys = manager.get('api_keys')

        if api_keys:
            keys_loaded = []
            keys_skipped = []

            for key, value in api_keys.items():
                if key not in os.environ:
                    os.environ[key] = value
                    keys_loaded.append(key)
                else:
                    keys_skipped.append(key)

            # Optional: Print debug info (visible with pytest -v or -s)
            if keys_loaded:
                print(f"\n[Preferences] Loaded {len(keys_loaded)} API keys from ~/.myagents/preferences.json")
            if keys_skipped:
                print(f"[Preferences] Skipped {len(keys_skipped)} keys (already in environment)")
        else:
            print("\n[Preferences] No API keys found in preferences.json")

    except ImportError as e:
        print(f"\n[Preferences] Warning: Could not import PreferencesManager: {e}")
    except Exception as e:
        print(f"\n[Preferences] Warning: Could not load API keys from preferences: {e}")

    yield
    # No cleanup needed - API keys should persist for entire test session


@pytest.fixture(scope="session", autouse=True)
def setup_test_isolation():
    """Enable test isolation for worktree-specific testing.

    Sets MYAGENTS_ALLOWED_DIR to worktree root for file operations tests.
    Sets PYTHONPATH to ensure subprocess calls to myagents use this worktree's code.

    With the home-directory-only architecture, tests validate behavior using
    ~/.config/myagents/ directory. Individual tests create/cleanup test configs
    as needed in the home directory.
    """
    # Set MYAGENTS_ALLOWED_DIR to worktree root for file operations tests
    worktree_root = Path(__file__).parent.parent
    os.environ["MYAGENTS_ALLOWED_DIR"] = str(worktree_root)

    # Set PYTHONPATH to ensure myagents subprocess calls use this worktree's code
    # Prepend worktree root to PYTHONPATH so it takes precedence over editable install
    current_pythonpath = os.environ.get('PYTHONPATH', '')
    new_pythonpath = str(worktree_root)
    if current_pythonpath:
        new_pythonpath = f"{new_pythonpath}:{current_pythonpath}"
    os.environ['PYTHONPATH'] = new_pythonpath

    yield
    # Cleanup after all tests
    os.environ.pop('MYAGENTS_ALLOWED_DIR', None)
    if current_pythonpath:
        os.environ['PYTHONPATH'] = current_pythonpath
    else:
        os.environ.pop('PYTHONPATH', None)


@pytest.fixture(autouse=True)
def reset_builder_agent_singleton():
    """Reset builder agent singleton between tests to prevent state pollution.

    The builder_agent module uses a singleton pattern (_agent_workflow) which can
    cause test isolation issues when tests run in sequence. This fixture ensures
    each test starts with a fresh workflow instance.

    This is critical for e2e tests that rely on the actual workflow behavior,
    as previous tests might have initialized the singleton with mocked LLMs.
    """
    yield
    # Reset the singleton after each test
    try:
        import myagents.backend.services.agents.workflows.builder_agent as builder_agent_module
        builder_agent_module._agent_workflow = None
    except (ImportError, AttributeError):
        # If module not imported or singleton doesn't exist, no cleanup needed
        pass


@pytest.fixture(autouse=True)
def cleanup_home_directory_test_files():
    """Clean up home directory test files between tests to prevent contamination.

    This fixture cleans up home directory config files created during tests.
    With the home-directory-only architecture, all langgraph.json files are
    stored in ~/.config/myagents/ rather than local project directories.
    This fixture ensures proper cleanup even if individual test cleanup fails.

    Note: Tests should use tmp_path fixtures for temporary files, which are
    automatically cleaned up by pytest.
    """
    yield
    # Clean up after each test
    import shutil
    from pathlib import Path

    home_config_dir = Path.home() / ".config" / "myagents"

    # Only clean up if directory exists and was likely created by tests
    if home_config_dir.exists():
        # Safety check: only clean if it looks like a test artifact
        # (contains config.yml, indicating test creation)
        test_markers = [
            home_config_dir / "config.yml"
        ]

        if any(marker.exists() for marker in test_markers):
            try:
                shutil.rmtree(home_config_dir)
            except (OSError, PermissionError):
                # If cleanup fails, log but don't fail the test
                pass
