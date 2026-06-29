-- BUSINESS RULE: a flagged signal must meet the documented count floor.
--
-- is_signal is defined as (pair_count >= 50 AND prr >= 2). This test guards that
-- contract: any row flagged as a signal with fewer than 50 supporting reports is
-- a logic error. Returns offending rows; should be empty.

select
    drug_name,
    reaction,
    pair_count,
    prr
from {{ ref('mart_drug_reaction_signals') }}
where is_signal
  and pair_count < 50
