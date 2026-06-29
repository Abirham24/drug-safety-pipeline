"""Stage 2 — Load raw JSON files into a local DuckDB warehouse.

WHAT IS DUCKDB?
    DuckDB is an in-process, file-based analytical (OLAP) database — think
    "SQLite for analytics". The entire database lives in a single file on disk
    (here: ``data/warehouse.duckdb``), there is no server to run, and it speaks
    SQL. It has first-class JSON support, which is exactly what we need to turn
    our raw ``data/raw/*.json`` files into queryable tables.

WHAT THIS STAGE DOES (LOADING ONLY):
    We take the three raw files saved in Stage 1 and load them into ``raw_``
    tables. We do NOT do any signal/disproportionality analysis and we do NOT
    fully flatten the nested event records — that comes later (dbt, Stage 3).
    For the nested ``sample_events`` records we keep the whole record as a JSON
    column plus a couple of convenient top-level fields.

IDEMPOTENCY — why CREATE OR REPLACE:
    Every table is built with ``CREATE OR REPLACE TABLE``. That means each run
    drops any existing table of the same name and rebuilds it from scratch, so
    re-running this script produces the exact same result instead of appending
    duplicate rows. The load is therefore safe to run as many times as you like.

Run it yourself with:
    python src/load/load_to_duckdb.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb

# --- Configuration ----------------------------------------------------------

# Project layout: this file is src/load/load_to_duckdb.py, so the project root
# is two directories up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# The DuckDB database file. Configurable via the WAREHOUSE_DB env var, but the
# sensible default lives alongside our data. It is git-ignored (*.duckdb).
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"
DB_PATH = Path(os.getenv("WAREHOUSE_DB", DEFAULT_DB_PATH))

# How many sample rows to print per table in the verification summary.
PREVIEW_ROWS = 3


def load_results(filename: str) -> list[dict] | None:
    """Read data/raw/<filename> and return the list under its ``results`` key.

    Returns None (and prints a clear message) if the file is missing, so a
    single absent raw file skips that table instead of crashing the whole load.
    """
    path = RAW_DIR / filename
    if not path.exists():
        print(f"  SKIP: raw file not found -> {path.relative_to(PROJECT_ROOT)}")
        return None

    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    results = payload.get("results", [])
    print(f"  read {len(results)} results from {path.relative_to(PROJECT_ROOT)}")
    return results


def load_counts_table(
    con: duckdb.DuckDBPyConnection,
    filename: str,
    table: str,
    term_column: str,
) -> None:
    """Load a ``{term, count}`` counts file into ``table``.

    Both counts files share the same shape — a list of ``{"term", "count"}`` —
    so this one helper handles drug counts and reaction counts; ``term_column``
    just renames ``term`` to a meaningful name (``drug`` or ``reaction``).
    """
    print(f"\n[{table}]")
    results = load_results(filename)
    if results is None:
        return

    # Build simple (term, count) rows and register them as a DuckDB relation,
    # then CREATE OR REPLACE so the load is idempotent (see module docstring).
    rows = [(r.get("term"), r.get("count")) for r in results]
    con.execute(
        f"CREATE OR REPLACE TABLE {table} "
        f"({term_column} VARCHAR, report_count BIGINT)"
    )
    if rows:
        con.executemany(f"INSERT INTO {table} VALUES (?, ?)", rows)
    print(f"  loaded {len(rows)} rows into {table}")


def load_sample_events(
    con: duckdb.DuckDBPyConnection,
    filename: str,
    table: str,
) -> None:
    """Load the nested adverse-event records into ``table``.

    The event records are deeply nested JSON. Per the Stage 2 constraints we do
    NOT flatten them: we keep the entire record as a JSON column (``record``)
    and pull out only a few convenient top-level identifiers/dates alongside it.
    Full flattening is a later (dbt) step.
    """
    print(f"\n[{table}]")
    results = load_results(filename)
    if results is None:
        return

    # Each row = the easily-extracted top-level fields + the whole record as a
    # JSON string. DuckDB's JSON type lets us query into ``record`` later.
    rows = [
        (
            r.get("safetyreportid"),
            r.get("receivedate"),
            r.get("serious"),
            json.dumps(r),
        )
        for r in results
    ]
    con.execute(
        f"CREATE OR REPLACE TABLE {table} ("
        "safetyreportid VARCHAR, "
        "receivedate VARCHAR, "
        "serious VARCHAR, "
        "record JSON"
        ")"
    )
    if rows:
        con.executemany(f"INSERT INTO {table} VALUES (?, ?, ?, ?)", rows)
    print(f"  loaded {len(rows)} rows into {table}")


def load_drug_reaction_pairs(
    con: duckdb.DuckDBPyConnection,
    filename: str,
    table: str,
) -> None:
    """Load the drug-reaction co-occurrence pairs into ``table``.

    This file is a plain JSON LIST of ``{drug, reaction, pair_count}`` records
    (produced by fetch_drug_reaction_pairs.py) and can be large (~75k rows).

    PERFORMANCE: instead of a Python row-by-row INSERT loop, we let DuckDB read
    the JSON file natively with ``read_json_auto`` and build the table in a
    single ``CREATE OR REPLACE TABLE ... AS SELECT``. DuckDB parses and bulk-loads
    the whole array in one fast C++ operation, and CREATE OR REPLACE keeps the
    load idempotent. We select explicit columns/types so the schema is stable
    regardless of what read_json_auto infers.
    """
    print(f"\n[{table}]")
    path = RAW_DIR / filename
    if not path.exists():
        print(f"  SKIP: raw file not found -> {path.relative_to(PROJECT_ROOT)}")
        return

    # Forward slashes so the path is a clean SQL string literal on Windows too.
    # Parameterized to avoid any quoting issues with the path.
    con.execute(
        f"CREATE OR REPLACE TABLE {table} AS "
        "SELECT "
        "  CAST(drug AS VARCHAR)        AS drug, "
        "  CAST(reaction AS VARCHAR)    AS reaction, "
        "  CAST(pair_count AS BIGINT)   AS pair_count "
        "FROM read_json_auto(?)",
        [path.as_posix()],
    )
    count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    print(f"  loaded {count} rows into {table} (bulk read_json_auto)")


def load_report_totals(
    con: duckdb.DuckDBPyConnection,
    filename: str,
    table: str,
) -> None:
    """Load N — the total number of reports in the ingestion window — as one row.

    Disproportionality (PRR) needs N = the total report count for the WHOLE
    database window (a + b + c + d), not just the analyzed drugs. openFDA returns
    it on every search response under ``meta.results.total``; the Stage 1
    sample_events fetch used the bare receivedate window, so ITS
    ``meta.results.total`` is exactly that N. We capture it here as a tiny one-row
    table so the dbt PRR model can reference it. CREATE OR REPLACE keeps it
    idempotent like the other loads.
    """
    print(f"\n[{table}]")
    path = RAW_DIR / filename
    if not path.exists():
        print(f"  SKIP: raw file not found -> {path.relative_to(PROJECT_ROOT)}")
        return

    with path.open("r", encoding="utf-8") as fh:
        meta = json.load(fh).get("meta", {})
    total = meta.get("results", {}).get("total")

    con.execute(f"CREATE OR REPLACE TABLE {table} (total_reports BIGINT)")
    if total is not None:
        con.execute(f"INSERT INTO {table} VALUES (?)", [total])
    print(f"  loaded total_reports = {total} into {table}")


def print_verification(con: duckdb.DuckDBPyConnection, table: str) -> None:
    """Print row count and the first few rows so the load can be eyeballed."""
    # If a raw file was missing the table won't exist — say so and move on.
    exists = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
        [table],
    ).fetchone()[0]
    if not exists:
        print(f"\n[{table}] not loaded (raw file was missing).")
        return

    count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    print(f"\n[{table}] {count} rows. First {PREVIEW_ROWS}:")
    preview = con.execute(f"SELECT * FROM {table} LIMIT {PREVIEW_ROWS}").fetchall()
    columns = [d[0] for d in con.description]
    print("  " + " | ".join(columns))
    for row in preview:
        # Truncate long JSON cells so the preview stays readable in a terminal.
        cells = [
            (str(v)[:80] + "…") if v is not None and len(str(v)) > 80 else str(v)
            for v in row
        ]
        print("  " + " | ".join(cells))


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"DuckDB warehouse -> {DB_PATH}")

    # Connecting creates the database file if it does not already exist.
    con = duckdb.connect(str(DB_PATH))
    try:
        load_counts_table(
            con, "counts_by_drug.json", "raw_counts_by_drug", "drug"
        )
        load_counts_table(
            con, "counts_by_reaction.json", "raw_counts_by_reaction", "reaction"
        )
        load_sample_events(con, "sample_events.json", "raw_sample_events")
        load_drug_reaction_pairs(
            con, "drug_reaction_pairs.json", "raw_drug_reaction_pairs"
        )
        load_report_totals(con, "sample_events.json", "raw_report_totals")

        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        for table in (
            "raw_counts_by_drug",
            "raw_counts_by_reaction",
            "raw_sample_events",
            "raw_drug_reaction_pairs",
            "raw_report_totals",
        ):
            print_verification(con, table)
    finally:
        con.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
