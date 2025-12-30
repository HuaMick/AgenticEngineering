"""FastAPI REST API endpoints for relay session management.

This module provides HTTP endpoints for managing relay sessions:
- POST /api/sessions: Create new session and get pairing code
- GET /api/sessions/{session_id}: Query session status
- DELETE /api/sessions/{session_id}: Close session

Used by desktop CLI to initiate relay sessions and by monitoring tools to check status.
"""

import base64
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent_remote.services.relay.domains.session_manager.entities import (
    InvalidPairingCodeException,
    SessionAlreadyPairedException,
    SessionExpiredException,
)
from agent_remote.services.relay.domains.session_manager.value_objects import (
    SessionId,
    SessionState,
)
from agent_remote.services.relay.infrastructure.in_memory_repository import (
    InMemorySessionRepository,
)
from agent_remote.services.relay.workflows.relay_workflow import (
    RelayWorkflow,
    SessionNotFoundException,
)


# ==============================================================================
# Request/Response Models
# ==============================================================================


class CreateSessionRequest(BaseModel):
    """Request body for POST /api/sessions.

    Attributes:
        desktop_public_key: Base64-encoded public key from desktop client
    """

    desktop_public_key: str = Field(
        ...,
        description="Base64-encoded public key for desktop E2E encryption",
        min_length=1,
    )


class CreateSessionResponse(BaseModel):
    """Response for POST /api/sessions.

    Attributes:
        session_id: Unique session identifier (UUID)
        pairing_code: 6-character code for client pairing
    """

    session_id: str = Field(..., description="Unique session identifier")
    pairing_code: str = Field(..., description="6-character pairing code")


class SessionStatusResponse(BaseModel):
    """Response for GET /api/sessions/{session_id}.

    Attributes:
        session_id: Unique session identifier
        state: Current session state (created, desktop_connected, paired, closed)
        desktop_connected: True if desktop WebSocket is connected
        client_connected: True if client WebSocket is connected
        expires_at: ISO 8601 timestamp when pairing code expires
    """

    session_id: str = Field(..., description="Unique session identifier")
    state: str = Field(..., description="Current session state")
    desktop_connected: bool = Field(
        ..., description="True if desktop WebSocket is connected"
    )
    client_connected: bool = Field(
        ..., description="True if client WebSocket is connected"
    )
    expires_at: str = Field(..., description="ISO 8601 timestamp when pairing code expires")


# ==============================================================================
# Dependency Injection
# ==============================================================================

# Singleton repository instance
# In production, this could be replaced with Redis or database-backed repository
_repository: Optional[InMemorySessionRepository] = None


def get_repository() -> InMemorySessionRepository:
    """Get or create the singleton repository instance.

    Returns:
        InMemorySessionRepository instance for session persistence
    """
    global _repository
    if _repository is None:
        _repository = InMemorySessionRepository()
    return _repository


def get_workflow(
    repository: InMemorySessionRepository = Depends(get_repository),
) -> RelayWorkflow:
    """Create RelayWorkflow instance with injected repository.

    Args:
        repository: SessionRepository implementation (injected)

    Returns:
        RelayWorkflow instance for orchestrating session operations
    """
    return RelayWorkflow(repository=repository)


# ==============================================================================
# FastAPI App (legacy - use server.py for production)
# ==============================================================================

# Note: For production use, import from server.py which has proper lifespan management.
# This app is kept for backwards compatibility and testing.
app = FastAPI(
    title="Agent Remote Relay API",
    description="REST API for managing relay sessions between desktop and web clients",
    version="1.0.0",
)

# Enable CORS for Flutter web client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# API Router (for use with server.py lifespan)
# ==============================================================================

router = APIRouter()


# ==============================================================================
# Error Handlers (standalone functions for registration in server.py)
# ==============================================================================


async def session_expired_handler(request, exc: SessionExpiredException):
    """Handle SessionExpiredException with 410 Gone status.

    Args:
        request: FastAPI request object
        exc: SessionExpiredException instance

    Returns:
        HTTP 410 Gone response
    """
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content={"detail": f"Session pairing code has expired: {str(exc)}"},
    )


async def invalid_pairing_code_handler(request, exc: InvalidPairingCodeException):
    """Handle InvalidPairingCodeException with 404 Not Found status.

    Args:
        request: FastAPI request object
        exc: InvalidPairingCodeException instance

    Returns:
        HTTP 404 Not Found response
    """
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": f"Invalid pairing code: {str(exc)}"},
    )


async def session_already_paired_handler(request, exc: SessionAlreadyPairedException):
    """Handle SessionAlreadyPairedException with 409 Conflict status.

    Args:
        request: FastAPI request object
        exc: SessionAlreadyPairedException instance

    Returns:
        HTTP 409 Conflict response
    """
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": f"Session is already paired: {str(exc)}"},
    )


