.PHONY: etl dbt api app

etl:
	python etl/ingest_logs.py

dbt:
	export DBT_PROFILES_DIR=./dbt_project && dbt --project-dir ./dbt_project run && dbt --project-dir ./dbt_project test

api:
	uvicorn serve.api:app --reload --port 8080

app:
	streamlit run serve/app.py
