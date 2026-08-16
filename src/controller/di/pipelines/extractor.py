from dishka import Provider, Scope, provide

from src.services.pipelines.extractor.apollon import ApollonExtractor
from src.services.pipelines.extractor.text import DescriptionExtractor


class ExtractorProvider(Provider):
    description_extractor = provide(DescriptionExtractor, scope=Scope.APP)
    apollon_extractor = provide(ApollonExtractor, scope=Scope.APP)
