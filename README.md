

# Mini Log Lakehouse

End-to-end mini lakehouse for Nginx access logs.
Pipeline: raw logs → Pandas ETL → partitioned Parquet → DuckDB → dbt models (staging, dimensions, fact) → Prefect orchestration → FastAPI endpoints → Streamlit dashboard.

## Table of Contents

* [Architecture](#architecture)
* [Repository Structure](#repository-structure)
* [Prerequisites](#prerequisites)
* [Setup](#setup)
* [Data](#data)
* [ETL](#etl)
* [Warehouse & Models (dbt + DuckDB)](#warehouse--models-dbt--duckdb)
* [Orchestration (Prefect)](#orchestration-prefect)
* [Serving (FastAPI)](#serving-fastapi)
* [Dashboard (Streamlit)](#dashboard-streamlit)
* [Docs (dbt Docs)](#docs-dbt-docs)
* [Quality Checks](#quality-checks)
* [Benchmarks](#benchmarks)
* [Troubleshooting](#troubleshooting)
* [License](#license)

## Architecture

```
Raw Nginx Logs  -->  ETL (Python)  -->  Parquet (partitioned by date)
                                   \
                                    --> DuckDB (file)
                                         \
                                          --> dbt models: stg_logs (table),
                                              dim_client, dim_endpoint (tables),
                                              fct_requests_hourly (table)
                                               \
                                                --> FastAPI / Streamlit
                                                    and dbt docs
Orchestration: Prefect runs ETL -> dbt run -> dbt test
```

## Repository Structure

```
mini-log-lakehouse/
  data/
    raw/
      nginx_access.log
    processed/
      date=YYYY-MM-DD/
        logs_YYYYMMDD.parquet
  dbt_project/
    models/
      staging/stg_logs.sql
      marts/dim_client.sql
      marts/dim_endpoint.sql
      marts/fct_requests_hourly.sql
      tests/test_status_range.sql
    profiles.yml
    dbt_project.yml
  etl/
    ingest_logs.py
  orchestration/
    flow.py
  serve/
    api.py
    app.py
  warehouse/
    warehouse.duckdb            # created after first dbt run
  README.md
```

## Prerequisites

* Windows 10/11 (PowerShell)
* Python 3.10+
* Recommended: virtual environment
* Python packages: `duckdb`, `dbt-core`, `dbt-duckdb`, `pandas`, `prefect`, `fastapi`, `uvicorn`, `streamlit`

## Setup

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install duckdb dbt-core dbt-duckdb pandas prefect fastapi uvicorn streamlit
mkdir .\warehouse -Force
```

## Data

Place Nginx access log lines in `data\raw\nginx_access.log`. Example:

```
127.0.0.1 - - [10/Nov/2025:10:21:34 +0530] "GET /api/v1/items?id=42 HTTP/1.1" 200 1234 "-" "Mozilla/5.0"
127.0.0.1 - - [10/Nov/2025:10:22:01 +0530] "GET /api/v1/items?id=42 HTTP/1.1" 304 0 "-" "Mozilla/5.0"
127.0.0.1 - - [10/Nov/2025:11:01:12 +0530] "POST /auth/login HTTP/1.1" 401 512 "-" "Mozilla/5.0"
```

## ETL

Parse raw logs and write partitioned Parquet by date:

```powershell
python .\etl\ingest_logs.py
```

Outputs under `data\processed\date=YYYY-MM-DD\logs_YYYYMMDD.parquet`.

Built-in validations:

* Non-empty output.
* HTTP status enforced to be in `[100, 599]`.

## Warehouse & Models (dbt + DuckDB)

All dbt commands run from `dbt_project/` with the bundled profile.

```powershell
cd .\dbt_project
$env:DBT_PROFILES_DIR = "$PWD"

dbt run      # builds stg_logs, dim_*, fct_requests_hourly
dbt test     # executes data tests
```

Models:

* `stg_logs` (table): from partitioned Parquet.
* `dim_client`, `dim_endpoint` (tables).
* `fct_requests_hourly` (table): grain = (date, hour, endpoint) with `requests`, `errors`.

## Orchestration (Prefect)

Run ETL → dbt run → dbt test in one flow:

```powershell
python .\orchestration\flow.py
```

## Serving (FastAPI)

Start the API (choose a free port, e.g., 8999):

```powershell
python -m uvicorn serve.api:app --host 127.0.0.1 --port 8999
```

Endpoints:

* `GET /health`
* `GET /errors_by_endpoint?date=YYYY-MM-DD`
* `GET /top_endpoints?date=YYYY-MM-DD&limit=10`

Example:

```powershell
Invoke-RestMethod "http://127.0.0.1:8999/errors_by_endpoint?date=2025-11-10"
```

## Dashboard (Streamlit)

```powershell
streamlit run .\serve\app.py
```

Features:

* Date selector (defaults to most recent).
* KPIs: requests, errors, error rate.
* Hourly table and error trend chart.

## Docs (dbt Docs)

```powershell
cd .\dbt_project
$env:DBT_PROFILES_DIR = "$PWD"
dbt docs generate
dbt docs serve --host 127.0.0.1 --port 8021
```

Open the browser to view lineage (staging → dimensions → fact).

## Quality Checks

* SQL tests under `dbt_project/models/tests/`:

  * `test_status_range.sql` validates HTTP status range.
  * Not-null tests on key columns.
* ETL assertions ensure non-empty output and valid status codes.

## Benchmarks

Warm-cache latency example (PowerShell here-string):

```powershell
@'
import time, statistics, duckdb
con = duckdb.connect("warehouse/warehouse.duckdb")
q = """select endpoint, sum(errors) as errors
       from fct_requests_hourly
       where date='2025-11-10'
       group by 1 order by errors desc"""
con.execute(q).fetchdf()  # warm-up
times = []
for _ in range(30):
    t0 = time.perf_counter()
    con.execute(q).fetchdf()
    times.append(time.perf_counter() - t0)
print("avg (ms):", round(statistics.mean(times)*1000, 2))
print("p95 (ms):", round(statistics.quantiles(times, n=20)[18]*1000, 2))
'@ | python -
```

## Troubleshooting

* **Port in use / permission error**

  ```powershell
  netstat -ano | findstr :8999
  python -m uvicorn serve.api:app --host 127.0.0.1 --port 8010
  ```
* **DuckDB file locked (Windows)**
  Close processes holding `warehouse/warehouse.duckdb` (e.g., API/Streamlit/dbt docs):

  ```powershell
  taskkill /PID <pid> /F
  ```
* **dbt cannot find project**
  Run from `dbt_project/` and set:

  ```powershell
  $env:DBT_PROFILES_DIR = "$PWD"
  ```

## License

MIT.
