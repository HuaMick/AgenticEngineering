"""Workers for background tasks in the relay service.

This module provides background workers for periodic tasks:
- cleanup_worker: Periodically closes expired and dead sessions
"""

from .cleanup_worker import start_cleanup_task

__all__ = ["start_cleanup_task"]
