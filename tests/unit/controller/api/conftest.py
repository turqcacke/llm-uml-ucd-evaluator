import pytest


@pytest.fixture(autouse=True)
def graphviz_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("graphviz.version", lambda: (14, 0, 0))
