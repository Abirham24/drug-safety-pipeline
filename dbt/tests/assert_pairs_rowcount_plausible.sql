-- ROW-COUNT SANITY: catch a silent empty or partial load.
--
-- stg_drug_reaction_pairs should hold thousands of rows (~75 drugs x their many
-- reactions). If a fetch or load silently failed we might end up with a near-empty
-- table while everything downstream still "succeeds". This fails when the table
-- has 1000 or fewer rows. HAVING with no GROUP BY evaluates over the whole table,
-- so it returns a single row only when the count is implausibly low; empty = OK.

select count(*) as row_count
from {{ ref('stg_drug_reaction_pairs') }}
having count(*) <= 1000
