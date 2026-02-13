"""Pytest configuration for integration tests.

These tests run the ACTUAL installed agentic CLI binary.
Skip if not installed.
"""
import shutil

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (runs real CLI)"
    )


@pytest.fixture(scope="session", autouse=True)
def verify_cli_installed():
    if not shutil.which("agentic"):
        pytest.skip("agentic CLI not installed - skipping integration tests")
