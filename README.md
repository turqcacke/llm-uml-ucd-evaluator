# LLM UML Evaluator

## Pipeline CLI

Run from the repository root with Python 3.14+ and dependencies installed
(`uv sync`). Configure `EXTRACTOR_MODEL`, `EXTRACTOR_API_KEY`, `MATCHER_MODEL`,
and `MATCHER_API_KEY` in the environment or in the root `.env` file. The
existing settings require all four values for pipeline execution.

```sh
uv run python -m src.controller.scripts.run_extractor description.txt > reference.json
uv run python -m src.controller.scripts.run_apollon_extractor apollon.json > candidate.json
uv run python -m src.controller.scripts.run_mathcer reference.json candidate.json > matching.json
```

All paths are positional arguments. Text is read as UTF-8. Matcher inputs
must be serialized `UseCaseDiagramPresentation` documents; Apollon input
must match `ApollonJson`. Each command writes its result as JSON to stdout.
Errors go to stderr with a nonzero exit code. Use `--help` for usage without
configuring or calling an LLM.

Each command also saves a UTF-8 JSON file with a unique UUID filename. Its
`RESULTS_PATH` constant defaults to `BASE_URL / "scripts_out" / <script_name>`:

- `scripts_out/run_extractor/`
- `scripts_out/run_apollon_extractor/`
- `scripts_out/run_mathcer/`

Directories are created automatically, and repeated runs keep earlier
results. Override the output directory with `--results-path /path/to/results`.

Pipeline providers live in `src/controller/di/pipelines/` and use the existing
Dishka chat model registrations. Prompt constants are currently empty;
prompt design and evaluation quality are outside the CLI implementation.
