"""SessionManager domain package.

This package provides pure domain logic for managing relay session lifecycle:
- Value objects: SessionId, PairingCode, PeerRole, SessionState
- Entity: Session (models complete session lifecycle)
- Repository: SessionRepository Protocol (defines persistence interface)
- Exceptions: Domain-specific exceptions for business rule violations

The domain layer has no infrastructure dependencies and contains only
business logic following DDD principles.
"""

from .entities import (
    InvalidPairingCodeException,
    InvalidStateTransitionException,
    Session,
    SessionAlreadyPairedException,
    SessionDomainException,
    SessionExpiredException,
)
from .repository import SessionRepository
from .value_objects import PairingCode, PeerRole, SessionId, SessionState

__all__ = [
    # Value Objects
    "SessionId",
    "PairingCode",
    "PeerRole",
    "SessionState",
    # Entity
    "Session",
    # Repository
    "SessionRepository",
    # Exceptions
    "SessionDomainException",
    "SessionExpiredException",
    "InvalidPairingCodeException",
    "SessionAlreadyPairedException",
    "InvalidStateTransitionException",
]
