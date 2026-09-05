from typing import Literal

from pydantic import BaseModel, Field

from src.model.domain import MetricsWithEvaluation, UseCaseDiagramPresentation

type GoldStandardMode = Literal["short", "full"]


class GoldStandardObservation(BaseModel):
    id: str = Field(serialization_alias="_id")
    experiment_name: str
    mode: GoldStandardMode
    sample: int
    description_path: str
    reference: UseCaseDiagramPresentation
    candidate: UseCaseDiagramPresentation
    metrics: MetricsWithEvaluation
