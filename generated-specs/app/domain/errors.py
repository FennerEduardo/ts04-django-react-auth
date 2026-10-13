"""Shared by every aggregate of the service."""


class DomainValidationError(ValueError):
    """Raised when a command or aggregate violates a domain invariant."""
