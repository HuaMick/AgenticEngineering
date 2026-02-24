"""Pytest configuration for integration tests.

These tests run the ACTUAL installed agentic CLI binary.
Skip if not installed.
"""
import shutil
import subprocess

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (runs real CLI)"
    )
    config.addinivalue_line(
        "markers", "tmux: mark test as requiring real tmux"
    )


@pytest.fixture(scope="session", autouse=True)
def verify_cli_installed():
    if not shutil.which("agentic"):
        pytest.skip("agentic CLI not installed - skipping integration tests")


requires_tmux = pytest.mark.skipif(
    not shutil.which("tmux"),
    reason="tmux not available",
)


@pytest.fixture
def tmux_session_cleanup():
    """Record existing sessions before test, kill new agentic-orch-* sessions after."""
    existing = set()
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        existing = set(result.stdout.strip().splitlines())

    yield

    # Kill any new agentic-orch-* sessions created during the test
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        for session in result.stdout.strip().splitlines():
            if session.startswith("agentic-orch-") and session not in existing:
                subprocess.run(
                    ["tmux", "kill-session", "-t", session],
                    capture_output=True,
                )


@pytest.fixture(scope="session", autouse=True)
def cleanup_all_orch_sessions_after_suite():
    """Safety net: kill ALL agentic-orch-* sessions after the entire test suite."""
    yield
    if not shutil.which("tmux"):
        return
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        for session in result.stdout.strip().splitlines():
            if session.startswith("agentic-orch-"):
                subprocess.run(
                    ["tmux", "kill-session", "-t", session],
                    capture_output=True,
                )
