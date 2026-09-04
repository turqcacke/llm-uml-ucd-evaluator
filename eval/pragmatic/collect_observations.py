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
from tqdm import tqdm

from eval.pragmatic.models import PragmaticMutationCase, load_dataset
from src.app_logging import logger
from src.config import BASE_URL, Settings, get_settings
from src.controller.di import ChatModelProvider, EvaluatorProvider
from src.infrastructure.requcd60.converter import ReqUCD60ToDomainConverter
from src.model.domain.evaluation import NodeNamingEvaluation
from src.services.evaluator import PragmaticInput, PragmaticLlmEvaluator

DATASET_PATH = BASE_URL / "datasets" / "10_pragmatic_mutations"
CHECKPOINTS_PATH = BASE_URL / "eval_out"
DATASET_ID = "10_pragmatic_mutations"
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
    parser.add_argument("--with-context", type=int, choices=(0, 1))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.experiment_name):
            raise ValueError(
                "Experiment name must contain only letters, digits, _ or -"
            )
        cases = load_dataset(DATASET_PATH)
        checkpoint = (
            CHECKPOINTS_PATH / f"{args.experiment_name}_pragmatic.json"
        )
        requested_context = (
            None if args.with_context is None else bool(args.with_context)
        )
        start_iteration = 1
        if args.resume:
            start_iteration, with_context = _load_checkpoint(
                checkpoint,
                args.repetitions,
                len(cases) * args.repetitions,
            )
            if (
                requested_context is not None
                and requested_context != with_context
            ):
                logger.warning(
                    "Checkpoint context mode {} overrides requested mode {}",
                    int(with_context),
                    int(requested_context),
                )
        elif checkpoint.exists():
            raise ValueError(
                f"Checkpoint exists: {checkpoint}; use --resume "
                "or a different --experiment-name"
            )
        else:
            with_context = (
                True if requested_context is None else requested_context
            )
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(
            _run(
                cases,
                args.experiment_name,
                args.repetitions,
                with_context,
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


def _load_checkpoint(
    checkpoint: Path,
    repetitions: int,
    last_iteration: int,
) -> tuple[int, bool]:
    if not checkpoint.exists():
        raise ValueError(f"Checkpoint does not exist: {checkpoint}")
    config = json.loads(checkpoint.read_text("utf-8"))
    if not isinstance(config, dict) or set(config) != {
        "dataset",
        "repetitions",
        "iteration",
        "with_context",
    }:
        raise ValueError(
            "Resume config must contain dataset, repetitions, iteration, "
            "and with_context"
        )
    if (
        config["dataset"] != DATASET_ID
        or type(config["repetitions"]) is not int
        or config["repetitions"] != repetitions
        or type(config["with_context"]) is not bool
    ):
        raise ValueError("Resume config does not match this run")
    iteration = config["iteration"]
    if type(iteration) is not int or not 1 <= iteration <= last_iteration:
        raise ValueError(
            f"iteration must be an integer from 1 to {last_iteration}"
        )
    return iteration, config["with_context"]


async def _run(
    cases: list[PragmaticMutationCase],
    experiment_name: str,
    repetitions: int,
    with_context: bool,
    start_iteration: int,
    checkpoint: Path,
    resume: bool,
) -> None:
    converter = ReqUCD60ToDomainConverter()
    async with app_container:
        database = await app_container.get(AsyncDatabase)
        collection = database[COLLECTION_NAME]
        if not resume and (
            await collection.find_one({"experiment_name": experiment_name})
            is not None
        ):
            raise ValueError(f"Experiment already exists: {experiment_name}")

        steps = [
            (case, repetition)
            for case in cases
            for repetition in range(1, repetitions + 1)
        ]
        remaining_steps = tqdm(
            steps[start_iteration - 1 :],
            total=len(steps),
            initial=start_iteration - 1,
            desc="Pragmatic naming",
            unit="observation",
        )
        for iteration, (case, repetition) in enumerate(
            remaining_steps, start=start_iteration
        ):
            temporary = checkpoint.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "dataset": DATASET_ID,
                        "repetitions": repetitions,
                        "iteration": iteration,
                        "with_context": with_context,
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
                        evaluator = await request_container.get(
                            PragmaticLlmEvaluator
                        )
                        actual = await evaluator.execute(
                            PragmaticInput(
                                use_case_diagram=converter.convert(
                                    case.mutation
                                ),
                                description=(
                                    case.description if with_context else None
                                ),
                            ),
                        )
            await collection.insert_one(
                {
                    "_id": document_id,
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
