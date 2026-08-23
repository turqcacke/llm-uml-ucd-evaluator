import argparse
import asyncio
from pathlib import Path

from src.app_logging import logger
from src.config import BASE_URL
from src.controller.di import container
from src.controller.scripts.results import save_result
from src.services.llm_client.exceptions import LlmProviderException
from src.services.pipelines.extractor.text import (
    DesciptionExtractorInput,
    DescriptionExtractor,
)

RESULTS_PATH = BASE_URL / "scripts_out" / "run_extractor"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a diagram from prose"
    )
    parser.add_argument("description", type=Path)
    parser.add_argument(
        "--results-path",
        type=Path,
        default=RESULTS_PATH,
        help="Result directory (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    try:
        logger.info(
            "Extractor CLI started input={} results_path={}",
            args.description,
            args.results_path,
        )
        data = DesciptionExtractorInput(args.description.read_text("utf-8"))
        with container:
            pipeline = container.get(DescriptionExtractor)
            result = asyncio.run(pipeline.execute(data))
        output = result.model_dump_json(indent=2)
        save_result(output, args.results_path)
    except (OSError, ValueError, LlmProviderException) as exc:
        logger.error("{}: error: {}", parser.prog, exc)
        return 1
    logger.info("{}", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
