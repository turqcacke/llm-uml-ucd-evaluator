from functools import lru_cache
from pathlib import Path

from pydantic import Field, Secret
from pydantic_settings import BaseSettings

BASE_URL = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    EXTRACTOR_API_KEY: Secret[str] = Field(default=...)
    EXTRACTOR_MODEL: str = Field(default=...)
    EXTRACTOR_BASE_URL: str | None = Field(default=None)

    MATCHER_API_KEY: Secret[str] = Field(default=...)
    MATCHER_MODEL: str = Field(default=...)
    MATCHER_BASE_URL: str | None = Field(default=None)

    class Config:
        env_file = BASE_URL / ".env"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    return settings
