from dataclasses import dataclass

from dishka import Provider, Scope, from_context, provide
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from eval.gold_standard.models import GoldStandardMode, GoldStandardObservation
from src.infrastructure.mongo import to_bson
from src.model.domain import MetricsWithEvaluation, UseCaseDiagramPresentation
from src.services.diagram_assessment import AssessmentWriteRepository

COLLECTION_NAME = "gold_standard_eval"


@dataclass(frozen=True)
class GoldStandardObservationContext:
    id: str
    experiment_name: str
    mode: GoldStandardMode
    sample: int
    description_path: str


class GoldStandardAssessmentWriteRepository(AssessmentWriteRepository):
    def __init__(
        self,
        database: AsyncDatabase,
        session: AsyncClientSession,
        context: GoldStandardObservationContext,
    ) -> None:
        self._database = database
        self._session = session
        self._context = context
        self._diagrams: dict[str, UseCaseDiagramPresentation] = {}

    async def save_diagram_presentation(
        self, data: UseCaseDiagramPresentation
    ) -> None:
        self._diagrams[data.uid] = data

    async def save_metrics(self, data: MetricsWithEvaluation) -> None:
        document = GoldStandardObservation(
            **self._context.__dict__,
            reference=self._diagrams[data.reference_uid],
            candidate=self._diagrams[data.candidate_uid],
            metrics=data,
        ).model_dump(mode="python", by_alias=True)
        await self._database[COLLECTION_NAME].insert_one(
            to_bson(document), session=self._session
        )


class GoldStandardRepositoryProvider(Provider):
    context = from_context(GoldStandardObservationContext, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST, override=True)
    def repository(
        self,
        database: AsyncDatabase,
        session: AsyncClientSession,
        context: GoldStandardObservationContext,
    ) -> AssessmentWriteRepository:
        return GoldStandardAssessmentWriteRepository(
            database, session, context
        )
