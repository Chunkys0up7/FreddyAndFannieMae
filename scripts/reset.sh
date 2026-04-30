#!/usr/bin/env bash
# Wipe ChromaDB collections and SQLite state for a clean restart.
set -euo pipefail

echo "==> Resetting ChromaDB collections…"
docker compose exec -T gse-pipeline python -c "
from pipeline.config import load_config
from pipeline.store.chroma_client import ChromaVectorStore
cfg = load_config()
store = ChromaVectorStore(cfg.chroma, cfg.embedding)
for col in (cfg.chroma.fannie_collection, cfg.chroma.freddie_collection, cfg.chroma.bulletins_collection):
    store.delete_collection(col)
    print(f'  deleted: {col}')
"

echo "==> Removing SQLite state DB…"
docker compose exec -T gse-pipeline rm -f /data/sqlite/gse.db

echo "==> Done. Re-run ./scripts/seed.sh to re-ingest."
