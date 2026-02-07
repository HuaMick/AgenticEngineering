"""Shell completion installation and management.

This module provides commands to install and manage shell auto-completion
for the agentic CLI using Typer's built-in completion support.
"""

import subprocess
import sys
from pathlib import Path

from agenticcli.console import print_info, print_error, print_success


def handle(args, ctx=None):
    """Handle completion command.

    Args:
        args: Parsed command-line arguments
        ctx: CLI context (optional)
    """
    if args.completion_command == "install":
        install_completion(args.shell)
    elif args.completion_command == "show":
        show_completion(args.shell)
    else:
        print_error("Unknown completion command. Use 'install' or 'show'.")
        sys.exit(1)


def install_completion(shell: str):
    """Install shell completion for the specified shell.

    Args:
        shell: Shell type (bash, zsh, fish, powershell)
    """
    print_info(f"Installing shell completion for {shell}...")

    # Use typer's built-in completion via the agentic-complete entry point
    try:
        # Run the typer app's install-completion command
        result = subprocess.run(
            ["agentic-complete", "--install-completion", shell],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print_success(f"Shell completion for {shell} installed successfully!")
            print_info(f"\nRestart your shell or run:")
            if shell == "bash":
                print_info("  source ~/.bashrc")
            elif shell == "zsh":
                print_info("  source ~/.zshrc")
            elif shell == "fish":
                print_info("  source ~/.config/fish/config.fish")
            print_info("\nThen try: agentic <TAB><TAB>")
        else:
            print_error(f"Failed to install completion: {result.stderr}")
            print_info("\nAlternative: Add this to your shell config:")
            print_info(f"  eval \"$(agentic-complete --show-completion {shell})\"")
            sys.exit(1)

    except FileNotFoundError:
        print_error("agentic-complete command not found.")
        print_info("\nPlease reinstall AgenticCLI with:")
        print_info("  cd modules/AgenticCLI")
        print_info("  pip install -e .")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error installing completion: {e}")
        sys.exit(1)


def show_completion(shell: str):
    """Show the completion script for the specified shell.

    Args:
        shell: Shell type (bash, zsh, fish, powershell)
    """
    try:
        # Get the completion script from typer
        result = subprocess.run(
            ["agentic-complete", "--show-completion", shell],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print(result.stdout)
        else:
            print_error(f"Failed to get completion script: {result.stderr}")
            sys.exit(1)

    except FileNotFoundError:
        print_error("agentic-complete command not found.")
        print_info("\nPlease reinstall AgenticCLI with:")
        print_info("  cd modules/AgenticCLI")
        print_info("  pip install -e .")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error getting completion script: {e}")
        sys.exit(1)
