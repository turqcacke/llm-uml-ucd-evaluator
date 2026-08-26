from dishka import make_async_container, make_container

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

assessment_container = make_async_container(
    ChatModelProvider(),
    ExtractorProvider(),
    MatcherProvider(),
    EvaluatorProvider(),
    MongoProvider(),
    DiagramAssessmentProvider(),
)

__all__ = [
    "ChatModelProvider",
    "DiagramAssessmentProvider",
    "EvaluatorProvider",
    "ExtractorProvider",
    "MatcherProvider",
    "container",
    "assessment_container",
]
