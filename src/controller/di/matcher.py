from dishka import Provider, Scope, provide

from src.services.matcher import UseCaseDiagramMatcher


class MatcherProvider(Provider):
    use_case_diagram_matcher = provide(UseCaseDiagramMatcher, scope=Scope.APP)
