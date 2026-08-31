from decimal import Decimal
from types import TracebackType

import pytest

from src.infrastructure.requcd60.converter import ReqUCD60ToDomainConverter
from src.model.domain import (
    EvaluationResult,
    MetricsWithEvaluation,
    Node,
    NodeRelation,
    NodeRelationType,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.model.domain.evaluation import (
    NamingUnderstandabilityScore,
    NodeEvaluation,
    RelationEvaluation,
)
from src.model.domain.matching import MinMatching, NodeMatch, RelationMatch
from src.model.requcd60.result import ReqUCD60Result
from src.services.diagram_assessment.requcd60_candidate import (
    ReqUCD60CandidateAssessment,
    ReqUCD60CandidateAssessmentInput,
)
from src.services.evaluator import PragmaticSyntacticLlmEvaluator
from src.services.exceptions import (
    LlmRequestError,
    ReferenceNotAllowedError,
    UseCaseError,
)
from src.services.extractor import DescriptionExtractor
from src.services.extractor.requcd60 import (
    ReqUCD60Extractor,
    ReqUCD60ExtractorInput,
)
from src.services.matcher import UseCaseDiagramMatcher
from src.services.ports import LLMRoles


class ControlledModel[T]:
    def __init__(self, result: T) -> None:
        self.result = result
        self.error: Exception | None = None
        self.prompts: list[str] = []

    async def invoke(self, prompt: str, role: LLMRoles) -> T:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.result


class FakePersistence:
    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.diagrams: list[UseCaseDiagramPresentation] = []
        self.results: list[MetricsWithEvaluation] = []
        self.pending_diagrams: list[UseCaseDiagramPresentation] = []
        self.pending_results: list[MetricsWithEvaluation] = []
        self.active = False
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> "FakePersistence":
        self.active = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        self.active = False

    async def save_diagram_presentation(
        self, data: UseCaseDiagramPresentation
    ) -> None:
        assert self.active
        if self.fail_on == "candidate" and self.pending_diagrams:
            raise RuntimeError("persistence failed")
        self.pending_diagrams.append(data.model_copy(deep=True))

    async def save_metrics(self, data: MetricsWithEvaluation) -> None:
        assert self.active
        if self.fail_on == "metrics":
            raise RuntimeError("persistence failed")
        self.pending_results.append(data.model_copy(deep=True))

    async def commit(self) -> None:
        assert self.active
        if self.fail_on == "commit":
            raise RuntimeError("persistence failed")
        self.diagrams.extend(self.pending_diagrams)
        self.results.extend(self.pending_results)
        self.pending_diagrams.clear()
        self.pending_results.clear()
        self.commits += 1

    async def rollback(self) -> None:
        self.pending_diagrams.clear()
        self.pending_results.clear()
        self.rollbacks += 1


def _annotation() -> ReqUCD60Result:
    return ReqUCD60Result(
        actors=["Customer"],
        usecases=["Place order"],
        association_relationships={"Customer": ["Place order"]},
        inclusion_relationships={},
        extension_relationships={},
        generalization_relationships_for_usecases={},
        generalization_relationships_for_actors={},
    )


def _reference() -> UseCaseDiagramPresentation:
    return UseCaseDiagramPresentation(
        nodes=[
            Node(uid="r-actor", name="Customer", type=NodeType.ACTOR),
            Node(uid="r-order", name="Place order", type=NodeType.USECASE),
            Node(
                uid="r-payment",
                name="Payment API",
                type=NodeType.EXTERNAL_SYSTEM,
            ),
            Node(uid="r-note", name="Generated note", type=NodeType.NOTE),
        ],
        relations=[
            NodeRelation(
                uid="r-association",
                source="r-actor",
                target="r-order",
                type=NodeRelationType.ASSOCIATION,
            )
        ],
    )


def _workflow(reference: UseCaseDiagramPresentation, store: FakePersistence):
    extraction = ControlledModel(reference)
    candidate = ReqUCD60ToDomainConverter().convert(_annotation())
    matching = ControlledModel(
        MinMatching(node_matches=[], relation_matches=[])
    )
    evaluation = ControlledModel(
        EvaluationResult(
            node_evaluations=[
                NodeEvaluation(
                    uid=node.uid,
                    naming_score=NamingUnderstandabilityScore.HIGH,
                    syntactic_errors=[],
                    rules_applied=[],
                )
                for node in candidate.nodes
                if node.type != NodeType.NOTE
            ],
            relation_evaluations=[
                RelationEvaluation(
                    uid=relation.uid, syntactic_errors=[], rules_applied=[]
                )
                for relation in candidate.relations
            ],
            applied_rules=[],
        )
    )
    workflow = ReqUCD60CandidateAssessment(
        candidate_extractor=ReqUCD60Extractor(ReqUCD60ToDomainConverter()),
        description_extractor=DescriptionExtractor(extraction),
        matcher=UseCaseDiagramMatcher(matching),
        evaluator=PragmaticSyntacticLlmEvaluator(evaluation),
        repository=store,
        unit_of_work=store,
    )
    return workflow, extraction, matching, evaluation


@pytest.mark.anyio
async def test_assessment_returns_and_atomically_saves_agreed_diagram_roles():
    annotation = _annotation()
    annotation_before = annotation.model_dump()
    candidate = await ReqUCD60Extractor(ReqUCD60ToDomainConverter()).execute(
        ReqUCD60ExtractorInput(annotation)
    )
    reference = _reference()
    reference_before = reference.model_dump()
    store = FakePersistence()
    workflow, extraction, matching, evaluation = _workflow(reference, store)
    matching.result = MinMatching(
        node_matches=[
            NodeMatch(
                reference_uid="r-actor", candidate_uid=candidate.actors[0]
            ),
            NodeMatch(
                reference_uid="r-order", candidate_uid=candidate.usecases[0]
            ),
        ],
        relation_matches=[
            RelationMatch(
                reference_uid="r-association",
                candidate_uid=candidate.relations[0].uid,
            )
        ],
    )

    result = await workflow.execute(
        ReqUCD60CandidateAssessmentInput(
            reference_description="A customer places an order.",
            candidate=annotation,
        )
    )

    assert result.candidate_is_allowed is True
    assert result.completeness_rate == Decimal("0.75")
    assert result.semantic_precision == Decimal("0.75")
    assert result.semantic_f1_score == Decimal("0.75")
    assert result.redundancy_rate == Decimal("0.25")
    assert result.syntactic_error_rate == 0
    assert result.naming_understandability_score == 3
    assert result.reference_complexity == result.candidate_complexity == 6
    assert (
        result.complexity_difference == result.complexity_deviation_rate == 0
    )
    assert store.commits == 1
    assert store.rollbacks == 0
    assert store.results == [result]
    saved_reference, saved_candidate = store.diagrams
    assert saved_reference.model_dump() == reference_before
    assert saved_candidate.model_dump(exclude={"uid"}) == candidate.model_dump(
        exclude={"uid"}
    )
    assert reference.model_dump() == reference_before
    assert annotation.model_dump() == annotation_before
    assert result.reference_uid == reference.uid
    assert result.candidate_uid == saved_candidate.uid
    assert result.matching is not None
    assert result.matching.reference == saved_reference
    assert result.matching.candidate == saved_candidate
    assert result.matching.missing_nodes == ["r-payment"]
    assert result.matching.redundant_nodes == candidate.systems
    assert result.evaluation is not None
    assert (
        result.evaluation.node_evaluations
        == evaluation.result.node_evaluations
    )
    assert result.evaluation.relation_evaluations == (
        evaluation.result.relation_evaluations
    )
    assert len(extraction.prompts) == len(evaluation.prompts) == 1
    assert len(matching.prompts) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "stage", [0, 1, 2], ids=["extract", "match", "evaluate"]
)
async def test_model_failure_propagates_without_persisted_assessment(
    stage: int,
):
    store = FakePersistence()
    workflow, *models = _workflow(_reference(), store)
    error = LlmRequestError("model unavailable")
    models[stage].error = error

    with pytest.raises(LlmRequestError) as raised:
        await workflow.execute(
            ReqUCD60CandidateAssessmentInput("Description", _annotation())
        )

    assert raised.value is error
    assert store.diagrams == store.results == []
    assert store.commits == 0


