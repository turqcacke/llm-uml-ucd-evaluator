class DomainError(Exception):
    """Base error for invalid domain operations."""


class MatchingError(DomainError):
    """Matching output cannot be reconciled with its diagrams."""
