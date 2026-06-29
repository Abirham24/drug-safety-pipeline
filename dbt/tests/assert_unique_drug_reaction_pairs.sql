-- INTEGRITY: each (drug_name, reaction) should appear exactly once in the signal
-- table. A duplicate would mean the pair grain broke somewhere upstream (e.g. a
-- fan-out join), which would distort any per-pair reading of PRR. Returns any
-- pair that appears more than once; should be empty.

select
    drug_name,
    reaction,
    count(*) as n_rows
from {{ ref('mart_drug_reaction_signals') }}
group by drug_name, reaction
having count(*) > 1
