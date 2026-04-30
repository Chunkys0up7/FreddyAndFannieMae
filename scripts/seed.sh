#!/usr/bin/env bash
# Seed the vector store and state DB with current guide content.
set -euo pipefail

echo "==> Seeding GSE Copilot pipeline (Fannie + Freddie + bulletins)…"
docker compose exec -T gse-pipeline python -m pipeline.main --all

echo "==> Done. Stats:"
docker compose exec -T gse-pipeline python -c "
from pipeline.config import load_config
from pipeline.store.chroma_client import ChromaVectorStore
from pipeline.store.state_store import StateStore
cfg = load_config()
store = ChromaVectorStore(cfg.chroma, cfg.embedding)
state = StateStore(cfg.sqlite_path)
print(f'  Fannie chunks:   {store.count(cfg.chroma.fannie_collection)}')
print(f'  Freddie chunks:  {store.count(cfg.chroma.freddie_collection)}')
print(f'  Bulletin chunks: {store.count(cfg.chroma.bulletins_collection)}')
print(f'  Bulletins:       {len(state.list_recent_bulletins(days=3650))}')
"
