# FDA Drug Safety Signal Pipeline

A data engineering pipeline that ingests FDA drug adverse-event data, transforms it,
detects safety signals, and runs on a schedule.

> **Status:** Stage 0 — project skeleton only. No pipeline logic or API calls yet.

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

## Notes

- **openFDA API key is optional.** The openFDA API works without a key, but a free key
  raises rate limits. See `.env.example`.
