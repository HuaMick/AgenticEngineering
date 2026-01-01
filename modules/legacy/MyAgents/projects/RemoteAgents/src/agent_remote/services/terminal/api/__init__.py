"""Terminal service API module.

This module exports the FastAPI application and WebSocket router for the terminal service.
"""

from agent_remote.services.terminal.api.websockets import router

__all__ = ["router"]
