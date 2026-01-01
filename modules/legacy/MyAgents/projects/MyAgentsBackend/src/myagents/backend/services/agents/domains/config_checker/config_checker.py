#!/usr/bin/env python3
"""Configuration checker for gcptoolkit - validates config exists before operations.

This module provides config detection and auto-setup functionality to ensure
gcptoolkit configuration is present before running commands that require secrets.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Tuple


class ErrorMessages:
    """Template methods for all error scenarios."""

    @staticmethod
    def missing_config_interactive() -> str:
        """Error message for missing config in interactive terminal.

        Returns:
            str: Formatted error message with auto-setup prompt
        """
        return """❌ Configuration file not found

gcptoolkit configuration is required but missing.

Expected file: ~/.config/agent-gcptoolkit/config.yml

This file is needed to:
- Retrieve API keys from GCP Secret Manager
- Authenticate with Google Cloud services
- Manage secrets securely

Would you like to set up configuration now? [Y/n]: """

    @staticmethod
    def missing_config_non_interactive() -> str:
        """Error message for missing config in non-interactive environment.

        Returns:
            str: Formatted error message with manual setup instructions
        """
        return """❌ Configuration file not found

gcptoolkit configuration is required but missing.

Expected file: ~/.config/agent-gcptoolkit/config.yml

To set up configuration:

1. Run the configuration wizard:
   myagents config init

2. Follow the prompts to enter:
   - GCP project ID
   - Service account key path (or use default)

3. Verify configuration:
   myagents config show

4. Test secret retrieval:
   myagents secrets get GEMINI_API_KEY

For detailed setup instructions, see SETUP.md

Exiting with error code 1.
"""

    @staticmethod
    def after_auto_setup_success() -> str:
        """Success message after auto-setup completes.

        Returns:
            str: Formatted success message
        """
        return """
✅ Configuration setup completed successfully!

Continuing with your original command...
"""

    @staticmethod
    def after_auto_setup_failure() -> str:
        """Error message after auto-setup fails.

        Returns:
            str: Formatted error message with troubleshooting info
        """
        return """❌ Configuration setup failed

Please run setup manually:
myagents config init

If problems persist, see SETUP.md (Troubleshooting section)
"""

    @staticmethod
    def user_declined_setup() -> str:
        """Message when user declines auto-setup.

        Returns:
            str: Formatted message with manual setup instructions
        """
        return """
Configuration setup cancelled.

To set up configuration later, run:
myagents config init

