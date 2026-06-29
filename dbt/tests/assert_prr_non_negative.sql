-- Singular data test: PRR must never be negative.
--
-- A dbt test passes when it returns ZERO rows, so this selects any offending
-- rows where prr < 0. PRR is a ratio of two non-negative reporting rates, so a
-- negative value would signal a bug in the calculation.

select
    drug_name,
    reaction,
    prr
from {{ ref('mart_drug_reaction_signals') }}
where prr < 0
