"""ChromaDB client used by agent tools."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

import chromadb
from chromadb.config import Settings

from ..config import AgentConfig


log = logging.getLogger(__name__)


class _LocalEmbedder:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            log.info("Loading embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def __call__(self, input):  # noqa: A002
        if isinstance(input, str):
            input = [input]
        return self._load().encode(input, convert_to_numpy=True).tolist()


@lru_cache(maxsize=1)
def _embedder(provider: str, model: str):
    if provider == "openai":
        from chromadb.utils import embedding_functions
        import os

        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model_name=model or "text-embedding-3-small",
        )
    return _LocalEmbedder(model or "all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def get_client(host: str, port: int):
    return chromadb.HttpClient(
        host=host, port=port, settings=Settings(anonymized_telemetry=False)
    )


def search_collection(
    cfg: AgentConfig,
    query: str,
    collection: str,
    top_k: int = 5,
    agency: Optional[str] = None,
) -> list[dict]:
    client = get_client(cfg.chroma_host, cfg.chroma_port)
    embed_fn = _embedder(cfg.embedding_provider, cfg.embedding_model)
    col = client.get_or_create_collection(name=collection, embedding_function=embed_fn)
    where = {"agency": agency} if agency else None
    res = col.query(query_texts=[query], n_results=top_k, where=where)
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[0.0] * len(ids)])[0]
    return [
        {"id": i, "text": d, "metadata": m or {}, "distance": float(dist)}
        for i, d, m, dist in zip(ids, docs, metas, dists)
    ]
