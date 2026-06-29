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
