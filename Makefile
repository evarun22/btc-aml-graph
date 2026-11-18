PYTHON ?= python
UVICORN ?= uvicorn
COMPOSE ?= docker compose

RANGE_START ?= 960000
RANGE_END ?= 960999

MONITOR_INTERVAL ?= 600
MONITOR_LIMIT ?= 10
ANALYTICS_EVERY ?= 100

API_PORT ?= 8010
WEB_PORT ?= 3000

STATE_DIR ?= .state
LOG_DIR ?= logs

.PHONY: help install up down ps logs schema status recompute test lint analytics \
	ingest-latest ingest-range backfill backfill-100 backfill-1000 backfill-5000 \
	load-ofac monitor monitor-once monitor-bg stop-monitor api web web-build \
	reset clean demo live compose-up compose-down compose-logs monitor-service stop-monitor-service

help: ## Show available Makefile commands
	@echo "Bitcoin AML Graph Intelligence Platform"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e .

up: ## Start Neo4j
	$(COMPOSE) up -d neo4j

down: ## Stop Neo4j
	$(COMPOSE) down

ps: ## Show Docker Compose process status
	$(COMPOSE) ps

logs: ## Tail Neo4j logs
	$(COMPOSE) logs -f neo4j

schema: ## Create Neo4j constraints and indexes
	$(PYTHON) -m btc_aml.cli schema

status: ## Show pipeline status and data quality
	$(PYTHON) -m btc_aml.cli status

recompute: ## Recompute address metrics
	$(PYTHON) -m btc_aml.cli recompute

test: ## Run backend tests
	$(PYTHON) -m pytest -q

lint: ## Run Ruff linting
	ruff check api tests scripts

analytics: ## Run full analytics pipeline
	$(PYTHON) -m btc_aml.cli run-analytics

ingest-latest: ## Ingest the latest blocks
	$(PYTHON) -m btc_aml.cli ingest-latest --limit 10

ingest-range: ## Ingest a block range using RANGE_START and RANGE_END
	$(PYTHON) -m btc_aml.cli ingest-blocks --start $(RANGE_START) --end $(RANGE_END) --allow-historical

backfill: ## Backfill RANGE_START-RANGE_END, recompute, analyze, and show status
	$(MAKE) ingest-range RANGE_START=$(RANGE_START) RANGE_END=$(RANGE_END)
	$(MAKE) recompute
	$(MAKE) analytics
	$(MAKE) status

backfill-100: ## Backfill 100 blocks
	$(MAKE) backfill RANGE_START=960000 RANGE_END=960099

backfill-1000: ## Backfill 1000 blocks
	$(MAKE) backfill RANGE_START=960000 RANGE_END=960999

backfill-5000: ## Backfill 5000 blocks
	$(MAKE) backfill RANGE_START=960000 RANGE_END=964999

load-ofac: ## Load OFAC sanctioned addresses into Neo4j
	$(PYTHON) -m btc_aml.cli load-ofac --csv data/ofac/sdn_advanced.csv

monitor: ## Run monitor in foreground
	$(PYTHON) -m btc_aml.cli monitor --interval $(MONITOR_INTERVAL) --limit $(MONITOR_LIMIT) --analytics-every $(ANALYTICS_EVERY)

monitor-once: ## Run one monitor iteration for testing
	$(PYTHON) -m btc_aml.cli monitor --interval 1 --limit 10 --analytics-every 0 --max-iterations 1

monitor-bg: ## Start background monitor and save PID
	mkdir -p $(STATE_DIR) $(LOG_DIR)
	nohup $(PYTHON) -m btc_aml.cli monitor --interval $(MONITOR_INTERVAL) --limit $(MONITOR_LIMIT) --analytics-every $(ANALYTICS_EVERY) > $(LOG_DIR)/monitor.log 2>&1 & echo $$! > $(STATE_DIR)/monitor.pid

stop-monitor: ## Stop background monitor using PID file
	@if [ -f $(STATE_DIR)/monitor.pid ]; then \
		kill `cat $(STATE_DIR)/monitor.pid` 2>/dev/null || true; \
		rm -f $(STATE_DIR)/monitor.pid; \
		echo "Monitor stopped."; \
	else \
		echo "No monitor PID file found."; \
	fi

api: ## Run FastAPI backend locally
	$(UVICORN) api.main:app --reload --port $(API_PORT)

web: ## Run Next.js dashboard locally
	cd web && npm run dev

web-build: ## Build Next.js dashboard for production
	cd web && npm run build

reset: ## Reset Neo4j database
	$(PYTHON) -m btc_aml.cli reset --confirm

clean: ## Remove local state and logs
	rm -rf $(STATE_DIR) $(LOG_DIR)

demo: ## One-command real-data demo setup
	$(MAKE) up
	$(MAKE) schema
	$(MAKE) load-ofac
	$(MAKE) backfill-1000
	$(MAKE) status

live: ## Populate data and start background monitor
	$(MAKE) demo
	$(MAKE) monitor-bg

compose-up: ## Build and start full Docker stack
	$(COMPOSE) up -d --build

compose-down: ## Stop full Docker stack
	$(COMPOSE) down

compose-logs: ## Tail full Docker stack logs
	$(COMPOSE) logs -f

monitor-service: ## Start monitor as Docker Compose service
	$(COMPOSE) --profile monitor up -d --build monitor

stop-monitor-service: ## Stop monitor Docker Compose service
	$(COMPOSE) --profile monitor stop monitor
