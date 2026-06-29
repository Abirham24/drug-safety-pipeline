-- DATA RULE: every published signal row must have pair_count >= 1.
--
-- A row exists in the signal table because at least one report linked the drug
-- and the reaction, so pair_count (the 'a' cell) must be at least 1. A zero or
-- negative value would indicate a broken join or count. Returns violations;
-- should be empty.

select
    drug_name,
    reaction,
    pair_count
from {{ ref('mart_drug_reaction_signals') }}
where pair_count < 1
