from typing import Literal

from dishka import Provider, Scope, provide

from src.config import get_settings
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.domain.evaluation import MatchingResult
from src.services.llm_client import ChatModel, LangChainChatModel
from src.services.pipelines.extractor.dependencies import (
    ApollonExtractorChatModel,
    TextExtractorChatModel,
)
from src.services.shared import prompts


def get_text_extractor_chat_model(
    type_: Literal["text", "apollon"],
) -> ChatModel[UseCaseDiagramPresentation]:
    settings = get_settings()
    model = LangChainChatModel(
        model=settings.EXTRACTOR_MODEL,
        api_key=settings.EXTRACTOR_API_KEY.get_secret_value(),
        base_url=settings.EXTRACTOR_BASE_URL,
        system_prompt=prompts.EXTRATOR_FROM_DESCRIPTION
        if type_ == "text"
        else prompts.EXTRACTOR_FROM_APOLLON_MODEL,
        response_type=UseCaseDiagramPresentation,
    )
    return model


def get_use_case_diagram_matcher_chat_model() -> ChatModel[MatchingResult]:
    settings = get_settings()
    model = LangChainChatModel(
        model=settings.MATCHER_MODEL,
        api_key=settings.MATCHER_API_KEY.get_secret_value(),
        base_url=settings.MATCHER_BASE_URL,
        system_prompt=prompts.USE_CASE_DIAGRAM_MATCHER,
        response_type=MatchingResult,
    )
    return model


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
    def use_case_diagram_matcher_chat_model(self) -> ChatModel[MatchingResult]:
        return get_use_case_diagram_matcher_chat_model()
