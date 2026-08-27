from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

from .authentication import authenticate

middlewares = [
    Middleware(
        BaseHTTPMiddleware,  # type: ignore[invalid-argument-type]
        dispatch=authenticate,
    )
]


__all__ = ["middlewares"]
