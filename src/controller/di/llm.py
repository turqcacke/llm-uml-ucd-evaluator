from typing import Annotated, Literal

from dishka import FromComponent, Provider, Scope, provide

from src.config import get_settings
from src.infrastructure.langchain import LangChainChatModel
from src.model.domain import EvaluationResult, UseCaseDiagramPresentation
from src.model.domain.matching import MinMatching
from src.services.ports import ChatModel
from src.services.shared import guardrails, prompts

type TextExtractorChatModel = Annotated[
    ChatModel[UseCaseDiagramPresentation], FromComponent("text")
]
type ApollonExtractorChatModel = Annotated[
    ChatModel[UseCaseDiagramPresentation], FromComponent("apollon")
]


def get_text_extractor_chat_model(
    type_: Literal["text", "apollon"],
) -> ChatModel[UseCaseDiagramPresentation]:
    settings = get_settings()
    apollon_guardrails = [guardrails.RESTRICT_TO_STRUCTURED_OUTPUT]
    text_guard_rails = [
        guardrails.USE_DESCRIPTION_FACTS,
        guardrails.RESTRICT_TO_STRUCTURED_OUTPUT,
    ]
    model = LangChainChatModel(
        model=settings.EXTRACTOR_MODEL,
        api_key=settings.EXTRACTOR_API_KEY.get_secret_value(),
        base_url=settings.EXTRACTOR_BASE_URL,
        model_provider=settings.EXTRACTOR_PROVIDER,
        system_prompt=prompts.EXTRACTOR_FROM_DESCRIPTION
        if type_ == "text"
        else prompts.EXTRACTOR_FROM_APOLLON_MODEL,
        response_type=UseCaseDiagramPresentation,
        guardrails=text_guard_rails if type_ == "text" else apollon_guardrails,
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
    )
    return model


def get_pragmatic_syntactic_evaluator_chat_model(
) -> ChatModel[EvaluationResult]:
    settings = get_settings()
    return LangChainChatModel(
        model=settings.EVALUATOR_MODEL,
        api_key=settings.EVALUATOR_API_KEY.get_secret_value(),
        base_url=settings.EVALUATOR_BASE_URL,
        model_provider=settings.EVALUATOR_PROVIDER,
        system_prompt=prompts.PRAGMATIC_SYNTACTIC_EVALUATOR,
        response_type=EvaluationResult,
        guardrails=[guardrails.RESTRICT_TO_STRUCTURED_OUTPUT],
    )


class ChatModelProvider(Provider):
    @provide(scope=Scope.APP)
    def text_extractor_chat_model(
        self,
    ) -> TextExtractorChatModel:
        return get_text_extractor_chat_model(type_="text")

    @provide(scope=Scope.APP)
    def apollon_extractor_chat_model(
        self,
    ) -> ApollonExtractorChatModel:
        return get_text_extractor_chat_model(type_="apollon")

    @provide(scope=Scope.APP)
    def use_case_diagram_matcher_chat_model(self) -> ChatModel[MinMatching]:
        return get_use_case_diagram_matcher_chat_model()

    @provide(scope=Scope.APP)
    def pragmatic_syntactic_evaluator_chat_model(
        self,
    ) -> ChatModel[EvaluationResult]:
        return get_pragmatic_syntactic_evaluator_chat_model()
