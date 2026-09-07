import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.infrastructure.requcd60.converter import ReqUCD60ToDomainConverter
from src.model.domain import NodeType
from src.model.requcd60.result import ReqUCD60Result
from src.services.exceptions import ConversionError
from src.services.extractor.requcd60 import (
    ReqUCD60Extractor,
    ReqUCD60ExtractorInput,
)

DATASET = Path(__file__).resolve().parents[4] / "datasets/60_ideal_UCD"


@pytest.mark.anyio
async def test_extractor_preserves_typed_labels_and_relationship_directions():
    annotation = ReqUCD60Result.model_validate(
        {
            "actors": ["Main System", " Payment API "],
            "usecases": ["Main System", " Pay ", "Pay"],
            "association_relationships": {
                "Main System": ["Main System"],
                " Payment API ": ["Pay"],
            },
            "inclusion_relationships": {"Main System": [" Pay "]},
            "extension_relationships": {"Main System": ["Pay"]},
            "generalization_relationships_for_usecases": {
                "Main System": ["Pay"]
            },
            "generalization_relationships_for_actors": {
                "Main System": [" Payment API "]
            },
        }
    )
    before = annotation.model_dump()
    extractor = ReqUCD60Extractor(ReqUCD60ToDomainConverter())

    result = await extractor.execute(ReqUCD60ExtractorInput(annotation))
    repeated = await extractor.execute(ReqUCD60ExtractorInput(annotation))

    assert result.model_dump(exclude={"uid"}) == repeated.model_dump(
        exclude={"uid"}
    )
    assert annotation.model_dump() == before
    assert [(node.name, node.type) for node in result.nodes] == [
        ("Main System", NodeType.SYSTEM_BOUNDARY),
        ("Main System", NodeType.ACTOR),
        (" Payment API ", NodeType.ACTOR),
        ("Main System", NodeType.USECASE),
        (" Pay ", NodeType.USECASE),
        ("Pay", NodeType.USECASE),
    ]
    system = result.system_boundaries[0]
    assert all(
        node.parent == (system if node.type == NodeType.USECASE else None)
        for node in result.nodes
    )
    identifiers = [node.uid for node in result.nodes] + [
        relation.uid for relation in result.relations
    ]
    assert len(set(identifiers)) == len(identifiers)
    nodes = {node.uid: (node.name, node.type) for node in result.nodes}
    assert [
        (nodes[relation.source], nodes[relation.target], relation.type)
        for relation in result.relations
    ] == [
        (("Main System", "actor"), ("Main System", "usecase"), "association"),
        ((" Payment API ", "actor"), ("Pay", "usecase"), "association"),
        (("Main System", "usecase"), (" Pay ", "usecase"), "include"),
        (("Pay", "usecase"), ("Main System", "usecase"), "extend"),
        (("Pay", "usecase"), ("Main System", "usecase"), "generalization"),
        (
            (" Payment API ", "actor"),
            ("Main System", "actor"),
            "generalization",
        ),
    ]


@pytest.mark.anyio
async def test_example_59_relationships():
    annotation = ReqUCD60Result.model_validate_json(
        (DATASET / "51-60/59_result.json").read_text()
    )
    result = await ReqUCD60Extractor(ReqUCD60ToDomainConverter()).execute(
        ReqUCD60ExtractorInput(annotation)
    )

    names = {node.uid: node.name for node in result.nodes}
    assert [
        (names[relation.source], names[relation.target], relation.type)
        for relation in result.relations
    ] == [
        ("Diver", "Develop Diving Plan", "association"),
        ("Diver", "Keep Diving Log", "association"),
        ("Diver", "Record Observation Notes", "association"),
        ("Diver", "Mark Key Event Points", "association"),
        ("Diving Master", "Develop Diving Plan", "association"),
        ("Diving Master", "Keep Diving Log", "association"),
        ("Diving Master", "Record Observation Notes", "association"),
        ("Diving Master", "Mark Key Event Points", "association"),
        ("Diving Master", "Review Diving Plan", "association"),
        ("Diving Master", "Generate Diving Report Summary", "association"),
        ("Diving Master", "Mark Potential Risk Events", "association"),
        ("Diving Master", "Receive Signal From Divers", "association"),
        ("Diving Master", "Initiate Emergency Response", "association"),
        ("Surface Support Personnel", "Monitor Diver's Status", "association"),
        (
            "Surface Support Personnel",
            "Manage Inventory Of Diving Gas Cylinders",
            "association",
        ),
        (
            "Surface Support Personnel",
            "Coordinate Depressurization Procedures",
            "association",
        ),
        ("Keep Diving Log", "Record Observation Notes", "include"),
        ("Keep Diving Log", "Mark Key Event Points", "include"),
        (
            "Initiate Emergency Response",
            "Receive Signal From Divers",
            "extend",
        ),
        ("Diving Master", "Diver", "generalization"),
    ]


@pytest.mark.anyio
async def test_all_60_annotations_convert_reproducibly_without_mutation():
    paths = list(DATASET.glob("*/*_result.json"))
    assert len(paths) == 60
    extractor = ReqUCD60Extractor(ReqUCD60ToDomainConverter())
    for path in paths:
        original = json.loads(path.read_text())
        annotation = ReqUCD60Result.model_validate(original)
        result = await extractor.execute(ReqUCD60ExtractorInput(annotation))
        repeated = await extractor.execute(ReqUCD60ExtractorInput(annotation))

        assert annotation.model_dump() == original, path
        assert result.model_dump(exclude={"uid"}) == repeated.model_dump(
            exclude={"uid"}
        ), path
        assert [
            node.name for node in result.nodes if node.type == NodeType.ACTOR
        ] == original["actors"], path
        assert [
            node.name for node in result.nodes if node.type == NodeType.USECASE
        ] == original["usecases"], path
        assert len(result.system_boundaries) == 1, path
        assert all(
            node.parent
            == (
                result.system_boundaries[0]
                if node.type == NodeType.USECASE
                else None
            )
            for node in result.nodes
        ), path
        assert len(result.relations) == sum(
            len(values)
            for field, mapping in original.items()
            if field not in {"actors", "usecases"}
            for values in mapping.values()
        ), path
        identifiers = [node.uid for node in result.nodes] + [
            relation.uid for relation in result.relations
        ]
        assert len(set(identifiers)) == len(identifiers), path


@pytest.mark.anyio
@pytest.mark.parametrize("actor", ["diver", "Develop Diving Plan"])
async def test_undeclared_actor_is_not_normalized_or_resolved_as_usecase(
    actor: str,
):
    annotation = ReqUCD60Result.model_validate_json(
        (DATASET / "51-60/59_result.json").read_text()
    )
    annotation.association_relationships = {actor: ["Keep Diving Log"]}

    with pytest.raises(ConversionError):
        await ReqUCD60Extractor(ReqUCD60ToDomainConverter()).execute(
            ReqUCD60ExtractorInput(annotation)
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actors", [7]),
        ("association_relationships", {"Diver": "Keep Diving Log"}),
    ],
)
def test_annotation_uses_pydantic_field_validation(field: str, value: object):
    annotation = json.loads((DATASET / "51-60/59_result.json").read_text())
    annotation[field] = value

    with pytest.raises(ValidationError):
        ReqUCD60Result.model_validate(annotation)
