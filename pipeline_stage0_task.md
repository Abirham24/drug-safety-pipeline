# Stage 0 Task — Data Pipeline Project Skeleton

## Goal
Set up a clean, well-organized project skeleton for a data engineering pipeline that
ingests FDA drug adverse-event data, transforms it, detects safety signals, and runs
on a schedule. This stage is STRUCTURE ONLY. Do NOT write pipeline logic or call any
API yet.

## What to create

### Folder structure
Create this layout (empty folders can hold a `.gitkeep` file so git tracks them):
```
.
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example          # template showing env vars, no real secrets
├── src/
│   ├── __init__.py
│   ├── ingest/           # API ingestion code (later)
│   ├── load/             # load to DuckDB (later)
│   └── utils/            # shared helpers (later)
├── dbt/                  # dbt project for transformations (later)
├── data/                 # local data files (gitignored)
│   └── .gitkeep
├── orchestration/        # Prefect flows (later)
└── docs/                 # architecture diagram, notes (later)
```

### Files to populate
- **.gitignore** — ignore: `.env`, the virtual environment (`venv/`, `.venv/`),
  `__pycache__/`, `*.pyc`, the `data/` contents (but keep `data/.gitkeep`), DuckDB
  database files (`*.duckdb`, `*.db`), and dbt artifacts (`dbt/target/`, `dbt/dbt_packages/`, `dbt/logs/`).
- **.env.example** — a template listing the env vars the project will use, with
  placeholder values, for example:
  `OPENFDA_API_KEY=your_optional_openfda_api_key_here`
  (Note: openFDA works without a key but a free key raises rate limits. Keep it optional.)
- **requirements.txt** — leave empty for now (we add libraries per stage).
- **README.md** — a short placeholder title: "FDA Drug Safety Signal Pipeline".

### Git
- Initialize a git repository.
- Set the default branch to `main`.
- Make an initial commit once the skeleton is in place.
- Before committing, run git status and confirm `.env` is NOT tracked (only `.env.example` should be).

## Constraints
- Structure only. No API calls, no pipeline logic, no dbt models yet.
- Create a Python virtual environment (`venv`) but do not install packages yet.
- Explain each folder's purpose briefly in comments or in the README so I understand the layout.
- I (the user) will activate the venv and run things myself.
