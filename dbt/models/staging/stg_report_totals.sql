-- stg_report_totals — N, the total number of adverse-event reports in the
-- ingestion window. One row, one column.
--
-- This is the denominator base (a + b + c + d) for PRR: the size of the WHOLE
-- database over the window, not just the analyzed drugs. It comes from openFDA's
-- meta.results.total (captured by the loader into raw_report_totals).

select
    cast(total_reports as bigint) as total_reports
from {{ source('raw', 'raw_report_totals') }}
