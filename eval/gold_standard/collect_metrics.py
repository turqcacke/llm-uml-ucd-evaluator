import argparse
import asyncio
import json
import re
from functools import partial
from pathlib import Path
from typing import Any

from dishka import Provider, Scope, make_async_container, provide
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.asynchronous.database import AsyncDatabase
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential
from tqdm import tqdm

from eval.batching import add_batch_arguments, run_in_batches
from eval.gold_standard.models import GoldStandardMode
from eval.gold_standard.repository import (
    COLLECTION_NAME,
    GoldStandardObservationContext,
    GoldStandardRepositoryProvider,
)
from src.app_logging import logger
from src.config import BASE_URL
from src.controller.di import (
    ChatModelProvider,
    DiagramAssessmentProvider,
    EvaluatorProvider,
    ExtractorProvider,
    MatcherProvider,
)
from src.controller.di.mongo import MongoProvider
from src.infrastructure.requcd60.converter import ReqUCD60ToDomainConverter
from src.model.domain import UseCaseDiagramPresentation
from src.model.requcd60.result import ReqUCD60Result
from src.services.diagram_assessment.requcd60_reference import (
    ReqUCD60ReferenceAssessment,
    ReqUCD60ReferenceAssessmentInput,
)
from src.services.extractor.converter import BaseConverter
from src.services.extractor.requcd60 import (
    ReqUCD60Extractor,
    ReqUCD60ExtractorInput,
)

ANNOTATIONS_PATH = BASE_URL / "datasets" / "60_ideal_UCD"
DESCRIPTIONS_PATH = BASE_URL / "datasets" / "60_artificial"
CHECKPOINTS_PATH = BASE_URL / "eval_out"


class GoldStandardReference(ReqUCD60Result):
    uid: str


class GoldStandardReqUCD60Extractor(ReqUCD60Extractor):
    async def execute(
        self, data: ReqUCD60ExtractorInput
    ) -> UseCaseDiagramPresentation:
        diagram = await super().execute(data)
        if isinstance(data.reference, GoldStandardReference):
            diagram.uid = data.reference.uid
        return diagram


class ReqUCD60Provider(Provider):
    @provide(scope=Scope.APP)
    def requcd60_to_domain_converter(
        self,
    ) -> BaseConverter[ReqUCD60Result, UseCaseDiagramPresentation]:
        return ReqUCD60ToDomainConverter()

    requcd60_extractor = provide(
        GoldStandardReqUCD60Extractor,
        provides=ReqUCD60Extractor,
        scope=Scope.REQUEST,
    )
    requcd60_reference_assessment = provide(
        ReqUCD60ReferenceAssessment, scope=Scope.REQUEST
    )


app_container = make_async_container(
    ChatModelProvider(),
    ExtractorProvider(),
    MatcherProvider(),
    EvaluatorProvider(),
    MongoProvider(),
    DiagramAssessmentProvider(),
    ReqUCD60Provider(),
    GoldStandardRepositoryProvider(),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare ReqUCD60 extraction with the gold standard"
    )
    parser.add_argument("--experiment-name", default="gold_standard")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--size", choices=("short", "full"), default="short")
    add_batch_arguments(parser)
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.experiment_name):
            raise ValueError(
                "Experiment name must contain only letters, digits, _ or -"
            )
        asyncio.run(_main(args))
    except Exception as exc:
        logger.error("{}: error: {}", parser.prog, exc)
        return 1
    return 0


async def _main(args: argparse.Namespace) -> None:
    mode = args.size
    samples = range(1, 61) if mode == "full" else (1, 11, 21, 31, 41, 51)
    steps = []
    for sample in samples:
        lower = (sample - 1) // 10 * 10 + 1
        group = f"{lower}-{lower + 9}"
        steps.append(
            (
                sample,
                ANNOTATIONS_PATH / group / f"{sample}_result.json",
                DESCRIPTIONS_PATH / group / f"{sample}.txt",
            )
        )
    checkpoint = (
        CHECKPOINTS_PATH / f"{args.experiment_name}_requcd60_{mode}.json"
    )
    start_iteration = 1
    if args.resume:
        config = json.loads(
            await asyncio.to_thread(checkpoint.read_text, "utf-8")
        )
        if not isinstance(config, dict) or set(config) != {
            "dataset",
            "mode",
            "iteration",
        }:
            raise ValueError(
                "Resume config must contain dataset, mode, and iteration"
            )
        if config["dataset"] != "requcd60" or config["mode"] != mode:
            raise ValueError("Resume config does not match this run")
        start_iteration = config["iteration"]
        if type(start_iteration) is not int or not 1 <= start_iteration <= len(
            steps
        ):
            raise ValueError(
                f"iteration must be an integer from 1 to {len(steps)}"
            )
    elif checkpoint.exists():
        raise ValueError(
            f"Checkpoint exists: {checkpoint}; use --resume "
            "or a different --experiment-name"
        )
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    await _run(
        steps,
        start_iteration,
        args.experiment_name,
        mode,
        checkpoint,
        args.resume,
        args.batch_size,
        args.requests_per_minute,
    )
    checkpoint.unlink()


