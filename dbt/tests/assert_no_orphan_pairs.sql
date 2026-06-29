-- REFERENTIAL INTEGRITY: every drug in the pairs must exist in stg_drug_counts.
--
-- The pair data and the drug counts come from the same openFDA source and are
-- cleaned the same way (trim + uppercase), so each drug_name in the pairs should
-- join to a drug-count row. An orphan signals a key/cleaning mismatch that would
-- silently drop the drug from PRR (its a+c marginal). Returns orphans; empty = OK.

select p.drug_name
from {{ ref('stg_drug_reaction_pairs') }} p
left join {{ ref('stg_drug_counts') }} d
    on d.drug_name = p.drug_name
where d.drug_name is null
group by p.drug_name
