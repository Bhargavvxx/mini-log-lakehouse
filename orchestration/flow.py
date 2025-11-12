import os
import sys
import subprocess
from prefect import flow, task

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir))  # project root
DBT_DIR = os.path.join(PROJECT_ROOT, "dbt_project")

# Hardcode the dbt CLI found in your venv to avoid PATH/module issues
DBT_BIN = r"C:\Users\jaypr\Downloads\mini-log-warehouse-scaffold\.venv\Scripts\dbt.exe"

@task
def etl():
    print("[flow] ETL start")
    subprocess.check_call([sys.executable, os.path.join(PROJECT_ROOT, "etl", "ingest_logs.py")])
    print("[flow] ETL done")

@task
def dbt_build():
    print("[flow] dbt build start")
    env = os.environ.copy()
    env["DBT_PROFILES_DIR"] = DBT_DIR  # use bundled profiles.yml
    # Run from dbt_project folder; no --project-dir needed
    subprocess.check_call([DBT_BIN, "run"], cwd=DBT_DIR, env=env)
    subprocess.check_call([DBT_BIN, "test"], cwd=DBT_DIR, env=env)
    print("[flow] dbt build done")

@flow
def mini_log_warehouse_flow():
    etl()
    dbt_build()

if __name__ == "__main__":
    mini_log_warehouse_flow()
