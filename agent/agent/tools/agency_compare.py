"""Cross-agency comparison tool: paired top results from both collections."""
from __future__ import annotations

from ..config import AgentConfig
from .chroma import search_collection


def agency_compare(cfg: AgentConfig, query: str, top_k: int = 3) -> dict:
    fannie = search_collection(
        cfg, query, cfg.fannie_collection, top_k=top_k, agency="fannie"
    )
    freddie = search_collection(
        cfg, query, cfg.freddie_collection, top_k=top_k, agency="freddie"
    )
    return {"fannie": fannie, "freddie": freddie}
