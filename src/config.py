from functools import lru_cache
from pathlib import Path

from pydantic import Field, Secret
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_URL = Path(__file__).resolve().parent.parent


def get_env_file() -> Path:
    return BASE_URL / ".env"


class LoggingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=get_env_file(), extra="ignore")

    LOG_LEVEL: str = Field(default="info")


class Settings(LoggingSettings):
    EXTRACTOR_API_KEY: Secret[str] = Field(default=...)
    EXTRACTOR_MODEL: str = Field(default=...)
    EXTRACTOR_BASE_URL: str | None = Field(default=None)
    EXTRACTOR_PROVIDER: str | None = Field(default=None)

    MATCHER_API_KEY: Secret[str] = Field(default=...)
    MATCHER_MODEL: str = Field(default=...)
    MATCHER_BASE_URL: str | None = Field(default=None)
    MATCHER_PROVIDER: str | None = Field(default=None)

    EVALUATOR_API_KEY: Secret[str] = Field(default=...)
    EVALUATOR_MODEL: str = Field(default=...)
    EVALUATOR_BASE_URL: str | None = Field(default=None)
    EVALUATOR_PROVIDER: str | None = Field(default=None)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    return settings
