from decimal import ROUND_HALF_EVEN, Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    field_serializer,
    field_validator,
)

from src.model.apollon import ApollonJson
from src.model.domain import (
    AssessmentState,
    EvaluationResult,
    ExtendedMatching,
    Node,
    NodeRelation,
)

Identifier = Annotated[StrictStr, Field(min_length=1, max_length=256)]
Name = Annotated[StrictStr, Field(max_length=512)]
Direction = Annotated[StrictStr, Field(min_length=1, max_length=64)]


class BoundsInput(BaseModel):
    x: float
    y: float


class EndpointInput(BaseModel):
    direction: Direction
    element: Identifier


class NodeInput(BaseModel):
    id: Identifier
    name: Name
    type: Literal[
        "UseCaseActor",
        "UseCaseSystem",
        "UseCase",
        "UseCaseExternalSystem",
        "ColorLegend",
        "InvalidNode",
    ]
    owner: Identifier | None
    bounds: BoundsInput


class RelationInput(BaseModel):
    id: Identifier
    name: Name
    type: Literal[
        "UseCaseAssociation",
        "UseCaseExtend",
        "UseCaseInclude",
        "UseCaseGeneralization",
        "UseCaseSupport",
    ]
    owner: Identifier | None = None
    bounds: BoundsInput
    source: EndpointInput
    target: EndpointInput


class ApollonModelInput(BaseModel):
    elements: dict[str, NodeInput]
    relationships: dict[str, RelationInput]


class ApollonInput(BaseModel):
    model: ApollonModelInput

    def to_service(self) -> ApollonJson:
        return ApollonJson.model_validate(self.model_dump())


class DescriptionAssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["description"]
    reference: StrictStr
    candidate: ApollonInput

    @field_validator("reference")
    @classmethod
    def reference_must_contain_text(cls, value: str) -> str:
        length = sum(not character.isspace() for character in value)
        if not 100 <= length <= 5000:
            raise ValueError(
                "must contain 100 to 5000 non-whitespace characters"
            )
        return value


class ApollonAssessmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["apollon"]
    reference: ApollonInput
    candidate: ApollonInput
    description: StrictStr | None = None


AssessmentInput = Annotated[
    DescriptionAssessmentInput | ApollonAssessmentInput,
    Field(discriminator="type"),
]


class AssessmentReference(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    nodes: list[Node]
    relations: list[NodeRelation]


class AssessmentResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    candidate_is_allowed: bool
    redundancy_rate: Decimal
    completeness_rate: Decimal
    semantic_precision: Decimal
    semantic_f1_score: Decimal
    syntactic_error_rate: Decimal
    naming_understandability_score: Decimal
    reference_complexity: Decimal
    candidate_complexity: Decimal
    complexity_difference: Decimal
    complexity_deviation_rate: Decimal = Field(allow_inf_nan=True)
    reference: AssessmentReference
    matching: ExtendedMatching | None
    evaluation: EvaluationResult | None

    @field_serializer(
        "redundancy_rate",
        "completeness_rate",
        "semantic_precision",
        "semantic_f1_score",
        "syntactic_error_rate",
        "naming_understandability_score",
        "reference_complexity",
        "candidate_complexity",
        "complexity_difference",
        "complexity_deviation_rate",
        when_used="json",
    )
    def serialize_metric(self, value: Decimal) -> int | float | str:
        if not value.is_finite():
            return str(value)
        rounded = value.quantize(Decimal("0.000001"), ROUND_HALF_EVEN)
        if rounded == rounded.to_integral():
            return int(rounded)
        return float(rounded)


class AssessmentProgress(BaseModel):
    state: AssessmentState


class AssessmentStreamResult(BaseModel):
    state: AssessmentState
    data: AssessmentResult
