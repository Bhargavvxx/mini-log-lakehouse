# serve/api.py
from fastapi import FastAPI, HTTPException, Query
from datetime import datetime
from pathlib import Path
import duckdb

app = FastAPI(title="Mini Log Warehouse API")

# Resolve DB path relative to the repo root: <project>/warehouse/warehouse.duckdb
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "warehouse" / "warehouse.duckdb"

def get_con():
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"DuckDB not found at: {DB_PATH}")
    # read-only connection is fine for serving
    return duckdb.connect(str(DB_PATH))

@app.get("/health")
def health():
    return {"status": "ok", "db_path": str(DB_PATH)}

@app.get("/errors_by_endpoint")
def errors_by_endpoint(date: str = Query(..., description="YYYY-MM-DD")):
    # basic validation
    try:
        dt = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    con = get_con()
    try:
        q = """
            SELECT endpoint,
                   SUM(errors)   AS errors,
                   SUM(requests) AS requests
            FROM fct_requests_hourly
            WHERE date = ?
            GROUP BY 1
            ORDER BY errors DESC, requests DESC
        """
        rows = con.execute(q, [str(dt)]).fetchall()
        return {"date": str(dt), "rows": [{"endpoint": r[0], "errors": r[1], "requests": r[2]} for r in rows]}
    except duckdb.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        con.close()


@app.get("/top_endpoints")
def top_endpoints(
    date: str = Query(..., description="YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=100)
):
    from datetime import datetime
    try:
        _ = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    con = get_con()
    try:
        q = """
        SELECT endpoint,
               SUM(requests) AS requests,
               SUM(errors)   AS errors
        FROM fct_requests_hourly
        WHERE date = ?
        GROUP BY 1
        ORDER BY requests DESC, errors DESC
        LIMIT ?
        """
        rows = con.execute(q, [date, limit]).fetchall()
        return {"date": date, "rows": [{"endpoint": r[0], "requests": r[1], "errors": r[2]} for r in rows]}
    finally:
        con.close()
