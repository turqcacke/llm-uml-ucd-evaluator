import argparse
import asyncio
from pathlib import Path

from src.config import BASE_URL
from src.controller.di import container
from src.controller.scripts.results import save_result
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.services.llm_client.exceptions import LlmProviderException
from src.services.pipelines.matcher.use_case_diagram import (
    UseCaseDiagramMatcher,
    UseCaseDiagramMatcherInput,
)

RESULTS_PATH = BASE_URL / "scripts_out" / "run_mathcer"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Match two use case diagrams")
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
        data = UseCaseDiagramMatcherInput(
            reference=UseCaseDiagramPresentation.model_validate_json(
                args.reference.read_text("utf-8")
            ),
            candidate=UseCaseDiagramPresentation.model_validate_json(
                args.candidate.read_text("utf-8")
            ),
        )
        with container:
            pipeline = container.get(UseCaseDiagramMatcher)
            result = asyncio.run(pipeline.execute(data))
        output = result.model_dump_json(indent=2)
        save_result(output, args.results_path)
    except (OSError, ValueError, LlmProviderException) as exc:
        parser.exit(1, f"{parser.prog}: error: {exc}\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
