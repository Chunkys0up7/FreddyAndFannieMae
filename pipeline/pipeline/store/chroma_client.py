"""Thin wrapper around ChromaDB shared by pipeline (writes) and agent (reads)."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

import chromadb
from chromadb.config import Settings

from ..config import ChromaConfig, EmbeddingConfig
from ..models import Chunk, ChunkResult


log = logging.getLogger(__name__)


class _LocalEmbedder:
    """Lazy-loaded sentence-transformers wrapper."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            log.info("Loading embedding model: %s", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def __call__(self, input):  # noqa: A002 — chromadb signature
        if isinstance(input, str):
            input = [input]
        # Return numpy arrays — chromadb's HTTP client calls .tolist() on each row.
        return self._load().encode(input, convert_to_numpy=True)


@lru_cache(maxsize=1)
def _embedder(provider: str, model: str):
    if provider == "openai":
        # Lazy import; only required if explicitly chosen.
        from chromadb.utils import embedding_functions

        import os

        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model_name=model or "text-embedding-3-small",
        )
    return _LocalEmbedder(model or "all-MiniLM-L6-v2")


class ChromaVectorStore:
    """High-level CRUD for guide / bulletin chunks."""

    def __init__(self, chroma_cfg: ChromaConfig, embedding_cfg: EmbeddingConfig):
        self.chroma_cfg = chroma_cfg
        self.embedding_cfg = embedding_cfg
        self._client: Optional[chromadb.api.ClientAPI] = None
        self._embed_fn = _embedder(embedding_cfg.provider, embedding_cfg.model)

    @property
    def client(self) -> chromadb.api.ClientAPI:
        if self._client is None:
            self._client = chromadb.HttpClient(
                host=self.chroma_cfg.host,
                port=self.chroma_cfg.port,
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    def _collection(self, name: str):
        return self.client.get_or_create_collection(
            name=name, embedding_function=self._embed_fn
        )

    def upsert_chunks(self, chunks: list[Chunk], collection: str) -> int:
        if not chunks:
            return 0
        col = self._collection(collection)
        col.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[c.metadata() for c in chunks],
        )
        return len(chunks)

    def search(
        self,
        query: str,
        collection: str,
        top_k: int = 5,
        agency: Optional[str] = None,
    ) -> list[ChunkResult]:
        col = self._collection(collection)
        where = {"agency": agency} if agency else None
        result = col.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
        )
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[0.0] * len(ids)])[0]
        return [
            ChunkResult(id=i, text=d, metadata=m or {}, distance=float(dist))
            for i, d, m, dist in zip(ids, docs, metas, dists)
        ]

    def delete_collection(self, collection: str) -> None:
        try:
            self.client.delete_collection(collection)
        except Exception as exc:  # pragma: no cover
            log.warning("delete_collection(%s) failed: %s", collection, exc)

    def count(self, collection: str) -> int:
        return self._collection(collection).count()
