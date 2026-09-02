from dishka import Provider, Scope, provide

from src.services.evaluator import (
    PragmaticLlmEvaluator,
    SyntacticDiagramEvaluator,
)


class EvaluatorProvider(Provider):
    pragmatic_evaluator = provide(
        PragmaticLlmEvaluator,
        scope=Scope.REQUEST,
    )

    syntactic_evaluator = provide(
        SyntacticDiagramEvaluator, scope=Scope.REQUEST
    )
