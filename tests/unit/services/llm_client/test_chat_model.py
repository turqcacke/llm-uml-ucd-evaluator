import pytest

from src.model.domain.evaluation import MatchingResult
from src.services.llm_client import chat_model
from src.services.llm_client.chat_model import _as_llm_exception
from src.services.llm_client.exceptions import ConfigError


def test_initialization_passes_base_url_to_langchain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passed_arguments: dict[str, object] = {}

    def capture_initialization(**kwargs: object) -> None:
        passed_arguments.update(kwargs)

    monkeypatch.setattr(
        chat_model, "init_chat_model", capture_initialization
    )

    chat_model.LangChainChatModel(
        "gpt-5",
        "test-key",
        base_url="https://llm.example.test/v1",
        system_prompt="",
        response_type=MatchingResult,
    )

    assert passed_arguments["base_url"] == "https://llm.example.test/v1"


def test_request_error_uses_model_as_provider_fallback() -> None:
    error = _as_llm_exception(
        RuntimeError("connection refused"),
        model="gpt-5",
    )

    assert str(error) == (
        "Could not invoke LLM 'gpt-5' from provider 'gpt-5': "
        "connection refused"
    )
    assert error.model == "gpt-5"
    assert error.provider is None


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
