#!/usr/bin/env bash
# Maintenance window: free the unified memory pool, run the chosen analytics stages,
# then bring the LLM back and restart the gateway that depends on it.  Readiness is
# always checked through Caddy + ai-gateway; nothing here ever calls llama directly.
set -uo pipefail

REPO="${REPO:-/home/evarun22/Projects/btc-aml-graph}"
RUN_USER="${RUN_USER:-evarun22}"
LLAMA_SERVICE="${LLAMA_SERVICE:-llama-server.service}"
GATEWAY_SERVICE="${GATEWAY_SERVICE:-ai-gateway.service}"
LLAMA_PROXY="${LLAMA_PROXY:-http://127.0.0.1:8080}"
LLAMA_MODEL="${LLAMA_MODEL:-}"            # empty = read it from $LLAMA_PROXY/v1/models
RESTART_LLAMA="${RESTART_LLAMA:-1}"
FORCE_RESTART_LLAMA="${FORCE_RESTART_LLAMA:-0}"
SMOKE_TEST="${SMOKE_TEST:-1}"
MIN_FREE_GIB="${MIN_FREE_GIB:-60}"
DRY_RUN="${DRY_RUN:-0}"

STAGES="${STAGES:-ingest recompute peel smurf ofac risk status}"
[ "$STAGES" = "full" ] && STAGES="ingest recompute coinjoin entities peel smurf ofac risk status"

INGEST_LIMIT="${INGEST_LIMIT:-12}"
SMURF_MAX_PAIRS="${SMURF_MAX_PAIRS:-200}"
SMURF_MAX_DEPTH="${SMURF_MAX_DEPTH:-4}"
OFAC_LIMIT="${OFAC_LIMIT:-500}"

cd "$REPO" || exit 1
mkdir -p logs .state
LOG="logs/maintenance-$(date +%Y%m%d-%H%M%S).log"
AS=(runuser -u "$RUN_USER" --)
CLI=("$REPO/.venv/bin/python" -m btc_aml.cli)

has() { [[ " $STAGES " == *" $1 "* ]]; }
log() { printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }
run() {
  log "RUN: $*"
  if [ "$DRY_RUN" = "1" ]; then return 0; fi
  "${AS[@]}" "$@" 2>&1 | tee -a "$LOG"
  return "${PIPESTATUS[0]}"
}

# Works with OpenAI-style {"data":[{"id":..}]} AND llama/gateway-style {"models":[{"model":..}]}
chain_model() {
  curl -sf -m 10 "$LLAMA_PROXY/v1/models" | /usr/bin/python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
items = d.get("data") or d.get("models") or []
if items:
    m = items[0]
    print(m.get("id") or m.get("model") or m.get("name") or "")
' 2>/dev/null | head -1
}

LLAMA_WAS_ACTIVE=0
systemctl is-active --quiet "$LLAMA_SERVICE" && LLAMA_WAS_ACTIVE=1

