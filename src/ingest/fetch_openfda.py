"""Stage 1 — Ingest raw adverse-event data from the openFDA API.

This script fetches THREE things from the openFDA drug adverse-event endpoint and
saves each as raw, unmodified JSON into ``data/raw/``:

1. counts_by_drug.json     — adverse-event report counts per drug (top drugs)
2. counts_by_reaction.json — adverse-event report counts per reaction (top reactions)
3. sample_events.json      — a sample of ~100 detailed event records

INGESTION ONLY: no DuckDB, no transformation, no analysis. We just fetch and save.

Run it yourself with:
    python src/ingest/fetch_openfda.py
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

# --- Configuration ----------------------------------------------------------

BASE_URL = "https://api.fda.gov/drug/event.json"

# openFDA caps results at 1000 per call. We keep the detailed-record sample small.
SAMPLE_LIMIT = 100

# How many of the top aggregated terms to ask for (count queries).
COUNT_LIMIT = 1000

# Where raw responses land — the "raw" layer of the pipeline.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# Per-request network timeout (seconds).
REQUEST_TIMEOUT = 30


def get_date_range() -> tuple[str, str]:
    """Return (one_year_ago, today) formatted as YYYYMMDD.

    We build the window programmatically so the ingestion always covers the most
    recent year relative to whenever it is run, rather than a hardcoded range.
    """
    today = date.today()
    one_year_ago = today - timedelta(days=365)
    fmt = "%Y%m%d"
    return one_year_ago.strftime(fmt), today.strftime(fmt)


def build_params(extra: dict) -> dict:
    """Assemble query params common to every request.

    DESIGN — date filtering: we restrict to a recent time window using the report
    received date field ``receivedate`` with the range syntax
    ``receivedate:[YYYYMMDD TO YYYYMMDD]``. This keeps us current and avoids pulling
    the entire history of the database.

    DESIGN — optional API key: openFDA works without a key, but a free key raises
    rate limits. If OPENFDA_API_KEY is set in the environment we include it;
    otherwise we call anonymously. The key is never hardcoded.
    """
    start, end = get_date_range()
    params = {"search": f"receivedate:[{start} TO {end}]"}
    params.update(extra)

    api_key = os.getenv("OPENFDA_API_KEY")
    if api_key:
        params["api_key"] = api_key

    return params


def fetch(label: str, extra_params: dict) -> dict | None:
    """Perform one openFDA GET request and return the parsed JSON (or None on error).

    Errors are handled gracefully: any failure (non-200, timeout, connection error,
    bad JSON) prints a clear message with the status code and URL and returns None,
    so one failed fetch does not crash the whole script.
    """
    params = build_params(extra_params)
    try:
        resp = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        print(f"[{label}] ERROR: request failed ({type(exc).__name__}): {exc}")
        return None

    # Always report what we asked for and the HTTP status.
    if resp.status_code != 200:
        print(
            f"[{label}] ERROR: HTTP {resp.status_code} for URL:\n    {resp.url}\n"
            f"    response: {resp.text[:300]}"
        )
        return None

    try:
        payload = resp.json()
    except ValueError as exc:
        print(f"[{label}] ERROR: could not parse JSON ({exc}) for URL:\n    {resp.url}")
        return None

    results = payload.get("results", [])
    print(f"[{label}] OK: HTTP {resp.status_code}, {len(results)} results — {resp.url}")
    return payload


def save_json(payload: dict, filename: str) -> None:
    """Write the raw, unmodified response to data/raw/<filename>."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / filename
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"         saved -> {out_path.relative_to(PROJECT_ROOT)}")


def main() -> None:
    # Load OPENFDA_API_KEY (if present) from .env. Absent key is fine.
    load_dotenv(PROJECT_ROOT / ".env")

    start, end = get_date_range()
    print(f"openFDA ingestion — receivedate window [{start} TO {end}]")
    key_status = "set" if os.getenv("OPENFDA_API_KEY") else "not set (anonymous)"
    print(f"API key: {key_status}\n")

    # 1) Counts of adverse events per drug.
    #    DESIGN — aggregation: the `count` parameter makes openFDA do the grouping
    #    server-side and return {term, count} pairs, so we get the top drugs by report
    #    volume in a single small response instead of bulk-downloading raw records.
    drug_counts = fetch(
        "counts_by_drug",
        {"count": "patient.drug.medicinalproduct.exact", "limit": COUNT_LIMIT},
    )
    if drug_counts is not None:
        save_json(drug_counts, "counts_by_drug.json")

    # 2) Counts of adverse events per reaction (same aggregation approach).
    reaction_counts = fetch(
        "counts_by_reaction",
        {"count": "patient.reaction.reactionmeddrapt.exact", "limit": COUNT_LIMIT},
    )
    if reaction_counts is not None:
        save_json(reaction_counts, "counts_by_reaction.json")

    # 3) A sample of detailed event records (no `count` — these are full records),
    #    limited to ~100 so we have granular data to inspect in later stages.
    sample_events = fetch("sample_events", {"limit": SAMPLE_LIMIT})
    if sample_events is not None:
        save_json(sample_events, "sample_events.json")

    print("\nDone.")


if __name__ == "__main__":
    main()
