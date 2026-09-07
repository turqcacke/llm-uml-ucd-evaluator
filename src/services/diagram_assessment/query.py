from src.model.domain import MetricsWithEvaluation
from src.services.use_case import map_use_case_exceptions

from .repository import AssessmentReadRepository


class GetAssessmentByCandidateId:
    def __init__(self, repository: AssessmentReadRepository) -> None:
        self._repository = repository

    @map_use_case_exceptions
    async def execute(
        self, candidate_id: str
    ) -> MetricsWithEvaluation | None:
        return await self._repository.get_by_candidate_uid(candidate_id)


class GetAssessmentByUid:
    def __init__(self, repository: AssessmentReadRepository) -> None:
        self._repository = repository

    @map_use_case_exceptions
    async def execute(self, uid: str) -> MetricsWithEvaluation | None:
        return await self._repository.get_by_uid(uid)
