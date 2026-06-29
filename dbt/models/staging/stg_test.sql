-- stg_test.sql — trivial connectivity check for Stage 3a.
--
-- This is NOT a real transformation. It just selects a constant so we can prove
-- the full path works: dbt reads dbt_project.yml + profiles.yml, connects to the
-- DuckDB warehouse, and materializes a model into it. Real staging models that
-- read the raw_* tables arrive in Stage 3b, which will replace this file.

select 1 as ok
