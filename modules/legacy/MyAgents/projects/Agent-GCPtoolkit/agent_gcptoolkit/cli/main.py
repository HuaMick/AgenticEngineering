"""CLI entrypoint for agent-gcptoolkit."""
import sys
import argparse
import subprocess
import logging
from pathlib import Path

from .validators import validate_secret_name

VERSION = "0.1.0"

# Configure logging to stderr
logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def _is_workspace_install():
    """Check if running from a workspace/editable install."""
    try:
        import pkg_resources
        dist = pkg_resources.get_distribution("agent-gcptoolkit")
        # Editable installs have location pointing to source directory
        return dist.location and "Agent-GCPtoolkit" in dist.location
    except Exception:
        return False


def cmd_self_update(args):
    """Update agent-gcptoolkit from the artifact registry."""
    # Check if running from workspace install
    if _is_workspace_install():
        print("Error: self-update disabled in workspace mode. Use 'uv sync' instead.", file=sys.stderr)
        sys.exit(1)

    print("Updating agent-gcptoolkit from artifact registry...")
    result = subprocess.run(
        ["uv", "pip", "install", "--system", "--upgrade", "agent-gcptoolkit"],
        check=False
    )

    if result.returncode == 0:
        print("Success: agent-gcptoolkit updated successfully. Restart your terminal to use the new version.")
    else:
        print("Error: Update failed. Check registry authentication and connectivity.", file=sys.stderr)

    sys.exit(result.returncode)


