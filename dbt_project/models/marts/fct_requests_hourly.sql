with base as (
  select
    date,
    hour,
    endpoint,
    count(*) as requests,
    sum(is_error) as errors,
    percentile_cont(0.95) within group (order by bytes_sent) as p95_bytes
  from {{ ref('stg_logs') }}
  group by 1,2,3
)
select * from base
