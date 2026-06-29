-- stg_reaction_counts — cleaned per-reaction adverse-event report counts.
--
-- Light cleanup only: trim the reaction term, cast the count to an integer, and
-- drop rows with no reaction. Reaction terms are already MedDRA preferred terms,
-- so we trim but do not force-uppercase them.

select
    trim(reaction)               as reaction,
    cast(report_count as integer) as report_count
from {{ source('raw', 'raw_counts_by_reaction') }}
where reaction is not null
  and trim(reaction) <> ''
