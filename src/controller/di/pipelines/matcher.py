from dishka import Provider, Scope, provide

from src.services.pipelines.matcher.use_case_diagram import (
    UseCaseDiagramMatcher,
)


class MatcherProvider(Provider):
    use_case_diagram_matcher = provide(UseCaseDiagramMatcher, scope=Scope.APP)
