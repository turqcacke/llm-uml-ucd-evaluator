import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from src.config import get_settings
from src.model.domain.evaluation import MatchingResult
from src.services.llm_client import chat_model
from src.services.shared import prompts


@pytest.fixture
def llm_calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    calls: list[tuple[str, list[BaseMessage]]] = []

    class FakeLanguageModel:
        def __init__(self, model: str):
            self.model = model
            self.response_type: type[BaseModel] = BaseModel

        def with_structured_output(self, response_type: type[BaseModel]):
            self.response_type = response_type
            return self

        async def ainvoke(self, messages: list[BaseMessage]) -> BaseModel:
            calls.append((self.model, messages))
            if self.response_type is MatchingResult:
                return MatchingResult(
                    node_matches=[],
                    missing_nodes=["missing"],
                    redundant_nodes=[],
                    missing_links=[],
                    redundant_links=[],
                )
            return self.response_type.model_validate(
                {"id": "extracted", "nodes": [], "relations": []}
            )

    def init_model(*, model: str, **kwargs: object):
        return FakeLanguageModel(model)

    monkeypatch.setattr(chat_model, "init_chat_model", init_model)
    monkeypatch.setenv("EXTRACTOR_MODEL", "test-extractor")
    monkeypatch.setenv("EXTRACTOR_API_KEY", "test-key")
    monkeypatch.setenv("MATCHER_MODEL", "test-matcher")
    monkeypatch.setenv("MATCHER_API_KEY", "test-key")
    monkeypatch.setattr(prompts, "EXTRATOR_FROM_DESCRIPTION", "Extract prose")
    monkeypatch.setattr(
        prompts, "EXTRACTOR_FROM_APOLLON_MODEL", "Extract JSON"
    )
    get_settings.cache_clear()
    for script in ("run_extractor", "run_mathcer", "run_apollon_extractor"):
        module = importlib.import_module(f"src.controller.scripts.{script}")
        monkeypatch.setattr(
            module,
            "RESULTS_PATH",
            tmp_path / "results" / script,
        )
    yield calls
    get_settings.cache_clear()


def test_extract_prose_from_cli(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    llm_calls: list[tuple[str, list[BaseMessage]]],
) -> None:
    from src.controller.scripts.run_extractor import main

    description = tmp_path / "description with spaces.txt"
    description.write_text("A user logs in.\nAn admin manages users.", "utf-8")

    assert main([str(description)]) == 0

    output = capsys.readouterr()
    assert json.loads(output.out)["id"] == "extracted"
    assert output.err == ""
    assert len(llm_calls) == 1
    model, messages = llm_calls[0]
    assert model == "test-extractor"
    assert "Extract prose" in messages[0].content
    assert messages[1].content == (
        "\nA user logs in.\nAn admin manages users.\n"
    )


def test_match_reference_and_candidate_from_cli(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    llm_calls: list[tuple[str, list[BaseMessage]]],
) -> None:
    from src.controller.scripts.run_mathcer import main

    reference = tmp_path / "reference.json"
    candidate = tmp_path / "candidate.json"
    reference.write_text(
        '{"id": "reference-id", "nodes": [], "relations": []}', "utf-8"
    )
    candidate.write_text(
        '{"id": "candidate-id", "nodes": [], "relations": []}', "utf-8"
    )

    assert main([str(reference), str(candidate)]) == 0

    output = capsys.readouterr()
    assert json.loads(output.out) == {
        "node_matches": [],
        "missing_nodes": ["missing"],
        "redundant_nodes": [],
        "missing_links": [],
        "redundant_links": [],
    }
    assert output.err == ""
    assert len(llm_calls) == 1
    model, messages = llm_calls[0]
    assert model == "test-matcher"
    content = messages[1].content
    assert isinstance(content, str)
    reference_prompt, candidate_prompt = content.split("Candidate:", 1)
    assert '"id":"reference-id"' in reference_prompt
    assert '"id":"candidate-id"' in candidate_prompt


def test_extract_apollon_from_cli(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    llm_calls: list[tuple[str, list[BaseMessage]]],
) -> None:
    from src.controller.scripts.run_apollon_extractor import main

    apollon = tmp_path / "apollon.json"
    apollon.write_text('{"model": {"elements": {}}}', "utf-8")

    assert main([str(apollon)]) == 0

    output = capsys.readouterr()
    assert json.loads(output.out)["id"] == "extracted"
    assert output.err == ""
    assert len(llm_calls) == 1
    model, messages = llm_calls[0]
    assert model == "test-extractor"
    assert "Extract JSON" in messages[0].content
    content = messages[1].content
    assert isinstance(content, str)
    assert json.loads(content) == {"model": {"elements": {}}}


