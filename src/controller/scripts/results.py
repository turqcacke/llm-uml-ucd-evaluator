from pathlib import Path
from uuid import uuid4


def save_result(output: str, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}.json"
    with path.open("x", encoding="utf-8") as file:
        file.write(output)
        file.write("\n")
