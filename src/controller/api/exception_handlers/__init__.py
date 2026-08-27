from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from .validation import validation_error


def add_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error)


__all__ = ["add_exception_handlers"]