bring_ai_back() {
  if [ "$DRY_RUN" = "1" ] || [ "$RESTART_LLAMA" != "1" ]; then return 0; fi
  if [ "$LLAMA_WAS_ACTIVE" != "1" ] && [ "$FORCE_RESTART_LLAMA" != "1" ]; then
    log "llama was already stopped before this run - leaving llama and gateway stopped"
    return 0
  fi

  log "starting $LLAMA_SERVICE"
  systemctl start "$LLAMA_SERVICE" || log "WARN: could not start $LLAMA_SERVICE"

  # ai-gateway declares Requires=llama-server.service, so systemd stopped it when we
  # stopped llama. Nothing restarts it automatically - we must.
  log "restarting $GATEWAY_SERVICE (it was stopped together with llama)"
  systemctl restart "$GATEWAY_SERVICE" || log "WARN: could not restart $GATEWAY_SERVICE"

  ready=0
  for _ in $(seq 1 60); do
    curl -sf -m 5 "$LLAMA_PROXY/v1/models" >/dev/null 2>&1 && { ready=1; break; }
    sleep 5
  done
  if [ "$ready" != "1" ]; then
    log "WARN: chain not answering on $LLAMA_PROXY/v1/models after 300s"
    return 0
  fi
  log "chain healthy via $LLAMA_PROXY/v1/models"

  if [ "$SMOKE_TEST" = "1" ]; then
    model="$LLAMA_MODEL"
    [ -z "$model" ] && model="$(chain_model)"
    if [ -z "$model" ]; then
      log "WARN: could not determine model id from $LLAMA_PROXY - smoke test skipped"
      return 0
    fi
    log "smoke test through the gateway"
    resp=$(curl -sf -m 180 "$LLAMA_PROXY/v1/chat/completions" -H 'Content-Type: application/json' \
           -d "{\"model\":\"$model\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the single word: ready\"}],\"max_tokens\":128,\"temperature\":0}")
    ans=$(printf '%s' "$resp" | /usr/bin/python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
    print(((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
except Exception:
    pass
' 2>/dev/null)
    if [ -n "$ans" ]; then log "AI round-trip OK - model said: ${ans:0:60}"
    else log "WARN: gateway replied but with no usable content"; fi
  fi
}

finish() {
  rc=$?
  bring_ai_back
  chown -R "$RUN_USER":"$RUN_USER" logs .state 2>/dev/null || true
  if [ "$rc" -eq 0 ]; then log "maintenance OK"; else log "maintenance FAILED rc=$rc"; fi
  exit "$rc"
}
trap finish EXIT

log "=== maintenance window start | stages: $STAGES | dry_run=$DRY_RUN ==="

if [ "$DRY_RUN" = "1" ]; then
  log "DRY RUN - llama not touched, nothing executed"
else
  if [ "$LLAMA_WAS_ACTIVE" = "1" ]; then
    log "stopping $LLAMA_SERVICE (and $GATEWAY_SERVICE with it)"
    systemctl stop "$LLAMA_SERVICE" || { log "cannot stop $LLAMA_SERVICE"; exit 1; }
  else
    log "$LLAMA_SERVICE already inactive"
  fi

  avail=0
  for _ in $(seq 1 60); do
    avail=$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)
    [ "$avail" -ge "$MIN_FREE_GIB" ] && break
    log "waiting for memory (available ${avail} GiB)"; sleep 5
  done
  log "MemAvailable=${avail} GiB"

  "${AS[@]}" docker compose up -d neo4j >>"$LOG" 2>&1 || true
  for _ in $(seq 1 60); do
    "${AS[@]}" docker compose ps neo4j 2>/dev/null | grep -q healthy && break; sleep 5
  done

  if [ -f .state/monitor.pid ] && kill -0 "$(cat .state/monitor.pid)" 2>/dev/null; then
    log "monitor pid $(cat .state/monitor.pid) running - waiting up to 30 min"
    for _ in $(seq 1 180); do
      kill -0 "$(cat .state/monitor.pid)" 2>/dev/null || break; sleep 10
    done
  fi
fi

if has ingest; then
  run "${CLI[@]}" ingest-latest --limit "$INGEST_LIMIT" || log "WARN: ingest failed, continuing"
fi
if has recompute; then run "${CLI[@]}" recompute; fi
if has coinjoin;  then run "${CLI[@]}" detect-coinjoin; fi
if has entities;  then run "${CLI[@]}" resolve-entities; fi
if has peel;      then run "${CLI[@]}" detect-peel; fi
if has smurf;     then run "${CLI[@]}" detect-smurf --max-pairs "$SMURF_MAX_PAIRS" --max-depth "$SMURF_MAX_DEPTH"; fi
if has ofac; then
  run "${CLI[@]}" screen-ofac --alert-addresses
  run "${CLI[@]}" screen-ofac --limit "$OFAC_LIMIT"
fi
if has risk;   then run "${CLI[@]}" compute-risk; fi
if has status; then run "${CLI[@]}" status; fi

log "=== maintenance window done ==="
