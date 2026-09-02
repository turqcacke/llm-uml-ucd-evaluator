from typing import cast

import pytest
from dishka import Provider, Scope, make_async_container, provide
from pydantic import BaseModel

from eval.gold_standard.collect_metrics import ReqUCD60Provider
from src.config import get_settings
from src.controller.di import (
    DiagramAssessmentProvider,
    EvaluatorProvider,
    ExtractorProvider,
    MatcherProvider,
)
from src.controller.di.llm import ChatModelProvider
from src.infrastructure.langchain import chat_model
from src.services.diagram_assessment import (
    ApollonToApollonAssessment,
    AssessmentWriteRepository,
    DescriptionReferenceAssessment,
)
from src.services.diagram_assessment.requcd60_reference import (
    ReqUCD60ReferenceAssessment,
)
from src.services.ports import UnitOfWork


class FakeLanguageModel:
    def with_structured_output(
        self, response_type: type[BaseModel], **_: object
    ) -> "FakeLanguageModel":
        return self


class PersistenceProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def repository(self) -> AssessmentWriteRepository:
        return cast(AssessmentWriteRepository, object())

    @provide(scope=Scope.REQUEST)
    def unit_of_work(self) -> UnitOfWork:
        return cast(UnitOfWork, object())


@pytest.mark.anyio
async def test_container_resolves_assessment_use_cases(
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

    local_container = make_async_container(
        ChatModelProvider(),
        ExtractorProvider(),
        MatcherProvider(),
        EvaluatorProvider(),
        PersistenceProvider(),
        DiagramAssessmentProvider(),
        ReqUCD60Provider(),
    )
    async with local_container() as request_container:
        assert isinstance(
            await request_container.get(DescriptionReferenceAssessment),
            DescriptionReferenceAssessment,
        )
        assert isinstance(
            await request_container.get(ApollonToApollonAssessment),
            ApollonToApollonAssessment,
        )
        assert isinstance(
            await request_container.get(ReqUCD60ReferenceAssessment),
            ReqUCD60ReferenceAssessment,
        )
    await local_container.close()

    get_settings.cache_clear()
