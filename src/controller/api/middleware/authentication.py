from collections.abc import Awaitable, Callable
from hmac import compare_digest

from fastapi import Request
from starlette.responses import Response

from src.controller.api.responses import failure


async def authenticate(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.url.path in {"/docs", "/redoc", "/openapi.json"}:
        return await call_next(request)
    expected = request.app.state.api_settings.API_SECRET
    supplied = request.headers.get("X-API-Key", "")
    if not compare_digest(supplied.encode(), expected.encode()):
        return failure(401, "UNAUTHORIZED", "Authentication is required.")
    return await call_next(request)
