.PHONY: install schema ingest-latest status recompute test

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
