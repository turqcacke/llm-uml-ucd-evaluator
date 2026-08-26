# LLM UML Evaluator

## Development MongoDB

Start the locally bound single-node replica set used by Diagram Assessment:

```sh
docker compose -f docker-compose-infra.yml up -d --wait mongodb
```

The default connection is
`mongodb://127.0.0.1:27017/llm_uml_evaluator?replicaSet=rs0`. Set
`MONGODB_URI` to override it; the URI must include the database name, and
credentials belong in the untracked `.env` file. The named Docker volume keeps
data through ordinary restarts. Running
`docker compose -f docker-compose-infra.yml down -v` intentionally deletes it.

Fresh databases create `use_case_diagram_presentations` and
`diagram_assessments` with unique UID indexes. Startup refuses to initialize
when the old draft collections `usecase_digarm_presentations` or
`metrics_presentations` contain data; migrating that data is separate work.

Integration tests start an isolated MongoDB replica set with Testcontainers:

```sh
PYTHONPATH=. uv run pytest tests/integration
```

## Workflow CLI

Run from the repository root with Python 3.14+ and dependencies installed
(`uv sync`). Configure `EXTRACTOR_MODEL`, `EXTRACTOR_API_KEY`, `MATCHER_MODEL`,
`MATCHER_API_KEY`, `EVALUATOR_MODEL`, and `EVALUATOR_API_KEY` in the
environment or in the root `.env` file. Matching `*_BASE_URL` and
`*_PROVIDER` settings configure each provider endpoint. Omit a provider to let
LangChain determine it from the model name.

```sh
uv run python -m src.controller.scripts.run_extractor description.txt > reference.json
uv run python -m src.controller.scripts.run_apollon_extractor apollon.json > candidate.json
uv run python -m src.controller.scripts.run_mathcer reference.json candidate.json > matching.json
uv run python -m src.controller.scripts.run_description_reference_assessment description.txt candidate.json
uv run python -m src.controller.scripts.run_apollon_reference_assessment reference.json candidate.json
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
- `scripts_out/run_description_reference_assessment/`
- `scripts_out/run_apollon_reference_assessment/`

Directories are created automatically, and repeated runs keep earlier
results. Override the output directory with `--results-path /path/to/results`.

Workflow providers live directly in `src/controller/di/` and use the existing
Dishka chat model registrations. Workflow modules live directly under
`src/services/`; LangChain, Apollon conversion, and MongoDB metadata live under
`src/infrastructure/`. Shared outbound contracts live in `src/services/ports/`;
feature-local contracts stay with their owning workflow module.

Diagram Assessment commands persist both diagrams and each distinct result in
one MongoDB transaction. The returned result `uid` identifies the stored
assessment.
