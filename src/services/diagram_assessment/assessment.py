from asyncio import TaskGroup
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import uuid4

from src.model.domain import (
    AssessmentState,
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

type AssessmentProgress = tuple[AssessmentState, MetricsWithEvaluation | None]


@dataclass(frozen=True)
class AssessmentDependencies:
    matcher: UseCaseDiagramMatcher
    evaluator: PragmaticSyntacticLlmEvaluator
    repository: AssessmentWriteRepository
    unit_of_work: UnitOfWork


async def stream_assess_diagrams(
    reference: UseCaseDiagramPresentation,
    candidate: UseCaseDiagramPresentation,
    dependencies: AssessmentDependencies,
) -> AsyncGenerator[AssessmentProgress]:
    yield AssessmentState.ANALYZING, None
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
                    dependencies.matcher.execute(
                        UseCaseDiagramMatcherInput(reference, candidate)
                    )
                )
                evaluation_task = tasks.create_task(
                    dependencies.evaluator.execute(
                        PragmaticSyntacticInput(candidate)
                    )
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

    yield AssessmentState.SAVING, None
    async with dependencies.unit_of_work:
        await dependencies.repository.save_diagram_presentation(reference)
        await dependencies.repository.save_diagram_presentation(candidate)
        await dependencies.repository.save_metrics(result)
        await dependencies.unit_of_work.commit()
    yield AssessmentState.COMPLETED, result
