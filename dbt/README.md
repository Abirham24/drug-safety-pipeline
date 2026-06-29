# dbt — drug_safety project (Stage 3a: setup & connection)

This folder is the dbt project that transforms the DuckDB warehouse
(`../data/warehouse.duckdb`). Stage 3a is **setup and connection only** — the
only model is a trivial `select 1` connectivity check. Real transformation
models come in Stage 3b.

## What the key files do

- **`dbt_project.yml`** — defines the project: its name (`drug_safety`), which
  connection profile to use, the standard folder layout, and default
  materializations. dbt reads it from the current working directory, so you run
  dbt commands from *inside this `dbt/` folder*.
- **`profiles.yml`** — the connection file. It tells dbt how to reach the
  database: `type: duckdb` pointing at `../data/warehouse.duckdb`. We keep it in
  the repo (instead of the default `~/.dbt/`) so the project is self-contained,
  and point dbt at it with the `DBT_PROFILES_DIR` env var. DuckDB is a local
  file (no host/user/password), so this file holds **no secrets** and is safe to
  commit.

## How to run dbt

dbt commands must run **from this `dbt/` folder**, with `DBT_PROFILES_DIR` set to
this folder so dbt finds the in-repo `profiles.yml`.

### Windows — PowerShell
```powershell
cd "D:\drug safety pipeline\dbt"
$env:DBT_PROFILES_DIR = "D:\drug safety pipeline\dbt"
..\venv\Scripts\dbt.exe debug   # verify the DuckDB connection
..\venv\Scripts\dbt.exe run     # build the test model into the warehouse
```

### Windows — Git Bash
```bash
cd "/d/drug safety pipeline/dbt"
export DBT_PROFILES_DIR="/d/drug safety pipeline/dbt"
../venv/Scripts/dbt.exe debug
../venv/Scripts/dbt.exe run
```

Expected results:
- `dbt debug` → `All checks passed!` (Connection test: OK connection ok)
- `dbt run` → builds `stg_test` as a view; `PASS=1 ... TOTAL=1`

You can confirm it landed with:
```bash
../venv/Scripts/python.exe -c "import duckdb; print(duckdb.connect('../data/warehouse.duckdb').execute('select * from main.stg_test').fetchall())"
```
(prints `[(1,)]`).

## Git hygiene

dbt's build artifacts are git-ignored (see repo `.gitignore`): `dbt/target/`,
`dbt/dbt_packages/`, `dbt/logs/`, and the generated `dbt/.user.yml`. The project
source — `dbt_project.yml`, `profiles.yml`, and `models/` — is committed.

## Data-quality testing strategy

The pipeline validates its own data so it fails loudly when something is wrong,
rather than silently serving bad numbers. `dbt test` runs the whole suite (and
`dbt build` runs models + tests together). There are two kinds of tests:

- **Generic tests** (declared inline in the `_sources.yml` / `_staging.yml` /
  `_marts.yml` schema files) cover column-level rules: `not_null` on keys and
  counts, `unique` on `stg_events.safety_report_id`, and `accepted_values` on the
  boolean `is_signal`. These are dbt's built-ins — no external packages.

- **Singular tests** (`.sql` files in `tests/`) cover business rules and
  cross-table integrity. Each is a query that must return ZERO rows when the data
  is valid:
  - `assert_prr_non_negative` — PRR is a ratio of non-negative rates, never < 0.
  - `assert_signals_meet_count_floor` — nothing is flagged `is_signal` with
    `pair_count < 50` (the documented signal threshold).
  - `assert_pair_count_positive` — every signal row has `pair_count >= 1`.
  - `assert_staging_counts_non_negative` — all ingested counts are >= 0.
  - `assert_no_orphan_pairs` — every drug in the pairs exists in `stg_drug_counts`
    (catches join/key/cleaning mismatches).
  - `assert_unique_drug_reaction_pairs` — each (drug, reaction) appears once in
    the signal table (guards the pair grain).
  - `assert_pairs_rowcount_plausible` — `stg_drug_reaction_pairs` has > 1000 rows,
    so a silent empty/partial load is caught.

We deliberately use singular SQL tests (instead of adding the `dbt_utils` package)
for range/non-negativity checks, keeping the project dependency-free. All tests
are expected to PASS on the current data — green means the data is valid.
