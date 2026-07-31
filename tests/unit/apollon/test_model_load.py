import json
from pathlib import Path
from typing import cast

import pytest

from src.config import BASE_URL
from src.model.apollon import ApollonJson

EXERCISE_URLS = [
    BASE_URL / f"exercises/exercise_{n}/exercise_{n}.json"
    for n in range(1, 23)
]


@pytest.mark.parametrize("json_path", EXERCISE_URLS)
def test_json_parse(json_path: Path) -> None:
    with open(json_path, "r", encoding="utf-8") as file:
        json_file = cast(dict[str, object], json.load(file))
        _ = ApollonJson.model_validate(json_file)
