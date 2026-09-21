# LLM UML Evaluator

Evaluate UML use case diagrams using extraction, semantic matching, and
syntactic and pragmatic evaluation.

## Contents

- [Setup](#setup)
- [HTTP API](#http-api)
- [Environment files](#environment-files)
- [Demo UI](#demo-ui)
- [Development MongoDB](#development-mongodb)
- [Workflow CLI](#workflow-cli)
- [Evaluation](#evaluation)
- [JupyterLab](#jupyterlab)
- [Tests and linting](#tests-and-linting)
- [Datasets](datasets/README.md)

## Setup

Run commands from the repository root. Install the prerequisites:

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [GNU Make](https://www.gnu.org/software/make/#download)
- [Docker with Docker Compose](https://docs.docker.com/get-started/get-docker/)
  for local MongoDB

Start the Docker daemon before running `make up-infra`.

Install the Graphviz system package for the current operating system:

| Platform | Command |
|---|---|
| macOS (Homebrew) | `brew install graphviz` |
| Windows (Windows Package Manager) | `winget install graphviz` |
| Ubuntu / Debian | `sudo apt install graphviz` |
| Fedora / Rocky Linux / RHEL / CentOS | `sudo dnf install graphviz` |

API startup requires `dot -V` to succeed.

```sh
uv sync
cp .env.example .env
```

Choose additional dependency groups as needed:

| Command | Installed dependencies |
|---|---|
| `uv sync` | Application dependencies and the default `dev` group (Testcontainers for integration tests). |
| `uv sync --group eval` | Also installs JupyterLab, pandas, and Matplotlib for analysis notebooks. |
| `uv sync --group tools` | Also installs Ruff and ty for linting and type checks. |
| `uv sync --all-groups` | Installs all groups: `dev`, `eval`, and `tools`. |

Groups can be combined: `uv sync --group eval --group tools`.

## HTTP API

Set a nonempty `API_SECRET` in
`.env`, configure all three models, then start the API with auto-reload:

```sh
make up-infra
make run-api
```

Open <http://127.0.0.1:8000/docs> and authorize with `API_SECRET` as
`X-API-Key`. Development is the default environment.
`GRAPHVIZ_CONCURRENCY_LIMIT` defaults to `4` concurrent layout jobs.
CLI commands do not require `API_SECRET`.

## Environment files

| File | Purpose |
|---|---|
| [`.env.example`](.env.example) | Backend configuration template with local MongoDB settings and placeholder model credentials. Copy it to `.env` and replace the placeholders. |
| `.env` | Local configuration for the HTTP API, workflow CLI, and evaluation collectors. Loaded automatically by backend settings; JupyterLab loads it through `--env-file .env`. |

The `.env` file is ignored by Git. The `.env.example` file contains placeholders
and serves as the shared configuration template.

### Backend settings

The complete set of application settings is defined in
[`src/config.py`](src/config.py) and included in `.env.example`.

| Variable | Purpose / default |
|---|---|
| `API_SECRET` | Nonempty access key required by the HTTP API; sent as `X-API-Key`. Not required by CLI commands. |
| `MONGODB_URI` | Database connection, including the database name; defaults to the local replica set described below. |
| `ENVIRONMENT` | API environment: `DEV` (default) or `PROD`. |
| `LOG_LEVEL` | Minimum log level, case-insensitive: `trace`, `debug`, `info`, `success`, `warning`, `error`, or `critical`; default `info`. Logs are written to stderr. |
| `GRAPHVIZ_CONCURRENCY_LIMIT` | Maximum concurrent API layout jobs; positive integer, default `4`. |

Configure model settings in the root `.env` or the process environment:

| Component | Model and credentials | Used by |
|---|---|---|
| Extractor | `EXTRACTOR_MODEL`, `EXTRACTOR_API_KEY` | Text extraction, description assessment, gold standard evaluation |
| Matcher | `MATCHER_MODEL`, `MATCHER_API_KEY` | Matching, Diagram Assessment, matching and gold standard evaluation |
| Evaluator | `EVALUATOR_MODEL`, `EVALUATOR_API_KEY` | Diagram Assessment, pragmatic and gold standard evaluation |

Each component has four settings:

| Variables | Purpose / default |
|---|---|
| `EXTRACTOR_MODEL`, `MATCHER_MODEL`, `EVALUATOR_MODEL` | Model identifiers; required, with no application default. |
| `EXTRACTOR_API_KEY`, `MATCHER_API_KEY`, `EVALUATOR_API_KEY` | Provider credentials; required, with no application default. |
| `EXTRACTOR_BASE_URL`, `MATCHER_BASE_URL`, `EVALUATOR_BASE_URL` | Optional provider endpoint overrides; omitted by default. The template uses a local endpoint at `http://127.0.0.1:8317/v1`; replace it or remove these entries to use provider defaults. |
| `EXTRACTOR_PROVIDER`, `MATCHER_PROVIDER`, `EVALUATOR_PROVIDER` | Optional provider identifiers; omitted by default so LangChain infers the provider from the model name. The template explicitly selects `openai`. |

> [!NOTE]
> Currently supported values for `EXTRACTOR_PROVIDER`, `MATCHER_PROVIDER`,
> and `EVALUATOR_PROVIDER` are `openai` and `openrouter`.

Apollon extraction is deterministic and requires no LLM configuration.

## Demo UI

> [!WARNING]
> The Demo UI was generated by an LLM for quick demonstrations. It is not a
> production-ready frontend.

The [`demo/`](demo/) directory contains a minimal Vite-based interface with two
Apollon editors. It can load an optional Candidate Diagram and Reference
Diagram, run description-to-Apollon or Apollon-to-Apollon assessments, display
live assessment progress, and show metrics and element-level diagnostics.

Start the API from the repository root as described in [HTTP API](#http-api).
Then run the frontend from the `demo` directory:

```sh
cd demo
cp .env.example .env
# Set VITE_API_KEY in .env to the same value as the backend API_SECRET.
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. The development server proxies `/api` requests to
<http://127.0.0.1:8000>, so no additional CORS configuration is required.

## Development MongoDB

```sh
make up-infra
```

Starts the locally bound single-node replica set and waits until it is ready.

| Command | Effect |
|---|---|
| `make up-infra` | Start MongoDB and wait for readiness. |
| `make down-infra` | Stop and remove containers; preserve stored data. |
| `make down-infra V=1` | Stop containers and delete the MongoDB data volume. |

The default URI is
`mongodb://127.0.0.1:27017/llm_uml_evaluator?replicaSet=rs0`.
Override it with `MONGODB_URI` in `.env`; include the database name.
Fresh databases create `use_case_diagram_presentations` and
`diagram_assessments` with unique UID indexes. Startup rejects populated
legacy collections `usecase_digarm_presentations` and `metrics_presentations`;
these require a separate migration.

## Workflow CLI

```sh
uv run python -m src.controller.scripts.run_description_extractor description.txt
uv run python -m src.controller.scripts.run_apollon_extractor apollon.json
uv run python -m src.controller.scripts.run_mathcer reference.json candidate.json
uv run python -m src.controller.scripts.run_description_reference_assessment description.txt candidate_apollon.json
uv run python -m src.controller.scripts.run_apollon_to_apollon_assessment reference_apollon.json candidate_apollon.json
```

| Argument | Meaning |
|---|---|
| Positional paths | Input files in the order shown; text is read as UTF-8. Matcher inputs are serialized `UseCaseDiagramPresentation` documents; Apollon inputs use `ApollonJson`. |
| `--description PATH` | Optional Context Description for the matcher and Apollon-to-Apollon assessment. |
| `--results-path PATH` | Output directory; defaults to `scripts_out/<script_name>/`. |
| `--help` | Show usage without configuring or calling an LLM. |

Results are saved as UTF-8 JSON files with unique UUID filenames and logged.
Directories are created automatically; repeated runs preserve earlier files.
Errors return a nonzero exit code. Diagram Assessment commands require MongoDB
and persist both diagrams and each distinct result in one transaction; the
returned `uid` identifies the stored assessment.

## Evaluation

> [!NOTE]
> A [MongoDB backup with experiment data](https://drive.google.com/drive/u/2/folders/1rUOZo8sPrs6Rjy2RchAhc_r_7UVPp0M-)
> is available for analyzing existing results without rerunning the experiments.

Start MongoDB with `make up-infra` and configure the models listed below.
Each example starts a new experiment; choose a unique name for each run.

### Common arguments

| Argument | Meaning / default |
|---|---|
| `--experiment-name NAME` | Letters, digits, underscores, and hyphens only. Required for mutation evaluations; defaults to `gold_standard` for gold standard evaluation. Completed names cannot be reused. |
| `--resume` | Resume with the original name, repetition count or size, and unchanged dataset contents and ordering. |
| `--batch-size N` | Concurrent samples per batch; positive integer, default `3`. |
| `--requests-per-minute N` | Maximum sample starts per minute; positive integer, default `10`. |
| `--help` | Show command usage. |

### Matching Mutation Evaluation

Requires the matcher. Compares semantic matches across
[60 controlled cases](datasets/10_match_mutations/README.md).

```sh
uv run python -m eval.matching.collect_observations \
  --experiment-name matching_run_1 --repetitions 3
```

| Argument | Meaning / default |
|---|---|
| `--repetitions {1,2,3}` | Repetitions per case; default `3`. |

Observations: `matching_eval` collection.
Checkpoint: `eval_out/<experiment-name>_matching.json`.

### Pragmatic Naming Mutation Evaluation

Requires the evaluator. Compares Naming Understandability Scores across
[40 controlled cases](datasets/10_pragmatic_mutations/README.md).

```sh
uv run python -m eval.pragmatic.collect_observations \
  --experiment-name pragmatic_run_1 --repetitions 3 --with-context 1
```

| Argument | Meaning / default |
|---|---|
| `--repetitions {1,2,3}` | Repetitions per case; default `3`. |
| `--with-context {0,1}` | Include the Context Description (`1`, default for new runs) or omit it (`0`). Both modes use full-context expectations. |

Observations: `pragmatic_naming_eval` collection.
Checkpoint: `eval_out/<experiment-name>_pragmatic.json`.
On resume, the checkpoint controls the context mode: omit `--with-context`
to use it silently; a conflicting explicit value warns and is overridden.

### Gold Standard Evaluation

Requires the extractor, matcher, and evaluator. Compares description-derived
Candidate Diagrams with the ReqUCD60 Reference Diagrams.

```sh
uv run python -m eval.gold_standard.collect_metrics \
  --experiment-name gold_standard_run_1 --size short
```

| Argument | Meaning / default |
|---|---|
| `--size {short,full}` | `short` (default): samples 1, 11, 21, 31, 41, 51. `full`: all 60 samples in numeric order. |

Observations: `gold_standard_eval` collection.
Checkpoint: `eval_out/<experiment-name>_requcd60_<size>.json`.
A crash between assessment persistence and progress recording can repeat an
assessment. Use a new name after changing references or conversion conventions.

To resume, repeat the original command with `--resume`, for example:

```sh
uv run python -m eval.gold_standard.collect_metrics \
  --experiment-name gold_standard_run_1 --size short --resume
```

## JupyterLab

```sh
uv sync --group eval
uv run --env-file .env --group eval jupyter lab
```

Analysis notebooks are in [`eval/notebooks/`](eval/notebooks/).
The `.env` file supplies their `MONGODB_URI`.

## Tests and linting

Install development dependencies and run the full test suite:

```sh
uv sync --group dev
make tests-run
```

Integration tests require a running Docker daemon. Testcontainers starts an
isolated MongoDB replica set, so `make up-infra` is not required for tests.
To run only integration tests:

```sh
PYTHONPATH=. uv run pytest tests/integration
```

Ruff and ty are managed by the project's `tools` dependency group:

```sh
uv sync --group tools
make lint
```

`make lint` runs both tools through `uv run --group tools`: Ruff applies
automatic fixes, and ty checks types. Their configuration is in
[`pyproject.toml`](pyproject.toml).
