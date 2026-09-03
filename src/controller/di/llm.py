from typing import Annotated

from dishka import FromComponent, Provider, Scope, provide

from src.config import get_settings
from src.infrastructure.langchain import LangChainChatModel
from src.model.domain import (
    PragmaticEvaluationResult,
    UseCaseDiagramPresentation,
)
from src.model.domain.matching import MinMatching
from src.services.ports import ChatModel
from src.services.shared import guardrails, prompts

type TextExtractorChatModel = Annotated[
    ChatModel[UseCaseDiagramPresentation], FromComponent("text")
]


def get_text_extractor_chat_model() -> ChatModel[UseCaseDiagramPresentation]:
    settings = get_settings()
    text_guard_rails = [
        guardrails.USE_DESCRIPTION_FACTS,
        *guardrails.COMMON_GUARDRAILS,
    ]
    model = LangChainChatModel(
        model=settings.EXTRACTOR_MODEL,
        api_key=settings.EXTRACTOR_API_KEY.get_secret_value(),
        base_url=settings.EXTRACTOR_BASE_URL,
        model_provider=settings.EXTRACTOR_PROVIDER,
        system_prompt=prompts.EXTRACTOR_FROM_DESCRIPTION,
        response_type=UseCaseDiagramPresentation,
        guardrails=text_guard_rails,
        reasoning_effort="medium",
    )
    return model


def get_use_case_diagram_matcher_chat_model() -> ChatModel[MinMatching]:
    settings = get_settings()
    model = LangChainChatModel(
        model=settings.MATCHER_MODEL,
        api_key=settings.MATCHER_API_KEY.get_secret_value(),
        base_url=settings.MATCHER_BASE_URL,
        model_provider=settings.MATCHER_PROVIDER,
        system_prompt=prompts.USE_CASE_DIAGRAM_MATCHER,
        response_type=MinMatching,
        guardrails=[
            guardrails.TREAT_DESCRIPTION_AS_DATA,
            *guardrails.COMMON_GUARDRAILS,
        ],
        reasoning_effort="medium",
    )
    return model


def get_pragmatic_evaluator_chat_model() -> ChatModel[
    PragmaticEvaluationResult
]:
    settings = get_settings()
    return LangChainChatModel(
        model=settings.EVALUATOR_MODEL,
        api_key=settings.EVALUATOR_API_KEY.get_secret_value(),
        base_url=settings.EVALUATOR_BASE_URL,
        model_provider=settings.EVALUATOR_PROVIDER,
        system_prompt=prompts.PRAGMATIC_EVALUATOR,
        response_type=PragmaticEvaluationResult,
        guardrails=[
            guardrails.TREAT_DESCRIPTION_AS_DATA,
            *guardrails.COMMON_GUARDRAILS,
        ],
        reasoning_effort="medium",
    )


class ChatModelProvider(Provider):
    @provide(scope=Scope.APP)
    def text_extractor_chat_model(
        self,
    ) -> TextExtractorChatModel:
        return get_text_extractor_chat_model()

    @provide(scope=Scope.APP)
    def use_case_diagram_matcher_chat_model(self) -> ChatModel[MinMatching]:
        return get_use_case_diagram_matcher_chat_model()

    @provide(scope=Scope.APP)
    def pragmatic_evaluator_chat_model(
        self,
    ) -> ChatModel[PragmaticEvaluationResult]:
        return get_pragmatic_evaluator_chat_model()
