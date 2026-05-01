#!/usr/bin/env bash
# Seed the local vector store via the pipeline CLI (no Docker).
# Requires: scripts/run-local.sh already running, APIFY_TOKEN in .env.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a; source .env; set +a

export CHROMA_HOST=127.0.0.1
export CHROMA_PORT=8500
export SQLITE_PATH="${SQLITE_PATH:-$ROOT/data/gse.db}"
export MANIFEST_DIR="${MANIFEST_DIR:-$ROOT/data/manifests}"

if [ "${APIFY_TOKEN:-}" = "" ] || [ "${APIFY_TOKEN:-}" = "apify_api_XXXXXXX" ]; then
  echo "ERROR: APIFY_TOKEN not set in .env"
  exit 1
fi

cd pipeline
echo "==> Seeding (Fannie HTML + Freddie PDF + bulletins)…"
python -m pipeline.main --all
echo "==> Done. Stats:"
python - <<'PY'
from pipeline.config import load_config
from pipeline.store.chroma_client import ChromaVectorStore
from pipeline.store.state_store import StateStore
cfg = load_config()
store = ChromaVectorStore(cfg.chroma, cfg.embedding)
state = StateStore(cfg.sqlite_path)
print(f"  Fannie chunks:   {store.count(cfg.chroma.fannie_collection)}")
print(f"  Freddie chunks:  {store.count(cfg.chroma.freddie_collection)}")
print(f"  Bulletin chunks: {store.count(cfg.chroma.bulletins_collection)}")
print(f"  Bulletins:       {len(state.list_recent_bulletins(days=3650))}")
PY
