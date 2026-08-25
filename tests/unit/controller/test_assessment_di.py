import pytest
from dishka import make_container
from pydantic import BaseModel

from src.config import get_settings
from src.controller.di.llm import ChatModelProvider
from src.controller.di.pipelines import (
    DiagramAssessmentProvider,
    EvaluatorProvider,
    ExtractorProvider,
    MatcherProvider,
)
from src.services.llm_client import chat_model
from src.services.pipelines.diagram_assessment import (
    ApollonReferenceAssessment,
    DescriptionReferenceAssessment,
)


class FakeLanguageModel:
    def with_structured_output(
        self, response_type: type[BaseModel], **_: object
    ) -> "FakeLanguageModel":
        return self


def test_container_resolves_assessment_pipelines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for prefix in ("EXTRACTOR", "MATCHER", "EVALUATOR"):
        monkeypatch.setenv(f"{prefix}_MODEL", f"test-{prefix.lower()}")
        monkeypatch.setenv(f"{prefix}_API_KEY", "test-key")
    monkeypatch.setattr(
        chat_model,
        "init_chat_model",
        lambda **_: FakeLanguageModel(),
    )
    get_settings.cache_clear()

    local_container = make_container(
        ChatModelProvider(),
        ExtractorProvider(),
        MatcherProvider(),
        EvaluatorProvider(),
        DiagramAssessmentProvider(),
    )
    with local_container:
        assert isinstance(
            local_container.get(DescriptionReferenceAssessment),
            DescriptionReferenceAssessment,
        )
        assert isinstance(
            local_container.get(ApollonReferenceAssessment),
            ApollonReferenceAssessment,
        )

    get_settings.cache_clear()
