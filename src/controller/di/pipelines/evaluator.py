from dishka import Provider, Scope, provide

from src.services.pipelines.evaluator import PragmaticSyntacticLlmEvaluator


class EvaluatorProvider(Provider):
    pragmatic_syntactic_evaluator = provide(
        PragmaticSyntacticLlmEvaluator,
        scope=Scope.APP,
    )
