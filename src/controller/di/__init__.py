from dishka import make_container

from .llm import ChatModelProvider
from .pipelines import ExtractorProvider, MatcherProvider

container = make_container(
    ChatModelProvider(), ExtractorProvider(), MatcherProvider()
)
