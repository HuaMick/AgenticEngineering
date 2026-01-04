"""Package management commands.

Handles update and rebuild operations.
"""

import subprocess
import sys
from pathlib import Path


def find_package_root() -> Path:
    """Find the AgenticCLI package root (where pyproject.toml lives)."""
    # Start from this file's location and go up
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent

    print("Error: Could not find pyproject.toml", file=sys.stderr)
    sys.exit(1)


def handle_update(args, ctx=None):
    """Reinstall AgenticCLI from source."""
    package_root = find_package_root()
    print(f"Updating AgenticCLI from {package_root}")

    try:
        subprocess.run(
            ["uv", "sync"],
            check=True,
            cwd=package_root,
        )
        print("Update complete")
    except subprocess.CalledProcessError as e:
        print(f"Error during update: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'uv' not found. Please install uv first.", file=sys.stderr)
        sys.exit(1)


def handle_rebuild(args, ctx=None):
    """Full rebuild and reinstall."""
    package_root = find_package_root()
    print(f"Rebuilding AgenticCLI from {package_root}")

    # Clean build artifacts
    print("Cleaning build artifacts...")
    for pattern in ["build", "dist", "*.egg-info"]:
        for path in package_root.glob(pattern):
            if path.is_dir():
                import shutil

                shutil.rmtree(path)
                print(f"  Removed {path.name}")

    # Also clean src/*.egg-info
    src_dir = package_root / "src"
    if src_dir.exists():
        for path in src_dir.glob("*.egg-info"):
            if path.is_dir():
                import shutil

                shutil.rmtree(path)
                print(f"  Removed src/{path.name}")

    # Rebuild
    print("Building package...")
    try:
        subprocess.run(
            ["python", "-m", "build", "--installer", "uv"],
            check=True,
            cwd=package_root,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error during build: {e}", file=sys.stderr)
        sys.exit(1)

    # Reinstall
    print("Reinstalling...")
    try:
        subprocess.run(
            ["uv", "sync"],
            check=True,
            cwd=package_root,
        )
        print("Rebuild complete")
    except subprocess.CalledProcessError as e:
        print(f"Error during reinstall: {e}", file=sys.stderr)
        sys.exit(1)
