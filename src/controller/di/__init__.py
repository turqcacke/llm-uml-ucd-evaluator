from dishka import make_container

from .diagram_assessment import DiagramAssessmentProvider
from .evaluator import EvaluatorProvider
from .extractor import ExtractorProvider
from .llm import ChatModelProvider
from .matcher import MatcherProvider

container = make_container(
    ChatModelProvider(),
    ExtractorProvider(),
    MatcherProvider(),
    EvaluatorProvider(),
    DiagramAssessmentProvider(),
)

__all__ = [
    "ChatModelProvider",
    "DiagramAssessmentProvider",
    "EvaluatorProvider",
    "ExtractorProvider",
    "MatcherProvider",
    "container",
]
