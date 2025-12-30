"""Server entrypoint combining REST API, WebSocket endpoints, and background workers.

This module is the main entry point for running the relay service. It combines:
1. FastAPI REST API from api.py (session management endpoints)
2. WebSocket router from websockets.py (desktop/client connections)
3. Cleanup worker from cleanup_worker.py (expired session cleanup)

The server is configured to:
- Listen on 0.0.0.0:8080 (all interfaces, default relay port)
- Run with single worker (required for in-memory repository)
- Start cleanup worker automatically on startup
- Gracefully shutdown cleanup worker on exit

Usage:
    # Run server directly
    python -m agent_remote.services.relay.api.server

    # Run with uvicorn CLI
    uvicorn agent_remote.services.relay.api.server:app --host 0.0.0.0 --port 8080

Configuration:
    - RELAY_HOST: Host to bind to (default: 0.0.0.0)
    - RELAY_PORT: Port to listen on (default: 8080)
    - CLEANUP_INTERVAL: Cleanup worker interval in seconds (default: 60)
    - LOG_LEVEL: Logging level (default: INFO)
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI

from agent_remote.services.relay.api.api import (
    get_repository,
    get_workflow,
    app as api_app,
)
from agent_remote.services.relay.api.websockets import router as websocket_router
from agent_remote.services.relay.workers.cleanup_worker import start_cleanup_task

# ==============================================================================
# Logging Configuration
# ==============================================================================

# Get log level from environment or default to INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Configure root logger
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


# ==============================================================================
# Lifespan Context Manager
# ==============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events.

    This replaces the deprecated @app.on_event("startup") and @app.on_event("shutdown")
    decorators with the modern lifespan pattern recommended by FastAPI.

    On startup:
    1. Log startup message with configuration
    2. Get repository and workflow instances
    3. Start cleanup worker task
    4. Log successful initialization

    On shutdown:
    1. Cancel cleanup worker task
    2. Wait for graceful shutdown
    3. Log shutdown completion

    Args:
        app: FastAPI application instance
    """
    # ==================== STARTUP ====================
    logger.info("=" * 70)
    logger.info("Starting Agent Remote Relay Service")
    logger.info("=" * 70)
    logger.info(f"Log Level: {LOG_LEVEL}")
    logger.info(f"Cleanup Interval: {get_cleanup_interval()}s")

    # Get repository and workflow instances
    repository = get_repository()
    workflow = get_workflow(repository)

    logger.info(f"Repository initialized: {repository}")
    logger.info(f"Workflow initialized: {workflow.__class__.__name__}")

    # Start cleanup worker
    cleanup_interval = get_cleanup_interval()
    cleanup_task = start_cleanup_task(workflow, interval=cleanup_interval)
    logger.info(f"Cleanup worker started (interval: {cleanup_interval}s)")

    logger.info("=" * 70)
    logger.info("Relay service startup complete")
    logger.info("=" * 70)

    yield  # Application runs here

    # ==================== SHUTDOWN ====================
    logger.info("=" * 70)
    logger.info("Shutting down Agent Remote Relay Service")
    logger.info("=" * 70)

    # Cancel cleanup worker if running
    if cleanup_task is not None:
        logger.info("Stopping cleanup worker...")
        cleanup_task.cancel()

        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("Cleanup worker stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping cleanup worker: {e}")

    logger.info("=" * 70)
    logger.info("Relay service shutdown complete")
    logger.info("=" * 70)


# ==============================================================================
# Create App with Lifespan
# ==============================================================================

# Create a new app that wraps the API app with lifespan management
# We need to re-export the app from api.py but with lifespan attached
# Since FastAPI doesn't allow changing lifespan after creation, we mount the routes

from agent_remote.services.relay.api.api import (
    CORSMiddleware,
    session_expired_handler,
    invalid_pairing_code_handler,
    session_already_paired_handler,
    session_not_found_handler,
    SessionExpiredException,
    InvalidPairingCodeException,
    SessionAlreadyPairedException,
    SessionNotFoundException,
)
from agent_remote.services.relay.api.api import router as api_router

# Create the main app with lifespan
app = FastAPI(
    title="Agent Remote Relay API",
    description="REST API for managing relay sessions between desktop and web clients",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Flutter web client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
app.add_exception_handler(SessionExpiredException, session_expired_handler)
app.add_exception_handler(InvalidPairingCodeException, invalid_pairing_code_handler)
app.add_exception_handler(SessionAlreadyPairedException, session_already_paired_handler)
app.add_exception_handler(SessionNotFoundException, session_not_found_handler)

# Include API routes
app.include_router(api_router)

# Include WebSocket router from websockets.py
app.include_router(websocket_router, tags=["WebSocket"])

logger.info("Routes registered:")
logger.info("  REST API:")
logger.info("    - POST /api/sessions")
logger.info("    - GET /api/sessions/{session_id}")
logger.info("    - DELETE /api/sessions/{session_id}")
logger.info("  WebSocket:")
logger.info("    - GET /ws/desktop/{session_id}")
logger.info("    - GET /ws/client/{pairing_code}")


# ==============================================================================
# Configuration Helpers
# ==============================================================================


def get_cleanup_interval() -> int:
    """Get cleanup interval from environment or default to 60 seconds.

    Returns:
        Cleanup interval in seconds
    """
    try:
        interval = int(os.getenv("CLEANUP_INTERVAL", "60"))
        if interval < 10:
            logger.warning(f"CLEANUP_INTERVAL={interval}s is too low, using 10s minimum")
            return 10
        return interval
    except ValueError:
        logger.warning("Invalid CLEANUP_INTERVAL, using default 60s")
        return 60


def get_host() -> str:
    """Get host from environment or default to 0.0.0.0.

    Returns:
        Host to bind to
    """
    return os.getenv("RELAY_HOST", "0.0.0.0")


def get_port() -> int:
    """Get port from environment or default to 8080.

    Returns:
        Port to listen on
    """
    try:
        port = int(os.getenv("RELAY_PORT", "8080"))
        if port < 1 or port > 65535:
            logger.warning(f"Invalid RELAY_PORT={port}, using default 8080")
            return 8080
        return port
    except ValueError:
        logger.warning("Invalid RELAY_PORT, using default 8080")
        return 8080


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def main():
    """Main entrypoint for running the relay server.

    Runs uvicorn server with configuration from environment variables.
    """
    host = get_host()
    port = get_port()

    logger.info(f"Starting uvicorn server on {host}:{port}")
    logger.info("Press CTRL+C to stop")

    # Run server with single worker (required for in-memory repository)
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=LOG_LEVEL.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    main()
