select distinct client_ip as client_id, user_agent from {{ ref('stg_logs') }}
