from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from hmac import compare_digest

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI, Request
from starlette.responses import Response

from src.config import ApiSettings
from src.controller.di import assessment_container

from .errors import add_exception_handlers, failure
from .v1 import router


def create_app(
    *,
    settings: ApiSettings | None = None,
    container: AsyncContainer = assessment_container,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            app.state.api_settings = settings or ApiSettings.model_validate({})
            yield
        finally:
            await container.close()

    app = FastAPI(
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def authenticate(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        public_paths = {"/docs", "/redoc", "/openapi.json"}
        if request.url.path in public_paths:
            return await call_next(request)
        expected = request.app.state.api_settings.API_SECRET
        supplied = request.headers.get("X-API-Key", "")
        if not compare_digest(supplied.encode(), expected.encode()):
            return failure(401, "UNAUTHORIZED", "Authentication is required.")
        return await call_next(request)

    app.include_router(router)
    add_exception_handlers(app)
    setup_dishka(container, app)
    return app


app = create_app()
