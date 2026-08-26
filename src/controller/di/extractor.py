from dishka import Provider, Scope, provide

from src.infrastructure.apollon import ApollonToDomainConverter
from src.model.apollon import ApollonJson
from src.model.domain import UseCaseDiagramPresentation
from src.services.extractor import (
    ApollonJsonExtractor,
    ApollonLlmExtractor,
    BaseConverter,
    DescriptionExtractor,
)

from .llm import ApollonExtractorChatModel, TextExtractorChatModel


class ExtractorProvider(Provider):
    @provide(scope=Scope.APP)
    def apollon_to_domain_converter(
        self,
    ) -> BaseConverter[ApollonJson, UseCaseDiagramPresentation]:
        return ApollonToDomainConverter()

    apollon_json_extractor = provide(ApollonJsonExtractor, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    def description_extractor(
        self, chat_model: TextExtractorChatModel
    ) -> DescriptionExtractor:
        return DescriptionExtractor(chat_model)

    @provide(scope=Scope.REQUEST)
    def apollon_extractor(
        self, chat_model: ApollonExtractorChatModel
    ) -> ApollonLlmExtractor:
        return ApollonLlmExtractor(chat_model)
