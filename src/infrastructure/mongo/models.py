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
    collection_name = "usecase_digarm_presentations"
    indexes = []


class MetricsWithEvaluationModel(MongoModel):
    collection_name = "metrics_presentations"
    indexes = []
