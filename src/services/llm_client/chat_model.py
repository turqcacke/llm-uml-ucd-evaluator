from typing import Any, Literal, Protocol, TypeVar, cast

from langchain.chat_models import BaseChatModel, init_chat_model
from langchain.messages import AnyMessage
from langchain_core.exceptions import OutputParserException
from openai import BadRequestError, NotFoundError
from pydantic import BaseModel, ValidationError

from src.app_logging import logger
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
        self._base_url = base_url
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
        logger.info(
            "LLM configured model={} provider={} base_url={}",
            model,
            model_provider or "auto",
            base_url or "provider default",
        )

    async def invoke(self, prompt: str, role: LLMRoles) -> TResponse:
        try:
            self._context_builder.add(LlmMessage(role, prompt))
            context = self._context_builder.build_context()
            try:
                return await self._invoke_structured(context, "json_schema")
            except (BadRequestError, NotFoundError) as exc:
                if not _should_use_function_calling(exc):
                    raise
                logger.info(
                    "LLM retry model={} method=function_calling reason={}",
                    self._model,
                    type(exc).__name__,
                )
                return await self._invoke_structured(
                    context, "function_calling"
                )
        except Exception as exc:
            raise _as_llm_exception(
                exc, provider=self._provider, model=self._model
            ) from exc

    async def _invoke_structured(
        self,
        context: list[AnyMessage],
        method: Literal["function_calling", "json_schema"],
    ) -> TResponse:
        logger.info(
            "LLM request model={} provider={} base_url={} method={} "
            "messages={}",
            self._model,
            self._provider or "auto",
            self._base_url or "provider default",
            method,
            len(context),
        )
        chat_model = self._chat_model.with_structured_output(
            self._response_type,
            method=method,
        )
        response = cast(TResponse, await chat_model.ainvoke(context))
        logger.info(
            "LLM response model={} response_type={}",
            self._model,
            type(response).__name__,
        )
        return response


def _should_use_function_calling(
    exc: BadRequestError | NotFoundError,
) -> bool:
    message = str(exc).lower()
    return "response_format" in message or "model_not_found" in message


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
