class DomainError(Exception):
    """Base error for invalid domain operations."""


class MatchingError(DomainError):
    """Matching output cannot be reconciled with its diagrams."""


class MetricsCalculationError(DomainError):
    """Metric inputs cannot support a trustworthy evaluation."""
