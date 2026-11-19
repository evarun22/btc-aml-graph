SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -ec

PYTHON ?= .venv/bin/python
UVICORN ?= .venv/bin/uvicorn
COMPOSE ?= docker compose
CLI = $(PYTHON) -m btc_aml.cli

RANGE_START ?= 960000
RANGE_END ?= 960999

MONITOR_INTERVAL ?= 600
MONITOR_LIMIT ?= 10
ANALYTICS_EVERY ?= 100

API_PORT ?= 8010
WEB_PORT ?= 3000

STATE_DIR ?= .state
LOG_DIR ?= logs
TS = $(shell date +%Y%m%d-%H%M%S)

# --- pre-flight gate -------------------------------------------------------
GUARD ?= 1                    # GUARD=0 to override deliberately
GUARD_MIN_GIB ?= 48
LLAMA_SERVICE ?= llama-server.service
# ---------------------------------------------------------------------------

SMURF_MAX_PAIRS ?= 20
SMURF_MAX_DEPTH ?= 4
OFAC_LIMIT ?= 500
PEEL_MIN_BTC ?= 1.0

.PHONY: help install up down ps logs schema status recompute test lint \
	guard analytics analytics-staged detect-coinjoin resolve-entities detect-peel \
	detect-smurf screen-ofac screen-ofac-alerts compute-risk \
	ingest-latest ingest-range backfill backfill-100 backfill-1000 backfill-5000 \
	load-ofac monitor monitor-once monitor-bg stop-monitor api web web-build web-start \
	reset clean demo live compose-up compose-down compose-logs \
	monitor-service stop-monitor-service \
	ai-stop ai-start ai-status ai-logs mem watch \
	maintenance-install maintenance-run maintenance-full maintenance-status

help: ## Show available Makefile commands
	@echo "Bitcoin AML Graph Intelligence Platform"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

guard: ## Refuse heavy jobs unless llama-server is stopped and memory is free
	@if [ "$(GUARD)" = "1" ]; then \
		if systemctl is-active --quiet $(LLAMA_SERVICE) 2>/dev/null; then \
			echo "ABORT: $(LLAMA_SERVICE) is active. Run: sudo systemctl stop $(LLAMA_SERVICE)  (or: make ai-stop)"; \
			exit 1; \
		fi; \
		avail=$$(awk '/MemAvailable/{print int($$2/1048576)}' /proc/meminfo); \
		echo "MemAvailable: $${avail} GiB"; \
		if [ "$$avail" -lt $(GUARD_MIN_GIB) ]; then \
			echo "ABORT: need >= $(GUARD_MIN_GIB) GiB available (override with GUARD=0)"; exit 1; \
		fi; \
		echo "Preflight OK"; \
	else \
		echo "Preflight SKIPPED (GUARD=0) - you are on your own"; \
	fi

mem: ## Show memory, swap and top RSS consumers
	@free -h; echo; swapon --show; echo; ps aux --sort=-rss | head -10

watch: ## 5s memory / llama / neo4j watch (run in a second terminal)
	@watch -n 5 'free -h; echo; systemctl is-active $(LLAMA_SERVICE); echo; docker stats --no-stream btc-aml-neo4j'

ai-stop: ## Stop the local LLM so heavy ingest/analytics can run
	sudo systemctl stop $(LLAMA_SERVICE)
	-sudo systemctl reset-failed $(LLAMA_SERVICE)
	@systemctl is-active $(LLAMA_SERVICE) || true; free -h

ai-start: ## Start the local LLM (AI features / screenshots only - never with analytics)
	sudo systemctl start $(LLAMA_SERVICE)
	@sleep 3; systemctl is-active $(LLAMA_SERVICE) || true

ai-status: ## LLM service state, memory headroom, and the exact model id for .env
	@printf '%s: %s\n' "$(LLAMA_SERVICE)" "$$(systemctl is-active $(LLAMA_SERVICE) 2>/dev/null || true)"; \
	awk '/MemTotal|MemAvailable/{printf "%s %.1f GiB\n", $$1, $$2/1048576}' /proc/meminfo; \
	if systemctl is-active --quiet $(LLAMA_SERVICE) 2>/dev/null; then \
		curl -s --http1.1 -H 'Accept: application/json' -H 'Accept-Encoding: identity' \
			http://127.0.0.1:8080/v1/models | head -c 500; echo; \
	fi

