from .base import BaseAppException


class ConversionError(BaseAppException):
    """A value could not be converted to the service output model."""

    def __init__(self, message: str, *, original: Exception) -> None:
        super().__init__(message)
        self.original = original
