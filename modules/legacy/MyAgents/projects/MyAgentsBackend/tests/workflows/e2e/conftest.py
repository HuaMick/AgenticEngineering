"""Pytest fixtures for e2e workflow tests.

This conftest provides fixtures for testing package installation,
registry interactions, and self-update functionality.

AUTOMATIC SETUP:
- Before running tests, this module ensures the current myagents CLI is installed
- This prevents failures due to old CLI versions with different command structures
- If reinstallation fails, tests will skip or fail based on individual skip conditions
- GCP authentication is set up using gcp_toolkit (agent-gcptoolkit) config
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _setup_gcp_credentials_from_gcptoolkit():
    """Set up GCP credentials using gcp_toolkit config.

    This function attempts to load the gcp_toolkit config and set
    GOOGLE_APPLICATION_CREDENTIALS environment variable so that
    keyrings.google-artifactregistry-auth can authenticate with
    Artifact Registry.

    Returns:
        bool: True if credentials were set up, False otherwise
    """
    try:
        # Try to import and use gcp_toolkit's config loader
        from agent_gcptoolkit.secrets.domains.config_loader import load_config, ConfigError

        try:
            config = load_config()
            if config and 'authentication' in config and 'service_account_path' in config['authentication']:
                service_account_path = config['authentication']['service_account_path']
                if os.path.exists(service_account_path):
                    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = service_account_path
                    return True
        except ConfigError:
            # Config not available - that's ok, will fall back to gcloud auth
            pass
    except ImportError:
        # agent_gcptoolkit not available - that's ok, will fall back to gcloud auth
        pass

    return False


@pytest.fixture
def isolated_test_venv(tmp_path):
    """Create isolated virtual environment for testing package installations.

    Provides a clean temporary virtual environment with:
    - Python executable path
    - pip executable path
    - Keyring helper installed for GCP auth
    - Automatic cleanup after test

    Yields:
        dict: Contains venv_path, python, and pip paths
    """
    venv_path = tmp_path / "test_venv"

    # Create venv
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

    # Determine executable paths
    if sys.platform == "win32":
        python = venv_path / "Scripts" / "python.exe"
        pip = venv_path / "Scripts" / "pip.exe"
    else:
        python = venv_path / "bin" / "python"
        pip = venv_path / "bin" / "pip"

    # Set up GCP credentials using gcp_toolkit before installing keyring helper
    # This ensures pip can authenticate with Artifact Registry
    credentials_setup = _setup_gcp_credentials_from_gcptoolkit()

    # Upgrade pip (disable interactive prompts and use only PyPI)
    env = os.environ.copy()
    env["PIP_NO_INPUT"] = "1"
    env["PIP_CONFIG_FILE"] = "/dev/null"
    # Ensure GOOGLE_APPLICATION_CREDENTIALS is passed to subprocess if set
    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
        env["GOOGLE_APPLICATION_CREDENTIALS"] = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]

    subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip", "--index-url", "https://pypi.org/simple"],
        capture_output=True,
        check=True,
        env=env
    )

    # Install keyring helper for GCP auth
    # With GOOGLE_APPLICATION_CREDENTIALS set from gcp_toolkit, this should work
    try:
        subprocess.run(
            [str(pip), "install", "keyrings.google-artifactregistry-auth", "--index-url", "https://pypi.org/simple"],
            capture_output=True,
            check=True,
            timeout=60,
            env=env
        )
    except subprocess.TimeoutExpired:
        pytest.skip("Timeout installing keyring helper")
    except subprocess.CalledProcessError as e:
        # If credentials were set up but install still failed, this is a real issue
        if credentials_setup:
            err_detail = e.stderr if hasattr(e, 'stderr') else e
            pytest.fail(f"Failed to install keyring helper despite gcp_toolkit credentials: {err_detail}")
        else:
            pytest.skip(f"Failed to install keyring helper (GCP credentials not available): {e}")

    # Set PIP_CONFIG_FILE environment variable to prevent global pip config from leaking
    # This must be set in os.environ so it persists for subprocess calls in tests
    original_pip_config = os.environ.get("PIP_CONFIG_FILE")
    os.environ["PIP_CONFIG_FILE"] = "/dev/null"

    # Clear PYTHONPATH to prevent pip from finding packages in source directory
    original_pythonpath = os.environ.get("PYTHONPATH")
    if "PYTHONPATH" in os.environ:
        del os.environ["PYTHONPATH"]

    # IMPORTANT: Change to tmp directory to prevent project directory
    # from being added to sys.path when subprocesses run
    original_cwd = os.getcwd()
    os.chdir(str(tmp_path))

    try:
        yield {
            "venv_path": venv_path,
            "python": str(python),
            "pip": str(pip)
        }
    finally:
        os.chdir(original_cwd)

        # Restore original PYTHONPATH
        if original_pythonpath is not None:
            os.environ["PYTHONPATH"] = original_pythonpath

        # Restore original PIP_CONFIG_FILE after test
        if original_pip_config is not None:
            os.environ["PIP_CONFIG_FILE"] = original_pip_config
        else:
            os.environ.pop("PIP_CONFIG_FILE", None)


@pytest.fixture
def test_registry_url():
    """Provide test registry URL for package installation tests.

    Returns:
        str: GCP Artifact Registry test URL
    """
    # Test registry URL from ARTIFACT-REGISTRY-MIGRATION-001
    # GCP authentication is handled by gcp_toolkit (sets GOOGLE_APPLICATION_CREDENTIALS)
    # and keyrings.google-artifactregistry-auth (uses those credentials)
    return "https://us-central1-python.pkg.dev/myagents-475112/myagents-python-test/simple/"


@pytest.fixture(scope="session", autouse=True)
def setup_gcp_credentials():
    """Set up GCP credentials from gcp_toolkit at session start.

    This ensures GOOGLE_APPLICATION_CREDENTIALS is available for all tests
    that need to authenticate with Artifact Registry.
    """
    _setup_gcp_credentials_from_gcptoolkit()


@pytest.fixture(scope="session", autouse=True)
def ensure_current_cli_installed():
    """Ensure the current myagents CLI is installed before running tests.

    This fixture runs once per test session and attempts to reinstall the
    current version of myagents CLI from the source directory.

    This helps prevent test failures due to:
    - Old CLI versions with different command structures
    - Missing subcommands (e.g., gcptoolkit)
    - Outdated command behavior

    If reinstallation fails, tests will still run (they may skip or fail
    based on their individual skip conditions).
    """
    # Dynamically resolve project root: tests/workflows/e2e/conftest.py -> project root
    project_root = Path(__file__).parents[3]

    # Only attempt reinstall if we're in the MyAgents project
    if not project_root.exists():
        return

    print("\n" + "=" * 70)
    print("E2E TEST SETUP: Ensuring current CLI is installed")
    print("=" * 70)

    try:
        # Reinstall current version using uv (venv doesn't have pip)
        result = subprocess.run(
            ["uv", "pip", "install", "-e", ".", "--reinstall-package", "myagents"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120,
            env=os.environ.copy()
        )

        if result.returncode == 0:
            print("✓ Current myagents CLI installed successfully")

            # Verify CLI is available
            verify_result = subprocess.run(
                ["myagents", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if verify_result.returncode == 0:
                print("✓ CLI verification passed")

                # Check for gcptoolkit subcommand
                if "gcptoolkit" in verify_result.stdout.lower():
                    print("✓ gcptoolkit subcommand available")
                else:
                    print("⚠ gcptoolkit subcommand not found (some tests may skip)")
            else:
                print("⚠ CLI verification failed (some tests may skip)")

        else:
            print("⚠ CLI installation had issues:")
            print(result.stderr[:500])
            print("\nTests will continue but may skip or fail")

    except subprocess.TimeoutExpired:
        print("⚠ CLI installation timed out")
        print("Tests will continue but may skip or fail")

    except Exception as e:
        print(f"⚠ CLI installation error: {e}")
        print("Tests will continue but may skip or fail")

    # Verify GCP authentication is available (via gcp_toolkit or gcloud)
    print("\nVerifying GCP authentication:")

    # First check if gcp_toolkit credentials are available
    credentials_setup = _setup_gcp_credentials_from_gcptoolkit()
    if credentials_setup and "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
        print(f"✓ GCP authentication via gcp_toolkit: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")
    else:
        # Fall back to checking gcloud auth
        try:
            gcloud_result = subprocess.run(
                ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if gcloud_result.returncode == 0 and gcloud_result.stdout.strip():
                print(f"✓ GCP authentication active (gcloud): {gcloud_result.stdout.strip()}")
            else:
                print("⚠ No active GCP authentication found (GCP registry tests may fail)")
        except Exception as e:
            print(f"⚠ Could not verify GCP authentication: {e}")

    print("=" * 70 + "\n")


@pytest.fixture(scope="session", autouse=True)
def setup_venv_path():
    """Set up PATH to prioritize venv binaries for all tests.

    This ensures subprocess calls in tests use the venv's myagents CLI
    instead of any globally installed version.
    """
    # Dynamically resolve project root: tests/workflows/e2e/conftest.py -> project root
    project_root = Path(__file__).parents[3]
    venv_bin = project_root / ".venv" / "bin"

    if venv_bin.exists():
        current_path = os.environ.get("PATH", "")
        new_path = f"{venv_bin}:{current_path}"
        os.environ["PATH"] = new_path
        print(f"\n✓ Updated PATH to prioritize venv binaries: {venv_bin}")
        print(f"  First PATH entry: {new_path.split(':')[0]}\n")


@pytest.fixture(scope="session")
def project_root():
    """Get the MyAgents project root directory."""
    # Dynamically resolve project root: tests/workflows/e2e/conftest.py -> project root
    return Path(__file__).parents[3]


