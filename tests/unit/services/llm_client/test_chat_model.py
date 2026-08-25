import pytest
from httpx2 import Request, Response
from openai import BadRequestError, NotFoundError

from src.model.domain.matching import MinMatching
from src.model.llm.context import LLMRoles
from src.services.exceptions import BaseAppException
from src.services.exceptions.llm_client import (
    ConfigError,
    LlmProviderException,
    LlmRequestError,
    LlmResponseError,
    RateLimitError,
)
from src.services.llm_client import chat_model


@pytest.mark.parametrize(
    "exception_type",
    [
        LlmProviderException,
        ConfigError,
        RateLimitError,
        LlmResponseError,
        LlmRequestError,
    ],
)
def test_llm_exceptions_are_service_exceptions(
    exception_type: type[BaseAppException],
) -> None:
    assert issubclass(exception_type, BaseAppException)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error_type", "message", "status_code"),
    [
        (
            BadRequestError,
            "Invalid schema for response_format 'MinMatching'.",
            400,
        ),
        (NotFoundError, "Error code: 404 - {'code': 'model_not_found'}", 404),
    ],
)
async def test_invocation_falls_back_to_function_calling(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[BadRequestError | NotFoundError],
    message: str,
    status_code: int,
) -> None:
    class FakeStructuredModel:
        def __init__(self, method: str) -> None:
            self._method = method

        async def ainvoke(self, _: object) -> MinMatching:
            if self._method == "json_schema":
                raise error_type(
                    message,
                    response=Response(
                        status_code,
                        request=Request("POST", "https://llm.example.test"),
                    ),
                    body=None,
                )
            return MinMatching(
                node_matches=[],
                relation_matches=[],
            )

    class FakeLanguageModel:
        def with_structured_output(
            self,
            _: type[MinMatching],
            *,
            method: str,
        ) -> FakeStructuredModel:
            return FakeStructuredModel(method)

    monkeypatch.setattr(
        chat_model,
        "init_chat_model",
        lambda **_: FakeLanguageModel(),
    )
    model = chat_model.LangChainChatModel(
        "gpt-5.5",
        "test-key",
        system_prompt="",
        response_type=MinMatching,
    )

    result = await model.invoke("Evaluate the diagram.", LLMRoles.USER)

    assert result == MinMatching(
        node_matches=[],
        relation_matches=[],
    )


@pytest.mark.anyio
async def test_invocation_reports_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_error = BadRequestError(
        "Invalid request.",
        response=Response(
            400,
            request=Request("POST", "https://llm.example.test"),
        ),
        body=None,
    )

    class FailingLanguageModel:
        def with_structured_output(
            self,
            _: type[MinMatching],
            **__: object,
        ) -> "FailingLanguageModel":
            return self

        async def ainvoke(self, _: object) -> MinMatching:
            raise provider_error

    monkeypatch.setattr(
        chat_model,
        "init_chat_model",
        lambda **_: FailingLanguageModel(),
    )
    model = chat_model.LangChainChatModel(
        "gpt-5.5",
        "test-key",
        system_prompt="",
        response_type=MinMatching,
    )

    with pytest.raises(LlmRequestError, match="Invalid request"):
        await model.invoke("Evaluate the diagram.", LLMRoles.USER)


@pytest.mark.anyio
async def test_invocation_preserves_service_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_error = LlmResponseError("Invalid structured response")

    class FailingLanguageModel:
        def with_structured_output(
            self,
            _: type[MinMatching],
            **__: object,
        ) -> "FailingLanguageModel":
            return self

        async def ainvoke(self, _: object) -> MinMatching:
            raise service_error

    monkeypatch.setattr(
        chat_model,
        "init_chat_model",
        lambda **_: FailingLanguageModel(),
    )
    model = chat_model.LangChainChatModel(
        "gpt-5.5",
        "test-key",
        system_prompt="",
        response_type=MinMatching,
    )

    with pytest.raises(LlmResponseError) as error_info:
        await model.invoke("Evaluate the diagram.", LLMRoles.USER)

    assert error_info.value is service_error


def test_configuration_error_uses_model_as_provider_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_initialization(**_: object) -> None:
        raise RuntimeError("invalid credentials")

    monkeypatch.setattr(chat_model, "init_chat_model", fail_initialization)

    with pytest.raises(ConfigError) as error_info:
        chat_model.LangChainChatModel(
            "gpt-5",
            "test-key",
            system_prompt="",
            response_type=MinMatching,
        )

    assert str(error_info.value) == (
        "Could not configure LLM 'gpt-5' from provider 'gpt-5': "
        "invalid credentials"
    )
    assert error_info.value.model == "gpt-5"
    assert error_info.value.provider is None
