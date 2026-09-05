import asyncio
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from eval.models import ClassificationCounts
from src.model.domain.evaluation import PragmaticEvaluationResult
from src.model.requcd60.result import ReqUCD60Result


class PragmaticMutationEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mutation: ReqUCD60Result
    expectation: PragmaticEvaluationResult
    description: str


class PragmaticMutationCase(BaseModel):
    sample: int
    mutation_number: int
    mutation: ReqUCD60Result
    expectation: PragmaticEvaluationResult
    description: str


class PragmaticObservation(BaseModel):
    id: str = Field(serialization_alias="_id")
    experiment_name: str
    sample: int
    mutation: int
    actual: PragmaticEvaluationResult
    nodes: ClassificationCounts


async def load_dataset(path: Path) -> list[PragmaticMutationCase]:
    cases: list[PragmaticMutationCase] = []

    for sample_path in sorted(
        (
            entry
            for entry in path.iterdir()
            if entry.is_dir() and entry.name.isdigit()
        ),
        key=lambda entry: int(entry.name),
    ):
        sample = int(sample_path.name)
        for mutation_number in range(4):
            envelope = PragmaticMutationEnvelope.model_validate_json(
                await asyncio.to_thread(
                    (
                        sample_path / f"{sample}_{mutation_number}.json"
                    ).read_text,
                    "utf-8",
                )
            )
            cases.append(
                PragmaticMutationCase(
                    sample=sample,
                    mutation_number=mutation_number,
                    **envelope.model_dump(),
                )
            )

    return cases
