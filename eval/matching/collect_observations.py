import argparse
import asyncio
import re
from collections.abc import AsyncIterable, Sequence

from dishka import Provider, Scope, make_async_container, provide
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from eval.matching.models import MutationCase, load_dataset
from src.app_logging import logger
from src.config import BASE_URL, Settings, get_settings
from src.controller.di import ChatModelProvider, MatcherProvider
from src.model.domain import MinMatching
from src.model.domain.matching import NodeMatch, RelationMatch
from src.services.matcher import (
    UseCaseDiagramMatcher,
    UseCaseDiagramMatcherInput,
)

DATASET_PATH = BASE_URL / "datasets" / "10_match_mutations"
COLLECTION_NAME = "matching_eval"


class MatchingMongoProvider(Provider):
    @provide(scope=Scope.APP)
    def settings(self) -> Settings:
        return get_settings()

    @provide(scope=Scope.APP)
    async def database(
        self, settings: Settings
    ) -> AsyncIterable[AsyncDatabase]:
        client = AsyncMongoClient(settings.MONGODB_URI)
        try:
            yield client.get_default_database()
        finally:
            await client.close()


app_container = make_async_container(
    ChatModelProvider(),
    MatcherProvider(),
    MatchingMongoProvider(),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate matcher behavior against controlled mutations"
    )
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--repetitions", type=int, choices=range(1, 4), default=3)
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.experiment_name):
            raise ValueError(
                "Experiment name must contain only letters, digits, _ or -"
            )
        cases = load_dataset(DATASET_PATH)
        asyncio.run(_run(cases, args.experiment_name, args.repetitions))
    except Exception as exc:
        logger.error("{}: error: {}", parser.prog, exc)
        return 1
    return 0


async def _run(
    cases: list[MutationCase],
    experiment_name: str,
    repetitions: int,
) -> None:
    async with app_container:
        database = await app_container.get(AsyncDatabase)
        collection = database[COLLECTION_NAME]
        if (
            await collection.find_one({"experiment_name": experiment_name})
            is not None
        ):
            raise ValueError(f"Experiment already exists: {experiment_name}")

        for case in cases:
            for repetition in range(1, repetitions + 1):
                async with app_container() as request_container:
                    matcher = await request_container.get(UseCaseDiagramMatcher)
                    result = await matcher.execute(
                        UseCaseDiagramMatcherInput(
                            reference=case.reference,
                            candidate=case.candidate,
                        )
                    )
                actual = MinMatching(
                    node_matches=result.node_matches,
                    relation_matches=result.relation_matches,
                )
                await collection.insert_one(
                    {
                        "_id": (
                            f"{experiment_name}_{case.sample}_"
                            f"{case.mutation_number}_{repetition}"
                        ),
                        "experiment_name": experiment_name,
                        "sample": case.sample,
                        "mutation": case.mutation_number,
                        "actual": actual.model_dump(),
                        "nodes": _counts(
                            case.expectation.node_matches,
                            actual.node_matches,
                        ),
                        "relations": _counts(
                            case.expectation.relation_matches,
                            actual.relation_matches,
                        ),
                    }
                )


def _counts(
    expected: Sequence[NodeMatch | RelationMatch],
    actual: Sequence[NodeMatch | RelationMatch],
) -> dict[str, int]:
    expected_pairs = {
        (match.reference_uid, match.candidate_uid) for match in expected
    }
    actual_pairs = {
        (match.reference_uid, match.candidate_uid) for match in actual
    }
    return {
        "true_positive": len(expected_pairs & actual_pairs),
        "false_positive": len(actual_pairs - expected_pairs),
        "false_negative": len(expected_pairs - actual_pairs),
    }


if __name__ == "__main__":
    raise SystemExit(main())
