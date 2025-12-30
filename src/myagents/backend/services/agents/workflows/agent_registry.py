"""Agent registry for dynamic agent invocation.

This module provides a centralized registry for all backend agents,
enabling dynamic loading and invocation of agent runners and factories.

Usage:
    from myagents.backend.services.agents.workflows.agent_registry import (
        get_agent_runner,
        get_agent_factory,
        list_agents,
    )

    # Get a runner function
    runner = get_agent_runner("builder")
    response, state = runner(user_input, state)

    # List available agents
    agents = list_agents()  # ['builder', 'coding']
"""
import importlib
from typing import Callable, Dict, Any, Optional, List


# Agent registry configuration
# Each entry maps an agent name to its module path and entry points
AGENT_REGISTRY: Dict[str, Dict[str, str]] = {
    "builder": {
        "module": "myagents.backend.services.agents.workflows.builder_agent",
        "runner": "run_builder_agent",
        "factory": "create_builder_agent",
        "description": "File operations agent with tool-calling support",
    },
    "coding": {
        # Alias for backward compatibility
        "module": "myagents.backend.services.agents.workflows.builder_agent",
        "runner": "run_builder_agent",
        "factory": "create_builder_agent",
        "description": "Alias for builder agent (backward compatibility)",
    },
    "cleaner-identify": {
        "module": "myagents.backend.services.agents.workflows.cleaner_agent",
        "runner": "run_cleaner_identify",
        "factory": "create_cleaner_agent",
        "description": "Cleaner agent identification mode - scans for cleanup targets",
    },
    "cleaner-execute": {
        "module": "myagents.backend.services.agents.workflows.cleaner_agent",
        "runner": "run_cleaner_execute",
        "factory": "create_cleaner_agent",
        "description": "Cleaner agent execution mode - processes approved targets",
    },
    # Test agents
    "test-runner": {
        "module": "myagents.backend.services.agents.workflows.test_agent",
        "runner": "run_test_runner",
        "factory": "create_test_agent",
        "description": "Test runner agent - executes tests and reports results",
    },
    "test-audit": {
        "module": "myagents.backend.services.agents.workflows.test_agent",
        "runner": "run_test_audit",
        "factory": "create_test_agent",
        "description": "Test audit agent - reviews test quality and skip patterns",
    },
    "test-user-sim": {
        "module": "myagents.backend.services.agents.workflows.test_agent",
        "runner": "run_test_user_simulator",
        "factory": "create_test_agent",
        "description": "User simulator agent - tests from documentation perspective",
    },
    # Explore agents
    "explore-architecture": {
        "module": "myagents.backend.services.agents.workflows.explore_agent",
        "runner": "run_explore_architecture",
        "factory": "create_explore_agent",
        "description": "Architecture explorer - analyzes project structure",
    },
    "explore-feature": {
        "module": "myagents.backend.services.agents.workflows.explore_agent",
        "runner": "run_explore_feature",
        "factory": "create_explore_agent",
        "description": "Feature explorer - analyzes feature implementations",
    },
    "explore-dependency": {
        "module": "myagents.backend.services.agents.workflows.explore_agent",
        "runner": "run_explore_dependency",
        "factory": "create_explore_agent",
        "description": "Dependency explorer - maps project dependencies",
    },
    "explore-test": {
        "module": "myagents.backend.services.agents.workflows.explore_agent",
        "runner": "run_explore_test",
        "factory": "create_explore_agent",
        "description": "Test explorer - analyzes testing patterns",
    },
    "explore-synthesis": {
        "module": "myagents.backend.services.agents.workflows.explore_agent",
        "runner": "run_explore_synthesis",
        "factory": "create_explore_agent",
        "description": "Synthesis explorer - combines all exploration findings",
    },
}


def get_agent_runner(agent_type: str) -> Callable:
    """Get the runner function for an agent type.

    Args:
        agent_type: The type of agent (e.g., 'builder', 'coding')

    Returns:
        The agent's runner function

    Raises:
        ValueError: If agent_type is not in the registry
    """
    if agent_type not in AGENT_REGISTRY:
        available = list(AGENT_REGISTRY.keys())
        raise ValueError(f"Unknown agent: {agent_type}. Available: {available}")

    entry = AGENT_REGISTRY[agent_type]
    module = importlib.import_module(entry["module"])
    return getattr(module, entry["runner"])


def get_agent_factory(agent_type: str) -> Callable:
    """Get the factory function for an agent type.

    Args:
        agent_type: The type of agent (e.g., 'builder', 'coding')

    Returns:
        The agent's factory function (creates the workflow)

    Raises:
        ValueError: If agent_type is not in the registry
    """
    if agent_type not in AGENT_REGISTRY:
        available = list(AGENT_REGISTRY.keys())
        raise ValueError(f"Unknown agent: {agent_type}. Available: {available}")

    entry = AGENT_REGISTRY[agent_type]
    module = importlib.import_module(entry["module"])
    return getattr(module, entry["factory"])


def list_agents() -> List[str]:
    """List all available agent types.

    Returns:
        List of agent type names
    """
    return list(AGENT_REGISTRY.keys())


def get_agent_description(agent_type: str) -> str:
    """Get the description for an agent type.

    Args:
        agent_type: The type of agent

    Returns:
        The agent's description

    Raises:
        ValueError: If agent_type is not in the registry
    """
    if agent_type not in AGENT_REGISTRY:
        available = list(AGENT_REGISTRY.keys())
        raise ValueError(f"Unknown agent: {agent_type}. Available: {available}")

    return AGENT_REGISTRY[agent_type].get("description", "No description available")


def register_agent(
    agent_type: str,
    module: str,
    runner: str,
    factory: Optional[str] = None,
    description: str = "",
) -> None:
    """Register a new agent type dynamically.

    Args:
        agent_type: The name for the agent type
        module: The module path containing the agent
        runner: The name of the runner function in the module
        factory: Optional factory function name
        description: Description of the agent

    Raises:
        ValueError: If agent_type already exists
    """
    if agent_type in AGENT_REGISTRY:
        raise ValueError(f"Agent '{agent_type}' already registered")

    entry: Dict[str, str] = {
        "module": module,
        "runner": runner,
    }
    if factory:
        entry["factory"] = factory
    if description:
        entry["description"] = description

    AGENT_REGISTRY[agent_type] = entry
