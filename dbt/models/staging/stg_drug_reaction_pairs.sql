-- stg_drug_reaction_pairs — cleaned drug-reaction co-occurrence counts.
--
-- One row per (drug, reaction): how many reports name that reaction for that
-- drug. Light cleanup only: standardize drug_name the same way as
-- stg_drug_counts (trim + uppercase) so the two models join cleanly later, trim
-- the reaction, cast the count to an integer, and drop rows missing either key.
-- The disproportionality math (PRR/ROR) comes in Stage 4b.

select
    upper(trim(drug))             as drug_name,
    trim(reaction)                as reaction,
    cast(pair_count as integer)   as pair_count
from {{ source('raw', 'raw_drug_reaction_pairs') }}
where drug is not null
  and trim(drug) <> ''
  and reaction is not null
  and trim(reaction) <> ''
