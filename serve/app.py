# serve/app.py
from pathlib import Path
from datetime import datetime
import duckdb
import pandas as pd
import streamlit as st

# Resolve <project>/warehouse/warehouse.duckdb
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "warehouse" / "warehouse.duckdb"

@st.cache_resource
def get_con():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DuckDB not found at: {DB_PATH}")
    # read-only connection for the dashboard
    return duckdb.connect(str(DB_PATH), read_only=True)

@st.cache_data(show_spinner=False)
def available_dates():
    con = get_con()
    try:
        df = con.execute("select distinct date from fct_requests_hourly order by 1").fetchdf()
        return [str(d) for d in df["date"].tolist()]
    except duckdb.Error as e:
        raise RuntimeError(f"Query failed: {e}")

@st.cache_data(show_spinner=False)
def data_for_date(d: str) -> pd.DataFrame:
    con = get_con()
    q = """
        select hour, endpoint, requests, errors
        from fct_requests_hourly
        where date = ?
        order by hour, endpoint
    """
    return con.execute(q, [d]).fetchdf()

def main():
    st.set_page_config(page_title="Mini Log Warehouse", layout="wide")
    st.title("Mini Log Warehouse – Errors by Endpoint")

    try:
        dates = available_dates()
    except Exception as e:
        st.error(str(e))
        st.stop()

    if not dates:
        st.warning("No data available. Run ETL + dbt first.")
        st.stop()

    # pick most recent date by default
    default_idx = len(dates) - 1
    picked = st.selectbox("Date", dates, index=default_idx)

    df = data_for_date(picked)
    if df.empty:
        st.info("No rows for this date.")
        st.stop()

    # KPIs
    total_requests = int(df["requests"].sum())
    total_errors = int(df["errors"].sum())
    err_rate = (total_errors / total_requests) * 100 if total_requests else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Requests", f"{total_requests}")
    k2.metric("Errors", f"{total_errors}")
    k3.metric("Error rate", f"{err_rate:.1f}%")

    # Table
    st.subheader("Hourly breakdown")
    st.dataframe(df, use_container_width=True)

    # Simple pivot for chart
    pivot = (
        df.groupby("hour", as_index=False)
          .agg(errors=("errors", "sum"), requests=("requests", "sum"))
          .sort_values("hour")
    )
    st.subheader("Errors per hour")
    st.line_chart(pivot.set_index("hour")[["errors"]])

    st.caption(f"DB: {DB_PATH}")

if __name__ == "__main__":
    main()
