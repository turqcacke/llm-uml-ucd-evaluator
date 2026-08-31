from pathlib import Path
from typing import Self

from pydantic import BaseModel

from src.infrastructure.requcd60.converter import ReqUCD60ToDomainConverter
from src.model.domain import ExtendedMatching, MinMatching
from src.model.domain.diagram_presentation import UseCaseDiagramPresentation
from src.model.requcd60.result import ReqUCD60Result


class MutationEnvelope(BaseModel):
    mutation: ReqUCD60Result
    expectation: MinMatching


class MutationCase(BaseModel):
    sample: int
    mutation_number: int
    reference: UseCaseDiagramPresentation
    candidate: UseCaseDiagramPresentation
    expectation: MinMatching

    @classmethod
    def from_mutation(
        cls,
        *,
        sample: int,
        mutation_number: int,
        reference: ReqUCD60Result,
        mutation: ReqUCD60Result,
        expectation: MinMatching,
    ) -> Self:
        converter = ReqUCD60ToDomainConverter()
        reference_diagram = converter.convert(reference)
        candidate_diagram = converter.convert(mutation)
        ExtendedMatching(
            **expectation.model_dump(),
            reference=reference_diagram,
            candidate=candidate_diagram,
        )
        if not any(
            match.reference_uid == match.candidate_uid == "system"
            for match in expectation.node_matches
        ):
            raise ValueError("Expectation must contain the system match.")
        return cls(
            sample=sample,
            mutation_number=mutation_number,
            reference=reference_diagram,
            candidate=candidate_diagram,
            expectation=expectation,
        )


def load_dataset(path: Path) -> list[MutationCase]:
    cases: list[MutationCase] = []
    for sample in range(1, 11):
        envelopes = [
            MutationEnvelope.model_validate_json(
                (path / str(sample) / f"{sample}_{mutation}.json").read_text(
                    "utf-8"
                )
            )
            for mutation in range(6)
        ]
        reference = envelopes[0].mutation
        cases.extend(
            MutationCase.from_mutation(
                sample=sample,
                mutation_number=mutation_number,
                reference=reference,
                mutation=envelope.mutation,
                expectation=envelope.expectation,
            )
            for mutation_number, envelope in enumerate(envelopes)
        )
    return cases