def cmd_registry_info(args):
    """Show artifact registry configuration and status."""
    import pkg_resources

    print("=== Agent-GCPtoolkit Registry Information ===\n")

    # Show current version
    try:
        version = pkg_resources.get_distribution("agent-gcptoolkit").version
        print(f"Current version: {version}")
    except Exception:
        print("Current version: Unable to determine")

    # Show registry configuration from pip (uv pip doesn't support config command)
    print("\nRegistry Configuration:")
    result = subprocess.run(
        ["pip", "config", "get", "global.extra-index-url"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        print(f"  Extra index URL: {result.stdout.strip()}")
    else:
        print("  No extra index URL configured")
        print("  Configure with: pip config set global.extra-index-url <registry-url>")


def cmd_registry_check_auth(args):
    """Check artifact registry authentication status."""
    print("Checking artifact registry authentication...\n")

    # Check if keyring is installed
    try:
        import keyring  # noqa: F401
        print("Success: keyring package installed")
    except ImportError:
        print("Error: keyring package not installed")
        print("  Install with: uv pip install keyring keyrings.google-artifactregistry-auth")
        sys.exit(1)

    # Check if GCP keyring is installed
    try:
        import keyrings.google_artifactregistry_auth  # noqa: F401
        print("Success: keyrings.google-artifactregistry-auth installed")
    except ImportError:
        print("Error: keyrings.google-artifactregistry-auth not installed")
        print("  Install with: uv pip install keyrings.google-artifactregistry-auth")
        sys.exit(1)

    # Check gcloud authentication
    result = subprocess.run(
        ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        print(f"Success: GCP authenticated as: {result.stdout.strip()}")
    else:
        print("Error: No active GCP authentication")
        print("  Authenticate with: gcloud auth login")
        sys.exit(1)

    print("\nSuccess: All authentication checks passed")


def cmd_version(args):
    """Show version information."""
    print(f"agent-gcptoolkit {VERSION}")


def cmd_config_set_path(args):
    """Set config file path preference."""
    from agent_gcptoolkit.secrets.domains.preferences import set_preference

    config_path = Path(args.path).resolve()

    # Validate that the path exists
    if not config_path.exists():
        print(f"Error: Config file does not exist: {config_path}", file=sys.stderr)
        sys.exit(1)

    if not config_path.is_file():
        print(f"Error: Path is not a file: {config_path}", file=sys.stderr)
        sys.exit(1)

    # Store absolute path in preferences
    set_preference("config_path", str(config_path))
    print(f"Config path set to: {config_path}")


def cmd_config_show(args):
    """Show current config file path."""
    from agent_gcptoolkit.secrets.domains.preferences import get_preference

    config_path_pref = get_preference("config_path")

    if config_path_pref:
        config_path = Path(config_path_pref)
        if config_path.exists():
            print(f"Config path: {config_path}")
            print("Source: preference")
        else:
            print(f"Config path (from preference, but file not found): {config_path}")
            print("Source: preference")
    else:
        default_config = Path.home() / ".config" / "agent-gcptoolkit" / "config.yml"
        if default_config.exists():
            print(f"Config path: {default_config}")
            print("Source: default")
        else:
            print(f"Config path: {default_config}")
            print("Source: default (file not found)")


def cmd_config_clear(args):
    """Clear config path preference."""
    from agent_gcptoolkit.secrets.domains.preferences import clear_preference

    clear_preference("config_path")
    default_config = Path.home() / ".config" / "agent-gcptoolkit" / "config.yml"
    print(f"Config path preference cleared. Will use default: {default_config}")


def cmd_config_init(args):
    """Interactive config setup."""
    from agent_gcptoolkit.secrets.domains.preferences import set_preference

    default_config = Path.home() / ".config" / "agent-gcptoolkit" / "config.yml"

    print("=== Agent-GCPtoolkit Configuration Setup ===\n")
    print(f"Default config location: {default_config}\n")

    # Check if config already exists
    if default_config.exists():
        print(f"Configuration file already exists at: {default_config}")
        response = input("Do you want to use a different config file? (y/N): ").strip().lower()
        if response != 'y':
            print(f"\nUsing existing config at: {default_config}")
            return
    else:
        # Ask if user wants to copy existing config or use default location
        print("Choose an option:")
        print("1. Copy an existing config file to default location")
        print("2. Point to an existing config file at a different location")
        print("3. Cancel (manually create config file later)")

        choice = input("\nEnter choice (1-3): ").strip()

        if choice == "1":
            source_path = input("Enter path to existing config file: ").strip()
            source = Path(source_path).expanduser().resolve()

            if not source.exists():
                print(f"Error: File not found: {source}", file=sys.stderr)
                sys.exit(1)

            # Create directory and copy file
            default_config.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(source, default_config)
            print(f"\nConfig copied to: {default_config}")
            return

        elif choice == "2":
            config_path = input("Enter path to config file: ").strip()
            config_file = Path(config_path).expanduser().resolve()

            if not config_file.exists():
                print(f"Error: File not found: {config_file}", file=sys.stderr)
                sys.exit(1)

            set_preference("config_path", str(config_file))
            print(f"\nConfig path set to: {config_file}")
            return

        elif choice == "3":
            print("\nSetup cancelled.")
            print(f"Create your config file at: {default_config}")
            print("Or use: myagents config set-path <path>")
            return

        else:
            print("Invalid choice.", file=sys.stderr)
            sys.exit(2)


def cmd_secrets_get(args):
    """Get a secret from GCP Secret Manager."""
    from agent_gcptoolkit.secrets.workflows.secret_operations import get_secret

    validate_secret_name(args.secret_name)
    secret_value = get_secret(args.secret_name, args.project_id, quiet=args.quiet)

    if secret_value:
        if args.quiet:
            # Quiet mode: output only value, no formatting
            print(secret_value)
        else:
            # Verbose mode: show secret name and value
            print(f"Secret '{args.secret_name}': {secret_value}")
        sys.exit(0)
    else:
        err_msg = f"Error: Secret '{args.secret_name}' not found in GCP or env"
        print(err_msg, file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entrypoint.

    Exit codes:
        0 - Success
        1 - Runtime errors (authentication, network, secret not found, etc.)
        2 - Usage errors (invalid arguments, invalid secret name format, etc.)
    """
    parser = argparse.ArgumentParser(
        prog="myagents",
        description="Agent-GCPtoolkit CLI - GCP Secret Manager toolkit with artifact registry integration",
        epilog="""
Exit codes:
  0 - Success
  1 - Runtime error (authentication, network, secret not found, etc.)
  2 - Usage error (invalid arguments, invalid secret name format, etc.)

Environment variables:
  GCP_PROJECT - GCP project ID (overrides config file)

Configuration:
  Default location: ~/.config/agent-gcptoolkit/config.yml
  Custom path: Set with 'myagents config set-path <path>'
  View current: Run 'myagents config show'

Note: Use the unified 'myagents' CLI (e.g., 'myagents secrets get', 'myagents config show', 'myagents self-update').
For more information, see the README.
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # version command
    _version_parser = subparsers.add_parser(
        "version",
        help="Show version information",
        description="Display the current version of agent-gcptoolkit"
    )

    # self-update command
    _self_update_parser = subparsers.add_parser(
        "self-update",
        help="Update agent-gcptoolkit from artifact registry",
        description="Update to the latest version of agent-gcptoolkit from the GCP Artifact Registry"
    )

    # registry command with subcommands
    registry_parser = subparsers.add_parser(
        "registry",
        help="Artifact registry operations",
        description="Manage artifact registry configuration and authentication"
    )
    registry_subparsers = registry_parser.add_subparsers(dest="registry_command")

    # registry info
    _registry_info_parser = registry_subparsers.add_parser(
        "info",
        help="Show registry configuration",
        description="Display current artifact registry configuration and package version"
    )

    # registry check-auth
    _registry_check_auth_parser = registry_subparsers.add_parser(
        "check-auth",
        help="Check registry authentication",
        description="Verify artifact registry authentication is configured correctly"
    )

    # config command
    config_parser = subparsers.add_parser(
        "config",
        help="Configuration management",
        description="Manage agent-gcptoolkit configuration"
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    # config set-path command
    config_set_path_parser = config_subparsers.add_parser(
        "set-path",
        help="Set config file path",
        description="""
Set the configuration file path preference.

This stores the absolute path to your config file in:
~/.config/agent-gcptoolkit/preferences.json

The path will be validated before storing.
        """
    )
    config_set_path_parser.add_argument(
        "path",
        help="Path to config file"
    )

    # config show command
    _config_show_parser = config_subparsers.add_parser(
        "show",
        help="Show current config path",
        description="""
Display the current configuration file path and its source.

Sources:
  - preference: Path set via 'config set-path'
  - default: Default XDG location (~/.config/agent-gcptoolkit/config.yml)
        """
    )

    # config clear command
    _config_clear_parser = config_subparsers.add_parser(
        "clear",
        help="Clear config path preference",
        description="""
Remove the config path preference.

After clearing, the default location will be used:
~/.config/agent-gcptoolkit/config.yml
        """
    )

    # config init command
    _config_init_parser = config_subparsers.add_parser(
        "init",
        help="Interactive config setup",
        description="""
Interactive setup wizard for agent-gcptoolkit configuration.

Options:
  1. Copy existing config to default location
  2. Point to existing config at different location
  3. Cancel and set up manually
        """
    )

    # secrets command
    secrets_parser = subparsers.add_parser(
        "secrets",
        help="Secret management operations",
        description="Manage secrets in GCP Secret Manager"
    )
    secrets_subparsers = secrets_parser.add_subparsers(dest="secrets_command")

    # secrets get command
    get_parser = secrets_subparsers.add_parser(
        "get",
        help="Get a secret value",
        description="""
Fetch a secret from GCP Secret Manager with automatic fallback to environment variables.

Behavior:
  1. Checks memory cache (within same process only)
  2. Fetches from GCP Secret Manager
  3. Falls back to environment variable if GCP fetch fails

The command will print the secret value to stdout. In quiet mode (-q),
only the value is printed. In normal mode, the secret name is also shown.

Exit codes:
  0 - Secret found and printed
  1 - Secret not found (not in GCP or environment)
  2 - Invalid secret name format
        """
    )
    get_parser.add_argument(
        "secret_name",
        help="Name of the secret (format: [a-zA-Z0-9_-]+, no dots or special chars)"
    )
    get_parser.add_argument(
        "--project-id",
        help="GCP project ID (auto-detected from GCP_PROJECT env var or config file if not provided)"
    )
    get_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Output only the secret value (suppresses warnings and formatting, useful for scripts)"
    )

    args = parser.parse_args()

    # If no command provided, show help and exit with usage error code
    if not args.command:
        parser.print_help()
        sys.exit(2)

    # Route to command handlers
    try:
        if args.command == "version":
            cmd_version(args)
        elif args.command == "self-update":
            cmd_self_update(args)
        elif args.command == "registry":
            if args.registry_command == "info":
                cmd_registry_info(args)
            elif args.registry_command == "check-auth":
                cmd_registry_check_auth(args)
            else:
                registry_parser.print_help()
                sys.exit(2)
        elif args.command == "config":
            if args.config_command == "set-path":
                cmd_config_set_path(args)
            elif args.config_command == "show":
                cmd_config_show(args)
            elif args.config_command == "clear":
                cmd_config_clear(args)
            elif args.config_command == "init":
                cmd_config_init(args)
            else:
                config_parser.print_help()
                sys.exit(2)
        elif args.command == "secrets":
            if args.secrets_command == "get":
                cmd_secrets_get(args)
            else:
                secrets_parser.print_help()
                sys.exit(2)
        else:
            parser.print_help()
            sys.exit(2)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
