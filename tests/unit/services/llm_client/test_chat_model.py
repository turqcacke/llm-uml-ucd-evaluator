import pytest
from httpx2 import Request, Response
from openai import BadRequestError, NotFoundError

from src.model.domain.evaluation import MatchingResult
from src.model.llm.context import LLMRoles
from src.services.llm_client import chat_model
from src.services.llm_client.exceptions import ConfigError, LlmRequestError


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error_type", "message", "status_code"),
    [
        (
            BadRequestError,
            "Invalid schema for response_format 'MatchingResult'.",
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

        async def ainvoke(self, _: object) -> MatchingResult:
            if self._method == "json_schema":
                raise error_type(
                    message,
                    response=Response(
                        status_code,
                        request=Request("POST", "https://llm.example.test"),
                    ),
                    body=None,
                )
            return MatchingResult(
                node_matches=[],
                missing_nodes=[],
                redundant_nodes=[],
                missing_links=[],
                redundant_links=[],
            )

    class FakeLanguageModel:
        def with_structured_output(
            self,
            _: type[MatchingResult],
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
        response_type=MatchingResult,
    )

    result = await model.invoke("Evaluate the diagram.", LLMRoles.USER)

    assert result == MatchingResult(
        node_matches=[],
        missing_nodes=[],
        redundant_nodes=[],
        missing_links=[],
        redundant_links=[],
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
            _: type[MatchingResult],
            **__: object,
        ) -> "FailingLanguageModel":
            return self

        async def ainvoke(self, _: object) -> MatchingResult:
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
        response_type=MatchingResult,
    )

    with pytest.raises(LlmRequestError, match="Invalid request"):
        await model.invoke("Evaluate the diagram.", LLMRoles.USER)


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
            response_type=MatchingResult,
        )

    assert str(error_info.value) == (
        "Could not configure LLM 'gpt-5' from provider 'gpt-5': "
        "invalid credentials"
    )
    assert error_info.value.model == "gpt-5"
    assert error_info.value.provider is None
