{{ config(severity='warn') }}
-- Upstream keeps about two weeks of daily files. A gap means the job did not run in time and that window is lost.
select file_name, to_ts, next_from_ts
from (
    select file_name, to_ts, lead(from_ts) over (order by from_ts) as next_from_ts
    from {{ source('bronze', 'bronze_off_change_files') }}
)
where next_from_ts is not null and next_from_ts <> to_ts