Exiting.
"""


def check_gcptoolkit_config() -> bool:
    """Check if gcptoolkit config file exists.

    Checks for configuration file at ~/.config/agent-gcptoolkit/config.yml

    Returns:
        bool: True if config exists, False otherwise
    """
    config_path = Path.home() / ".config" / "agent-gcptoolkit" / "config.yml"
    return config_path.exists()


def is_interactive_terminal() -> bool:
    """Check if running in interactive terminal.

    Checks both stdin/stdout tty status and CI/CD environment variables.

    Returns:
        bool: True if interactive terminal (not CI/CD), False otherwise
    """
    # Check if stdin and stdout are TTY
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False

    # Check for common CI/CD environment variables
    ci_env_vars = [
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_URL",
        "TRAVIS",
        "CIRCLECI",
        "BUILDKITE",
        "DRONE",
    ]

    for var in ci_env_vars:
        if os.environ.get(var):
            return False

    return True


def prompt_auto_setup() -> bool:
    """Prompt user to run auto-setup for gcptoolkit configuration.

    Displays error message and prompts user with [Y/n] choice.
    Handles Y/y/yes to run setup, n/N/no to exit, and Ctrl+C gracefully.

    Returns:
        bool: True if setup completed successfully, False otherwise

    Raises:
        SystemExit: Exits with code 1 if user declines or setup fails
                   Exits with code 130 if user presses Ctrl+C
    """
    try:
        # Display error message with prompt
        response = input(ErrorMessages.missing_config_interactive()).strip().lower()

        # Handle response
        if response in ['y', 'yes', '']:
            # User wants to run setup
            print("\nRunning configuration setup...\n")
            return run_auto_setup()
        else:
            # User declined setup
            print(ErrorMessages.user_declined_setup())
            sys.exit(1)

    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\n\nSetup cancelled by user.")
        sys.exit(130)
    except EOFError:
        # Handle EOF (e.g., piped input)
        print("\n\nNo input available. Please run 'myagents config init' manually.")
        sys.exit(1)


def run_auto_setup() -> bool:
    """Run fully interactive configuration setup.

    Prompts user for service account path and project ID, creates config file,
    verifies it works, and returns control to original command flow.

    Returns:
        bool: True if setup succeeded, False otherwise

    Raises:
        SystemExit: Exits with code 1 if setup fails
    """
    import yaml  # type: ignore[import-untyped]
    import json
    from pathlib import Path

    try:
        # Get service account path
        print("Service account JSON file path:")
        print("(Press Enter to use default: ~/.config/gcloud/application_default_credentials.json)")
        service_account_input = input("> ").strip()

        if not service_account_input:
            # Use default
            service_account_path = str(Path.home() / ".config" / "gcloud" / "application_default_credentials.json")
        else:
            # Expand ~ if present
            service_account_path = str(Path(service_account_input).expanduser())

        # Validate service account file exists
        if not Path(service_account_path).exists():
            print(f"\nError: Service account file not found at: {service_account_path}")
            print(ErrorMessages.after_auto_setup_failure())
            sys.exit(1)

        # Validate service account file is valid JSON
        try:
            with open(service_account_path, 'r') as f:
                sa_data = json.load(f)

            # Basic validation
            required_fields = ['type', 'project_id', 'private_key', 'client_email']
            missing_fields = [field for field in required_fields if field not in sa_data]

            if missing_fields:
                print(f"\nError: Service account file is missing required fields: {', '.join(missing_fields)}")
                print(ErrorMessages.after_auto_setup_failure())
                sys.exit(1)

            if sa_data.get('type') != 'service_account':
                print(f"\nError: Invalid service account type: {sa_data.get('type')}")
                print(ErrorMessages.after_auto_setup_failure())
                sys.exit(1)

        except json.JSONDecodeError as e:
            print(f"\nError: Service account file is not valid JSON: {e}")
            print(ErrorMessages.after_auto_setup_failure())
            sys.exit(1)

        # Get project ID
        print("\nGCP Project ID:")
        project_id = input("> ").strip()

        if not project_id:
            print("\nError: Project ID is required")
            print(ErrorMessages.after_auto_setup_failure())
            sys.exit(1)

        # Create config directory
        config_dir = Path.home() / ".config" / "agent-gcptoolkit"
        config_dir.mkdir(parents=True, exist_ok=True)

        # Create config file
        config_path = config_dir / "config.yml"
        config_data = {
            'authentication': {
                'type': 'service_account',
                'service_account_path': service_account_path
            },
            'gcp': {
                'project_id': project_id
            }
        }

        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        print(f"\n✓ Configuration created at: {config_path}")

        # Verify configuration works
        print("\nVerifying configuration...")
        from myagents.backend.services.agents.domains.config_checker.config_validator import validate_config

        is_valid, errors = validate_config(str(config_path))

        if is_valid:
            print("✓ Configuration verified successfully")

            # Test secret retrieval
            print("\nTesting secret retrieval (GEMINI_API_KEY)...")
            try:
                from myagents.backend.services.agents.domains.secrets import get_secret
                get_secret("GEMINI_API_KEY")
                print("✓ Secret retrieval successful")
            except Exception as e:
                print(f"⚠ Warning: Could not test secret retrieval: {e}")
                print("  You may need to verify Secret Manager access manually")

            # Display success message
            print(ErrorMessages.after_auto_setup_success())
            return True
        else:
            print("✗ Configuration validation failed:")
            for error in errors:
                print(f"  - {error}")
            print(ErrorMessages.after_auto_setup_failure())
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(130)
    except EOFError:
        print("\n\nNo input available.")
        print(ErrorMessages.after_auto_setup_failure())
        sys.exit(1)
    except Exception as e:
        print(f"\nError during setup: {e}")
        import traceback
        traceback.print_exc()
        print(ErrorMessages.after_auto_setup_failure())
        sys.exit(1)


def ensure_config_or_exit() -> None:
    """Ensure gcptoolkit config exists or prompt setup/exit.

    This is the main entry point for config checking. It will:
    1. Check if config exists
    2. If missing + interactive: prompt for auto-setup
    3. If missing + non-interactive: display error and exit

    Raises:
        SystemExit: Exits with code 1 if config is missing and setup fails/declined
    """
    if check_gcptoolkit_config():
        # Config exists, continue
        return

    # Config is missing
    if is_interactive_terminal():
        # Interactive terminal: prompt for auto-setup
        prompt_auto_setup()
    else:
        # Non-interactive: display error and exit
        print(ErrorMessages.missing_config_non_interactive(), file=sys.stderr)
        sys.exit(1)
