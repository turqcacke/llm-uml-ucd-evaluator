from asyncio import TaskGroup

from src.model.domain import (
    EvaluationResult,
    ExtendedMatching,
    MetricsWithEvaluation,
    UseCaseDiagramPresentation,
)
from src.model.domain.exceptions import MetricsCalculationError

from ..evaluator import PragmaticSyntacticInput, PragmaticSyntacticLlmEvaluator
from ..matcher.use_case_diagram import (
    UseCaseDiagramMatcher,
    UseCaseDiagramMatcherInput,
)


async def assess(
    reference: UseCaseDiagramPresentation,
    candidate: UseCaseDiagramPresentation,
    matcher: UseCaseDiagramMatcher,
    evaluator: PragmaticSyntacticLlmEvaluator,
) -> MetricsWithEvaluation:
    if not reference.is_allowed:
        raise MetricsCalculationError("Reference diagram is not allowed.")
    if not candidate.is_allowed:
        return MetricsWithEvaluation.calculate_metrics(
            reference,
            candidate,
            EvaluationResult(
                node_evaluations=[],
                relation_evaluations=[],
                applied_rules=[],
            ),
            ExtendedMatching(
                reference=reference,
                candidate=candidate,
                node_matches=[],
                relation_matches=[],
            ),
        )

    async with TaskGroup() as tasks:
        matching_task = tasks.create_task(
            matcher.execute(UseCaseDiagramMatcherInput(reference, candidate))
        )
        evaluation_task = tasks.create_task(
            evaluator.execute(PragmaticSyntacticInput(candidate))
        )

    evaluation = evaluation_task.result()
    metrics = MetricsWithEvaluation.calculate_metrics(
        reference,
        candidate,
        evaluation,
        matching_task.result(),
    )
    return metrics.model_copy(update={"evaluation": evaluation})
