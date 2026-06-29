-- DATA RULE: every ingested count must be non-negative.
--
-- Report counts and pair counts are tallies of reports, so a negative value would
-- mean corrupt ingestion or a bad cast. We check all three staging count columns
-- in one place and return any negative value; should be empty.

select 'stg_drug_counts' as model, drug_name as item, report_count as value
from {{ ref('stg_drug_counts') }}
where report_count < 0

union all

select 'stg_reaction_counts' as model, reaction as item, report_count as value
from {{ ref('stg_reaction_counts') }}
where report_count < 0

union all

select 'stg_drug_reaction_pairs' as model, drug_name || ' / ' || reaction as item, pair_count as value
from {{ ref('stg_drug_reaction_pairs') }}
where pair_count < 0