async def session_not_found_handler(request, exc: SessionNotFoundException):
    """Handle SessionNotFoundException with 404 Not Found status.

    Args:
        request: FastAPI request object
        exc: SessionNotFoundException instance

    Returns:
        HTTP 404 Not Found response
    """
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": f"Session not found: {str(exc)}"},
    )


# Register exception handlers on legacy app
app.add_exception_handler(SessionExpiredException, session_expired_handler)
app.add_exception_handler(InvalidPairingCodeException, invalid_pairing_code_handler)
app.add_exception_handler(SessionAlreadyPairedException, session_already_paired_handler)
app.add_exception_handler(SessionNotFoundException, session_not_found_handler)


# ==============================================================================
# Endpoints
# ==============================================================================


@router.post(
    "/api/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new relay session",
    description="Creates a new relay session with generated pairing code. "
    "Desktop client provides public key and receives session ID and pairing code.",
)
@app.post(
    "/api/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new relay session",
    description="Creates a new relay session with generated pairing code. "
    "Desktop client provides public key and receives session ID and pairing code.",
)
async def create_session(
    request: CreateSessionRequest,
    workflow: RelayWorkflow = Depends(get_workflow),
) -> CreateSessionResponse:
    """Create a new relay session.

    Args:
        request: CreateSessionRequest with desktop_public_key (base64)
        workflow: RelayWorkflow instance (injected)

    Returns:
        CreateSessionResponse with session_id and pairing_code

    Raises:
        HTTPException: 400 Bad Request if public key is invalid base64
    """
    # Decode base64 public key to bytes
    try:
        desktop_public_key_bytes = base64.b64decode(request.desktop_public_key)
        # Store as base64 string (domain expects string)
        desktop_public_key = request.desktop_public_key
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64-encoded public key: {str(e)}",
        )

    # Create session via workflow
    session_id, pairing_code = workflow.create_session(
        desktop_public_key=desktop_public_key
    )

    return CreateSessionResponse(
        session_id=str(session_id),
        pairing_code=str(pairing_code),
    )


@router.get(
    "/api/sessions/{session_id}",
    response_model=SessionStatusResponse,
    summary="Get session status",
    description="Retrieves current status of a relay session including state "
    "and connection status.",
)
@app.get(
    "/api/sessions/{session_id}",
    response_model=SessionStatusResponse,
    summary="Get session status",
    description="Retrieves current status of a relay session including state "
    "and connection status.",
)
async def get_session_status(
    session_id: str,
    repository: InMemorySessionRepository = Depends(get_repository),
) -> SessionStatusResponse:
    """Get session status.

    Args:
        session_id: Unique session identifier (UUID string)
        repository: SessionRepository instance (injected)

    Returns:
        SessionStatusResponse with session details

    Raises:
        HTTPException: 404 Not Found if session doesn't exist
        HTTPException: 400 Bad Request if session_id is invalid UUID
    """
    # Validate and convert session_id to SessionId value object
    try:
        session_id_obj = SessionId(session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid session ID format: {str(e)}",
        )

    # Retrieve session from repository
    session = repository.get_by_id(session_id_obj)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    # Convert expires_at timestamp to ISO 8601 string
    expires_at_datetime = datetime.fromtimestamp(session.expires_at)
    expires_at_iso = expires_at_datetime.isoformat()

    return SessionStatusResponse(
        session_id=str(session.session_id),
        state=session.state.value,
        desktop_connected=session.desktop_ws is not None,
        client_connected=session.client_ws is not None,
        expires_at=expires_at_iso,
    )


@router.delete(
    "/api/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Close relay session",
    description="Closes a relay session and removes it from the repository. "
    "This operation is idempotent.",
)
@app.delete(
    "/api/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Close relay session",
    description="Closes a relay session and removes it from the repository. "
    "This operation is idempotent.",
)
async def delete_session(
    session_id: str,
    workflow: RelayWorkflow = Depends(get_workflow),
) -> None:
    """Close a relay session.

    Args:
        session_id: Unique session identifier (UUID string)
        workflow: RelayWorkflow instance (injected)

    Raises:
        HTTPException: 400 Bad Request if session_id is invalid UUID

    Note:
        This operation is idempotent. Deleting a non-existent session
        is not an error and returns 204 No Content.
    """
    # Validate and convert session_id to SessionId value object
    try:
        session_id_obj = SessionId(session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid session ID format: {str(e)}",
        )

    # Close session via workflow (idempotent operation)
    workflow.close_session(session_id=session_id_obj, reason="user_request")


# ==============================================================================
# Health Check
# ==============================================================================


@router.get(
    "/health",
    summary="Health check",
    description="Returns API health status and repository statistics",
)
@app.get(
    "/health",
    summary="Health check",
    description="Returns API health status and repository statistics",
)
async def health_check(
    repository: InMemorySessionRepository = Depends(get_repository),
):
    """Health check endpoint.

    Args:
        repository: SessionRepository instance (injected)

    Returns:
        Dict with status and repository statistics
    """
    return {
        "status": "healthy",
        "repository": str(repository),
    }
