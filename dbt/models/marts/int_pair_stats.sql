-- int_pair_stats — the 2x2 contingency components (a, b, c, d) for each
-- drug-reaction pair, built from UNIQUE REPORT COUNTS.
--
--                       this reaction      other reactions
--   this drug                 a                  c
--   all other drugs           b                  d
--
-- WHY NOT SUM pair_count (the previous, broken approach):
--   openFDA's per-drug reaction aggregation counts REPORTS per reaction, and one
--   report usually lists several reactions. So summing pair_count over a drug's
--   reactions counts each report many times — it is NOT the drug's report total.
--   Using those sums as the marginals (a+c, a+b, a+b+c+d) inflated the
--   denominators and, because the reaction "background" b was taken over only the
--   ~75 analyzed drugs, drove b to ~0 and PRR to absurd values (20,000+).
--
-- THE FIX — use openFDA's report-level counts, which are mutually consistent
-- (all count REPORTS over the same receivedate window):
--   a   = pair_count                         (reports with THIS drug AND reaction)
--   a+c = stg_drug_counts.report_count       (all reports for THIS drug)
--   a+b = stg_reaction_counts.report_count   (all reports for THIS reaction, whole DB)
--   N   = stg_report_totals.total_reports    (all reports in the window) = a+b+c+d
-- then c = (a+c) - a,  b = (a+b) - a,  d = N - a - b - c.
--
-- SCOPE LIMITATION: a reaction's whole-DB background (a+b) is only known for
-- reactions in the ingested top-1000 reaction list. Pairs whose reaction is not
-- in that list are dropped here (inner join) because PRR is not computable without
-- a background frequency. All ~75 analyzed drugs are in the drug-count list, so no
-- drug is dropped. See _marts.yml.

with pairs as (

    select drug_name, reaction, pair_count
    from {{ ref('stg_drug_reaction_pairs') }}

),

drug_reports as (

    -- a + c : total reports for the drug (unique reports, not summed reactions)
    select drug_name, report_count as drug_report_count
    from {{ ref('stg_drug_counts') }}

),

reaction_reports as (

    -- a + b : total reports for the reaction across the whole database
    select reaction, report_count as reaction_report_count
    from {{ ref('stg_reaction_counts') }}

),

total as (

    -- a + b + c + d : total reports in the window
    select total_reports from {{ ref('stg_report_totals') }}

)

select
    p.drug_name,
    p.reaction,
    p.pair_count,
    dr.drug_report_count,
    rr.reaction_report_count,
    t.total_reports,

    -- a: this drug WITH this reaction
    p.pair_count                                                   as a,
    -- b: all OTHER drugs WITH this reaction
    rr.reaction_report_count - p.pair_count                        as b,
    -- c: this drug WITHOUT this reaction
    dr.drug_report_count - p.pair_count                            as c,
    -- d: all OTHER drugs WITHOUT this reaction (N - a - b - c)
    t.total_reports - dr.drug_report_count
        - rr.reaction_report_count + p.pair_count                  as d

from pairs p
join drug_reports dr     on dr.drug_name = p.drug_name
join reaction_reports rr on rr.reaction = p.reaction
cross join total t
