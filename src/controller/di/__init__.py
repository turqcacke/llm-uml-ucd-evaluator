from dishka import (
    AsyncContainer,
    Provider,
    make_async_container,
    make_container,
)

from src.config import ApiSettings

from .api import ApiProvider
from .diagram_assessment import DiagramAssessmentProvider
from .evaluator import EvaluatorProvider
from .extractor import ExtractorProvider
from .llm import ChatModelProvider
from .matcher import MatcherProvider
from .mongo import MongoProvider

container = make_container(
    ChatModelProvider(),
    ExtractorProvider(),
    MatcherProvider(),
    EvaluatorProvider(),
)


def make_api_container(
    *providers: Provider,
    settings: ApiSettings | None = None,
) -> AsyncContainer:
    return make_async_container(ApiProvider(settings), *providers)


assessment_container = make_api_container(
    ChatModelProvider(),
    ExtractorProvider(),
    MatcherProvider(),
    EvaluatorProvider(),
    MongoProvider(),
    DiagramAssessmentProvider(),
)

__all__ = [
    "ApiProvider",
    "ChatModelProvider",
    "DiagramAssessmentProvider",
    "EvaluatorProvider",
    "ExtractorProvider",
    "MatcherProvider",
    "container",
    "assessment_container",
    "make_api_container",
]
