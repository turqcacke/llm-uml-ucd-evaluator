from .base import BaseAppException


class LlmProviderException(BaseAppException):
    """Base exception for errors raised by an LLM provider or client."""

    def __init__(
        self,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        original: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.original = original


class ConfigError(LlmProviderException):
    """The model or provider configuration is invalid."""

    error_code = "CONFIG_ERROR"


class RateLimitError(LlmProviderException):
    """The provider rate limit or quota was exceeded."""

    error_code = "LLM_RATE_LIMIT_ERROR"


class LlmResponseError(LlmProviderException):
    """The provider response does not match the requested schema."""

    error_code = "LLM_RESPONSE_ERROR"


class LlmRequestError(LlmProviderException):
    """The provider request failed."""

    error_code = "LLM_REQUEST_ERROR"
