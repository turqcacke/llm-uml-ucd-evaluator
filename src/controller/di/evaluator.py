from dishka import Provider, Scope, provide

from src.services.evaluator import PragmaticSyntacticLlmEvaluator


class EvaluatorProvider(Provider):
    pragmatic_syntactic_evaluator = provide(
        PragmaticSyntacticLlmEvaluator,
        scope=Scope.REQUEST,
    )
