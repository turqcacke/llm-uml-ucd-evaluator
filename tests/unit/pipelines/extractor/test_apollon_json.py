import pytest

from src.model.apollon import ApollonJson
from src.services.converters.apollon_to_domain import (
    ApollonToDomainConverter,
)
from src.services.exceptions.converters import ConversionError
from src.services.pipelines.extractor.apollon_json import (
    ApollonJsonExtractor,
    ApollonJsonExtractorInput,
)


def _source(*, duplicate_ids: bool = False) -> ApollonJson:
    return ApollonJson.model_validate(
        {
            "model": {
                "elements": {
                    "actor": {
                        "id": "actor",
                        "name": "Customer",
                        "type": "UseCaseActor",
                        "owner": None,
                        "bounds": {"x": 0, "y": 0},
                    },
                    "usecase": {
                        "id": "actor" if duplicate_ids else "usecase",
                        "name": "Place order",
                        "type": "UseCase",
                        "owner": None,
                        "bounds": {"x": 0, "y": 0},
                    },
                },
                "relationships": {
                    "relation": {
                        "id": "relation",
                        "name": "",
                        "type": "UseCaseAssociation",
                        "bounds": {"x": 0, "y": 0},
                        "source": {
                            "direction": "Right",
                            "element": "actor",
                        },
                        "target": {
                            "direction": "Left",
                            "element": "usecase",
                        },
                    }
                },
            }
        }
    )


@pytest.mark.anyio
async def test_json_extractor_returns_domain_presentation() -> None:
    extractor = ApollonJsonExtractor(ApollonToDomainConverter())

    result = await extractor.execute(ApollonJsonExtractorInput(_source()))

    assert result.model_dump(exclude={"id"}) == {
        "nodes": [
            {
                "id": "actor",
                "name": "Customer",
                "parent": None,
                "type": "actor",
            },
            {
                "id": "usecase",
                "name": "Place order",
                "parent": None,
                "type": "usecase",
            },
        ],
        "relations": [
            {
                "id": "relation",
                "source": "actor",
                "target": "usecase",
                "type": "association",
            }
        ],
        "actors": ["actor"],
        "usecases": ["usecase"],
        "notes": [],
        "others": [],
        "systems": [],
        "external_systems": [],
    }


@pytest.mark.anyio
async def test_json_extractor_rejects_invalid_diagram() -> None:
    extractor = ApollonJsonExtractor(ApollonToDomainConverter())

    with pytest.raises(ConversionError, match="Node IDs must be unique"):
        await extractor.execute(
            ApollonJsonExtractorInput(_source(duplicate_ids=True))
        )
