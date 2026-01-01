"""FastAPI REST API for relay session management.

Exports the FastAPI app instance for use by server runners (uvicorn, etc).

Note: For production use, import from server.py which includes WebSocket routes
and lifecycle handlers. This module exports the base app for flexibility.
"""

from .api import app

__all__ = ["app"]
