-- mart_drug_reaction_signals — Proportional Reporting Ratio (PRR) per drug-reaction pair.
--
-- PRR compares how often a reaction is reported FOR THIS DRUG versus for all
-- OTHER drugs, so a high PRR means the reaction is disproportionately associated
-- with the drug (a candidate safety SIGNAL — not proof of causation; see _marts.yml).
--
--     PRR = ( a / (a + c) ) / ( b / (b + d) )
--
-- where a/b/c/d come from int_pair_stats, which builds them from UNIQUE REPORT
-- COUNTS (see that model for why summing pair_count was wrong and inflated PRR):
--     a / (a + c) = reaction rate among THIS drug's reports
--     b / (b + d) = reaction rate among all OTHER drugs' reports (whole-DB background)
--
-- CONTINUITY CORRECTION: we add the standard Haldane-Anscombe 0.5 to every cell
-- so PRR stays defined and strictly positive even if a future re-ingestion yields
-- a zero cell. With the report-count marginals the counts are large, so this
-- barely moves PRR — it is just a safety guard (the current data has no zero cells).

with stats as (

    select * from {{ ref('int_pair_stats') }}

),

prr_calc as (

    select
        drug_name,
        reaction,
        pair_count,
        a,
        b,
        c,
        d,
        -- Haldane-Anscombe: +0.5 per cell  =>  (a+c) becomes (a+c+1), etc.
        (
            (a + 0.5) / (a + c + 1.0)
        ) / (
            (b + 0.5) / (b + d + 1.0)
        ) as prr_raw
    from stats

)

select
    drug_name,
    reaction,
    pair_count,
    round(prr_raw, 2) as prr,

    -- A pair is flagged is_signal only when it is BOTH disproportionate AND
    -- well-supported:
    --   prr_raw >= 2     -> the reaction is disproportionately reported for this drug
    --   pair_count >= 50 -> there are enough reports for that ratio to be trusted
    --
    -- WHY THE COUNT FLOOR (50, not just 3): PRR is a ratio, and with a tiny
    -- numerator count the denominator side is also tiny, so a single extra report
    -- can swing PRR wildly (the small-denominator / small-sample effect). High PRR
    -- on a low-count pair is therefore statistically fragile. Requiring >= 50
    -- reports keeps only signals that are substantiated by report volume, not
    -- artifacts of sparse data. Raw prr and pair_count remain on every row, so
    -- low-count pairs are still visible for inspection — they are simply not
    -- flagged as substantiated signals.
    (pair_count >= 50 and prr_raw >= 2.0) as is_signal

from prr_calc

-- Strongest candidates first: flagged signals on top, then by PRR, then by volume.
order by
    is_signal desc,
    prr desc,
    pair_count desc
