# FDA Drug Safety Signal Pipeline

A data engineering pipeline that ingests FDA drug adverse-event data, transforms it,
detects safety signals, and runs on a schedule.

> **Status:** Stage 6 — end-to-end pipeline (ingest → load → dbt transform/signals → tests)
> wired into a single orchestrated Prefect flow.

## Project layout

```
.
├── README.md            # this file
├── requirements.txt     # Python dependencies (added per stage)
├── .gitignore           # files/dirs git should ignore
├── .env.example         # template of env vars (copy to .env, fill in real values)
├── src/                 # Python source code
│   ├── ingest/          # API ingestion code — pull adverse-event data from openFDA (later)
│   ├── load/            # load raw/clean data into DuckDB (later)
│   └── utils/           # shared helpers used across the pipeline (later)
├── dbt/                 # dbt project for SQL transformations / models (later)
├── data/                # local data files (gitignored, kept out of version control)
├── orchestration/       # Prefect flows that schedule and run the pipeline (later)
└── docs/                # architecture diagram, design notes (later)
```

## Getting started

1. Create and activate a virtual environment:
   ```
   python -m venv venv
   # Windows (PowerShell): venv\Scripts\Activate.ps1
   # macOS/Linux:          source venv/bin/activate
   ```
2. Copy the env template and fill in any values:
   ```
   cp .env.example .env
   ```
3. Install dependencies (added in later stages):
   ```
   pip install -r requirements.txt
   ```

## Running the full pipeline (orchestration)

The whole pipeline is wired into one Prefect flow so it runs with a single command:

```
python orchestration/pipeline_flow.py
```

The flow (`orchestration/pipeline_flow.py`) runs these existing steps **in strict order**,
logging each task and stopping immediately if one fails:

1. `ingest_counts` — `src/ingest/fetch_openfda.py` (drug/reaction counts + sample events)
2. `ingest_pairs`  — `src/ingest/fetch_drug_reaction_pairs.py` (drug-reaction pairs)
3. `load_duckdb`   — `src/load/load_to_duckdb.py` (raw JSON → DuckDB)
4. `dbt_run`       — `dbt run` (staging + marts, from `dbt/` with `DBT_PROFILES_DIR` set)
5. `dbt_test`      — `dbt test` (data-quality suite)

**Why strictly sequential:** DuckDB allows only one writer at a time, and the load and dbt
steps all write to `data/warehouse.duckdb`. The flow calls its tasks one after another (never
concurrently), and each step runs as a subprocess that raises on a non-zero exit code — so a
failed ingest **fails fast** and never proceeds to load/transform stale data.

The flow is **manually triggered**; it resolves the project root from its own location, so it
works regardless of the directory it's launched from. It could later be put on a schedule via
a Prefect deployment (e.g. daily) without code changes — see the note at the bottom of
`pipeline_flow.py`.

## Running with Docker

The project is containerization-ready: a `Dockerfile`, `.dockerignore`, and
`docker-compose.yml` are provided. The image installs the Python dependencies and
runs the Prefect flow (`ingest → load → dbt run → dbt test`) as its default command.

> **Honest status:** Docker is **not installed in the development environment**, so
> the image has **not been built or run locally** — these files are provided and
> reviewed but unbuilt. Build and run them on a machine with Docker. Nothing here
> claims a container was deployed.

Build and run:

```
docker build -t drug-safety-pipeline .
docker run --env-file .env drug-safety-pipeline
```

Or with docker-compose:

```
docker compose build
docker compose up
```

**Secrets:** the openFDA API key is supplied **at runtime** via `--env-file .env`
(or compose's `env_file:`), and is **never baked into the image**. `.dockerignore`
excludes `.env`, `venv/`, `data/`, `.git/`, caches, dbt artifacts, and the
`*.duckdb` file — so no secrets and no stale local data enter the image, keeping it
small and reproducible. Raw data and the DuckDB warehouse are regenerated inside the
container when the flow runs.

## Notes

- **openFDA API key is optional.** The openFDA API works without a key, but a free key
  raises rate limits. See `.env.example`.
