# Bitcoin AML Graph Intelligence Platform

Chain-analytics for Bitcoin on a graph database: ingest real blocks, build a UTXO-style
property graph in Neo4j, run money-laundering typology detection, resolve entities with
the Common Input Ownership Heuristic, screen OFAC exposure, score every address with an
explainable model, and serve it all through FastAPI + Next.js — with a governed local-LLM
analyst assistant that never leaves the machine.

**Scale of the live dataset:** 242 blocks · 1,137,198 transactions · 953,052 addresses ·
727,029 entities · 3,318,985 co-spend edges · 303 alerts · risk scored on 100 % of
addresses.

## Why this project

Real chain analytics is a data-engineering problem before it is an ML problem: a graph
schema that models UTXO flow honestly, heuristics with explicit thresholds that fit in
memory on a single machine, deterministic and idempotent pipelines, an API surface an
analyst can actually use, and an LLM assistant that is governed, audited and optional.
This project builds all of that end to end on one 122 GiB unified-memory workstation.

## Architecture

```text
        blockchain.info / blockstream
                    │  Python ETL · proportional flow estimation · idempotent MERGE
                    ▼
   ┌───────────────────────────────────────────────┐
   │  Neo4j 5.26 Community + GDS + APOC  (Docker)  │  Block · Tx · Address · Entity
   │  24 GiB heap · 32 GiB page cache              │  Alert · SanctionedAddress
   └───────────────┬───────────────────────────────┘
                   │  7-stage analytics pipeline (any subset, in fixed order)
                   ▼
   Alerts · Entities · OFAC exposure · Risk scores
                   │  parameterised Cypher only
                   ▼
        FastAPI :8010  ──────────────┐
                   │                 │
                   ▼                 ▼
        Next.js :3000          /docs (OpenAPI)
        analyst dashboard
                             governed LLM chain
        API :8010 → Caddy :8080 → ai-gateway :8000 → llama.cpp :8081
                    (single entry)   (audit proxy)     (local model)
```

Every request to the model passes through a logging reverse proxy. There is no direct
path to the model, and the dashboard works fully when the model is off.

## Tech stack

Python 3.11 · FastAPI · httpx · Neo4j 5.26 · Graph Data Science (WCC) · APOC · Next.js 14 ·
TypeScript · Tailwind · Cytoscape.js · llama.cpp · Docker Compose · GNU Make · pytest · Ruff ·
GitHub Actions · systemd · Caddy.

## Detection heuristics (explicit thresholds)

| Typology | Fires when | Alert id |
|---|---|---|
| **CoinJoin / Mixer** | non-coinbase tx with ≥ 50 distinct inputs **and** ≥ 50 distinct outputs, input/output asymmetry ≤ 0.20, ≥ 35 % of outputs in value buckets of size ≥ 2, and ≥ 0.7 divergence of post-tx `SENT` destinations | `MIXER_{tx_hash}` |
| **Entity resolution (CIOH)** | addresses sharing a transaction input are linked by a weighted `CO_SPENT` edge; GDS Weakly Connected Components become `Entity` nodes. Mixer txs excluded; txs with > 100 inputs excluded (consolidation guard) | — |
| **Peel chain** | BFS over `SENT`: next ≤ current − 0.05 BTC **and** next ≥ current × 0.40, chain length ≥ 4, anchored on the largest flows first | `PEEL_{first_tx_hash}` |
| **Smurfing** | source out-degree ≥ 50, sink in-degree ≥ 50, ≥ 3 shortest paths within depth 6 | `SMURF_{src}_{dst}` |
| **OFAC exposure** | exact match = distance 0; otherwise graph proximity up to distance 2 | `OFAC_{address}_{dist}` |
| **Risk score** | OFAC 0/1/2 → +100/+60/+35 · CoinJoin +20 · peel +40 · smurf +40 · entity ≥ 10 addrs +10 · out-degree ≥ 50 +10 · in-degree ≥ 50 +10, capped at 100. Levels: ≥ 80 CRITICAL, ≥ 50 HIGH, ≥ 25 MEDIUM | — |

