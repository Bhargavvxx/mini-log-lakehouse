-- FAIL any row with invalid HTTP status code
select *
from {{ ref('stg_logs') }}
where status < 100 or status > 599