@pytest.mark.anyio
@pytest.mark.parametrize("stage", ["candidate", "metrics", "commit"])
async def test_persistence_failure_leaves_no_committed_assessment(stage: str):
    store = FakePersistence(fail_on=stage)
    workflow, *_ = _workflow(_reference(), store)

    with pytest.raises(UseCaseError, match="persistence failed") as raised:
        await workflow.execute(
            ReqUCD60CandidateAssessmentInput("Description", _annotation())
        )

    assert isinstance(raised.value.original, RuntimeError)
    assert store.diagrams == store.results == []
    assert store.pending_diagrams == store.pending_results == []
    assert store.commits == 0
    assert store.rollbacks == 1


@pytest.mark.anyio
async def test_disallowed_candidate_is_saved_with_prescribed_scores():
    candidate = _annotation()
    candidate.actors = []
    candidate.usecases = []
    candidate.association_relationships = {}
    store = FakePersistence()
    workflow, _, matching, evaluation = _workflow(_reference(), store)

    result = await workflow.execute(
        ReqUCD60CandidateAssessmentInput("Description", candidate)
    )

    assert result.model_dump(
        exclude={"uid", "reference_uid", "candidate_uid"}
    ) == {
        "candidate_is_allowed": False,
        "completeness_rate": Decimal(0),
        "semantic_precision": Decimal(0),
        "semantic_f1_score": Decimal(0),
        "redundancy_rate": Decimal(1),
        "syntactic_error_rate": Decimal(1),
        "naming_understandability_score": Decimal(0),
        "reference_complexity": Decimal(6),
        "candidate_complexity": Decimal(0),
        "complexity_difference": Decimal(-6),
        "complexity_deviation_rate": Decimal(1),
        "evaluation": None,
        "matching": None,
    }
    assert store.results == [result]
    assert len(store.diagrams) == 2
    assert store.diagrams[1].actors == store.diagrams[1].usecases == []
    assert store.commits == 1
    assert matching.prompts == evaluation.prompts == []