Every score carries a `risk_score_version` stamp so results are reproducible and
re-scoring after a threshold change is traceable.

## Data model

```text
(:Block)  (:Tx)  (:Address)  (:Address:SanctionedAddress)  (:Entity)  (:Alert)  (:PipelineState)

(:Block)-[:CONTAINS]->(:Tx)
(:Tx)-[:INPUT {value_satoshi}]->(:Address)
(:Tx)-[:OUTPUT {value_satoshi}]->(:Address)
(:Address)-[:SENT {tx_hash, transferred_btc, block_height, heuristic_version}]->(:Address)
(:Address)-[:RETURNED_CHANGE {…, is_dust}]->(:Address)
(:Address)-[:CO_SPENT {co_tx_count, first_tx_hash}]->(:Address)
(:Address)-[:CONTROLLED_BY]->(:Entity)
(:Address)-[:FLAGGED_IN]->(:Alert)
(:Alert)-[:ABOUT_TX]->(:Tx)
(:Entity)-[:HAS_RISK_EXPOSURE]->(:Alert)
```

`CO_SPENT` is an *inference* edge, not value movement: one directed edge per address pair,
weighted by how many transactions they co-spent. GDS projects it undirected for WCC.

## The analytics pipeline — seven stages, fixed order

```text
1 recompute → 2 coinjoin → 3 entities → 4 peel → 5 smurf → 6 ofac → 7 risk
```

Risk is always last (it reads the alerts the others create); entity resolution must follow
CoinJoin (CIOH excludes mixer transactions). Every stage is idempotent — all writes are
`MERGE` on block/tx/address hash or `alert_id`, so re-running never duplicates.

| Stage | Cost on 242 blocks | Result |
|---|---|---|
| recompute | minutes | received/spent/first-seen on 953 k addresses |
| coinjoin | minutes | 11 alerts |
| entities (CIOH) | **10–25 min** | 3.32 M `CO_SPENT`, 727 k entities |
| peel | ~14 s | 292 alerts |
| smurf | seconds | 0 alerts (sampling-bound, see Limitations) |
| ofac | ~1 min | 252 sanctioned at distance 0 |
| risk | ~20 s | 10,483,572 properties written |

## Running it

```bash
make install        # python deps
make up             # Neo4j (Docker)
make schema         # constraints + indexes
make load-ofac      # sanctioned address list
make ingest-range RANGE_START=960000 RANGE_END=960999
make run-nightly    # analytics window (see memory model below)
make app-up         # API + dashboard
make ops            # one screen of truth
```

`make help` prints the full operations map: **Truth · App · Pipeline · Presets ·
Ingestion · Safe window · Monitor · LLM · Docker · Dev · Danger**, plus the fixed stage
order and `p1-recompute … p7-risk`.

## Memory management — the real engineering constraint

The host is an NVIDIA DGX Spark: **122 GiB of unified memory shared by CPU and GPU.** The
local 27B-class model pins ~83 GiB permanently; Neo4j needs 24 GiB heap plus up to 32 GiB
page cache. They do not both fit during graph analytics. Instead of shrinking either, the
platform enforces ordering:

1. **`make guard`** — every heavy target aborts unless the model is stopped and
   `MemAvailable ≥ 48 GiB`. Non-overridable by environment variable.
2. **`scripts/scheduled_analytics.sh`** — the maintenance window: stop the model, *poll*
   until the pool is genuinely free, run any subset of stages, then restart the model and
   the logging proxy that systemd stops with it, and health-check the whole chain through
   the reverse proxy. Runs to completion even if a stage fails.
3. **systemd hardening** — `Restart=no` (an OOM kill must not resurrect an 83 GiB process
   on top of the database) and `OOMScoreAdjust=500` so the model, never the desktop
   session, is the sacrifice if memory ever runs out again.

