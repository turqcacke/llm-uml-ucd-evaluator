from typing import cast

import pytest
from pymongo.errors import OperationFailure

from src.infrastructure.mongo import MongoUnitOfWork


class FakeSession:
    def __init__(self) -> None:
        self.in_transaction = False
        self.commit_calls = 0
        self.abort_calls = 0

    async def start_transaction(self) -> None:
        self.in_transaction = True

    async def commit_transaction(self) -> None:
        self.commit_calls += 1
        if self.commit_calls == 1:
            raise OperationFailure(
                "Commit result unknown",
                details={"errorLabels": ["UnknownTransactionCommitResult"]},
            )
        self.in_transaction = False

    async def abort_transaction(self) -> None:
        self.abort_calls += 1
        self.in_transaction = False

@pytest.mark.anyio
async def test_unknown_commit_result_retries_commit_only() -> None:
    from pymongo.asynchronous.client_session import AsyncClientSession

    session = FakeSession()
    unit_of_work = MongoUnitOfWork(cast(AsyncClientSession, session))

    async with unit_of_work:
        await unit_of_work.commit()

    assert session.commit_calls == 2
    assert session.abort_calls == 0
