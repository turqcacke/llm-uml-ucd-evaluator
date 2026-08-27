from .base import BaseAppException


class UseCaseError(BaseAppException):
    """A use case could not complete its operation."""

    error_code = "USE_CASE_ERROR"

    def __init__(self, message: str, *, original: Exception) -> None:
        super().__init__(message)
        self.original = original


class ReferenceNotAllowedError(UseCaseError):
    """The Reference Diagram cannot participate in an assessment."""

    error_code = "REFERENCE_NOT_ALLOWED"
