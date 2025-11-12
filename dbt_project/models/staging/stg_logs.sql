{{ config(materialized='table') }}

-- Reads partitioned parquet files from data/processed
with src as (
  select * from read_parquet('../data/processed/date=*/logs_*.parquet')
)
select
  cast(timestamp as timestamp)        as ts,
  cast(status as int)                 as status,
  cast(bytes_sent as bigint)          as bytes_sent,
  split_part(request_path,'?',1)      as endpoint,
  client_ip,
  user_agent,
  date(ts)                            as date,
  strftime(ts, '%H')                  as hour,
  case when status >= 400 then 1 else 0 end as is_error
from src
