from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from src.controller.di import assessment_container

from .descriptions import API_DESCRIPTION
from .exception_handlers import add_exception_handlers
from .lifespan import lifespan
from .middleware import middlewares
from .v1 import router


def create_app(
    *,
    container: AsyncContainer = assessment_container,
) -> FastAPI:
    app = FastAPI(
        description=API_DESCRIPTION,
        lifespan=lifespan,
        middleware=middlewares,
    )
    app.include_router(router)
    add_exception_handlers(app)
    setup_dishka(container, app)
    return app


app = create_app()
