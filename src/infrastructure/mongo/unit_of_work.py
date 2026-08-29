from types import TracebackType

from anyio import CancelScope
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.errors import PyMongoError


class MongoUnitOfWork:
    def __init__(self, session: AsyncClientSession) -> None:
        self._session = session

    async def __aenter__(self) -> "MongoUnitOfWork":
        await self._session.start_transaction()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        with CancelScope(shield=True):
            await self.rollback()

    async def commit(self) -> None:
        try:
            await self._session.commit_transaction()
        except PyMongoError as exc:
            if not exc.has_error_label("UnknownTransactionCommitResult"):
                raise
            await self._session.commit_transaction()

    async def rollback(self) -> None:
        if self._session.in_transaction:
            await self._session.abort_transaction()
