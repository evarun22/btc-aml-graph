# Bitcoin AML Graph Intelligence Platform

A Bitcoin AML / Chain Analytics Graph Intelligence Platform that ingests Bitcoin blocks and transactions, builds a UTXO-style graph in Neo4j, detects AML typologies, resolves entities using CIOH, screens OFAC exposure, computes risk scores, and exposes results through a FastAPI backend and Next.js dashboard with a governed local LLM AI assistant.

## Overview

This project is a blockchain analytics / AML compliance system.

It is a modular local data platform with:

- Python ingestion pipeline
- Neo4j graph database
- AML analytics engine
- FastAPI backend
- Next.js dashboard
- Governed local LLM assistant
- Docker deployment support
- Continuous monitoring / backfill safety

## Architecture

```text
Bitcoin blockchain APIs
        ↓
Python ingestion / ETL
        ↓
Neo4j graph database
        ↓
AML analytics engine
        ↓
Alerts, entities, OFAC exposure, risk scores
        ↓
FastAPI backend
        ↓
Next.js dashboard + AI analyst assistant
```

## Core Features

- Ingest Bitcoin blocks and transactions
- Build a UTXO-style graph in Neo4j
- Track addresses, transactions, blocks, entities, and alerts
- Detect CoinJoin / mixer-like behavior
- Resolve entities using Common Input Ownership Heuristic
- Detect peel chains
- Detect fan-out / fan-in smurfing patterns
- Screen OFAC sanctioned address exposure
- Compute explainable risk scores
- Expose graph subgraphs through API
- Dashboard for KPIs, alerts, entities, OFAC, and graph exploration
- Governed local LLM explanations and summaries
- Continuous monitor with safe historical backfill

## Tech Stack

```text
Python 3.11
FastAPI
Neo4j 5
GDS
APOC
Next.js
TypeScript
Tailwind CSS
Cytoscape.js
llama.cpp
Docker
Docker Compose
Make
pytest
Ruff
```

## Detection Heuristics

### CoinJoin / Mixer Detection

Detects transactions with mixer-like properties:

- many inputs
- many outputs
- symmetric input/output shape
- clustered output values
- post-transaction divergence

### Entity Resolution / CIOH

Groups addresses that likely belong to the same actor using Common Input Ownership Heuristic.

Addresses that co-spend inputs are linked with `CO_SPENT` edges, then weakly connected components are materialized as `Entity` nodes.

### Peel Chain Detection

Detects chains where funds move through multiple addresses with gradually decreasing volume.

### Smurfing / Fan-Out / Fan-In Detection

Detects fragmented movement of funds across multiple addresses using shortest-path enumeration between high-degree source and sink addresses.

### OFAC Screening

Screens addresses for exact matches and graph proximity to sanctioned addresses.

### Risk Scoring

Computes rule-based risk scores for addresses and entities using:

- alert flags
- OFAC distance
- entity size
- in-degree
- out-degree
- typology exposure

## Data Model

Main nodes:

```text
Block
Tx
Address
Entity
Alert
PipelineState
SanctionedAddress
```

Main relationships:

```text
Block CONTAINS Tx
Tx INPUT Address
Tx OUTPUT Address
Address SENT Address
Address RETURNED_CHANGE Address
Address CO_SPENT Address
Address CONTROLLED_BY Entity
Address FLAGGED_IN Alert
Alert ABOUT_TX Tx
Entity HAS_RISK_EXPOSURE Alert
```

## AI Assistant

The platform includes a governed local LLM assistant layer.

Capabilities:

- explain alerts
- summarize addresses
- provider abstraction
- timeouts
- prompt size limits
- context truncation
- sensitive key redaction
- JSONL audit logging
- graceful degradation when the model is unavailable

The AI layer is optional for core dashboard functionality.

## Quickstart

### 1. Install dependencies

```bash
make install
```

### 2. Start Neo4j

```bash
make up
```

### 3. Create schema

```bash
make schema
```

### 4. Load OFAC data

```bash
make load-ofac
```

### 5. Backfill real data

```bash
make backfill-1000
```

This ingests a 1000-block historical range, recomputes metrics, runs analytics, and prints status.

### 6. Start API

```bash
make api
```

API docs:

```text
http://localhost:8010/docs
```

### 7. Start dashboard

```bash
make web
```

Dashboard:

```text
http://localhost:3000
```

### 8. Start continuous monitor

```bash
make monitor-bg
```

Stop it with:

```bash
make stop-monitor
```

## One-Command Demo Setup

To populate the database and start the monitor:

```bash
make live
```

This runs:

```bash
make up
make schema
make load-ofac
make backfill-1000
make status
make monitor-bg
```

## Makefile Commands

Run:

```bash
make help
```

Common commands:

```bash
make install
make up
make schema
make load-ofac
make backfill-1000
make analytics
make status
make api
make web
make monitor-bg
make stop-monitor
make test
make lint
make compose-up
make compose-down
```

## Data Strategy

This project uses a real-data strategy.

Instead of relying only on a tiny fixed sample, the system can:

1. backfill a historical block range
2. ingest the latest blocks continuously
3. rerun analytics periodically
4. keep the checkpoint monotonic
5. allow safe historical backfill

Example:

```bash
make backfill-1000
make monitor-bg
```

The monitor continuously ingests new blocks and reruns analytics every configured number of newly ingested blocks.

## Deployment

The project can be run as a Docker Compose stack:

```bash
make compose-up
```

Services:

```text
neo4j
api
web
monitor
```

The monitor service is optional:

```bash
make monitor-service
```

Stop it with:

```bash
make stop-monitor-service
```

## API Examples

Health:

```http
GET /api/health
```

KPIs:

```http
GET /api/kpis
```

Address report:

```http
GET /api/addresses/{address}
```

Alerts:

```http
GET /api/alerts
```

Entities:

```http
GET /api/entities
```

OFAC check:

```http
GET /api/ofac/check?address={address}
```

AI status:

```http
GET /api/ai/status
```

Explain alert:

```http
POST /api/ai/explain-alert
```

Summarize address:

```http
POST /api/ai/summarize-address
```

## Testing

Run backend tests:

```bash
make test
```

Run linting:

```bash
make lint
```

## Local Port Layout

```text
Neo4j browser:      http://localhost:7474
Neo4j bolt:         bolt://localhost:7687
Next.js dashboard:  http://localhost:3000
FastAPI AML API:    http://localhost:8010
llama.cpp:          http://127.0.0.1:8080
```

## Limitations

- Analytics currently rerun over the full graph.
- Large backfills may require more time and memory.
- Smurfing detection uses Cypher shortest-path enumeration for stability.
- OFAC parser supports common CSV address columns but may need upgrades for complex exports.
- Local LLM path is machine-specific and should not be committed.

## Roadmap

- Incremental analytics
- More AML typologies
- Address clustering improvements
- Public read-only demo
- Scheduled analytics jobs
- Alert triage workflow
- AI analyst chat interface
- Graph anomaly detection