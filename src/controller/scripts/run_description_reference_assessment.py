import argparse
import asyncio
from pathlib import Path

from src.app_logging import logger
from src.config import BASE_URL
from src.controller.di import container
from src.controller.scripts.results import save_result
from src.model.apollon import ApollonJson
from src.services.exceptions import BaseAppException
from src.services.pipelines.diagram_assessment import (
    DescriptionReferenceAssessment,
    DescriptionReferenceAssessmentInput,
)

RESULTS_PATH = (
    BASE_URL / "scripts_out" / "run_description_reference_assessment"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assess an Apollon diagram against prose"
    )
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument(
        "--results-path",
        type=Path,
        default=RESULTS_PATH,
        help="Result directory (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    try:
        logger.info(
            "Description assessment CLI started reference={} candidate={} "
            "results_path={}",
            args.reference,
            args.candidate,
            args.results_path,
        )
        data = DescriptionReferenceAssessmentInput(
            reference_description=args.reference.read_text("utf-8"),
            candidate=ApollonJson.model_validate_json(
                args.candidate.read_text("utf-8")
            ),
        )
        with container:
            pipeline = container.get(DescriptionReferenceAssessment)
            result = asyncio.run(pipeline.execute(data))
        output = result.model_dump_json(indent=2)
        save_result(output, args.results_path)
    except (OSError, ValueError, BaseAppException) as exc:
        logger.error("{}: error: {}", parser.prog, exc)
        return 1
    logger.info("{}", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
