#!/usr/bin/env bash
# Run the entire GSE Copilot stack locally without Docker.
# Starts ChromaDB, pipeline API, agent, and frontend dev server.
# Logs go to logs/, PIDs to .pids/. Stop with ./scripts/stop-local.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# --- Load .env -------------------------------------------------------------
if [ ! -f .env ]; then
  echo "ERROR: .env missing. Run: cp .env.example .env  (then add API keys)"
  exit 1
fi
set -a; source .env; set +a

# Force local hostnames (override any docker-network defaults from .env)
export CHROMA_HOST=127.0.0.1
export CHROMA_PORT=8500
export PIPELINE_API_URL=http://127.0.0.1:8001
export PIPELINE_API_PORT=8001
export AGENT_PORT=8000
export AGENT_URL=http://127.0.0.1:8000/copilotkit
export NEXT_PUBLIC_PIPELINE_API_URL=http://127.0.0.1:8001
export SQLITE_PATH="${SQLITE_PATH:-$ROOT/data/gse.db}"
export MANIFEST_DIR="${MANIFEST_DIR:-$ROOT/data/manifests}"

mkdir -p data data/chroma data/manifests logs .pids

# --- Helper to start a service --------------------------------------------
start() {
  local name="$1"; shift
  local logfile="${ROOT}/logs/${name}.log"
  local pidfile="${ROOT}/.pids/${name}.pid"
  echo "==> starting ${name}  (logs: logs/${name}.log)"
  ( "$@" ) >"$logfile" 2>&1 &
  echo $! > "$pidfile"
}

wait_for() {
  local name="$1" url="$2" deadline=$((SECONDS + 90))
  while ! curl -sf "$url" >/dev/null 2>&1; do
    if [ $SECONDS -ge $deadline ]; then
      echo "  ! ${name} failed to come up. Check logs/${name}.log"
      tail -20 "${ROOT}/logs/${name}.log" || true
      exit 1
    fi
    sleep 1
  done
  echo "  ✓ ${name} ready"
}

# --- 1. ChromaDB ----------------------------------------------------------
start chroma chroma run --path "$ROOT/data/chroma" --host 127.0.0.1 --port 8500
wait_for chroma "http://127.0.0.1:8500/api/v1/heartbeat"

# --- 2. Pipeline API ------------------------------------------------------
( cd pipeline && start pipeline python -m pipeline.api )
wait_for pipeline "http://127.0.0.1:8001/health"

# --- 3. Agent -------------------------------------------------------------
( cd agent && start agent python -m uvicorn agent.server:app --host 127.0.0.1 --port 8000 )
wait_for agent "http://127.0.0.1:8000/health"

# --- 4. Frontend (Next.js dev) --------------------------------------------
if [ ! -d frontend/node_modules ]; then
  echo "==> installing frontend deps (one-time)…"
  ( cd frontend && npm install --no-audit --no-fund --loglevel=error )
fi
( cd frontend && start frontend npm run dev )
wait_for frontend "http://127.0.0.1:3000"

cat <<EOF

  All four services are running:
    Frontend   →  http://localhost:3000
    Agent      →  http://localhost:8000  (CopilotKit at /copilotkit)
    Pipeline   →  http://localhost:8001  (REST API)
    ChromaDB   →  http://localhost:8500

  Next steps:
    1. Open http://localhost:3000 (the dashboard will be empty until you seed)
    2. Seed content (needs APIFY_TOKEN in .env):
         ./scripts/seed-local.sh
    3. Ask the copilot a question.

  Tail logs:   tail -f logs/*.log
  Stop all:    ./scripts/stop-local.sh
EOF
