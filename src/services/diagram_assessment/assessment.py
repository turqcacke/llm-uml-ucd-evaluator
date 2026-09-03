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
    PragmaticEvaluationResult,
    SyntacticEvaluationResult,
    UseCaseDiagramPresentation,
)
from src.model.domain.exceptions import MetricsCalculationError
from src.services.evaluator import (
    PragmaticInput,
    PragmaticLlmEvaluator,
    SyntacticDiagramEvaluator,
)
from src.services.exceptions import (
    BaseAppException,
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
    pragmatic_evaluator: PragmaticLlmEvaluator
    repository: AssessmentWriteRepository
    unit_of_work: UnitOfWork
    syntactic_evaluator: SyntacticDiagramEvaluator


async def stream_assess_diagrams(
    reference: UseCaseDiagramPresentation,
    candidate: UseCaseDiagramPresentation,
    dependencies: AssessmentDependencies,
    *,
    description: str | None = None,
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
                syntactic=SyntacticEvaluationResult(nodes=[], relations=[]),
                pragmatic=PragmaticEvaluationResult(nodes=[]),
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
            reference=reference,
            evaluation=None,
            matching=None,
        )
    else:
        syntactic = await dependencies.syntactic_evaluator.execute(candidate)
        try:
            async with TaskGroup() as tasks:
                matching_task = tasks.create_task(
                    dependencies.matcher.execute(
                        UseCaseDiagramMatcherInput(
                            reference, candidate, description
                        )
                    )
                )
                pragmatic_task = tasks.create_task(
                    dependencies.pragmatic_evaluator.execute(
                        PragmaticInput(candidate, description)
                    )
                )
        except ExceptionGroup as exc:
            if len(exc.exceptions) == 1 and isinstance(
                error := exc.exceptions[0], BaseAppException
            ):
                raise error from exc
            raise

        evaluation = EvaluationResult(
            syntactic=syntactic, pragmatic=pragmatic_task.result()
        )
        matching = matching_task.result()
        metrics = Metrics.calculate_metrics(
            reference,
            candidate,
            evaluation,
            matching,
        )
        result = MetricsWithEvaluation(
            **metrics.model_dump(),
            uid=uuid4().hex,
            reference_uid=reference.uid,
            candidate_uid=candidate.uid,
            reference=reference,
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
