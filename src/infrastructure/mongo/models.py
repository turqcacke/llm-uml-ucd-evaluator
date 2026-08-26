from typing import ClassVar

from pymongo import IndexModel


class MongoModel:
    collection_name: ClassVar[str]
    indexes: ClassVar[list[IndexModel]] = []

    @classmethod
    def collection(cls, db):
        return db[cls.collection_name]

    @classmethod
    async def ensure_indexes(cls, db):
        if cls.indexes:
            await cls.collection(db).create_indexes(cls.indexes)


class UseCaseDiagramPresentationModel(MongoModel):
    collection_name = "use_case_diagram_presentations"
    indexes = [IndexModel("uid", unique=True)]


class MetricsWithEvaluationModel(MongoModel):
    collection_name = "diagram_assessments"
    indexes = [
        IndexModel("uid", unique=True),
        IndexModel("reference_uid"),
        IndexModel("candidate_uid"),
    ]


MONGO_MODELS = (
    UseCaseDiagramPresentationModel,
    MetricsWithEvaluationModel,
)
