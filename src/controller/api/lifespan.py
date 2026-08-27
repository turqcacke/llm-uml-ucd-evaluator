from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import ApiSettings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        app.state.api_settings = (
            app.state.api_settings_source
            or ApiSettings.model_validate({})
        )
        yield
    finally:
        await app.state.dishka_container.close()
