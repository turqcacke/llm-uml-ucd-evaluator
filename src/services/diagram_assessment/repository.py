from typing import Protocol

from src.model.domain import MetricsWithEvaluation, UseCaseDiagramPresentation


class AssessmentWriteRepository(Protocol):
    async def save_metrics(self, data: MetricsWithEvaluation) -> None: ...

    async def save_diagram_presentation(
        self, data: UseCaseDiagramPresentation
    ) -> None: ...


class AssessmentReadRepository(Protocol):
    async def get_by_uid(self, uid: str) -> MetricsWithEvaluation | None: ...

    async def get_by_candidate_uid(
        self, candidate_uid: str
    ) -> MetricsWithEvaluation | None: ...
