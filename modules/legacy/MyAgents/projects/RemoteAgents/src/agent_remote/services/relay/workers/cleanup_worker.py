"""Cleanup worker for expired and dead relay sessions.

This worker runs periodically in the background to:
1. Close sessions with expired pairing codes (5 minutes after creation)
2. Optionally detect and close sessions with dead WebSocket connections
3. Log cleanup events for observability

The worker is designed to be non-blocking and runs in its own asyncio task,
allowing WebSocket message routing to continue uninterrupted.
"""

import asyncio
import logging
from typing import Optional

from agent_remote.services.relay.workflows.relay_workflow import RelayWorkflow

# Configure logger for cleanup worker
logger = logging.getLogger(__name__)


async def run_cleanup_loop(workflow: RelayWorkflow, interval: int = 60) -> None:
    """Run cleanup loop to close expired sessions periodically.

    This is an infinite async loop that runs every `interval` seconds to:
    1. Retrieve all active sessions from the repository
    2. Check each session for expiry
    3. Close expired sessions via workflow.close_session()
    4. Log cleanup events

    The loop is designed to be resilient - exceptions during cleanup of
    individual sessions do not crash the entire loop.

    Args:
        workflow: RelayWorkflow instance with access to session repository
        interval: Cleanup interval in seconds (default: 60)

    Note:
        This function runs indefinitely and should be executed as an asyncio.Task.
        Use start_cleanup_task() for proper task management.

    Example:
        >>> workflow = RelayWorkflow(repository)
        >>> await run_cleanup_loop(workflow, interval=30)
        # Runs every 30 seconds until cancelled
    """
    logger.info(f"Starting cleanup worker with {interval}s interval")

    while True:
        try:
            # Wait for next cleanup cycle
            await asyncio.sleep(interval)

            # Get all active sessions (not in CLOSED state)
            active_sessions = workflow._repository.get_all_active()

            if not active_sessions:
                logger.debug("No active sessions to clean up")
                continue

            logger.debug(f"Checking {len(active_sessions)} active sessions for cleanup")

            # Track cleanup statistics
            expired_count = 0
            dead_ws_count = 0
            error_count = 0

            # Check each session for cleanup conditions
            for session in active_sessions:
                try:
                    session_id = str(session.session_id)

                    # Check if session has expired pairing code
                    if session.is_expired():
                        logger.info(
                            f"Closing expired session: {session_id} "
                            f"(pairing_code={session.pairing_code})"
                        )
                        workflow.close_session(session.session_id, "expired")
                        expired_count += 1
                        continue

                    # Optional: Check for dead WebSocket connections
                    # This is complex as we need to determine if WebSocket is still alive
                    # Different implementations (FastAPI, aiohttp) have different APIs
                    # For now, we skip this check and rely on explicit disconnect handling
                    #
                    # Potential approaches:
                    # 1. Check WebSocket state attribute (e.g., ws.client_state)
                    # 2. Send ping/pong to detect dead connections
                    # 3. Track last activity timestamp in Session entity
                    #
                    # Example implementation (FastAPI):
                    # if session.desktop_ws is not None:
                    #     try:
                    #         if session.desktop_ws.client_state == WebSocketState.DISCONNECTED:
                    #             logger.info(f"Closing session with dead desktop WebSocket: {session_id}")
                    #             workflow.close_session(session.session_id, "desktop_disconnected")
                    #             dead_ws_count += 1
                    #             continue
                    #     except Exception as e:
                    #         logger.warning(f"Failed to check desktop WebSocket state: {e}")
                    #
                    # if session.client_ws is not None:
                    #     try:
                    #         if session.client_ws.client_state == WebSocketState.DISCONNECTED:
                    #             logger.info(f"Closing session with dead client WebSocket: {session_id}")
                    #             workflow.close_session(session.session_id, "client_disconnected")
                    #             dead_ws_count += 1
                    #             continue
                    #     except Exception as e:
                    #         logger.warning(f"Failed to check client WebSocket state: {e}")

                except Exception as e:
                    # Log error but continue processing other sessions
                    logger.error(
                        f"Failed to clean up session {session.session_id}: {e}",
                        exc_info=True
                    )
                    error_count += 1

            # Log cleanup summary if any actions were taken
            if expired_count > 0 or dead_ws_count > 0 or error_count > 0:
                logger.info(
                    f"Cleanup cycle completed: "
                    f"expired={expired_count}, "
                    f"dead_ws={dead_ws_count}, "
                    f"errors={error_count}"
                )

        except asyncio.CancelledError:
            # Task was cancelled - clean shutdown
            logger.info("Cleanup worker cancelled, shutting down gracefully")
            raise

        except Exception as e:
            # Unexpected error in cleanup loop - log and continue
            logger.error(f"Unexpected error in cleanup loop: {e}", exc_info=True)
            # Continue loop despite error


def start_cleanup_task(
    workflow: RelayWorkflow,
    interval: int = 60
) -> asyncio.Task:
    """Start cleanup task for background session cleanup.

    Creates and returns an asyncio.Task that runs the cleanup loop.
    Suitable for use in FastAPI startup events or other async initialization.

    The task runs indefinitely until cancelled or the event loop stops.

    Args:
        workflow: RelayWorkflow instance with access to session repository
        interval: Cleanup interval in seconds (default: 60)

    Returns:
        asyncio.Task that can be awaited or cancelled

    Example (FastAPI):
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>>
        >>> cleanup_task: Optional[asyncio.Task] = None
        >>>
        >>> @app.on_event("startup")
        >>> async def startup_event():
        ...     global cleanup_task
        ...     workflow = RelayWorkflow(repository)
        ...     cleanup_task = start_cleanup_task(workflow, interval=30)
        ...     logger.info("Cleanup worker started")
        >>>
        >>> @app.on_event("shutdown")
        >>> async def shutdown_event():
        ...     global cleanup_task
        ...     if cleanup_task is not None:
        ...         cleanup_task.cancel()
        ...         try:
        ...             await cleanup_task
        ...         except asyncio.CancelledError:
        ...             logger.info("Cleanup worker stopped")

    Example (standalone):
        >>> workflow = RelayWorkflow(repository)
        >>> task = start_cleanup_task(workflow)
        >>> # Let it run in background
        >>> await asyncio.sleep(300)  # Run for 5 minutes
        >>> task.cancel()
        >>> await task  # Wait for graceful shutdown
    """
    task = asyncio.create_task(run_cleanup_loop(workflow, interval))
    logger.info(f"Cleanup task created with {interval}s interval")
    return task
