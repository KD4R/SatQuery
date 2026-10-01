#!/usr/bin/env bash
# Run the three services the live dashboard needs — gateway, agent, inference —
# directly with uvicorn: no Docker, no Postgres, no Redis.
#
#   python3 -m venv .venv && source .venv/bin/activate
#   pip install -r requirements.txt
#   ./scripts/run-local-backend.sh            # Ctrl-C stops all three
#
# Then, in another terminal:
#   cd apps/web && npm install && GATEWAY_ORIGIN=http://localhost:8000 npm run dev
#
# What works this way: dev sign-in, live runs (agent in-process thread mode),
# Planetary Computer search, inference with the baseline method, the water
# outline (stored under .local-artifacts/). What does not: the mission service
# and Redis, so agent pop-ups over WebSocket and cross-process run state are
# off; the dashboard does not need them to show a result.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

export PYTHONPATH="$ROOT:$ROOT/infrastructure/docker"   # sitecustomize maps services.eo_data
export SATQUERY_REPO_ROOT="$ROOT"
export ENVIRONMENT=development
export AUTH_ALGORITHM=HS256
export AUTH_SECRET_KEY="${AUTH_SECRET_KEY:-local-dev-secret}"
export SATQUERY_DEV_LOGIN=1
export SATQUERY_DEV_ORG_ID="${SATQUERY_DEV_ORG_ID:-org-dev}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"   # optional; failures are tolerated
export AGENT_SERVICE_URL=http://localhost:8002
export INFERENCE_SERVICE_URL=http://localhost:8003
export MISSION_SERVICE_URL=http://localhost:8001
export INFERENCE_TIMEOUT_S=180
export AGENT_INFERENCE_TIMEOUT_S=180
export CORS_ALLOW_ORIGINS=http://localhost:3000
export SATQUERY_ARTIFACT_DIR="$ROOT/.local-artifacts"
mkdir -p "$SATQUERY_ARTIFACT_DIR"

pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

uvicorn services.inference.implementation:app --port 8003 --log-level warning & pids+=($!)
uvicorn services.agent.app.api.implementation:app --port 8002 --log-level warning & pids+=($!)
uvicorn services.gateway.implementation:app --port 8000 --log-level warning & pids+=($!)

echo "gateway  http://localhost:8000  (dev sign-in on)"
echo "agent    http://localhost:8002"
echo "inference http://localhost:8003  (outlines in .local-artifacts/)"
wait
