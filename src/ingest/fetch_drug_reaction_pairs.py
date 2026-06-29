"""Stage 4a — Ingest drug-reaction CO-OCCURRENCE counts from openFDA.

Disproportionality analysis (Stage 4b) needs to know, for each drug, how often
each reaction is reported alongside it. Stages 1-2 gave us drug counts and
reaction counts SEPARATELY; this script fills the gap by pulling the pair data.

APPROACH (efficient — uses openFDA server-side aggregation, no bulk download):
    1. Take the top ~75 drugs by report volume (from counts_by_drug.json).
    2. For each drug, ask openFDA to ``count`` reactions filtered to that drug:
         search = patient.drug.medicinalproduct:"<DRUG>" AND receivedate:[from TO to]
         count  = patient.reaction.reactionmeddrapt.exact
       which returns that drug's {reaction term, count} breakdown in one call.
    3. Flatten everything into {drug, reaction, pair_count} records and save to
       data/raw/drug_reaction_pairs.json.

INGESTION ONLY: no disproportionality math here (that is Stage 4b).

We reuse the 1-year receivedate window and API-key loading from fetch_openfda.

Run it yourself with:
    python src/ingest/fetch_drug_reaction_pairs.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# Reuse the date-window logic and shared constants from the Stage 1 script.
# (Both live in src/ingest/, which is on sys.path when this is run as a script.)
from fetch_openfda import (
    BASE_URL,
    PROJECT_ROOT,
    RAW_DIR,
    REQUEST_TIMEOUT,
    get_date_range,
    mask_api_key,
)

# --- Configuration ----------------------------------------------------------

# How many of the top drugs (by report volume) to pull reaction breakdowns for.
# Agreed scope is the top 50-100; we use ~75.
TOP_N_DRUGS = 75

# openFDA caps count results at 1000 terms per call — plenty per drug.
REACTION_LIMIT = 1000

# Politeness controls so we do not hammer the API.
SLEEP_BETWEEN_CALLS = 0.3   # seconds to pause between drugs
MAX_RETRIES = 3             # attempts per drug on rate-limit / transient errors
RETRY_BACKOFF = 2.0         # base seconds; waits grow 2s, 4s, 6s with attempt

DRUG_COUNTS_FILE = RAW_DIR / "counts_by_drug.json"
OUTPUT_FILE = RAW_DIR / "drug_reaction_pairs.json"


def load_top_drugs(n: int) -> list[str]:
    """Return the top ``n`` drug names by report volume from counts_by_drug.json.

    The counts file is already sorted by count descending, but we sort defensively
    so this does not depend on that ordering.
    """
    if not DRUG_COUNTS_FILE.exists():
        raise FileNotFoundError(
            f"Missing {DRUG_COUNTS_FILE.relative_to(PROJECT_ROOT)} — run "
            "src/ingest/fetch_openfda.py first to ingest drug counts."
        )

    with DRUG_COUNTS_FILE.open("r", encoding="utf-8") as fh:
        results = json.load(fh).get("results", [])

    ranked = sorted(results, key=lambda r: r.get("count", 0), reverse=True)
    drugs = [r["term"] for r in ranked[:n] if r.get("term")]
    return drugs


def build_params(drug: str) -> dict:
    """Assemble the openFDA query params for one drug's reaction breakdown.

    Mirrors fetch_openfda: restrict to the recent receivedate window and include
    the optional API key from the environment if set (never hardcoded).
    """
    start, end = get_date_range()
    params = {
        "search": (
            f'patient.drug.medicinalproduct:"{drug}" '
            f"AND receivedate:[{start} TO {end}]"
        ),
        "count": "patient.reaction.reactionmeddrapt.exact",
        "limit": REACTION_LIMIT,
    }
    api_key = os.getenv("OPENFDA_API_KEY")
    if api_key:
        params["api_key"] = api_key
    return params


def fetch_drug_reactions(drug: str) -> list[dict] | None:
    """Fetch the reaction breakdown for one drug, with retry on 429/transient errors.

    Returns the list of {term, count} results, or None if every attempt failed.
    A drug with zero matching reports yields an empty list (not an error).
    """
    params = build_params(drug)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            wait = RETRY_BACKOFF * attempt
            print(f"    request error ({type(exc).__name__}); retry in {wait:.0f}s")
            time.sleep(wait)
            continue

        # openFDA returns 404 with a "No matches found" body when a drug has no
        # reports in the window — treat that as an empty (but successful) result.
        if resp.status_code == 404:
            return []

        # Rate limited — back off and retry.
        if resp.status_code == 429:
            wait = RETRY_BACKOFF * attempt
            print(f"    HTTP 429 rate limited; waiting {wait:.0f}s then retrying")
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            # Mask defensively in case the error body ever echoes the request URL.
            print(f"    HTTP {resp.status_code}: {mask_api_key(resp.text[:150])}")
            return None

        try:
            return resp.json().get("results", [])
        except ValueError as exc:
            print(f"    bad JSON ({exc})")
            return None

    return None


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    start, end = get_date_range()
    key_status = "set" if os.getenv("OPENFDA_API_KEY") else "not set (anonymous)"
    print(f"Drug-reaction pair ingestion — receivedate window [{start} TO {end}]")
    print(f"API key: {key_status}")

    drugs = load_top_drugs(TOP_N_DRUGS)
    print(f"Fetching reaction breakdowns for top {len(drugs)} drugs...\n")

    pairs: list[dict] = []
    succeeded = 0
    failed: list[str] = []

    for i, drug in enumerate(drugs, start=1):
        reactions = fetch_drug_reactions(drug)
        if reactions is None:
            print(f"[{i}/{len(drugs)}] {drug}: FAILED (skipped)")
            failed.append(drug)
        else:
            for r in reactions:
                term, count = r.get("term"), r.get("count")
                if term is not None:
                    pairs.append(
                        {"drug": drug, "reaction": term, "pair_count": count}
                    )
            succeeded += 1
            print(f"[{i}/{len(drugs)}] {drug}: {len(reactions)} reactions")

        # Be polite: small pause between drugs (skip after the last one).
        if i < len(drugs):
            time.sleep(SLEEP_BETWEEN_CALLS)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(pairs, fh, indent=2)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  drugs succeeded : {succeeded}/{len(drugs)}")
    if failed:
        print(f"  drugs failed    : {len(failed)} -> {', '.join(failed)}")
    print(f"  total pair rows : {len(pairs)}")
    print(f"  saved -> {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
