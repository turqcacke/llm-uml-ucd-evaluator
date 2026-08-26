import pytest

from src.model.apollon import ApollonJson
from src.services.converters.apollon_to_domain import (
    ApollonToDomainConverter,
)
from src.services.exceptions.converters import ConversionError


def _apollon_json() -> ApollonJson:
    node_types = (
        "UseCaseActor",
        "UseCaseSystem",
        "UseCase",
        "UseCaseExternalSystem",
        "ColorLegend",
        "InvalidNode",
    )
    relation_types = (
        "UseCaseAssociation",
        "UseCaseExtend",
        "UseCaseInclude",
        "UseCaseGeneralization",
        "UseCaseSupport",
    )
    return ApollonJson.model_validate(
        {
            "model": {
                "elements": {
                    str(index): {
                        "id": str(index),
                        "name": f"Node {index}",
                        "type": node_type,
                        "owner": "2" if index == 3 else None,
                        "bounds": {"x": 0, "y": 0},
                    }
                    for index, node_type in enumerate(node_types, start=1)
                },
                "relationships": {
                    str(index): {
                        "id": str(index),
                        "name": "",
                        "type": relation_type,
                        "bounds": {"x": 0, "y": 0},
                        "source": {"direction": "Right", "element": "1"},
                        "target": {"direction": "Left", "element": "3"},
                    }
                    for index, relation_type in enumerate(
                        relation_types, start=7
                    )
                },
            }
        }
    )


def test_apollon_diagram_is_converted_to_domain_presentation() -> None:
    result = ApollonToDomainConverter().convert(_apollon_json())

    assert result.model_dump(exclude={"uid"}) == {
        "nodes": [
            {"uid": "1", "name": "Node 1", "parent": None, "type": "actor"},
            {"uid": "2", "name": "Node 2", "parent": None, "type": "system"},
            {"uid": "3", "name": "Node 3", "parent": "2", "type": "usecase"},
            {
                "uid": "4",
                "name": "Node 4",
                "parent": None,
                "type": "external_system",
            },
            {"uid": "5", "name": "Node 5", "parent": None, "type": "note"},
            {"uid": "6", "name": "Node 6", "parent": None, "type": "other"},
        ],
        "relations": [
            {"uid": "7", "source": "1", "target": "3", "type": "association"},
            {"uid": "8", "source": "1", "target": "3", "type": "extend"},
            {"uid": "9", "source": "1", "target": "3", "type": "include"},
            {
                "uid": "10",
                "source": "1",
                "target": "3",
                "type": "generalization",
            },
            {
                "uid": "11",
                "source": "1",
                "target": "3",
                "type": "association",
            },
        ],
        "actors": ["1"],
        "usecases": ["3"],
        "notes": ["5"],
        "others": ["6"],
        "systems": ["2"],
        "external_systems": ["4"],
    }


def test_apollon_diagram_with_duplicate_node_ids_is_rejected() -> None:
    source = _apollon_json()
    source.model.elements["2"].id = "1"

    with pytest.raises(ConversionError, match="Node UIDs must be unique"):
        ApollonToDomainConverter().convert(source)
