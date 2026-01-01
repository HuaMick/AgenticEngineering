"""Server entrypoint for the terminal service with PTY support.

This module is the main entry point for running the terminal service. It provides:
1. FastAPI application with WebSocket endpoints for terminal I/O
2. PTY session management via TerminalWorkflow
3. Graceful shutdown with PTY cleanup

The server is configured to:
- Listen on 0.0.0.0:8081 (all interfaces, default terminal port)
- Create PTY sessions on WebSocket connect
- Route terminal I/O bidirectionally (client <-> PTY)
- Handle window resizing (SIGWINCH to PTY)
- Clean up PTY processes on shutdown

Usage:
    # Run server directly
    python -m agent_remote.services.terminal.api.server

    # Run with uvicorn CLI
    uvicorn agent_remote.services.terminal.api.server:app --host 0.0.0.0 --port 8081

Configuration:
    - TERMINAL_HOST: Host to bind to (default: 0.0.0.0)
    - TERMINAL_PORT: Port to listen on (default: 8081)
    - LOG_LEVEL: Logging level (default: INFO)
    - TERMINAL_SHELL: Shell to use for PTY sessions (default: /bin/bash)
"""

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_remote.services.terminal.api.websockets import (
    get_workflow,
    router as websocket_router,
)

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
    2. Initialize TerminalWorkflow
    3. Log successful initialization

    On shutdown:
    1. Stop all active PTY sessions
    2. Wait for graceful PTY process termination
    3. Log shutdown completion

    Args:
        app: FastAPI application instance
    """
    # ==================== STARTUP ====================
    logger.info("=" * 70)
    logger.info("Starting Agent Remote Terminal Service")
    logger.info("=" * 70)
    logger.info(f"Log Level: {LOG_LEVEL}")
    logger.info(f"Terminal Shell: {get_terminal_shell()}")

    # Get workflow instance
    workflow = get_workflow()
    logger.info(f"Workflow initialized: {workflow.__class__.__name__}")

    logger.info("=" * 70)
    logger.info("Terminal service startup complete")
    logger.info("=" * 70)

    yield  # Application runs here

    # ==================== SHUTDOWN ====================
    logger.info("=" * 70)
    logger.info("Shutting down Agent Remote Terminal Service")
    logger.info("=" * 70)

    # Stop all active PTY sessions
    try:
        active_sessions = workflow.get_active_sessions()
        logger.info(f"Stopping {len(active_sessions)} active PTY sessions...")

        for session in active_sessions:
            try:
                exit_code = await workflow.stop_session(session.session_id)
                logger.info(
                    f"Stopped session '{session.session_id}' with exit code {exit_code}"
                )
            except Exception as e:
                logger.error(
                    f"Error stopping session '{session.session_id}': {e}"
                )

        logger.info("All PTY sessions stopped")
    except Exception as e:
        logger.error(f"Error during PTY cleanup: {e}")

    logger.info("=" * 70)
    logger.info("Terminal service shutdown complete")
    logger.info("=" * 70)


# ==============================================================================
# Create FastAPI App
# ==============================================================================

# Create the main app with lifespan
app = FastAPI(
    title="Agent Remote Terminal API",
    description="WebSocket API for terminal PTY sessions",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for web client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include WebSocket router
app.include_router(websocket_router, tags=["WebSocket"])


# ==============================================================================
# Health Check Endpoint
# ==============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancers.

    Returns:
        JSON response with service status and active session count
    """
    workflow = get_workflow()
    active_sessions = workflow.get_active_sessions()

    return {
        "status": "healthy",
        "service": "terminal",
        "active_sessions": len(active_sessions),
    }


logger.info("Routes registered:")
logger.info("  Health:")
logger.info("    - GET /health")
logger.info("  WebSocket:")
logger.info("    - GET /ws/terminal/{session_id}")


# ==============================================================================
# Configuration Helpers
# ==============================================================================


def get_terminal_shell() -> str:
    """Get shell command from environment or default to /bin/bash.

    Returns:
        Shell command to use for PTY sessions
    """
    return os.getenv("TERMINAL_SHELL", "/bin/bash")


def get_host() -> str:
    """Get host from environment or default to 0.0.0.0.

    Returns:
        Host to bind to
    """
    return os.getenv("TERMINAL_HOST", "0.0.0.0")


def get_port() -> int:
    """Get port from environment or default to 8081.

    Returns:
        Port to listen on
    """
    try:
        port = int(os.getenv("TERMINAL_PORT", "8081"))
        if port < 1 or port > 65535:
            logger.warning(f"Invalid TERMINAL_PORT={port}, using default 8081")
            return 8081
        return port
    except ValueError:
        logger.warning("Invalid TERMINAL_PORT, using default 8081")
        return 8081


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def main():
    """Main entrypoint for running the terminal server.

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
