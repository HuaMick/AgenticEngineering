"""Help Workflow for MyAgents CLI.

This workflow provides help, version, and documentation display functionality.
Extracted from myagents.frontend/cli/myagents_cli.py to follow the Domain → Workflow → Entrypoint pattern.
"""

import sys
from importlib.metadata import version, PackageNotFoundError
from typing import Dict, List, Optional


class HelpWorkflow:
    """Workflow for CLI help, version, and documentation.

    This workflow provides multiple entrypoints for:
    - Displaying main CLI help
    - Showing command-specific help
    - Displaying version information
    - Showing workflow documentation
    - Generating usage examples
    """

    def __init__(self):
        """Initialize the help workflow."""
        pass

    def show_version(self) -> str:
        """Display version information.

        Returns:
            str: Version string in format "myagents X.Y.Z" or "myagents (development version)"
        """
        try:
            pkg_version = version("myagents")
            return f"myagents {pkg_version}"
        except PackageNotFoundError:
            return "myagents (development version)"

    def show_main_help(self) -> str:
        """Display main CLI help text.

        Returns:
            str: Main help text with command overview
        """
        help_text = """
MyAgents - LangGraph agent framework with Studio integration

Usage:
  myagents [command] [options]

Commands:
  chat                    Start interactive agent chat
  studio                  Manage LangGraph Studio (start/stop/status/restart)
  preferences             Manage user preferences (get/set/delete/list/clear)
  config                  Configuration management (init/set-path/show/clear)
  secrets                 Secret management operations (get)
  update                  Reinstall myagents from current source
  rebuild                 Rebuild and reinstall myagents package

Options:
  --version, -v           Show version information
  --help, -h              Show this help message

Examples:
  myagents chat                              # Start interactive chat
  myagents studio start                      # Start LangGraph Studio
  myagents preferences set agent.default coding
  myagents config init                       # Interactive config setup
  myagents secrets get GEMINI_API_KEY

For detailed help on a specific command, use:
  myagents [command] --help
"""
        return help_text.strip()

    def show_command_help(self, command: str) -> str:
        """Show help for a specific command.

        Args:
            command: Command name to show help for

        Returns:
            str: Help text for the specified command
        """
        command_help = {
            "chat": self._get_chat_help(),
            "studio": self._get_studio_help(),
            "preferences": self._get_preferences_help(),
            "config": self._get_config_help(),
            "secrets": self._get_secrets_help(),
            "update": self._get_update_help(),
            "rebuild": self._get_rebuild_help()
        }

        return command_help.get(command, f"No help available for command: {command}")

    def show_workflow_docs(self, workflow: str) -> str:
        """Show documentation for a specific workflow.

        Args:
            workflow: Workflow name (e.g., "health_check", "studio", "preferences")

        Returns:
            str: Documentation for the specified workflow
        """
        workflow_docs = {
            "health_check": self._get_health_check_docs(),
            "studio": self._get_studio_workflow_docs(),
            "setup": self._get_setup_workflow_docs(),
            "preferences": self._get_setup_workflow_docs(),  # Alias for backward compatibility
            "help": self._get_help_workflow_docs()
        }

        return workflow_docs.get(workflow, f"No documentation available for workflow: {workflow}")

    def generate_usage_examples(self, command: Optional[str] = None) -> List[str]:
        """Generate usage examples for commands.

        Args:
            command: Optional command name to generate examples for. If None, returns all examples.

        Returns:
            List[str]: List of usage example strings
        """
        all_examples = {
            "chat": [
                "myagents chat",
                "myagents chat --agent echo",
                "myagents c -a coding"
            ],
            "studio": [
                "myagents studio start",
                "myagents studio start --port 3000",
                "myagents studio start --foreground",
                "myagents studio stop",
                "myagents studio stop --force",
                "myagents studio restart",
                "myagents studio status"
            ],
            "preferences": [
                "myagents preferences set agent.default coding",
                "myagents preferences get agent.default",
                "myagents preferences set studio.port 3000",
                "myagents preferences list",
                "myagents preferences delete agent.default",
                "myagents preferences clear"
            ],
            "config": [
                "myagents config init",
                "myagents config set-path /path/to/config.yml",
                "myagents config show",
                "myagents config clear"
            ],
            "secrets": [
                "myagents secrets get GEMINI_API_KEY",
                "myagents secrets get MY_SECRET --project-id my-project",
                "myagents secrets get MY_SECRET -q"
            ],
            "update": [
                "myagents update"
            ],
            "rebuild": [
                "myagents rebuild"
            ]
        }

        if command:
            return all_examples.get(command, [f"# No examples available for: {command}"])

        # Return all examples
        all_example_list = []
        for cmd, examples in all_examples.items():
            all_example_list.append(f"# {cmd.upper()} examples:")
            all_example_list.extend(examples)
            all_example_list.append("")  # blank line between sections

        return all_example_list

    # Private helper methods for detailed help text

    def _get_chat_help(self) -> str:
        """Get detailed help for chat command."""
        return """
Chat Command - Start interactive agent chat

Usage:
  myagents chat [options]
  myagents c [options]              # Alias

Options:
  --agent, -a AGENT    Agent type to use: coding (default) or echo

Description:
  Start an interactive chat session with a MyAgents agent. The chat
  supports natural language conversations and the coding agent can
  execute file operations, code generation, and more.

  Type 'quit', 'exit', or 'q' to end the chat session.

Examples:
  myagents chat                     # Start with coding agent (default)
  myagents chat --agent echo        # Start with echo agent
  myagents c -a coding              # Using alias

Note:
  This is a PROJECT-SCOPED command. Must be run from within a
  MyAgents project directory (containing langgraph.json).
""".strip()

    def _get_studio_help(self) -> str:
        """Get detailed help for studio command."""
        return """
Studio Command - Manage LangGraph Studio

Usage:
  myagents studio <subcommand> [options]

Subcommands:
  start       Start LangGraph Studio
  stop        Stop LangGraph Studio
  restart     Restart LangGraph Studio
  status      Show Studio status

Start Options:
  --port, -p PORT        Port for Studio server (default: 2024)
  --foreground, -f       Run in foreground instead of background

Stop Options:
  --force                Force kill if graceful shutdown fails

Examples:
  myagents studio start                    # Start in background
  myagents studio start --port 3000        # Start on custom port
  myagents studio start --foreground       # Start in foreground
  myagents studio stop                     # Graceful shutdown
  myagents studio stop --force             # Force kill
  myagents studio restart                  # Restart Studio
  myagents studio status                   # Check status

Note:
  This is a PROJECT-SCOPED command. Must be run from within a
  MyAgents project directory (containing langgraph.json).
""".strip()

    def _get_preferences_help(self) -> str:
        """Get detailed help for preferences command."""
        return """
Preferences Command - Manage user preferences

Usage:
  myagents preferences <subcommand> [arguments]
  myagents prefs <subcommand> [arguments]     # Alias
  myagents pref <subcommand> [arguments]      # Alias

Subcommands:
  get KEY              Get a preference value
  set KEY VALUE        Set a preference value
  delete KEY           Delete a preference (aliases: del, rm)
  list                 List all preferences (alias: ls)
  clear                Clear all preferences

Description:
  Preferences support dot notation for nested keys (e.g., 'agent.default').
  Values can be JSON (objects, arrays, numbers, booleans) or strings.

Examples:
  myagents preferences set agent.default coding
  myagents preferences get agent.default
  myagents preferences set studio.port 3000
  myagents prefs list
  myagents pref delete agent.default
  myagents preferences clear

Note:
  This is a PROJECT-SCOPED command. Must be run from within a
  MyAgents project directory (containing langgraph.json).
""".strip()

    def _get_config_help(self) -> str:
        """Get detailed help for config command."""
        return """
Config Command - Configuration management

Usage:
  myagents config <subcommand> [arguments]

Subcommands:
  init              Interactive config setup
  set-path PATH     Set config file path
  show              Show current config path
  clear             Clear config path preference

Description:
  Manage MyAgents configuration file location and settings.
  This delegates to agent_gcptoolkit for configuration management.

Examples:
  myagents config init                           # Interactive setup
  myagents config set-path /path/to/config.yml   # Set custom path
  myagents config show                           # Show current path
  myagents config clear                          # Clear custom path
""".strip()

    def _get_secrets_help(self) -> str:
        """Get detailed help for secrets command."""
        return """
Secrets Command - Secret management operations

Usage:
  myagents secrets get SECRET_NAME [options]

Options:
  --project-id ID      GCP project ID (auto-detected if not provided)
  -q, --quiet          Output only the secret value (for scripts)

Description:
  Fetch secrets from GCP Secret Manager with automatic fallback to
  environment variables. Uses in-memory caching for performance.

  Secret name format: [a-zA-Z0-9_-]+ (no dots or special chars)

Exit Codes:
  0 - Secret found and printed
  1 - Secret not found
  2 - Invalid secret name format

Examples:
  myagents secrets get GEMINI_API_KEY
  myagents secrets get MY_SECRET --project-id my-project
  myagents secrets get MY_SECRET -q               # Quiet mode
""".strip()

    def _get_update_help(self) -> str:
        """Get detailed help for update command."""
        return """
Update Command - Reinstall myagents from current source

Usage:
  myagents update

Description:
  Reinstall the myagents package from its current source location.
  Uses 'uv sync' if available, falls back to 'pip install -e'.

  This is a GLOBAL command that can be run from any directory.

Example:
  myagents update
""".strip()

    def _get_rebuild_help(self) -> str:
        """Get detailed help for rebuild command."""
        return """
Rebuild Command - Rebuild and reinstall myagents package

Usage:
  myagents rebuild

Description:
  Clean previous build artifacts, rebuild the package from source,
  and reinstall it. Uses 'python -m build' for building and
  'uv sync' or 'pip install -e' for installation.

  This is a GLOBAL command that can be run from any directory.

Example:
  myagents rebuild
""".strip()

    def _get_health_check_docs(self) -> str:
        """Get workflow documentation for health_check."""
        return """
Health Check Workflow
=====================

Purpose:
  Provides health checking and context detection for the MyAgents CLI.

Entrypoints:
  - check_cli_health()        Verify CLI installation
  - check_project_health()    Verify project context
  - detect_context()          Combined detection for routing
  - validate_environment()    Check prerequisites

Usage:
  from myagents.backend.services.agents.workflows.health_check_workflow import HealthCheckWorkflow

  workflow = HealthCheckWorkflow()
  cli_health = workflow.check_cli_health()
  project_health = workflow.check_project_health()
  context = workflow.detect_context(command="chat")
  env_status = workflow.validate_environment()

Extracted From:
  HealthCheckWorkflow functions:
    - detect_cli_source_root()
    - detect_langgraph_path()
    - detect_config_path()
""".strip()

    def _get_studio_workflow_docs(self) -> str:
        """Get workflow documentation for studio."""
        return """
Studio Workflow
===============

Purpose:
  Manages the LangGraph Studio lifecycle including start, stop, restart,
  status checking, health verification, and state recovery.

Entrypoints:
  - start_studio()         Start Studio service
  - stop_studio()          Stop Studio
  - restart_studio()       Restart Studio
  - get_studio_status()    Get current status
  - check_studio_health()  Verify Studio responding
  - recover_studio_state() Recover from inconsistent state

Location:
  backend/services/agents/workflows/studio_workflow.py

Usage:
  from myagents.backend.services.agents.workflows.studio_workflow import (
      start_studio, stop_studio, restart_studio, get_studio_status
  )

  success, message = start_studio(home_config_dir, config_path)
  status = get_studio_status(home_config_dir, config_path)
""".strip()

    def _get_setup_workflow_docs(self) -> str:
        """Get workflow documentation for setup."""
        return """
Setup Workflow
==============

Purpose:
  Manages initial setup and user preferences with support for nested keys
  (dot notation), JSON values, and persistent storage.

Entrypoints:
  - run_setup()           Create initial configuration
  - get_preference()      Retrieve preference value
  - set_preference()      Set preference value
  - delete_preference()   Remove preference
  - list_preferences()    List all preferences
  - clear_preferences()   Remove all preferences

Location:
  backend/services/agents/src/workflows/setup_workflow.py

Usage:
  from myagents.backend.services.agents.workflows.setup_workflow import SetupWorkflow

  # Initial setup
  workflow = SetupWorkflow()
  success, msg = workflow.run_setup()

  # Preference management
  success, msg, value = workflow.get_preference(key="agent.default")
  success, msg = workflow.set_preference(key="agent.default", value="coding")
  success, msg, prefs = workflow.list_preferences()

Note:
  PreferencesWorkflow is now an alias for SetupWorkflow (backward compatibility).
""".strip()

    def _get_help_workflow_docs(self) -> str:
        """Get workflow documentation for help."""
        return """
Help Workflow
=============

Purpose:
  Provides help, version, and documentation display functionality
  for the MyAgents CLI.

Entrypoints:
  - show_main_help()           Display main CLI help
  - show_command_help()        Show command-specific help
  - show_version()             Display version
  - show_workflow_docs()       Show workflow documentation
  - generate_usage_examples()  Generate usage examples

Location:
  backend/services/agents/src/workflows/help_workflow.py

Usage:
  from myagents.backend.services.agents.workflows.help_workflow import HelpWorkflow

  workflow = HelpWorkflow()
  print(workflow.show_version())
  print(workflow.show_main_help())
  print(workflow.show_command_help("chat"))
  examples = workflow.generate_usage_examples("studio")
""".strip()
