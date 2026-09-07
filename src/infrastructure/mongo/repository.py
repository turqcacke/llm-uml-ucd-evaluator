from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from bson.decimal128 import Decimal128
from pydantic import BaseModel
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from src.model.domain import (
    MetricsWithEvaluation,
    UseCaseDiagramPresentation,
)
from src.services.diagram_assessment import AssessmentWriteRepository

from .models import (
    MetricsWithEvaluationModel,
    UseCaseDiagramPresentationModel,
)


def to_bson(value: Any) -> Any:
    if isinstance(value, Decimal):
        return Decimal128(value)
    if isinstance(value, Mapping):
        return {key: to_bson(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_bson(item) for item in value]
    return value


def from_bson(value: Any) -> Any:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, Mapping):
        return {key: from_bson(item) for key, item in value.items()}
    if isinstance(value, list):
        return [from_bson(item) for item in value]
    return value


class MongoAssessmentRepository(AssessmentWriteRepository):
    def __init__(
        self, database: AsyncDatabase, session: AsyncClientSession
    ) -> None:
        self._database = database
        self._session = session

    async def save_diagram_presentation(
        self, data: UseCaseDiagramPresentation
    ) -> None:
        document = _document(data)
        collection = UseCaseDiagramPresentationModel.collection(self._database)
        existing = await collection.find_one(
            {"uid": data.uid}, session=self._session
        )
        if existing is not None:
            existing.pop("_id", None)
            if existing != document:
                raise ValueError(
                    f"Diagram UID {data.uid!r} already has different content."
                )
            return
        await collection.insert_one(document, session=self._session)

    async def save_metrics(self, data: MetricsWithEvaluation) -> None:
        document = _document(data)
        await MetricsWithEvaluationModel.collection(self._database).insert_one(
            document, session=self._session
        )

    async def get_by_candidate_uid(
        self, candidate_uid: str
    ) -> MetricsWithEvaluation | None:
        document = await MetricsWithEvaluationModel.collection(
            self._database
        ).find_one(
            {"candidate_uid": candidate_uid},
            sort=[("_id", -1)],
            session=self._session,
        )
        return await self._hydrate(document)

    async def get_by_uid(self, uid: str) -> MetricsWithEvaluation | None:
        document = await MetricsWithEvaluationModel.collection(
            self._database
        ).find_one({"uid": uid}, session=self._session)
        return await self._hydrate(document)

    async def _hydrate(
        self, document: dict[str, Any] | None
    ) -> MetricsWithEvaluation | None:
        if document is None:
            return None
        document.pop("_id")
        reference = await UseCaseDiagramPresentationModel.collection(
            self._database
        ).find_one({"uid": document["reference_uid"]}, session=self._session)
        if reference is not None:
            reference.pop("_id")
        document["reference"] = reference
        return MetricsWithEvaluation.model_validate(from_bson(document))


def _document(model: BaseModel) -> dict[str, Any]:
    return to_bson(model.model_dump(mode="python"))
