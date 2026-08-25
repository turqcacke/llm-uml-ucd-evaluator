import argparse
import asyncio
from pathlib import Path

from src.app_logging import logger
from src.config import BASE_URL
from src.controller.di import container
from src.controller.scripts.results import save_result
from src.model.apollon import ApollonJson
from src.services.exceptions import BaseAppException
from src.services.pipelines.extractor.apollon_llm import (
    ApollonLlmExtractor,
    ApollonLlmExtractorInput,
)

RESULTS_PATH = BASE_URL / "scripts_out" / "run_apollon_extractor"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a diagram from Apollon"
    )
    parser.add_argument("apollon", type=Path)
    parser.add_argument(
        "--results-path",
        type=Path,
        default=RESULTS_PATH,
        help="Result directory (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    try:
        logger.info(
            "Apollon extractor CLI started input={} results_path={}",
            args.apollon,
            args.results_path,
        )
        data = ApollonLlmExtractorInput(
            ApollonJson.model_validate_json(args.apollon.read_text("utf-8"))
        )
        with container:
            pipeline = container.get(ApollonLlmExtractor)
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
