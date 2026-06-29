# Stage 1 Task — Ingest from the openFDA Adverse Event API

## Goal
Prove we can reliably fetch real drug adverse-event data from the openFDA API and save
the raw responses locally. This stage is INGESTION ONLY. Do NOT load into DuckDB,
transform, or analyze yet. Just fetch and save raw JSON.

## Background (important context for the code)
- Base endpoint: `https://api.fda.gov/drug/event.json`
- No API key required, but an optional key (env var `OPENFDA_API_KEY`) raises rate limits.
  If the env var is present, include it as `&api_key=...`; if absent, call without it.
- Max 1000 records per call. The API also supports server-side aggregation with the
  `count` parameter (e.g. `count=patient.drug.medicinalproduct.exact` returns counts per
  drug), which we will use so we do NOT bulk-download millions of records.
- We want a recent TIME WINDOW, not all history. Filter by the report received date field
  `receivedate` using a date range (e.g. the last 1 year up to today), using the search
  syntax: `search=receivedate:[YYYYMMDD+TO+YYYYMMDD]`.

## What to build
Create an ingestion script at `src/ingest/fetch_openfda.py` that fetches THREE things and
saves each as raw JSON into the `data/raw/` folder (create it if needed):

1. **Counts of adverse events per drug** (top drugs by report volume) over the last year.
   Use the `count` parameter on the drug name field, combined with the date-range search.
   Save to `data/raw/counts_by_drug.json`.

2. **Counts of adverse events per reaction** (top reactions) over the last year.
   Use `count` on the reaction field (`patient.reaction.reactionmeddrapt.exact`).
   Save to `data/raw/counts_by_reaction.json`.

3. **A sample of detailed event records** (e.g. limit=100) over the last year, so we have
   some granular records to inspect later.
   Save to `data/raw/sample_events.json`.

## Requirements
- Add `requests` (and `python-dotenv` if not already present) to requirements.txt and
  install into the venv.
- Load the optional API key from `.env` via python-dotenv; work fine without it.
- Build the date range programmatically (today, and one year ago) so it stays current.
- Handle errors gracefully: if a request fails (non-200, timeout, rate limit), print a
  clear message with the status code and the URL, and do not crash the whole script.
- Print a short summary for each fetch: what was requested, the HTTP status, and how many
  results came back.
- Add comments explaining the aggregation (`count`) approach and the date filtering, since
  these are key design decisions.

## Constraints
- Ingestion only. No DuckDB, no transformation, no analysis.
- Do NOT hardcode any API key in the code; read from .env.
- Save raw, unmodified JSON responses (this is the "raw" layer of the pipeline).
- I (the user) will run it myself with `python src/ingest/fetch_openfda.py`.

## What success looks like
- Three JSON files appear in `data/raw/`.
- The terminal prints the status and result counts for each.
- counts_by_drug.json and counts_by_reaction.json contain lists of {term, count} pairs;
  sample_events.json contains ~100 detailed records.
