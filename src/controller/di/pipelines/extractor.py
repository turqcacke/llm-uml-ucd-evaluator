from dishka import Provider, Scope, provide

from src.services.pipelines.extractor.apollon_llm import ApollonLlmExtractor
from src.services.pipelines.extractor.text import DescriptionExtractor


class ExtractorProvider(Provider):
    description_extractor = provide(DescriptionExtractor, scope=Scope.APP)
    apollon_extractor = provide(ApollonLlmExtractor, scope=Scope.APP)
