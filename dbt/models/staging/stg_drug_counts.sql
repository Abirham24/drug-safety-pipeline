-- stg_drug_counts — cleaned per-drug adverse-event report counts.
--
-- Staging = light cleanup only: rename to clear column names, standardize the
-- drug name (trim + uppercase so the same drug always keys the same way), cast
-- the count to an integer, and drop rows with no drug name. No aggregation or
-- joins here — that is Stage 4.

select
    upper(trim(drug))        as drug_name,
    cast(report_count as integer) as report_count
from {{ source('raw', 'raw_counts_by_drug') }}
where drug is not null
  and trim(drug) <> ''
