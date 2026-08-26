import importlib
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from src.model.domain import MetricsWithEvaluation


class FakeUseCase:
    def __init__(self) -> None:
        self.calls: list[Any] = []

    async def execute(self, data: Any) -> MetricsWithEvaluation:
        self.calls.append(data)
        return MetricsWithEvaluation(
            candidate_is_allowed=False,
            redundancy_rate=Decimal(1),
            completeness_rate=Decimal(0),
            semantic_precision=Decimal(0),
            semantic_f1_score=Decimal(0),
            syntactic_error_rate=Decimal(1),
            naming_understandability_score=Decimal(0),
            reference_complexity=Decimal(0),
            candidate_complexity=Decimal(0),
            complexity_difference=Decimal(0),
            complexity_deviation_rate=Decimal(0),
            evaluation=None,
        )


class FakeContainer:
    def __init__(self, use_case: FakeUseCase) -> None:
        self.use_case = use_case

    def __enter__(self) -> "FakeContainer":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def get(self, dependency: type[object]) -> FakeUseCase:
        return self.use_case


@pytest.mark.parametrize(
    ("script", "reference_content"),
    [
        (
            "run_description_reference_assessment",
            "A customer places an order.",
        ),
        (
            "run_apollon_reference_assessment",
            '{"model": {"elements": {}, "relationships": {}}}',
        ),
    ],
)
def test_assessment_cli_reads_inputs_and_saves_result(
    script: str,
    reference_content: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(f"src.controller.scripts.{script}")
    reference = tmp_path / "reference input"
    candidate = tmp_path / "candidate.json"
    results_path = tmp_path / "results"
    reference.write_text(reference_content, "utf-8")
    candidate.write_text(
        '{"model": {"elements": {}, "relationships": {}}}', "utf-8"
    )
    use_case = FakeUseCase()
    saved: list[tuple[str, Path]] = []
    monkeypatch.setattr(module, "container", FakeContainer(use_case))
    monkeypatch.setattr(module, "save_result", lambda value, path: saved.append((value, path)))

    assert module.main(
        [str(reference), str(candidate), "--results-path", str(results_path)]
    ) == 0

    assert len(use_case.calls) == 1
    [data] = use_case.calls
    if script == "run_description_reference_assessment":
        assert data.reference_description == reference_content
    else:
        assert data.reference.model.elements == {}
    assert data.candidate.model.elements == {}
    assert len(saved) == 1
    assert saved[0][1] == results_path


@pytest.mark.parametrize(
    "script",
    [
        "run_description_reference_assessment",
        "run_apollon_reference_assessment",
    ],
)
def test_assessment_cli_reports_unreadable_input(
    script: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = importlib.import_module(f"src.controller.scripts.{script}")
    use_case = FakeUseCase()
    monkeypatch.setattr(module, "container", FakeContainer(use_case))

    assert module.main([str(tmp_path / "missing"), "candidate.json"]) == 1
    assert "error:" in capsys.readouterr().err
    assert use_case.calls == []