ai-logs: ## Tail llama-server journal
	sudo journalctl -u $(LLAMA_SERVICE) -f

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
	$(CLI) schema

status: ## Show pipeline status and data quality
	$(CLI) status

test: ## Run backend tests
	$(PYTHON) -m pytest -q

lint: ## Run Ruff linting
	ruff check api tests scripts

# ---- staged analytics (use these instead of the full pipeline) -------------
recompute: guard ## Recompute address metrics
	@mkdir -p $(LOG_DIR)
	$(CLI) recompute 2>&1 | tee $(LOG_DIR)/recompute-$(TS).log

detect-coinjoin: guard ## Stage 2: CoinJoin / mixer detection
	@mkdir -p $(LOG_DIR)
	$(CLI) detect-coinjoin 2>&1 | tee $(LOG_DIR)/detect-coinjoin-$(TS).log

resolve-entities: guard ## Stage 3: CIOH entity resolution (expensive, ~10-25 min)
	@mkdir -p $(LOG_DIR)
	$(CLI) resolve-entities 2>&1 | tee $(LOG_DIR)/resolve-entities-$(TS).log

detect-peel: guard ## Stage 4: peel chain detection
	@mkdir -p $(LOG_DIR)
	$(CLI) detect-peel --min-starting-btc $(PEEL_MIN_BTC) 2>&1 | tee $(LOG_DIR)/detect-peel-$(TS).log

detect-smurf: guard ## Stage 5: fan-out/fan-in smurfing (SMURF_MAX_PAIRS / SMURF_MAX_DEPTH)
	@mkdir -p $(LOG_DIR)
	$(CLI) detect-smurf --max-pairs $(SMURF_MAX_PAIRS) --max-depth $(SMURF_MAX_DEPTH) 2>&1 | tee $(LOG_DIR)/detect-smurf-$(TS).log

screen-ofac-alerts: guard ## Stage 6a: OFAC proximity for already-flagged addresses
	@mkdir -p $(LOG_DIR)
	$(CLI) screen-ofac --alert-addresses 2>&1 | tee $(LOG_DIR)/screen-ofac-alerts-$(TS).log

screen-ofac: guard ## Stage 6b: OFAC proximity sweep (OFAC_LIMIT, keep 200-500)
	@mkdir -p $(LOG_DIR)
	$(CLI) screen-ofac --limit $(OFAC_LIMIT) 2>&1 | tee $(LOG_DIR)/screen-ofac-$(TS).log

compute-risk: guard ## Stage 7: address + entity risk scoring
	@mkdir -p $(LOG_DIR)
	$(CLI) compute-risk 2>&1 | tee $(LOG_DIR)/compute-risk-$(TS).log

analytics-staged: guard ## Tail stages only: smurf -> OFAC -> risk -> status
	$(MAKE) detect-smurf SMURF_MAX_PAIRS=$(SMURF_MAX_PAIRS) SMURF_MAX_DEPTH=$(SMURF_MAX_DEPTH)
	$(MAKE) screen-ofac-alerts
	$(MAKE) screen-ofac OFAC_LIMIT=$(OFAC_LIMIT)
	$(MAKE) compute-risk
	$(MAKE) status

analytics: guard ## Run the FULL analytics pipeline (rebuilds entities - slow)
	@mkdir -p $(LOG_DIR)
	$(CLI) run-analytics 2>&1 | tee $(LOG_DIR)/run-analytics-$(TS).log

load-ofac: ## Load OFAC sanctioned addresses into Neo4j
	$(CLI) load-ofac --csv data/ofac/sdn_advanced.csv

# ---- ingestion ------------------------------------------------------------
ingest-latest: guard ## Ingest the latest blocks
	@mkdir -p $(LOG_DIR)
	$(CLI) ingest-latest --limit 10 2>&1 | tee $(LOG_DIR)/ingest-latest-$(TS).log

