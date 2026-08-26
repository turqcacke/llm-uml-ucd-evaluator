import asyncio
from decimal import Decimal
from typing import Any

import pytest
from bson.decimal128 import Decimal128
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from src.infrastructure.mongo import (
    MetricsWithEvaluationModel,
    MongoAssessmentWriteRepository,
    MongoUnitOfWork,
    UseCaseDiagramPresentationModel,
    prepare_database,
)
from src.model.domain import (
    EvaluationResult,
    ExtendedMatching,
    MetricsWithEvaluation,
    Node,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.model.domain.matching import NodeMatch


def _diagram(uid: str, node_uid: str) -> UseCaseDiagramPresentation:
    return UseCaseDiagramPresentation(
        uid=uid,
        nodes=[Node(uid=node_uid, name="Customer", type=NodeType.ACTOR)],
        relations=[],
    )


def _result(
    uid: str,
    reference: UseCaseDiagramPresentation,
    candidate: UseCaseDiagramPresentation,
) -> MetricsWithEvaluation:
    return MetricsWithEvaluation(
        uid=uid,
        reference_uid=reference.uid,
        candidate_uid=candidate.uid,
        candidate_is_allowed=True,
        redundancy_rate=Decimal("0.123456789123456789"),
        completeness_rate=Decimal(1),
        semantic_precision=Decimal(1),
        semantic_f1_score=Decimal(1),
        syntactic_error_rate=Decimal(0),
        naming_understandability_score=Decimal(3),
        reference_complexity=Decimal(0),
        candidate_complexity=Decimal(2),
        complexity_difference=Decimal(2),
        complexity_deviation_rate=Decimal("Infinity"),
        evaluation=EvaluationResult(
            node_evaluations=[], relation_evaluations=[], applied_rules=[]
        ),
    )


@pytest.mark.anyio
async def test_repository_persists_complete_assessment_and_identity_rules(
    mongo_database: AsyncDatabase[Any],
) -> None:
    database = mongo_database
    reference = _diagram("reference", "r1")
    candidate = _diagram("candidate", "c1")
    result = _result("result", reference, candidate)
    matching = ExtendedMatching(
        reference=reference,
        candidate=candidate,
        node_matches=[NodeMatch(reference_uid="r1", candidate_uid="c1")],
        relation_matches=[],
    )
    result.matching = matching

    async with database.client.start_session() as session:
        repository = MongoAssessmentWriteRepository(database, session)
        async with MongoUnitOfWork(session) as unit_of_work:
            await repository.save_diagram_presentation(reference)
            await repository.save_diagram_presentation(candidate)
            await repository.save_metrics(result)
            await unit_of_work.commit()

    stored = await MetricsWithEvaluationModel.collection(database).find_one(
        {"uid": result.uid}
    )
    assert stored["reference_uid"] == reference.uid
    assert stored["matching"]["node_matches"] == [
        {"reference_uid": "r1", "candidate_uid": "c1"}
    ]
    assert stored["matching"]["missing_nodes"] == []
    assert stored["redundancy_rate"] == Decimal128("0.123456789123456789")
    assert stored["complexity_deviation_rate"] == Decimal128("Infinity")

    empty_matching = ExtendedMatching(
        reference=reference,
        candidate=candidate,
        node_matches=[],
        relation_matches=[],
    )
    async with database.client.start_session() as session:
        repository = MongoAssessmentWriteRepository(database, session)
        async with MongoUnitOfWork(session) as unit_of_work:
            empty_result = _result("empty-matching", reference, candidate)
            empty_result.matching = empty_matching
            await repository.save_metrics(empty_result)
            await repository.save_metrics(
                _result("skipped-matching", reference, candidate)
            )
            await unit_of_work.commit()
    collection = MetricsWithEvaluationModel.collection(database)
    assert set(await collection.index_information()) >= {
        "uid_1",
        "reference_uid_1",
        "candidate_uid_1",
    }
    assert (await collection.find_one({"uid": "empty-matching"}))["matching"][
        "node_matches"
    ] == []
    assert (await collection.find_one({"uid": "skipped-matching"}))[
        "matching"
    ] is None

    async with database.client.start_session() as session:
        repository = MongoAssessmentWriteRepository(database, session)
        async with MongoUnitOfWork(session) as unit_of_work:
            await repository.save_diagram_presentation(reference)
            await repository.save_diagram_presentation(
                reference.model_copy(update={"uid": "same-content-new-uid"})
            )
            await unit_of_work.commit()
    assert (
        await UseCaseDiagramPresentationModel.collection(
            database
        ).count_documents({"nodes": reference.model_dump()["nodes"]})
        == 2
    )

    conflicting = reference.model_copy(
        update={"nodes": [Node(uid="r1", name="Other", type=NodeType.ACTOR)]}
    )
    async with database.client.start_session() as session:
        repository = MongoAssessmentWriteRepository(database, session)
        with pytest.raises(ValueError, match="different content"):
            async with MongoUnitOfWork(session):
                await repository.save_diagram_presentation(conflicting)

    async with database.client.start_session() as session:
        repository = MongoAssessmentWriteRepository(database, session)
        with pytest.raises(DuplicateKeyError):
            async with MongoUnitOfWork(session):
                await repository.save_metrics(result)


@pytest.mark.anyio
async def test_failed_and_cancelled_transactions_do_not_affect_commits(
    mongo_database: AsyncDatabase[Any],
) -> None:
    database = mongo_database
    started = asyncio.Event()

    async with database.client.start_session() as session:
        repository = MongoAssessmentWriteRepository(database, session)
        with pytest.raises(RuntimeError, match="write failed"):
            async with MongoUnitOfWork(session):
                await repository.save_diagram_presentation(
                    _diagram("failed", "f")
                )
                raise RuntimeError("write failed")

    async def cancelled_write() -> None:
        async with database.client.start_session() as session:
            repository = MongoAssessmentWriteRepository(database, session)
            async with MongoUnitOfWork(session):
                await repository.save_diagram_presentation(
                    _diagram("cancelled", "c")
                )
                started.set()
                await asyncio.Event().wait()

    task = asyncio.create_task(cancelled_write())
    await started.wait()
    async with database.client.start_session() as session:
        repository = MongoAssessmentWriteRepository(database, session)
        async with MongoUnitOfWork(session) as unit_of_work:
            await repository.save_diagram_presentation(
                _diagram("committed", "ok")
            )
            await unit_of_work.commit()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    collection = UseCaseDiagramPresentationModel.collection(database)
    assert await collection.find_one({"uid": "committed"}) is not None
    assert await collection.find_one({"uid": "failed"}) is None
    assert await collection.find_one({"uid": "cancelled"}) is None


@pytest.mark.anyio
async def test_schema_rejects_legacy_data(
    mongo_database: AsyncDatabase[Any],
) -> None:
    database = mongo_database
    await database["metrics_presentations"].insert_one({"uid": "legacy"})

    with pytest.raises(RuntimeError, match="migration required"):
        await prepare_database(database)
