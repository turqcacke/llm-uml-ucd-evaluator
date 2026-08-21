from typing import Any, Protocol, TypeVar, cast

from langchain.chat_models import BaseChatModel, init_chat_model
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, ValidationError

from src.model.llm.context import LlmMessage, LLMRoles

from .exceptions import (
    ConfigError,
    LlmProviderException,
    LlmRequestError,
    LlmResponseError,
    RateLimitError,
)
from .llm_context import ContextBuilder, SimpleContextBuilder

TResponse = TypeVar("TResponse", bound=BaseModel)


class ChatModel[TResponse](Protocol):
    async def invoke(self, prompt: str, role: LLMRoles) -> TResponse: ...


class LangChainChatModel[TResponse](ChatModel[TResponse]):
    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        system_prompt: str,
        response_type: type[TResponse],
        model_provider: str | None = None,
        base_url: str | None = None,
        guardrails: list[str] | None = None,
        **additional_args: Any,
    ) -> None:
        self._model = model
        self._provider = model_provider
        try:
            self._chat_model: BaseChatModel = init_chat_model(
                model=model,
                api_key=api_key,
                model_provider=model_provider,
                base_url=base_url,
                **additional_args,
            )
        except Exception as exc:
            raise ConfigError(
                _error_message(
                    "configure",
                    model=model,
                    provider=model_provider,
                    exc=exc,
                ),
                provider=model_provider,
                model=model,
                original=exc,
            ) from exc
        self._context_builder: ContextBuilder = SimpleContextBuilder(
            guardrails=guardrails or list(), system_prompt=system_prompt
        )
        self._response_type = response_type

    async def invoke(self, prompt: str, role: LLMRoles) -> TResponse:
        try:
            self._context_builder.add(LlmMessage(role, prompt))
            context = self._context_builder.build_context()
            chat_model = self._chat_model.with_structured_output(
                self._response_type
            )
            return cast(TResponse, await chat_model.ainvoke(context))
        except Exception as exc:
            raise _as_llm_exception(
                exc, provider=self._provider, model=self._model
            ) from exc


def _as_llm_exception(
    exc: Exception,
    *,
    model: str,
    provider: str | None = None,
) -> LlmProviderException:
    exception_name = type(exc).__name__.lower()

    if isinstance(exc, (ValidationError, OutputParserException)):
        return LlmResponseError(
            _error_message(
                "parse response from",
                model=model,
                provider=provider,
                exc=exc,
            ),
            provider=provider,
            model=model,
            original=exc,
        )

    if "ratelimit" in exception_name or "rate_limit" in exception_name.lower():
        return RateLimitError(
            _error_message(
                "invoke",
                model=model,
                provider=provider,
                exc=exc,
            ),
            provider=provider,
            model=model,
            original=exc,
        )

    return LlmRequestError(
        _error_message(
            "invoke",
            model=model,
            provider=provider,
            exc=exc,
        ),
        provider=provider,
        model=model,
        original=exc,
    )


def _error_message(
    operation: str,
    *,
    model: str,
    provider: str | None,
    exc: Exception,
) -> str:
    reason = str(exc) or type(exc).__name__
    provider = provider or model
    return (
        f"Could not {operation} LLM {model!r} from provider "
        f"{provider!r}: {reason}"
    )
