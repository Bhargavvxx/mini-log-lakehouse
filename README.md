

# Mini Log Lakehouse

End-to-end mini lakehouse for Nginx access logs.
Pipeline: raw logs → Pandas ETL → partitioned Parquet → DuckDB → dbt models (staging, dimensions, fact) → Prefect orchestration → FastAPI endpoints → Streamlit dashboard.

## Contents

* [Architecture](#architecture)
* [Repo structure](#repo-structure)
* [Prerequisites](#prerequisites)
* [Setup](#setup)
* [Data](#data)
* [ETL](#etl)
* [Warehouse and models (dbt + DuckDB)](#warehouse-and-models-dbt--duckdb)
* [Orchestration (Prefect)](#orchestration-prefect)
* [Serving (FastAPI API)](#serving-fastapi-api)
* [Dashboard (Streamlit)](#dashboard-streamlit)
* [Docs (dbt Docs)](#docs-dbt-docs)
* [Quality checks](#quality-checks)
* [Benchmarks](#benchmarks)
* [Troubleshooting](#troubleshooting)
* [Optional: API key auth](#optional-api-key-auth)
* [Optional: synthetic data generator](#optional-synthetic-data-generator)
* [Notes for resume/portfolio](#notes-for-resumeportfolio)
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
                                                --> API (FastAPI) / Streamlit
                                                    and dbt docs
Orchestration: Prefect runs ETL -> dbt run -> dbt test
```

## Repo structure

```
mini-log-warehouse-scaffold/
  data/
    raw/
      nginx_access.log          # input
    processed/
      date=YYYY-MM-DD/
        logs_YYYYMMDD.parquet   # ETL output
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
    ingest_logs.py              # parses nginx_access.log -> partitioned parquet
  orchestration/
    flow.py                     # Prefect: ETL -> dbt run -> dbt test
  serve/
    api.py                      # FastAPI endpoints
    app.py                      # Streamlit dashboard
  warehouse/
    warehouse.duckdb            # DuckDB file (created after first dbt run)
  scripts/
    generate_logs.py            # optional: synthesize more logs (if added)
  .venv/                        # Python venv (local)
  README.md
```

## Prerequisites

* Windows 10/11 (PowerShell)
* Python 3.10+
* Recommended: a virtual environment
* Packages: `duckdb`, `dbt-core`, `dbt-duckdb`, `pandas`, `prefect`, `fastapi`, `uvicorn`, `streamlit`

## Setup

From project root:

```powershell
# 1) Create and activate a venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2) Install dependencies
pip install -U pip
pip install duckdb dbt-core dbt-duckdb pandas prefect fastapi uvicorn streamlit

# 3) Ensure warehouse folder exists (dbt will write here)
mkdir .\warehouse -Force
```

## Data

Place your log lines in `data\raw\nginx_access.log`.
Example lines:

```
127.0.0.1 - - [10/Nov/2025:10:21:34 +0530] "GET /api/v1/items?id=42 HTTP/1.1" 200 1234 "-" "Mozilla/5.0"
127.0.0.1 - - [10/Nov/2025:10:22:01 +0530] "GET /api/v1/items?id=42 HTTP/1.1" 304 0 "-" "Mozilla/5.0"
127.0.0.1 - - [10/Nov/2025:11:01:12 +0530] "POST /auth/login HTTP/1.1" 401 512 "-" "Mozilla/5.0"
```

## ETL

Parses the raw log file and writes partitioned Parquet per date:

```powershell
python .\etl\ingest_logs.py
```

Output example:

```
data\processed\date=2025-11-10\logs_20251110.parquet
```

Two simple correctness checks are enforced in the ETL:

* At least one row parsed.
* HTTP status is in [100, 599].

## Warehouse and models (dbt + DuckDB)

All dbt commands are run from `dbt_project/`.
Profile is bundled; point `DBT_PROFILES_DIR` to that folder.

```powershell
cd .\dbt_project
$env:DBT_PROFILES_DIR = "$PWD"

# Build models (staging/dim/fact)
dbt run

# Run tests
dbt test
```

Models:

* `stg_logs` (table): materialized from partitioned Parquet
* `dim_client`, `dim_endpoint` (tables)
* `fct_requests_hourly` (table): grain = date, hour, endpoint with request and error counts

## Orchestration (Prefect)

Runs ETL → dbt run → dbt test:

```powershell
# From project root
python .\orchestration\flow.py
```

This uses your local venv’s dbt binary and the bundled profiles.

## Serving (FastAPI API)

Start the API on a free port (example: 8999):

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

Example response:

```json
{
  "date": "2025-11-10",
  "rows": [
    {"endpoint": "/api/v1/items", "errors": 1, "requests": 3},
    {"endpoint": "/auth/login",   "errors": 1, "requests": 1},
    {"endpoint": "/health",       "errors": 0, "requests": 1}
  ]
}
```

## Dashboard (Streamlit)

```powershell
streamlit run .\serve\app.py
```

Features:

* Date picker (defaults to most recent)
* KPIs: requests, errors, error rate
* Hourly table and simple error chart

## Docs (dbt Docs)

Generate and serve docs locally:

```powershell
cd .\dbt_project
$env:DBT_PROFILES_DIR = "$PWD"
dbt docs generate
dbt docs serve --host 127.0.0.1 --port 8021
```

Open the browser to view the lineage graph (staging → dims → fact).

## Quality checks

* SQL data tests in `dbt_project/models/tests/`:

  * `test_status_range.sql` fails any row with invalid HTTP status.
  * Not-null tests on key columns.
* ETL assertions ensure non-empty output and status range.

To add a minimal “has at least one row” test for the fact table:

```sql
-- dbt_project/models/tests/test_min_rows.sql
select * from {{ ref('fct_requests_hourly') }} limit 1
```

Run `dbt test` again.

## Benchmarks

Warm-cache latency measurement:

```powershell
@'
import time, statistics, duckdb
con = duckdb.connect("warehouse/warehouse.duckdb")
q = """select endpoint, sum(errors) as errors
       from fct_requests_hourly
       where date='2025-11-10'
       group by 1 order by errors desc"""
# warm-up
con.execute(q).fetchdf()
# measure 30 runs
times = []
for _ in range(30):
    t0 = time.perf_counter()
    con.execute(q).fetchdf()
    times.append(time.perf_counter() - t0)
print("avg (ms):", round(statistics.mean(times)*1000, 2))
print("p95 (ms):", round(statistics.quantiles(times, n=20)[18]*1000, 2))
'@ | python -
```

Example observed on local sample data: average ~1.7 ms, p95 ~2.74 ms.

## Troubleshooting

* **Port already in use** or **permission error**
  Check and change the port:

  ```powershell
  netstat -ano | findstr :8999
  python -m uvicorn serve.api:app --host 127.0.0.1 --port 8010
  ```

* **DuckDB file locked** on Windows
  Only one writer, multiple readers. Close any process that is holding `warehouse/warehouse.duckdb`:

  ```powershell
  taskkill /PID <pid> /F
  ```

  Stop Streamlit/API/dbt docs while running `dbt run` or `dbt docs generate`.

* **dbt cannot find project**
  Ensure you run dbt from `dbt_project/` and set:

  ```powershell
  $env:DBT_PROFILES_DIR = "$PWD"
  ```

* **API returns 401 Unauthorized**
  You are likely hitting a different process on another port. This API has no auth by default. Use the port where uvicorn is running (for example, `http://127.0.0.1:8999`).

## Optional: API key auth

If you want simple protection, add a header check in `serve/api.py`:

```python
from fastapi import Depends, Header

API_KEY = "change-me"

def require_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

Apply to routes:

```python
@app.get("/errors_by_endpoint", dependencies=[Depends(require_key)])
def errors_by_endpoint(...):
    ...

@app.get("/top_endpoints", dependencies=[Depends(require_key)])
def top_endpoints(...):
    ...
```

Call with:

```powershell
Invoke-RestMethod "http://127.0.0.1:8999/errors_by_endpoint?date=2025-11-10" -Headers @{ "x-api-key"="change-me" }
```

## Optional: synthetic data generator

Create `scripts/generate_logs.py`:

```python
import random, datetime as dt
from pathlib import Path

OUT = Path("data/raw/nginx_access.log")
endpoints = ["/api/v1/items","/auth/login","/health","/api/v1/cart","/api/v1/search"]
uas = ["Mozilla/5.0","curl/8.1.2","PostmanRuntime/7.36.1"]
statuses = [200,200,200,200,304,401,403,404,500,503]

def line(ts):
    ip = f"192.168.1.{random.randint(1,254)}"
    ep = random.choice(endpoints)
    if ep.endswith("items"):
        ep += f"?id={random.randint(1,999)}"
    st = random.choice(statuses)
    bytes_ = 0 if st == 304 else random.randint(100, 4000)
    ua = random.choice(uas)
    ts_str = ts.strftime("%d/%b/%Y:%H:%M:%S +0530")
    return f'{ip} - - [{ts_str}] "GET {ep} HTTP/1.1" {st} {bytes_} "-" "{ua}"\n'

if __name__ == "__main__":
    start = dt.datetime(2025, 11, 10, 9, 0, 0)
    with OUT.open("a", encoding="utf-8") as f:
        for _ in range(2000):
            ts = start + dt.timedelta(seconds=random.randint(0, 172800))
            f.write(line(ts))
    print("Appended ~2000 lines")
```

Run generator and rebuild:

```powershell
python .\scripts\generate_logs.py
python .\orchestration\flow.py
```

Re-benchmark and update the README numbers.

## Notes for resume/portfolio

* Built an end-to-end mini lakehouse with Python, DuckDB, and dbt.
* ETL to partitioned Parquet, modeled into staging/dim/fact.
* Orchestrated ETL → dbt run/test with Prefect.
* Served results via FastAPI and Streamlit.
* Data quality: status-range and not-null tests; all pass.
* Example performance on sample data: DuckDB warm query avg ~1.7 ms, p95 ~2.74 ms.



