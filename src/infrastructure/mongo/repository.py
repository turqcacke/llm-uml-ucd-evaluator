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


class MongoAssessmentWriteRepository(AssessmentWriteRepository):
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


def _document(model: BaseModel) -> dict[str, Any]:
    return to_bson(model.model_dump(mode="python"))
