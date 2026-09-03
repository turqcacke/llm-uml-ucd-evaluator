import argparse
import asyncio
from pathlib import Path

from src.app_logging import logger
from src.config import BASE_URL
from src.controller.di import assessment_container as app_container
from src.controller.scripts.results import save_result
from src.model.apollon import ApollonJson
from src.model.domain import MetricsWithEvaluation
from src.services.diagram_assessment import (
    ApollonToApollonAssessment,
    ApollonToApollonAssessmentInput,
)
from src.services.exceptions import BaseAppException

RESULTS_PATH = BASE_URL / "scripts_out" / "run_apollon_to_apollon_assessment"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assess one Apollon diagram against another"
    )
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--description", type=Path)
    parser.add_argument(
        "--results-path",
        type=Path,
        default=RESULTS_PATH,
        help="Result directory (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    try:
        logger.info(
            "Apollon assessment CLI started reference={} candidate={} "
            "results_path={}",
            args.reference,
            args.candidate,
            args.results_path,
        )
        data = ApollonToApollonAssessmentInput(
            reference=ApollonJson.model_validate_json(
                args.reference.read_text("utf-8")
            ),
            candidate=ApollonJson.model_validate_json(
                args.candidate.read_text("utf-8")
            ),
            description=(
                args.description.read_text("utf-8")
                if args.description
                else None
            ),
        )
        result = asyncio.run(_execute(data))
        output = result.model_dump_json(indent=2, exclude={"matching"})
        save_result(output, args.results_path)
    except (OSError, ValueError, BaseAppException) as exc:
        logger.error("{}: error: {}", parser.prog, exc)
        return 1
    logger.info("{}", output)
    return 0


async def _execute(
    data: ApollonToApollonAssessmentInput,
) -> MetricsWithEvaluation:
    async with app_container:
        async with app_container() as request_container:
            use_case = await request_container.get(ApollonToApollonAssessment)
            return await use_case.execute(data)


if __name__ == "__main__":
    raise SystemExit(main())