Measured: pool released in 3–4 s, model reloaded in ~105 s, no OOM since.

## Governed AI assistant

Three layers, each independently controllable:

| Layer | Where | Responsibility |
|---|---|---|
| Governance in the app | `api/services/ai_service.py` | provider abstraction (`disabled` is a real kill switch), context truncation, per-string caps, prompt char cap, secret-key redaction, graph payloads stripped from prompts, address/alert validation before prompting, timeouts, graceful 404/422/502/503 |
| Audit log | `logs/ai_audit.jsonl` | one JSON line per call: endpoint, provider, model, status, latency, prompt/output size — never committed |
| Logging proxy | external `ai-gateway.service` → Caddy front door | every prompt logged server-side before it reaches the model; the model binds loopback so the proxy is the only route |

Responses are read from `content` with a fallback to `reasoning_content`, because
llama.cpp runs with reasoning enabled; timeouts are monotonic outward (API < reverse proxy)
so failures are reported by the layer that actually failed. Verified end to end:
`POST /api/ai/explain-alert → 200 OK in 44 s, 2 657 characters, audited`.

Measured model throughput: **26 tokens/s generation, 156 tokens/s prompt processing.**

## API

```http
GET  /api/health            GET  /api/kpis              GET  /api/pipeline/status
GET  /api/addresses/{address}          GET /api/addresses/{address}/graph
GET  /api/alerts            GET /api/alerts/{id}        GET  /api/alerts/{id}/graph
GET  /api/entities          GET /api/entities/{id}      GET  /api/entities/{id}/graph
GET  /api/ofac/check?address=…         GET /api/ofac/exposure
GET  /api/graph/subgraph
GET  /api/ai/status         POST /api/ai/explain-alert  POST /api/ai/summarize-address
```

Invalid address → `422`. Valid but unknown → `{"exists": false}`. Missing alert → `404`.
Model down → `503`. Provider failure → `502` with a reason. All Cypher is parameterised;
user input is never concatenated into a query.

## Ports

```text
Neo4j Browser   http://localhost:7474      Neo4j bolt   bolt://localhost:7687
Dashboard       http://localhost:3000      AML API      http://localhost:8010
LLM front door  http://127.0.0.1:8080      ai-gateway   http://127.0.0.1:8000
llama.cpp       http://127.0.0.1:8081
```

## Testing and CI

`make test` (12 backend tests: address validation, proportional matrix, AI governance,
API health, AI status) and `make lint` (Ruff). CI runs backend lint + tests and a
production `next build`; it deliberately does not require Neo4j.

## Limitations — stated plainly

- **Smurfing returns 0 alerts.** Candidate pairs are sampled (200 of ~216 000), so absence
  of findings is not evidence of absence. Fix: seed pairs from real 2-hop fan-out→fan-in
  structure instead of a cross-product sample.
- **OFAC proximity returns 0 hits and there are no CRITICAL addresses.** The proximity
  query is outgoing-only, so *received-from-sanctioned* exposure is invisible; with no
  OFAC hits and no address hit by two typologies, nothing can reach the 80-point CRITICAL
  threshold. Fix: undirected proximity, or a targeted ingest window around a listed
  address with on-chain history.
- Full-graph analytics: `make run-full` costs 10–25 minutes; incremental analytics is
  roadmap, not current.
- `INPUT`/`OUTPUT` `value_satoshi` is overwritten rather than summed when one address
  appears in multiple inputs of the same transaction.
- Proportional flow estimation is skipped for very large transactions
  (`proportional_skipped`), which depresses peel and smurf recall.
- ~76 % of CIOH components are single addresses; the entity explorer should filter
  `address_count >= 2`.
- Alerts accumulate across runs; only `last_detected_at` refreshes.

## Roadmap

Incremental analytics · structural smurf candidate seeding · undirected OFAC proximity ·
alert triage workflow with status transitions · scheduled maintenance windows (systemd
timers) · public read-only demo · graph anomaly detection · AI analyst chat with tool use.