async def _write_checkpoint(
    iteration: int,
    *,
    checkpoint: Path,
    mode: GoldStandardMode,
) -> None:
    temporary = checkpoint.with_suffix(".tmp")
    content = (
        json.dumps(
            {
                "dataset": "requcd60",
                "mode": mode,
                "iteration": iteration,
            }
        )
        + "\n"
    )
    await asyncio.to_thread(temporary.write_text, content, "utf-8")
    await asyncio.to_thread(temporary.replace, checkpoint)


async def _collect_assessment(
    iteration: int,
    step: tuple[int, Path, Path],
    *,
    collection: AsyncCollection[dict[str, Any]],
    experiment_name: str,
    mode: GoldStandardMode,
    resume: bool,
    total_steps: int,
    progress: tqdm,
) -> None:
    sample, annotation_path, description_path = step
    observation_id = f"{experiment_name}_requcd60_{mode}_{sample}"
    if (
        resume
        and await collection.find_one({"_id": observation_id}) is not None
    ):
        progress.update()
        return
    annotation = await asyncio.to_thread(
        annotation_path.read_text,
        "utf-8",
    )
    reference = GoldStandardReference(
        **ReqUCD60Result.model_validate_json(annotation).model_dump(),
        uid=observation_id,
    )
    description = await asyncio.to_thread(description_path.read_text, "utf-8")
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, max=30),
        sleep=asyncio.sleep,
        reraise=True,
    ):
        with attempt:
            logger.info(
                "Iteration {}/{} mode={} sample={} attempt={}",
                iteration,
                total_steps,
                mode,
                sample,
                attempt.retry_state.attempt_number,
            )
            context = GoldStandardObservationContext(
                id=observation_id,
                experiment_name=experiment_name,
                mode=mode,
                sample=sample,
                description_path=description_path.relative_to(
                    BASE_URL
                ).as_posix(),
            )
            async with app_container(
                {GoldStandardObservationContext: context}
            ) as request_container:
                assessment = await request_container.get(
                    ReqUCD60ReferenceAssessment
                )
                result = await assessment.execute(
                    ReqUCD60ReferenceAssessmentInput(
                        reference=reference,
                        candidate_description=description,
                    )
                )
            logger.info(
                "Iteration {} sample={} reference={} saved result={}",
                iteration,
                sample,
                reference.uid,
                result.uid,
            )
    progress.update()


async def _run(
    steps: list[tuple[int, Path, Path]],
    start_iteration: int,
    experiment_name: str,
    mode: str,
    checkpoint: Path,
    resume: bool,
    batch_size: int,
    requests_per_minute: int,
) -> None:
    async with app_container:
        database = await app_container.get(AsyncDatabase)
        collection = database[COLLECTION_NAME]
        if not resume and (
            await collection.find_one({"experiment_name": experiment_name})
            is not None
        ):
            raise ValueError(f"Experiment already exists: {experiment_name}")

        progress = tqdm(
            total=len(steps),
            initial=start_iteration - 1,
            desc="Gold standard",
            unit="assessment",
        )
        try:
            await run_in_batches(
                steps,
                start_iteration=start_iteration,
                batch_size=batch_size,
                requests_per_minute=requests_per_minute,
                before_batch=partial(
                    _write_checkpoint,
                    checkpoint=checkpoint,
                    mode=mode,
                ),
                worker=partial(
                    _collect_assessment,
                    collection=collection,
                    experiment_name=experiment_name,
                    mode=mode,
                    resume=resume,
                    total_steps=len(steps),
                    progress=progress,
                ),
            )
        finally:
            progress.close()


if __name__ == "__main__":
    raise SystemExit(main())
