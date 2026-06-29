-- stg_events — cleaned, typed top-level fields from the sample adverse-event records.
--
-- We pull a handful of clean top-level fields and a couple of useful values out
-- of the nested `record` JSON using DuckDB's JSON accessors. We deliberately do
-- NOT flatten the whole nested structure (reactions, drugs arrays) — that stays
-- in `record` for a later stage. Staging just makes the headline fields usable.
--
-- openFDA field notes:
--   serious:     '1' = serious, '2' = non-serious  -> cast to a boolean
--   receivedate: 'YYYYMMDD' string                 -> parse to a real DATE
--   patientsex:  '1' = Male, '2' = Female, else Unknown

select
    safetyreportid                                   as safety_report_id,

    -- Parse the YYYYMMDD string into a DATE. try_strptime yields NULL instead of
    -- erroring if a value is ever malformed.
    try_strptime(received_date_raw, '%Y%m%d')::date  as received_date,

    -- '1' means serious; anything else (e.g. '2') is non-serious.
    (serious = '1')                                  as is_serious,

    -- Reporter country is a clean top-level field inside the record JSON.
    record ->> '$.primarysourcecountry'              as reporter_country,

    -- Patient sex lives under patient.patientsex; decode the numeric code.
    case record ->> '$.patient.patientsex'
        when '1' then 'Male'
        when '2' then 'Female'
        else 'Unknown'
    end                                              as patient_sex

from (
    select
        safetyreportid,
        serious,
        receivedate as received_date_raw,
        record
    from {{ source('raw', 'raw_sample_events') }}
)
where safetyreportid is not null
