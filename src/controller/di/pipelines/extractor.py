from dishka import Provider, Scope, provide

from src.model.apollon import ApollonJson
from src.model.domain import UseCaseDiagramPresentation
from src.services.converters.apollon_to_domain import ApollonToDomainConverter
from src.services.converters.base import BaseConverter
from src.services.pipelines.extractor.apollon_json import ApollonJsonExtractor
from src.services.pipelines.extractor.apollon_llm import ApollonLlmExtractor
from src.services.pipelines.extractor.text import DescriptionExtractor


class ExtractorProvider(Provider):
    @provide(scope=Scope.APP)
    def apollon_to_domain_converter(
        self,
    ) -> BaseConverter[ApollonJson, UseCaseDiagramPresentation]:
        return ApollonToDomainConverter()

    apollon_json_extractor = provide(ApollonJsonExtractor, scope=Scope.APP)
    description_extractor = provide(DescriptionExtractor, scope=Scope.APP)
    apollon_extractor = provide(ApollonLlmExtractor, scope=Scope.APP)
