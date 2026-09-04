import argparse
import asyncio
import re
from collections.abc import AsyncIterable, Sequence

from dishka import Provider, Scope, make_async_container, provide
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from eval.pragmatic.models import PragmaticMutationCase, load_dataset
from src.app_logging import logger
from src.config import BASE_URL, Settings, get_settings
from src.controller.di import ChatModelProvider, EvaluatorProvider
from src.infrastructure.requcd60.converter import ReqUCD60ToDomainConverter
from src.model.domain.evaluation import NodeNamingEvaluation
from src.services.evaluator import PragmaticInput, PragmaticLlmEvaluator

DATASET_PATH = BASE_URL / "datasets" / "10_pragmatic_mutations"
COLLECTION_NAME = "pragmatic_naming_eval"


class PragmaticMongoProvider(Provider):
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
    EvaluatorProvider(),
    PragmaticMongoProvider(),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate pragmatic naming against controlled mutations"
    )
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument(
        "--repetitions", type=int, choices=range(1, 4), default=3
    )
    parser.add_argument("--with-context", type=int, choices=(0, 1), default=1)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.experiment_name):
            raise ValueError(
                "Experiment name must contain only letters, digits, _ or -"
            )
        if args.resume:
            raise ValueError("Resume support is not implemented yet")
        asyncio.run(
            _run(
                load_dataset(DATASET_PATH),
                args.experiment_name,
                args.repetitions,
                bool(args.with_context),
            )
        )
    except Exception as exc:
        logger.error("{}: error: {}", parser.prog, exc)
        return 1
    return 0


async def _run(
    cases: list[PragmaticMutationCase],
    experiment_name: str,
    repetitions: int,
    with_context: bool,
) -> None:
    converter = ReqUCD60ToDomainConverter()
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
                    evaluator = await request_container.get(
                        PragmaticLlmEvaluator
                    )
                    actual = await evaluator.execute(
                        PragmaticInput(
                            use_case_diagram=converter.convert(case.mutation),
                            description=(
                                case.description if with_context else None
                            ),
                        )
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
                        "nodes": _counts(case.expectation.nodes, actual.nodes),
                    }
                )


def _counts(
    expected: Sequence[NodeNamingEvaluation],
    actual: Sequence[NodeNamingEvaluation],
) -> dict[str, int]:
    expected_pairs = {(node.uid, node.score) for node in expected}
    actual_pairs = {(node.uid, node.score) for node in actual}
    return {
        "true_positive": len(expected_pairs & actual_pairs),
        "false_positive": len(actual_pairs - expected_pairs),
        "false_negative": len(expected_pairs - actual_pairs),
    }


if __name__ == "__main__":
    raise SystemExit(main())