@pytest.mark.anyio
async def test_disallowed_reference_fails_without_analysis_or_persistence():
    store = FakePersistence()
    workflow, _, matching, evaluation = _workflow(
        UseCaseDiagramPresentation(nodes=[], relations=[]), store
    )

    with pytest.raises(ReferenceNotAllowedError):
        await workflow.execute(
            ReqUCD60CandidateAssessmentInput("Description", _annotation())
        )

    assert matching.prompts == evaluation.prompts == []
    assert store.diagrams == store.results == []
    assert store.commits == 0


@pytest.mark.anyio
@pytest.mark.parametrize("different_reference", [False, True])
async def test_repeated_assessments_keep_distinct_results(
    different_reference: bool,
):
    store = FakePersistence()
    workflow, extraction, *_ = _workflow(_reference(), store)
    data = ReqUCD60CandidateAssessmentInput("Description", _annotation())

    first = await workflow.execute(data)
    if different_reference:
        extraction.result = _reference()
        extraction.result.nodes[1].name = "Submit order"
    second = await workflow.execute(data)

    assert first.uid != second.uid
    assert store.results == [first, second]
    assert store.commits == 2
    assert store.diagrams[1].model_dump(exclude={"uid"}) == (
        store.diagrams[3].model_dump(exclude={"uid"})
    )
    if different_reference:
        assert first.reference_uid != second.reference_uid
        assert store.diagrams[0].nodes[1].name == "Place order"
        assert store.diagrams[2].nodes[1].name == "Submit order"
    else:
        assert store.diagrams[0] == store.diagrams[2]
