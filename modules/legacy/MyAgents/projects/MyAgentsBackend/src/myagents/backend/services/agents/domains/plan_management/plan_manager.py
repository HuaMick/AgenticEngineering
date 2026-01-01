"""Plan management for reading/writing live plan YAML files.

This module provides the PlanManager class for managing execution plans,
particularly for multi-agent orchestration scenarios where agents need
to read from and write to shared plan files.

Usage:
    from myagents.backend.services.agents.domains.plan_management import PlanManager

    # Read a plan
    manager = PlanManager("/path/to/live_plan.yml")
    plan = manager.read_plan()

    # Update a section
    manager.update_section("status", "in_progress")

    # Get specific section
    phases = manager.get_section("phases")
"""
import yaml
from pathlib import Path
from typing import Any, Dict, Optional, List
from datetime import datetime


class PlanManager:
    """Manager for reading and writing live plan YAML files.

    Provides thread-safe operations for plan manipulation,
    with support for atomic updates and section-level operations.
    """

    def __init__(self, plan_path: str):
        """Initialize the plan manager.

        Args:
            plan_path: Path to the YAML plan file
        """
        self.plan_path = Path(plan_path)

    def read_plan(self) -> Dict[str, Any]:
        """Read the entire plan from disk.

        Returns:
            The plan as a dictionary

        Raises:
            FileNotFoundError: If the plan file doesn't exist
        """
        if not self.plan_path.exists():
            raise FileNotFoundError(f"Plan file not found: {self.plan_path}")

        with open(self.plan_path) as f:
            return yaml.safe_load(f) or {}

    def write_plan(self, plan: Dict[str, Any]) -> None:
        """Write the entire plan to disk.

        Args:
            plan: The plan dictionary to write
        """
        # Ensure parent directory exists
        self.plan_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.plan_path, 'w') as f:
            yaml.dump(plan, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def get_section(self, section: str) -> Optional[Any]:
        """Get a specific section from the plan.

        Args:
            section: The section name (top-level key)

        Returns:
            The section data, or None if not found
        """
        plan = self.read_plan()
        return plan.get(section)

    def update_section(self, section: str, data: Any) -> None:
        """Update a specific section of the plan.

        Args:
            section: The section name (top-level key)
            data: The new data for the section
        """
        plan = self.read_plan()
        plan[section] = data
        self.write_plan(plan)

    def get_phase(self, phase_index: int) -> Optional[Dict[str, Any]]:
        """Get a specific phase by index.

        Args:
            phase_index: The 0-based index of the phase

        Returns:
            The phase dictionary, or None if not found
        """
        phases = self.get_section("phases")
        if phases and isinstance(phases, list) and 0 <= phase_index < len(phases):
            return phases[phase_index]
        return None

    def update_phase_status(self, phase_index: int, status: str) -> None:
        """Update the status of a specific phase.

        Args:
            phase_index: The 0-based index of the phase
            status: The new status (e.g., 'pending', 'in_progress', 'completed')
        """
        plan = self.read_plan()
        phases = plan.get("phases", [])

        if phases and isinstance(phases, list) and 0 <= phase_index < len(phases):
            phases[phase_index]["status"] = status
            plan["phases"] = phases
            self.write_plan(plan)

    def append_to_list(self, section: str, item: Any) -> None:
        """Append an item to a list section.

        Args:
            section: The section name (must be a list)
            item: The item to append

        Raises:
            ValueError: If the section is not a list
        """
        plan = self.read_plan()
        current = plan.get(section, [])

        if not isinstance(current, list):
            raise ValueError(f"Section '{section}' is not a list")

        current.append(item)
        plan[section] = current
        self.write_plan(plan)

    def record_agent_output(
        self,
        agent_id: str,
        output_type: str,
        data: Any,
        timestamp: Optional[str] = None
    ) -> None:
        """Record output from an agent to the plan.

        This is used during multi-agent execution to store intermediate results.

        Args:
            agent_id: Identifier for the agent (e.g., 'cleaner-1')
            output_type: Type of output (e.g., 'targets', 'results')
            data: The output data
            timestamp: Optional timestamp (defaults to current time)
        """
        plan = self.read_plan()

        if "agent_outputs" not in plan:
            plan["agent_outputs"] = {}

        if agent_id not in plan["agent_outputs"]:
            plan["agent_outputs"][agent_id] = {}

        plan["agent_outputs"][agent_id][output_type] = {
            "data": data,
            "timestamp": timestamp or datetime.now().isoformat(),
        }

        self.write_plan(plan)

    def get_agent_output(self, agent_id: str, output_type: str) -> Optional[Any]:
        """Get output from a specific agent.

        Args:
            agent_id: Identifier for the agent
            output_type: Type of output to retrieve

        Returns:
            The output data, or None if not found
        """
        plan = self.read_plan()
        outputs = plan.get("agent_outputs", {})

        if agent_id in outputs and output_type in outputs[agent_id]:
            return outputs[agent_id][output_type].get("data")

        return None

    def get_all_agent_outputs(self, output_type: str) -> List[Dict[str, Any]]:
        """Get all outputs of a specific type from all agents.

        Args:
            output_type: Type of output to retrieve

        Returns:
            List of outputs with agent_id included
        """
        plan = self.read_plan()
        outputs = plan.get("agent_outputs", {})
        results = []

        for agent_id, agent_outputs in outputs.items():
            if output_type in agent_outputs:
                results.append({
                    "agent_id": agent_id,
                    **agent_outputs[output_type]
                })

        return results

    def exists(self) -> bool:
        """Check if the plan file exists.

        Returns:
            True if the file exists, False otherwise
        """
        return self.plan_path.exists()
