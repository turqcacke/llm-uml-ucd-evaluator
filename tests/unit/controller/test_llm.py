import json
from types import SimpleNamespace

import pytest
from httpx2 import AsyncClient, Request, Response
from openrouter.chat import Chat

from src.controller.di import llm
from src.services.ports import LLMRoles


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("factory", "role", "content"),
    [
        (
            "get_text_extractor_chat_model",
            "EXTRACTOR",
            {"nodes": [], "relations": []},
        ),
        (
            "get_use_case_diagram_matcher_chat_model",
            "MATCHER",
            {"node_matches": [], "relation_matches": []},
        ),
        ("get_pragmatic_evaluator_chat_model", "EVALUATOR", {"nodes": []}),
    ],
)
@pytest.mark.parametrize(
    ("model", "provider", "uses_openrouter_reasoning"),
    [
        ("qwen/qwen3.8-flash", "openrouter", True),
        ("google/gemini-flash", "openrouter", True),
        ("qwen/qwen3.8-flash", "openai", False),
    ],
)
async def test_role_sends_reasoning_options_to_provider(
    monkeypatch,
    factory,
    role,
    content,
    model,
    provider,
    uses_openrouter_reasoning,
):
    settings = SimpleNamespace(
        **{
            f"{role}_MODEL": model,
            f"{role}_BASE_URL": "https://openrouter.ai/api/v1",
            f"{role}_PROVIDER": provider,
            f"{role}_API_KEY": SimpleNamespace(
                get_secret_value=lambda: "test-key"
            ),
        }
    )
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    requests = []

    class ChatResponse:
        def model_dump(self, **kwargs):
            return {
                "id": "test-completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(content),
                        },
                    }
                ],
            }

    async def send_openrouter(self, **kwargs):
        requests.append(kwargs)
        return ChatResponse()

    async def send(self, request: Request, **kwargs):
        assert request.url.path.endswith("/chat/completions")
        requests.append(json.loads(request.content))
        body = {
            "id": "test-completion",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(content),
                    },
                }
            ],
        }
        return Response(200, request=request, json=body)

    monkeypatch.setattr(AsyncClient, "send", send)
    monkeypatch.setattr(Chat, "send_async", send_openrouter)
    chat_model = getattr(llm, factory)()
    result = await chat_model.invoke("Evaluate the diagram.", LLMRoles.USER)

    assert result.model_dump(include=set(content)) == content
    assert len(requests) == 1
    if uses_openrouter_reasoning:
        assert requests[0]["reasoning"] == {"effort": "medium"}
        assert "reasoning_effort" not in requests[0]
    else:
        assert requests[0]["reasoning_effort"] == "medium"
        assert "reasoning" not in requests[0]
