"""
Exception classes for secrets management.
"""


class SecretsError(Exception):
    """Base exception for secrets operations."""
    pass


class SecretNotFoundError(SecretsError):
    """Raised when a secret is not found (exit code 1)."""
    pass


class InvalidSecretNameError(SecretsError):
    """Raised when secret name format is invalid (exit code 2)."""
    pass


class GCPToolkitNotFoundError(SecretsError):
    """Raised when gcptoolkit CLI is not found in PATH."""
    pass
