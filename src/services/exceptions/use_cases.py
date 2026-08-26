from .base import BaseAppException


class UseCaseError(BaseAppException):
    """A use case could not complete its operation."""

    def __init__(self, message: str, *, original: Exception) -> None:
        super().__init__(message)
        self.original = original
