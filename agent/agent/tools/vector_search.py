"""Vector search tool over ChromaDB."""
from __future__ import annotations

from typing import Optional

from ..config import AgentConfig
from .chroma import search_collection


def vector_search(
    cfg: AgentConfig,
    query: str,
    agency: Optional[str] = None,
    top_k: int = 5,
    include_bulletins: bool = False,
) -> list[dict]:
    """Search guide section collections (and optionally bulletins).

    `agency` filters to "fannie" | "freddie". Without it, searches both.
    """
    results: list[dict] = []
    if agency in (None, "fannie"):
        results.extend(
            search_collection(cfg, query, cfg.fannie_collection, top_k=top_k, agency="fannie")
        )
    if agency in (None, "freddie"):
        results.extend(
            search_collection(cfg, query, cfg.freddie_collection, top_k=top_k, agency="freddie")
        )
    if include_bulletins:
        results.extend(search_collection(cfg, query, cfg.bulletins_collection, top_k=top_k))
    results.sort(key=lambda r: r["distance"])
    return results[:top_k]
