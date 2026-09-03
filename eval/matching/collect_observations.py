import argparse
import asyncio
import json
import re
from collections.abc import AsyncIterable, Sequence
from pathlib import Path

from dishka import Provider, Scope, make_async_container, provide
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

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
DESCRIPTIONS_PATH = BASE_URL / "datasets" / "60_artificial" / "51-60"
CHECKPOINTS_PATH = BASE_URL / "eval_out"
DATASET_ID = "10_match_mutations"
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
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.experiment_name):
            raise ValueError(
                "Experiment name must contain only letters, digits, _ or -"
            )
        cases = load_dataset(DATASET_PATH)
        checkpoint = CHECKPOINTS_PATH / f"{args.experiment_name}_matching.json"
        start_iteration = 1
        if args.resume:
            if not checkpoint.exists():
                raise ValueError(f"Checkpoint does not exist: {checkpoint}")
            config = json.loads(checkpoint.read_text("utf-8"))
            if not isinstance(config, dict) or set(config) != {
                "dataset",
                "repetitions",
                "iteration",
            }:
                raise ValueError(
                    "Resume config must contain dataset, repetitions, and "
                    "iteration"
                )
            if (
                config["dataset"] != DATASET_ID
                or type(config["repetitions"]) is not int
                or config["repetitions"] != args.repetitions
            ):
                raise ValueError("Resume config does not match this run")
            start_iteration = config["iteration"]
            last_iteration = len(cases) * args.repetitions
            if (
                type(start_iteration) is not int
                or not 1 <= start_iteration <= last_iteration
            ):
                raise ValueError(
                    f"iteration must be an integer from 1 to {last_iteration}"
                )
        elif checkpoint.exists():
            raise ValueError(
                f"Checkpoint exists: {checkpoint}; use --resume "
                "or a different --experiment-name"
            )
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(
            _run(
                cases,
                args.experiment_name,
                args.repetitions,
                start_iteration,
                checkpoint,
                args.resume,
            )
        )
        checkpoint.unlink()
    except Exception as exc:
        logger.error("{}: error: {}", parser.prog, exc)
        return 1
    return 0


async def _run(
    cases: list[MutationCase],
    experiment_name: str,
    repetitions: int,
    start_iteration: int,
    checkpoint: Path,
    resume: bool,
) -> None:
    async with app_container:
        database = await app_container.get(AsyncDatabase)
        collection = database[COLLECTION_NAME]
        if not resume and (
            await collection.find_one({"experiment_name": experiment_name})
            is not None
        ):
            raise ValueError(f"Experiment already exists: {experiment_name}")

        steps = (
            (case, repetition)
            for case in cases
            for repetition in range(1, repetitions + 1)
        )
        for iteration, (case, repetition) in enumerate(steps, start=1):
            if iteration < start_iteration:
                continue
            temporary = checkpoint.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "dataset": DATASET_ID,
                        "repetitions": repetitions,
                        "iteration": iteration,
                    }
                )
                + "\n",
                "utf-8",
            )
            temporary.replace(checkpoint)
            document_id = (
                f"{experiment_name}_{case.sample}_"
                f"{case.mutation_number}_{repetition}"
            )
            if (
                resume
                and iteration == start_iteration
                and await collection.find_one({"_id": document_id}) is not None
            ):
                continue
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(4),
                wait=wait_exponential(multiplier=2, max=30),
                sleep=asyncio.sleep,
                reraise=True,
            ):
                with attempt:
                    async with app_container() as request_container:
                        matcher = await request_container.get(
                            UseCaseDiagramMatcher
                        )
                        result = await matcher.execute(
                            UseCaseDiagramMatcherInput(
                                reference=case.reference,
                                candidate=case.candidate,
                                description=(
                                    DESCRIPTIONS_PATH
                                    / f"{case.sample + 50}.txt"
                                ).read_text("utf-8"),
                            )
                        )
            actual = MinMatching(
                node_matches=result.node_matches,
                relation_matches=result.relation_matches,
            )
            await collection.insert_one(
                {
                    "_id": document_id,
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