ingest-range: guard ## Ingest RANGE_START-RANGE_END (does NOT resume; rerun last block is safe)
	@mkdir -p $(LOG_DIR)
	$(CLI) ingest-blocks --start $(RANGE_START) --end $(RANGE_END) --allow-historical 2>&1 | tee $(LOG_DIR)/ingest-range-$(RANGE_START)-$(RANGE_END)-$(TS).log

backfill: guard ## Backfill RANGE_START-RANGE_END, recompute, analyze, status
	$(MAKE) ingest-range RANGE_START=$(RANGE_START) RANGE_END=$(RANGE_END)
	$(MAKE) recompute
	$(MAKE) analytics
	$(MAKE) status

backfill-100: ## Backfill 100 blocks (fixed range)
	$(MAKE) backfill RANGE_START=960000 RANGE_END=960099

backfill-1000: ## Backfill 1000 blocks (fixed range)
	$(MAKE) backfill RANGE_START=960000 RANGE_END=960999

backfill-5000: ## Backfill 5000 blocks (fixed range; only after analytics is green)
	$(MAKE) backfill RANGE_START=960000 RANGE_END=964999

# ---- monitor --------------------------------------------------------------
monitor: guard ## Run monitor in foreground
	$(CLI) monitor --interval $(MONITOR_INTERVAL) --limit $(MONITOR_LIMIT) --analytics-every $(ANALYTICS_EVERY)

monitor-once: ## Run one monitor iteration for testing
	$(CLI) monitor --interval 1 --limit 10 --analytics-every 0 --max-iterations 1

monitor-bg: guard ## Start background monitor (use ANALYTICS_EVERY=0 while llama is up)
	@mkdir -p $(STATE_DIR) $(LOG_DIR)
	nohup $(CLI) monitor --interval $(MONITOR_INTERVAL) --limit $(MONITOR_LIMIT) --analytics-every $(ANALYTICS_EVERY) > $(LOG_DIR)/monitor.log 2>&1 & echo $$! > $(STATE_DIR)/monitor.pid
	@echo "monitor pid $$(cat $(STATE_DIR)/monitor.pid) -> $(LOG_DIR)/monitor.log"

stop-monitor: ## Stop background monitor using PID file
	@if [ -f $(STATE_DIR)/monitor.pid ]; then \
		kill `cat $(STATE_DIR)/monitor.pid` 2>/dev/null || true; \
		rm -f $(STATE_DIR)/monitor.pid; echo "Monitor stopped."; \
	else echo "No monitor PID file found."; fi

# ---- apps -----------------------------------------------------------------
api: ## Run FastAPI backend locally on :$(API_PORT)
	$(UVICORN) api.main:app --reload --port $(API_PORT)

web: ## Run Next.js dashboard in dev mode
	cd web && npm run dev

web-build: ## Build Next.js dashboard for production
	cd web && npm run build

web-start: ## Serve the production build on :$(WEB_PORT)
	cd web && npm run start

# ---- scheduled maintenance window ----------------------------------------
maintenance-install: ## Install the analytics maintenance units + timers
	sudo cp deploy/btc-aml-analytics*.service deploy/btc-aml-analytics*.timer /etc/systemd/system/
	sudo chmod +x scripts/scheduled_analytics.sh
	sudo systemctl daemon-reload
	sudo systemctl enable --now btc-aml-analytics.timer btc-aml-analytics-full.timer
	systemctl list-timers 'btc-aml-*'

maintenance-run: ## Run the staged maintenance window now (stops llama, restores it after)
	sudo systemctl start btc-aml-analytics.service

maintenance-full: ## Run the full window incl. CIOH rebuild now
	sudo systemctl start btc-aml-analytics-full.service

maintenance-status: ## Timers, last result and journal for the maintenance window
	@systemctl list-timers 'btc-aml-*' --all; echo; \
	systemctl status btc-aml-analytics.service --no-pager -n 20 || true

# ---- lifecycle ------------------------------------------------------------
reset: guard ## Reset Neo4j database
	$(CLI) reset --confirm

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

monitor-service: guard ## Start monitor as Docker Compose service
	$(COMPOSE) --profile monitor up -d --build monitor

stop-monitor-service: ## Stop monitor Docker Compose service
	$(COMPOSE) --profile monitor stop monitor
