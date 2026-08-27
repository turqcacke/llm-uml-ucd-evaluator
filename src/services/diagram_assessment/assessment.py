from asyncio import TaskGroup
from uuid import uuid4

from src.model.domain import (
    EvaluationResult,
    ExtendedMatching,
    Metrics,
    MetricsWithEvaluation,
    UseCaseDiagramPresentation,
)
from src.model.domain.exceptions import MetricsCalculationError
from src.services.evaluator import (
    PragmaticSyntacticInput,
    PragmaticSyntacticLlmEvaluator,
)
from src.services.exceptions import (
    BaseAppException,
    LlmResponseError,
    ReferenceNotAllowedError,
)
from src.services.matcher import (
    UseCaseDiagramMatcher,
    UseCaseDiagramMatcherInput,
)
from src.services.ports import UnitOfWork

from .repository import AssessmentWriteRepository


async def assess_diagrams(
    reference: UseCaseDiagramPresentation,
    candidate: UseCaseDiagramPresentation,
    matcher: UseCaseDiagramMatcher,
    evaluator: PragmaticSyntacticLlmEvaluator,
    repository: AssessmentWriteRepository,
    unit_of_work: UnitOfWork,
) -> MetricsWithEvaluation:
    if not reference.is_allowed:
        error = MetricsCalculationError("Reference diagram is not allowed.")
        raise ReferenceNotAllowedError(str(error), original=error) from error
    if not candidate.is_allowed:
        metrics = Metrics.calculate_metrics(
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
        result = MetricsWithEvaluation(
            **metrics.model_dump(),
            uid=uuid4().hex,
            reference_uid=reference.uid,
            candidate_uid=candidate.uid,
            evaluation=None,
            matching=None,
        )
    else:
        try:
            async with TaskGroup() as tasks:
                matching_task = tasks.create_task(
                    matcher.execute(
                        UseCaseDiagramMatcherInput(reference, candidate)
                    )
                )
                evaluation_task = tasks.create_task(
                    evaluator.execute(PragmaticSyntacticInput(candidate))
                )
        except ExceptionGroup as exc:
            if len(exc.exceptions) == 1 and isinstance(
                error := exc.exceptions[0], BaseAppException
            ):
                raise error from exc
            raise

        evaluation = evaluation_task.result()
        matching = matching_task.result()
        try:
            metrics = Metrics.calculate_metrics(
                reference,
                candidate,
                evaluation,
                matching,
            )
        except MetricsCalculationError as exc:
            raise LlmResponseError(str(exc), original=exc) from exc
        result = MetricsWithEvaluation(
            **metrics.model_dump(),
            uid=uuid4().hex,
            reference_uid=reference.uid,
            candidate_uid=candidate.uid,
            evaluation=evaluation,
            matching=matching,
        )

    async with unit_of_work:
        await repository.save_diagram_presentation(reference)
        await repository.save_diagram_presentation(candidate)
        await repository.save_metrics(result)
        await unit_of_work.commit()
    return result
