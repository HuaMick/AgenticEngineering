# story: US-GDN-097, US-PLN-061
"""Phase routing validation utilities.

Validates that epic phases have complete agent routing configuration
in TinyDB. Used by ``transition_epic_status()`` for in_progress
precondition checks and by display/status commands.

Canonical enforcement of routing validity is in
``EpicRepository.transition_epic_status()`` — this module provides
the shared predicate.

Also provides ``has_any_routed_phase()`` for the weaker 'any phase has
routing' check used by status/display code paths.

# @story US-001
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agenticguidance.services.epic import PhaseData
    from agenticguidance.services.epic_repository import EpicRepository

logger = logging.getLogger(__name__)


def validate_phase_routing(
    repo: EpicRepository,
    epic_folder: str,
) -> tuple[bool, str | None]:
    """Check whether an epic's phases are fully routed and ready for execution.

    Encapsulates the shared predicate used by discovery and execution paths:
    1. Phases exist in TinyDB
    2. Every phase has an ``agent`` field set
    3. Not all tickets are still in ``proposed`` status (skeleton-only)

    Args:
        repo: An already-instantiated EpicRepository.
        epic_folder: Epic folder name (e.g., '260328AG_my_epic').

    Returns:
        Tuple of (is_valid, reason).
        If valid, reason is None.

    Examples:
        >>> is_valid, reason = validate_phase_routing(repo, "260328AG_my_epic")
        >>> if not is_valid:
        ...     print(f"Not ready: {reason}")
    """
    # 1. Check phases exist
    phases = repo.list_phases(epic_folder)
    if not phases:
        return False, "no phases in TinyDB"

    # 2. Check all phases have agent routing
    unrouted = [(p.phase_id or p.name) for p in phases if not p.agent]
    if unrouted:
        names = ", ".join(unrouted)
        return False, f"phases missing agent routing: {names}"

    # 2b. Check all agent names are in the valid roster
    from agenticcli.commands.epic import get_valid_agent_types

    valid_agents = get_valid_agent_types()
    if valid_agents:
        invalid = [((p.phase_id or p.name), p.agent) for p in phases if p.agent and p.agent not in valid_agents]
        if invalid:
            details = ", ".join(f"{label} (agent={agent})" for label, agent in invalid)
            return False, f"phases have invalid agent names: {details}"

    # 3. Check ticket status — all-proposed means skeleton only, needs planning
    epic_data = repo.get_epic(epic_folder)
    tickets = epic_data.tasks if epic_data else []
    if tickets and all(t.status == "proposed" for t in tickets):
        return False, f"all {len(tickets)} tickets still proposed"

    return True, None


def has_any_routed_phase(phases: list[PhaseData]) -> bool:
    """Check whether at least one phase has agent routing set.

    This is the weaker counterpart to ``validate_phase_routing()``:
    it checks *any* (not *all*) and operates on an already-fetched
    phase list rather than querying the repo itself.

    Used by status/display code to determine if an epic has any
    orchestration at all (e.g., ``_check_has_orchestration()`` and
    ``_collect_validation()`` in the epic CLI commands).

    Args:
        phases: List of PhaseData objects (may be empty).

    Returns:
        True if phases is non-empty and at least one has a truthy ``agent`` field.

    Examples:
        >>> has_any_routed_phase([])
        False
        >>> has_any_routed_phase([phase_with_agent, phase_without_agent])
        True
    """
    return bool(phases) and any(p.agent for p in phases)
