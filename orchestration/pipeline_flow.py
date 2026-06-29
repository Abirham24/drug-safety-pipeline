"""Stage 6 — Orchestrate the whole drug-safety pipeline as one Prefect flow.

This turns "run four scripts and two dbt commands by hand" into a single
command:

    python orchestration/pipeline_flow.py

The flow runs the EXISTING steps, unchanged, in this strict order:

    1. ingest_counts -> src/ingest/fetch_openfda.py
    2. ingest_pairs  -> src/ingest/fetch_drug_reaction_pairs.py
    3. load_duckdb   -> src/load/load_to_duckdb.py
    4. dbt_run       -> dbt run   (from dbt/, with DBT_PROFILES_DIR set)
    5. dbt_test      -> dbt test

WHY STRICTLY SEQUENTIAL: DuckDB allows only ONE writer at a time. The load and
the dbt steps all write to data/warehouse.duckdb, so they must never run
concurrently. We therefore call the tasks one after another (not .submit()), so
each fully completes before the next begins.

FAIL FAST: every task runs its step as a subprocess and RAISES on a non-zero
exit code, so a failed ingest stops the flow before it can load/transform stale
or partial data. The failing step's output is logged.

This is ORCHESTRATION ONLY — it wraps the existing scripts and changes none of
the ingestion / load / transformation logic.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from prefect import flow, get_run_logger, task

# --- Robust paths (work no matter where the flow is launched from) ----------

# orchestration/pipeline_flow.py -> project root is one level up.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DBT_DIR = PROJECT_ROOT / "dbt"

# Prefer the venv's own interpreter and dbt so a LOCAL run does not depend on
# whatever python/dbt happen to be on PATH (Windows: venv/Scripts, POSIX:
# venv/bin). But in a CONTAINER there is no venv — dependencies are installed
# system-wide — so we fall back to the running interpreter (sys.executable) and a
# PATH-resolved ``dbt``. This keeps the flow portable across local and Docker.
_VENV_BIN = PROJECT_ROOT / "venv" / ("Scripts" if os.name == "nt" else "bin")
_EXE = ".exe" if os.name == "nt" else ""

_venv_python = _VENV_BIN / f"python{_EXE}"
_venv_dbt = _VENV_BIN / f"dbt{_EXE}"
VENV_PYTHON = str(_venv_python) if _venv_python.exists() else sys.executable
VENV_DBT = str(_venv_dbt) if _venv_dbt.exists() else "dbt"


def _run_step(label: str, cmd: list[str], cwd: Path, env: dict | None = None) -> str:
    """Run one pipeline step as a subprocess; log its output; raise on failure.

    Returns captured stdout on success. Raises RuntimeError on a non-zero exit
    code so the calling task fails and the flow stops (fail-fast).
    """
    logger = get_run_logger()
    logger.info(f"[{label}] starting -> {' '.join(cmd)} (cwd={cwd})")

    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        logger.info(f"[{label}] output:\n{result.stdout.strip()}")

    if result.returncode != 0:
        logger.error(f"[{label}] FAILED with exit code {result.returncode}")
        if result.stderr.strip():
            logger.error(f"[{label}] stderr:\n{result.stderr.strip()}")
        raise RuntimeError(f"Step '{label}' failed (exit {result.returncode})")

    logger.info(f"[{label}] finished OK")
    return result.stdout


def _dbt_env() -> dict:
    """Environment for the dbt steps: inherit everything, point at the in-repo
    profiles.yml via DBT_PROFILES_DIR (no secrets — DuckDB needs none)."""
    return {**os.environ, "DBT_PROFILES_DIR": str(DBT_DIR)}


# --- Tasks: one per existing pipeline step ----------------------------------

@task
def ingest_counts() -> str:
    """Step 1 — fetch base drug/reaction counts + sample events from openFDA."""
    return _run_step(
        "ingest_counts",
        [str(VENV_PYTHON), str(PROJECT_ROOT / "src" / "ingest" / "fetch_openfda.py")],
        cwd=PROJECT_ROOT,
    )


@task
def ingest_pairs() -> str:
    """Step 2 — fetch drug-reaction co-occurrence pairs from openFDA."""
    return _run_step(
        "ingest_pairs",
        [str(VENV_PYTHON), str(PROJECT_ROOT / "src" / "ingest" / "fetch_drug_reaction_pairs.py")],
        cwd=PROJECT_ROOT,
    )


@task
def load_duckdb() -> str:
    """Step 3 — load all raw JSON into the DuckDB warehouse."""
    return _run_step(
        "load_duckdb",
        [str(VENV_PYTHON), str(PROJECT_ROOT / "src" / "load" / "load_to_duckdb.py")],
        cwd=PROJECT_ROOT,
    )


@task
def dbt_run() -> str:
    """Step 4 — build the dbt models (staging + marts) into the warehouse."""
    return _run_step("dbt_run", [str(VENV_DBT), "run"], cwd=DBT_DIR, env=_dbt_env())


@task
def dbt_test() -> str:
    """Step 5 — run the dbt data-quality test suite."""
    return _run_step("dbt_test", [str(VENV_DBT), "test"], cwd=DBT_DIR, env=_dbt_env())


# --- The flow ---------------------------------------------------------------

@flow(name="drug_safety_pipeline")
def drug_safety_pipeline() -> None:
    """Run the five pipeline steps in strict order, stopping on the first failure.

    The tasks are CALLED DIRECTLY (not submitted to a task runner), so each one
    runs to completion before the next starts — guaranteeing the sequential,
    single-writer execution DuckDB requires.
    """
    logger = get_run_logger()
    logger.info("drug_safety_pipeline: starting (strictly sequential — DuckDB single-writer)")

    ingest_counts()   # 1
    ingest_pairs()    # 2
    load_duckdb()     # 3
    dbt_run()         # 4
    dbt_test()        # 5

    logger.info("drug_safety_pipeline: all five steps completed successfully.")


# --- Optional scheduling (informational — NOT enabled here) -----------------
#
# This flow is manually triggered. To run it on a schedule later, you would
# create a Prefect deployment, e.g. a daily cron, without changing this file:
#
#     drug_safety_pipeline.serve(name="daily", cron="0 6 * * *")
#
# That starts a long-running scheduler process, which is intentionally out of
# scope for this stage — here we only need a one-command, manually-run flow.


if __name__ == "__main__":
    drug_safety_pipeline()
