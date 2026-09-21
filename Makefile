.PHONY: install schema ingest-latest status recompute test analytics detect-coinjoin resolve-entities detect-peel detect-smurf load-ofac screen-ofac compute-risk run-api run-web web-install

install:
	pip install -r requirements.txt
	pip install -e .

schema:
	python -m btc_aml.cli schema

ingest-latest:
	python -m btc_aml.cli ingest-latest --limit 10

status:
	python -m btc_aml.cli status

recompute:
	python -m btc_aml.cli recompute

test:
	pytest

analytics:
	python -m btc_aml.cli run-analytics

detect-coinjoin:
	python -m btc_aml.cli detect-coinjoin

resolve-entities:
	python -m btc_aml.cli resolve-entities

detect-peel:
	python -m btc_aml.cli detect-peel

detect-smurf:
	python -m btc_aml.cli detect-smurf

load-ofac:
	python -m btc_aml.cli load-ofac --csv data/ofac/sdn_advanced.csv

screen-ofac:
	python -m btc_aml.cli screen-ofac --limit 2000

compute-risk:
	python -m btc_aml.cli compute-risk
run-api:
	uvicorn api.main:app --reload --port 8000

web-install:
	cd web && npm install

run-web:
	cd web && npm run dev
