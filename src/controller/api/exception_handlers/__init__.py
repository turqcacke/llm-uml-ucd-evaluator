from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from src.controller.api.responses import failure
from src.services.exceptions import (
    BaseAppException,
    ConfigError,
    ConversionError,
    LlmRequestError,
    LlmResponseError,
    RateLimitError,
    ReferenceNotAllowedError,
    UseCaseError,
)

from .validation import validation_error

INTERNAL_ERROR_MESSAGE = "An internal error occurred."
SERVICE_ERROR_MESSAGE = "The operation could not be completed."

_SERVICE_ERROR_STATUSES: dict[type[BaseAppException], int] = {
    ConversionError: 422,
    ReferenceNotAllowedError: 422,
    LlmRequestError: 502,
    LlmResponseError: 502,
    RateLimitError: 503,
    ConfigError: 500,
    UseCaseError: 500,
}


async def service_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, BaseAppException)
    status = next(
        (
            status
            for exception_type, status in _SERVICE_ERROR_STATUSES.items()
            if isinstance(exc, exception_type)
        ),
        500,
    )
    return failure(
        status,
        exc.error_code,
        SERVICE_ERROR_MESSAGE,
    )


async def http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    try:
        phrase = HTTPStatus(exc.status_code).phrase
    except ValueError:
        phrase = "HTTP Error"
    return failure(
        exc.status_code,
        phrase.upper().replace(" ", "_"),
        f"{phrase}.",
        exc.headers,
    )


async def internal_error(_: Request, __: Exception) -> JSONResponse:
    return failure(500, "INTERNAL_ERROR", INTERNAL_ERROR_MESSAGE)


def add_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(ResponseValidationError, internal_error)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(BaseAppException, service_error)
    app.add_exception_handler(Exception, internal_error)


__all__ = ["add_exception_handlers"]
