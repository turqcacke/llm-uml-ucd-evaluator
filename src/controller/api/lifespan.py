from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import graphviz
from anyio import to_thread
from fastapi import FastAPI

from src.config import ApiSettings
from src.services.converter import ApollonLayoutConverter


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        app.state.api_settings = await app.state.dishka_container.get(
            ApiSettings
        )
        await to_thread.run_sync(graphviz.version)
        await app.state.dishka_container.get(ApollonLayoutConverter)
        yield
    finally:
        await app.state.dishka_container.close()
