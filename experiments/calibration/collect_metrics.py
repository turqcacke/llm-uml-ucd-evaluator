import argparse
import asyncio
import json
import re
from pathlib import Path

from dishka import Provider, Scope, make_async_container
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

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
from src.model.apollon import ApollonJson
from src.model.domain import UseCaseDiagramPresentation
from src.services.diagram_assessment import (
    ApollonReferenceAssessment,
    ApollonReferenceAssessmentInput,
    DescriptionReferenceAssessment,
    DescriptionReferenceAssessmentInput,
)
from src.services.extractor import (
    ApollonJsonExtractor,
    ApollonJsonExtractorInput,
)

EXERCISES_PATH = BASE_URL / "exercises"
CHECKPOINTS_PATH = BASE_URL / "experiments_out"


class CalibrationCandidate(ApollonJson):
    uid: str


class CalibrationExtractor(ApollonJsonExtractor):
    async def execute(
        self, data: ApollonJsonExtractorInput
    ) -> UseCaseDiagramPresentation:
        diagram = await super().execute(data)
        if isinstance(data.apollon_model, CalibrationCandidate):
            diagram.uid = data.apollon_model.uid
        return diagram


calibration_provider = Provider()
calibration_provider.provide(
    CalibrationExtractor,
    provides=ApollonJsonExtractor,
    scope=Scope.REQUEST,
    override=True,
)
app_container = make_async_container(
    ChatModelProvider(),
    ExtractorProvider(),
    MatcherProvider(),
    EvaluatorProvider(),
    MongoProvider(),
    DiagramAssessmentProvider(),
    calibration_provider,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run reference/reference calibration on every third exercise"
    )
    parser.add_argument("--experiment-name", default="calibration")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.experiment_name):
            raise ValueError(
                "Experiment name must contain only letters, digits, _ or -"
            )
        exercises = sorted(
            (
                path
                for path in EXERCISES_PATH.iterdir()
                if path.is_dir()
                and re.fullmatch(r"exercise_[0-9]+", path.name)
            ),
            key=lambda path: int(path.name.removeprefix("exercise_")),
        )[::3]
        steps = [
            (exercise, usecase_type)
            for exercise in exercises
            for usecase_type in ("apollon", "description")
        ]
        if not steps:
            raise ValueError("No exercises found")
        checkpoint = CHECKPOINTS_PATH / f"{args.experiment_name}.json"
        n = 1
        if args.resume:
            config = json.loads(checkpoint.read_text("utf-8"))
            if not isinstance(config, dict) or set(config) != {"n"}:
                raise ValueError('Resume config must contain only "n"')
            n = config["n"]
            if type(n) is not int or not 1 <= n <= len(steps):
                raise ValueError(
                    f"n must be an integer from 1 to {len(steps)}"
                )
        elif checkpoint.exists():
            raise ValueError(
                f"Checkpoint exists: {checkpoint}; use --resume "
                "or a different --experiment-name"
            )
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(_run(steps, n, args.experiment_name, checkpoint))
        checkpoint.unlink()
    except Exception as exc:
        logger.error("{}: error: {}", parser.prog, exc)
        return 1
    return 0


async def _run(
    steps: list[tuple[Path, str]],
    start: int,
    experiment_name: str,
    checkpoint: Path,
) -> None:
    async with app_container:
        for n, (exercise, usecase_type) in enumerate(steps, start=1):
            if n < start:
                continue
            # Replace atomically so interruption cannot leave partial JSON.
            temporary = checkpoint.with_suffix(".tmp")
            temporary.write_text(json.dumps({"n": n}) + "\n", "utf-8")
            temporary.replace(checkpoint)
            reference = ApollonJson.model_validate_json(
                (exercise / f"{exercise.name}.json").read_text("utf-8")
            )
            candidate_uid = f"{experiment_name}_{exercise.name}_{usecase_type}"
            candidate = CalibrationCandidate(
                model=reference.model, uid=candidate_uid
            )
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(4),
                wait=wait_exponential(multiplier=2, max=30),
                reraise=True,
            ):
                with attempt:
                    logger.info(
                        "Iteration {}/{} candidate={} attempt={}",
                        n,
                        len(steps),
                        candidate_uid,
                        attempt.retry_state.attempt_number,
                    )
                    async with app_container() as request_container:
                        if usecase_type == "apollon":
                            apollon = await request_container.get(
                                ApollonReferenceAssessment
                            )
                            result = await apollon.execute(
                                ApollonReferenceAssessmentInput(
                                    reference=reference,
                                    candidate=candidate,
                                )
                            )
                        else:
                            description = await request_container.get(
                                DescriptionReferenceAssessment
                            )
                            result = await description.execute(
                                DescriptionReferenceAssessmentInput(
                                    reference_description=(
                                        exercise / f"{exercise.name}.txt"
                                    ).read_text("utf-8"),
                                    candidate=candidate,
                                )
                            )
                    logger.info("Iteration {} saved result={}", n, result.uid)


if __name__ == "__main__":
    raise SystemExit(main())