@pytest.mark.parametrize(
    "script", ["run_extractor", "run_mathcer", "run_apollon_extractor"]
)
@pytest.mark.parametrize("custom_path", [False, True])
def test_cli_saves_each_result_without_overwriting(
    script: str,
    custom_path: bool,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    llm_calls: list[tuple[str, list[BaseMessage]]],
) -> None:
    module = importlib.import_module(f"src.controller.scripts.{script}")
    source = tmp_path / "input.json"
    source.write_text(
        '{"model": {"elements": {}}, "nodes": [], "relations": []}',
        "utf-8",
    )
    args = [str(source)] * (2 if script == "run_mathcer" else 1)
    directory = module.RESULTS_PATH
    if custom_path:
        directory = tmp_path / "custom results" / script
        args.extend(["--results-path", str(directory)])

    for _ in range(2):
        assert module.main(args) == 0
        output = capsys.readouterr()
        assert output.err == ""

    files = list(directory.glob("*.json"))
    assert len(files) == 2
    for path in files:
        assert json.loads(path.read_text("utf-8")) == json.loads(output.out)


@pytest.mark.parametrize(
    "script", ["run_extractor", "run_mathcer", "run_apollon_extractor"]
)
def test_output_directory_failure_is_cli_error(
    script: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    llm_calls: list[tuple[str, list[BaseMessage]]],
) -> None:
    module = importlib.import_module(f"src.controller.scripts.{script}")
    source = tmp_path / "input.json"
    source.write_text(
        '{"model": {"elements": {}}, "nodes": [], "relations": []}',
        "utf-8",
    )
    directory = tmp_path / "occupied"
    directory.write_text("existing content", "utf-8")
    args = [str(source)] * (2 if script == "run_mathcer" else 1)
    args.extend(["--results-path", str(directory)])

    with pytest.raises(SystemExit) as exc:
        module.main(args)

    assert exc.value.code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "error:" in output.err
    assert "Traceback" not in output.err
    assert directory.read_text("utf-8") == "existing content"


@pytest.mark.parametrize(
    "script", ["run_extractor", "run_mathcer", "run_apollon_extractor"]
)
@pytest.mark.parametrize("problem", ["missing", "directory", "encoding"])
def test_unreadable_input_fails_before_llm_request(
    script: str,
    problem: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    llm_calls: list[tuple[str, list[BaseMessage]]],
) -> None:
    main = importlib.import_module(f"src.controller.scripts.{script}").main
    path = tmp_path / "input"
    if problem == "directory":
        path.mkdir()
    elif problem == "encoding":
        path.write_bytes(b"\xff")
    args = [str(path)] * (2 if script == "run_mathcer" else 1)

    with pytest.raises(SystemExit) as exc:
        main(args)

    assert exc.value.code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "error:" in output.err
    assert llm_calls == []


@pytest.mark.parametrize("script", ["run_mathcer", "run_apollon_extractor"])
@pytest.mark.parametrize("content", ["not json", "{}"])
def test_invalid_json_fails_before_llm_request(
    script: str,
    content: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    llm_calls: list[tuple[str, list[BaseMessage]]],
) -> None:
    main = importlib.import_module(f"src.controller.scripts.{script}").main
    invalid = tmp_path / "invalid.json"
    invalid.write_text(content, "utf-8")
    args = [str(invalid)]
    if script == "run_mathcer":
        reference = tmp_path / "reference.json"
        reference.write_text('{"nodes": [], "relations": []}', "utf-8")
        args.insert(0, str(reference))

    with pytest.raises(SystemExit) as exc:
        main(args)

    assert exc.value.code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "error:" in output.err
    assert llm_calls == []


@pytest.mark.parametrize(
    "script", ["run_extractor", "run_mathcer", "run_apollon_extractor"]
)
def test_model_configuration_failure_is_cli_error(
    script: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    llm_calls: list[tuple[str, list[BaseMessage]]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_configuration(**kwargs: object):
        raise RuntimeError("Model unavailable")

    monkeypatch.setattr(chat_model, "init_chat_model", fail_configuration)
    main = importlib.import_module(f"src.controller.scripts.{script}").main
    path = tmp_path / "input"
    path.write_text(
        '{"model": {"elements": {}}, "nodes": [], "relations": []}',
        "utf-8",
    )
    args = [str(path)] * (2 if script == "run_mathcer" else 1)

    with pytest.raises(SystemExit) as exc:
        main(args)

    assert exc.value.code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "Model unavailable" in output.err
    assert "Traceback" not in output.err
    assert llm_calls == []


@pytest.mark.parametrize(
    "script", ["run_extractor", "run_mathcer", "run_apollon_extractor"]
)
@pytest.mark.parametrize("args, code", [(["--help"], 0), ([], 2)])
def test_module_cli_usage_without_llm_configuration(
    script: str, args: list[str], code: int
) -> None:
    env = dict(os.environ)
    for name in (
        "EXTRACTOR_MODEL",
        "EXTRACTOR_API_KEY",
        "MATCHER_MODEL",
        "MATCHER_API_KEY",
    ):
        env[name] = ""
    result = subprocess.run(
        [sys.executable, "-m", f"src.controller.scripts.{script}", *args],
        cwd=Path(__file__).resolve().parents[3],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == code
    assert "usage:" in (result.stdout if code == 0 else result.stderr)
    assert "Traceback" not in result.stderr
