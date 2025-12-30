"""Domain models for secret management."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Secret:
    """Represents a secret with its metadata."""
    name: str
    value: str
    project_id: str
    source: str  # "gcp" or "env"


@dataclass
class SecretRequest:
    """Request for fetching a secret."""
    name: str
    project_id: Optional[str] = None
