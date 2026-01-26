"""
AgenticTmux - Terminal session management for AgenticEngineering workflows.

This module provides tmux session management commands integrated with
AgenticGuidance services. It acts as a thin presentation layer over
the SessionService in AgenticGuidance.

Usage:
    agentic-tmux session create <name>
    agentic-tmux session attach <name>
    agentic-tmux session list
    agentic-tmux session kill <name>
"""

__version__ = "0.1.0"
