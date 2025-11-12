select distinct endpoint from {{ ref('stg_logs') }}
