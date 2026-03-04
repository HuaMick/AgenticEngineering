"""Task workflow - compatibility shim.

This module is retained for backwards compatibility.
New code should import from ticket_workflow instead:

    from agenticcli.workflows.ticket_workflow import TicketPresetWorkflow

TaskPresetWorkflow is an alias for TicketPresetWorkflow.
"""

from agenticcli.workflows.ticket_workflow import PresetLoadResult, TicketPresetWorkflow

# Backwards-compatible alias
TaskPresetWorkflow = TicketPresetWorkflow

__all__ = [
    "PresetLoadResult",
    "TaskPresetWorkflow",
    "TicketPresetWorkflow",
]
