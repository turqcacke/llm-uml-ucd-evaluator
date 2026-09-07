from collections.abc import AsyncIterable

from dishka import Provider, Scope, alias, provide
from pymongo import AsyncMongoClient
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from src.config import Settings, get_settings
from src.infrastructure.mongo import (
    MongoAssessmentRepository,
    MongoUnitOfWork,
    prepare_database,
)
from src.services.diagram_assessment import (
    AssessmentReadRepository,
    AssessmentWriteRepository,
)
from src.services.ports import UnitOfWork


class MongoProvider(Provider):
    @provide(scope=Scope.APP)
    def settings(self) -> Settings:
        return get_settings()

    @provide(scope=Scope.APP)
    async def client(
        self, settings: Settings
    ) -> AsyncIterable[AsyncMongoClient]:
        client = AsyncMongoClient(settings.MONGODB_URI)
        try:
            yield client
        finally:
            await client.close()

    @provide(scope=Scope.APP)
    async def database(self, client: AsyncMongoClient) -> AsyncDatabase:
        database = client.get_default_database()
        await prepare_database(database)
        return database

    @provide(scope=Scope.REQUEST)
    async def session(
        self, client: AsyncMongoClient
    ) -> AsyncIterable[AsyncClientSession]:
        async with client.start_session() as session:
            yield session

    @provide(scope=Scope.REQUEST)
    def repository(
        self,
        database: AsyncDatabase,
        session: AsyncClientSession,
    ) -> MongoAssessmentRepository:
        return MongoAssessmentRepository(database, session)

    assessment_write_repository = alias(
        MongoAssessmentRepository,
        provides=AssessmentWriteRepository,
    )
    assessment_read_repository = alias(
        MongoAssessmentRepository,
        provides=AssessmentReadRepository,
    )

    @provide(scope=Scope.REQUEST)
    def unit_of_work(self, session: AsyncClientSession) -> UnitOfWork:
        return MongoUnitOfWork(session)
